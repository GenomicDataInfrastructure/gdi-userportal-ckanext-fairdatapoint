#!/bin/sh

# SPDX-FileCopyrightText: 2024 Stichting Health-RI
#
# SPDX-License-Identifier: AGPL-3.0-only

# Initialize database
ckan -c test.ini db init

# Run tests
pytest --ckan-ini=test.ini --cov=ckanext.fairdatapoint --disable-warnings ckanext/fairdatapoint

# Generate coverage report
coverage xml -o coverage.xml
