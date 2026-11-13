<!--
SPDX-FileCopyrightText: 2023 Civity 
SPDX-FileContributor: 2024 Stichting Health-RI

SPDX-License-Identifier: CC-BY-4.0
-->

[![REUSE status](https://api.reuse.software/badge/github.com/GenomicDataInfrastructure/gdi-userportal-ckanext-fairdatapoint)](https://api.reuse.software/info/github.com/GenomicDataInfrastructure/gdi-userportal-ckanext-fairdatapoint)
[![Tests](https://github.com/GenomicDataInfrastructure/gdi-userportal-ckanext-fairdatapoint/actions/workflows/test.yml/badge.svg)](https://github.com/GenomicDataInfrastructure/gdi-userportal-ckanext-fairdatapoint/actions/workflows/test.yml)
[![Quality Gate Status](https://sonarcloud.io/api/project_badges/measure?project=GenomicDataInfrastructure_gdi-userportal-ckanext-fairdatapoint&metric=alert_status)](https://sonarcloud.io/summary/new_code?id=GenomicDataInfrastructure_gdi-userportal-ckanext-fairdatapoint)
[![Release](https://github.com/GenomicDataInfrastructure/gdi-userportal-ckanext-fairdatapoint/actions/workflows/release.yml/badge.svg)](https://github.com/GenomicDataInfrastructure/gdi-userportal-ckanext-fairdatapoint/actions/workflows/release.yml)
[![Main](https://github.com/GenomicDataInfrastructure/gdi-userportal-ckanext-fairdatapoint/actions/workflows/main.yml/badge.svg)](https://github.com/GenomicDataInfrastructure/gdi-userportal-ckanext-fairdatapoint/actions/workflows/main.yml)
[![GitHub contributors](https://img.shields.io/github/contributors/GenomicDataInfrastructure/gdi-userportal-ckanext-fairdatapoint)](https://github.com/GenomicDataInfrastructure/gdi-userportal-ckanext-fairdatapoint/graphs/contributors)
[![Contributor Covenant](https://img.shields.io/badge/Contributor%20Covenant-2.1-4baaaa.svg)](CODE_OF_CONDUCT.md)

# ckanext-fairdatapoint

CKAN harvester for [FAIR Data Point](https://www.fairdatapoint.org/). Contains a harvester for FAIR data points. In the future, the FAIR data point API might be supported by this extension too.

## Stages

The harvester runs in three stages. Each of these stages can be modified.

 1. Gather stage. The gather stage uses the FairDataPointRecordProvider (`ckanext/fairdatapoint/harvesters/domain/fair_data_point_record_provider.py`) to create a list of identifiers of the objects which should be included in the harvest. In case of a FAIR data point, this list includes catalogs and datasets. In the future, collections could be added;
 2. Fetch stage. The fetch stage downloads the RDF of each record. The record provider then adds the information of the record's distributions and of its contact point to the graph, so the import sees one self-contained record;
 3. Import stage. The import stage does the actual import. How the RDF from the FAIR data point is mapped to CKAN packages and resources is determined by so-called application profiles. In case of a FAIR data point which uses custom fields, a profile must be created. A profile can be defined as a Python class in `ckanext/fairdatapoint/profiles.py`. The new profile must be registered in the `[ckan.rdf.profiles]` section of `setup.py`. Which profile is used for a particular source is determined by the harvester configuration.

### Selecting the metadata profile of a source

A harvest source picks one of the metadata profiles the deployment enables (`GDI_METADATA_PROFILES`; see
`docs/metadata-profiles.md` in `gdi-userportal-ckan-docker`) in its configuration:

```json
{
 "metadata_profile": "healthdcat_r8"
}
```

- Absent, `null` or empty: the main profile of the deployment.
- A profile that is not enabled is rejected when the source is saved (the message names the enabled
  profiles). One retired afterwards fails the harvest job with a gather error, with no fallback to the main profile.
- The FAIR data point clean-up (tags, labels) runs whichever profile is selected. `gdi_current` already includes it
  (`fairdatapoint_dcat_ap`); for other profiles `fairdatapoint_additive` is added after the profile's own RDF profiles.
- When `ckanext-gdi-userportal` is installed, the import stage logs a WARNING for each dataset that does not conform
  to the source's profile at its access layer, naming the missing properties (for example `Dataset <id> (harvest
  object <id>) does not conform to metadata profile 'healthdcat_r8' at access layer NON_PUBLIC: keyword`). It is
  information only: it never blocks or fails an import. A source with a raw `profile` chain names no profile to check.

The `profile` key still works as an explicit override. It is a space-separated chain of RDF profile names (for
example `"fairdatapoint_dcat_ap euro_dcat_ap_nl"`), used exactly as written. Setting both `metadata_profile` and
`profile` is rejected, and `profile` is checked against the installed RDF profiles when the source is saved.

To run a harvest source from the command line:

```bash
ckan --config=<full path to CKAN ini-file> harvester job <source id>
```

Use `harvester job` rather than `harvester run-test`: `run-test` runs the stages in the CLI process, next to the
gather and fetch consumers that are already running, and the two race each other.

To rebuild the index in case it is not automatically updated after clearing all packages from a harvester:

```bash
ckan --config=<full path to CKAN ini-file> search-index rebuild
```

For more information go to [GDI harvester information](https://genomicdatainfrastructure.github.io/gdi-userportal-docs/docs/ckan/harvester/)

## Requirements

Compatibility with core CKAN versions:

| CKAN version    | Compatible? |
|-----------------|-------------|
| 2.10            | tested      |

## Installation

To install gdi-userportal-ckanext-fairdatapoint:

1. Activate your CKAN virtual environment, for example:

     . /usr/lib/ckan/default/bin/activate

2. Clone the source and install it on the virtualenv

    git clone https://github.com/GenomicDataInfrastructure/gdi-userportal-ckanext-fairdatapoint.git
    cd gdi-userportal-ckanext-fairdatapoint
    pip install -e .
    pip install -r requirements.txt

3. Add the plugins to the `ckan.plugins` setting in your CKAN config file (by default
   `/etc/ckan/default/ckan.ini`):

   - `fairdatapointharvester`: the FAIR data point harvester. Required to harvest.
   - `fairdatapoint`: registers the extension's templates, public files and fanstatic resources with CKAN.

4. Restart CKAN. For example if you've deployed CKAN with Apache on Ubuntu:

     sudo service apache2 reload

## Config settings

### Catalog harvesting

There is a setting `ckanext.fairdatapoint.harvest_catalogs`. Default is `false`. If set to `true`,
CKAN will harvest catalogs as datasets.

The setting can be overridden in the harvester profile, by setting `"harvest_catalogs": "true"` or
`"harvest_catalogs": "false"` in the harvester configuration JSON.

### Request timeout

The FDP harvester supports a per-request timeout in seconds via
`ckanext.fairdatapoint.request_timeout`. Default is `100`.

The setting can be overridden per harvester source by adding
`"request_timeout": "30"` (or another integer value in seconds) in the harvester configuration JSON.

### Label resolving

Labels are always resolved: for each URI-valued term of a dataset that has no label yet in a language, the
harvester loads the label from the URI's source and stores it as a CKAN translation. There is no switch to
turn this off.

The resolvers, chosen by the URI's host:

- Wikidata entities (`wikidata.org` URIs), read from the Wikidata entity RDF.
- BioOntology URIs (`bioontology.org`), read from the BioOntology API. The API needs the BioPortal key set
  with `ckanext.fairdatapoint.bioportal_api_key`; without it these URIs are not loaded.
- ICD-10 URIs (`http://icd.who.int/browse10/...`), read from the public WHO ICD-10 browser.
- DPV doc pages (`w3c.github.io` and `w3c-cg.github.io` URIs), rewritten to their `w3id.org` identifier first.
- Any other `http(s)` URI, loaded by content negotiation.

Which values of a dataset are looked up is decided by the dataset schema, through the action
`gdi_terms_to_translate` of ckanext-gdi-userportal: the values of the fields that the catalogue shows as a
label, so every label it sends out is stored. A deployment without that extension uses the field lists in
`ckanext/fairdatapoint/labels.py`.

The labels are stored in English, Dutch and every other language the dataset schema offers in its form
(`form_languages`); no setting of this extension is needed for that.

## Developer installation

To install ckanext-fairdatapoint for development, activate your CKAN virtualenv and
do:

    git clone https://github.com/GenomicDataInfrastructure/gdi-userportal-ckanext-fairdatapoint.git
    cd gdi-userportal-ckanext-fairdatapoint
    pip install -e .
    pip install -r dev-requirements.txt

Fairdatapoint plugin depends on `ckanext-scheming`, `ckanext-harvester` and `ckanext-dcat`. Make sure these are installed,
otherwise run:

```commandline
pip install -e 'git+https://github.com/ckan/ckanext-scheming.git@release-3.0.0#egg=ckanext-scheming[requirements]'
pip install -e 'git+https://github.com/ckan/ckanext-harvest.git@v1.6.0#egg=ckanext-harvest[requirements]'
pip install -e 'git+https://github.com/ckan/ckanext-dcat.git@v2.2.0#egg=ckanext-dcat'
pip install -r https://raw.githubusercontent.com/ckan/ckanext-dcat/v2.2.0/requirements.txt
```

## Tests

To run the tests go to [GDI harvester test information](https://genomicdatainfrastructure.github.io/gdi-userportal-docs/developer-guide/ckan/extension-local-setup-and-testing/)

The tests need a CKAN database configured in `test.ini`. From the repository root, with the development
requirements installed:

```bash
pytest --ckan-ini=test.ini ckanext/fairdatapoint
```

CI runs the same command (`.github/workflows/test.yml`).

## Releasing a new version of ckanext-fairdatapoint

Releases are made by the `Release` workflow (`.github/workflows/release.yml`), which is started by hand from
the Actions tab with a version increment (`major`, `minor` or `patch`):

1. It takes the latest tag (`vMAJOR.MINOR.PATCH`), increments the chosen part and pushes the new tag.
2. It creates a GitHub release for the new tag with generated release notes.

The version in `setup.py` is not changed by the workflow.

## License

This work is licensed under multiple licenses. Because keeping this section up-to-date is challenging, here is a brief summary:

- All original source code is licensed under [AGPL](./LICENSES/AGPL-3.0-only.txt).
- All documentation is licensed under [CC-BY-4.0](./LICENSES/CC-BY-4.0.txt).
- Some configuration and data files are licensed under [CC-BY-4.0](./LICENSES/CC-BY-4.0.txt).
- For more accurate information, check the individual files.
