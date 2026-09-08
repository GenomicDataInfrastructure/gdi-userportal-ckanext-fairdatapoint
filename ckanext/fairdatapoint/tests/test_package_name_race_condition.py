# SPDX-FileCopyrightText: 2026 Health-RI
#
# SPDX-License-Identifier: Apache-2.0

"""
Deterministic reproduction of the intermittent `package_name_key` UniqueViolation
observed during FDP harvesting.

`HarvesterBase._gen_new_name` (ckanext-harvest) decides a package name is free
via a plain SELECT, and only afterwards does the harvester actually create the
package. If another package is committed under that exact name in the gap
between those two steps - which is exactly what happens when another harvest
process (a background gather/fetch consumer, a cron-triggered run, a second
manual run) is active at the same time - the SELECT's verdict is stale, and
`package_create` can raise an unhandled `IntegrityError` instead of the
uniqueness fallback picking a different name.

There is actually a second SELECT-then-trust check standing between
`_gen_new_name` and the real insert: CKAN's own schema-level
`package_name_validator` (ckan/logic/validators.py) re-checks uniqueness during
`package_create`'s validation step. It has exactly the same race condition, and
in production it is what "closes" the window most of the time - which is
precisely why the bug is intermittent rather than constant. To reproduce the
final, deepest failure deterministically (a raw `IntegrityError` out of
`model_save.package_dict_save`, matching the reported traceback) this test lets
that validator run for real - so it sees the name as free, exactly like
production - and only introduces the colliding package immediately after it
passes.

A genuinely separate DB connection was tried here first to stand in for "the
concurrent harvest process", but it deadlocks: pytest-ckan's `clean_db` runs
the whole test inside one outer transaction, so a second real connection can
never see the `factories.Organization()` row and blocks forever on the
`owner_org` foreign key. Instead, the colliding package is flushed on the
*same* session, immediately after the real validator's check - which is
exactly the state a concurrent commit would have produced, without fighting
the test harness's transaction isolation. The harvester's subsequent, real
insert for its own package then collides with that row for the same reason a
concurrent harvester's insert would: the unique index doesn't care whether the
conflicting row came from another transaction or earlier in the same one.

`_create_or_update_package` only catches `toolkit.ValidationError`, so this
test is expected to demonstrate the crash (i.e. pass by observing the
unhandled `IntegrityError`) until the retry-on-conflict fix is in place.
"""

import uuid
from unittest import mock
from unittest.mock import MagicMock

import pytest

import ckan.plugins.toolkit as toolkit
from ckan import model
from ckan.tests import factories
from ckan.logic.validators import package_name_validator as real_package_name_validator

from ckanext.fairdatapoint.harvesters.civity_harvester import CivityHarvester


class _MinimalHarvester(CivityHarvester):
    """Concrete stub - only the abstract methods need a body for this test."""

    def setup_record_provider(self, harvest_url, harvest_config_dict):
        pass

    def setup_record_to_package_converter(self, harvest_url, harvest_config_dict):
        pass


@pytest.mark.usefixtures("clean_db")
class TestPackageNameRaceCondition:

    def test_race_condition_currently_crashes_import(self):
        # NB: this test passing is BAD NEWS, not a clean bill of health - it
        # means the crash still reproduces. Once the retry-on-conflict fix is
        # in place, this test must be rewritten to assert a successful create
        # (with a renamed package) instead of `pytest.raises(...)`.
        sysadmin = factories.Sysadmin()
        org = factories.Organization()
        harvester = _MinimalHarvester()

        title = "Race Condition Probe"

        # Step 1: exactly what the harvester does to pick a name. At this
        # instant no package with the derived name exists, so it is (correctly,
        # at the time) reported as free.
        name = harvester._gen_new_name(title)

        def race_after_schema_check(key, data, errors, context):
            # Let CKAN's real schema-level uniqueness check run first: at this
            # point nothing has raced yet, so - exactly like in production -
            # it correctly reports the name as free.
            real_package_name_validator(key, data, errors, context)

            # Now land the collision in the gap between that check and the
            # harvester's actual insert - standing in for a concurrent harvest
            # process that just committed a package under this exact name.
            model.Session.add(
                model.Package(
                    id=str(uuid.uuid4()),
                    name=name,
                    title=title,
                    type="dataset",
                    state="active",
                    owner_org=org["id"],
                )
            )
            model.Session.flush()

        package_dict = {
            "id": str(uuid.uuid4()),
            "name": name,
            "title": title,
            "owner_org": org["id"],
        }
        context = {
            "user": sysadmin["name"],
            "return_id_only": True,
            "ignore_auth": True,
        }

        try:
            # This is the bug: the DB-level UniqueViolation crashes the import
            # instead of the harvester retrying with a new name. CKAN's search
            # indexing hook also fires on this same flush and re-touches the
            # (now aborted) session, so the exact exception class that escapes
            # varies (IntegrityError directly, or a PendingRollbackError from
            # a second query hitting the aborted transaction) - what's
            # invariant is that it is *not* the ValidationError
            # `_create_or_update_package` actually handles, and its root cause
            # is always the package_name_key UniqueViolation.
            with mock.patch.dict(
                "ckan.logic._validators_cache",
                {"package_name_validator": race_after_schema_check},
            ):
                with pytest.raises(Exception) as exc_info:
                    harvester._create_or_update_package(
                        package_dict, "create", context, MagicMock()
                    )

            raised = exc_info.value
            assert not isinstance(raised, toolkit.ValidationError), (
                "harvester reported a clean validation error instead of "
                "crashing - the collision did not land where intended"
            )

            chain = []
            exc, seen = raised, set()
            while exc is not None and id(exc) not in seen:
                seen.add(id(exc))
                chain.append(str(exc))
                exc = exc.__cause__ or exc.__context__

            assert any("package_name_key" in msg for msg in chain), (
                "expected the package_name_key UniqueViolation somewhere in "
                "the exception chain, got: %r" % chain
            )
        finally:
            # The failure leaves model.Session's transaction aborted; roll
            # back so the clean_db fixture can tear down normally.
            model.Session.rollback()
