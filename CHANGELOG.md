<!--
SPDX-FileCopyrightText: 2024 Strichting Health-RI

SPDX-License-Identifier: CC-BY-4.0
-->

# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).


## [v1.6.3] - 2025-10-21

### Changed
- Move 'status' field to resource replace fields by @Quinten in f95ccfe


## [v1.6.2] - 2025-10-14

### Changed
- Improve error handling for RDF graph loading by @Quinten in f0cbe0c


## [v1.6.1] - 2025-10-03

### Added
- feat(multi-lingual-support) Added extra sanitasation on translated tags by @Hans-christian in d5fc478


### Changed
- Improve BioPortal API key handling and add tests by @Quinten in 62e42ce
- Aplly correct logging by @Hans-christian in 87f3866
- Apply suggestion from @sourcery-ai[bot] by @Hans-Christian in 68efa1f
- Remove commented out code by @Hans-Christian in 965769e
- Restrict label translations to supported languages by @Hans-christian in 74ed6d0
- Remove token set by @Hans-christian in 1492b15
- Bump packages by @Hans-christian in d3213f7
- Apply suggestion from @sourcery-ai[bot] by @Hans-Christian in c299bd4
- Fix test by @Hans-christian in fb035ed
- update test.yml by @Hans-christian in 29cf6c4
- chore(deps): update dependency rdflib to ~=7.2.1 by @Renovate Bot in 02c7b4b
- chore(deps): update actions/checkout action to v5 by @Renovate Bot in 9fa1f01
- doc: update CHANGELOG.md for v1.6.0 by @LNDS-Sysadmins in 116a1de


### Fixed
- fix release major minor and patch by @Hans-christian in 666f9b5
- Improve error handling and code clarity in label resolver by @Quinten in dd07134
- fix UT by @Hans-christian in 0c5e4fb
- fix UT by @Hans-christian in 6845adc
- fix test.yml by @Hans-christian in 8b751a2
- fix run by @Hans-christian in 60b5c4b
- patch sonar cloud by @Hans-christian in b38fe94
- fix UT by @Hans-christian in 5e83d33


## [v1.6.0] - 2025-07-08

### Changed
- chore(deps): update dependency setuptools to v80 [security] by @Renovate Bot in 8a4395f


## [v1.4.0] - 2025-06-10

### Added
- fix(feat) Finishing up UT for gather phase by @Hans-Chrstian in f0c4f90


### Changed
- Use name instead of guid instead by @Hans-christian in 2f60959
- Apply suggestions from code review by @Hans-Christian in bae45a4
- Update .github/workflows/test.yml by @Hans-Christian in 415dd04
- Feat(UT) Added UT for import stage by @Hans-Christian van der Werf in 9b76348
- Added Ut for gather phase by @Hans-Chrstian in 48810fd
- test(harvester): add unit tests for fetch_stage covering all status scenarios by @Hans-Chrstian in d54c62b
- test(harvester): add unit tests for fetch_stage covering all status scenarios by @Hans-Chrstian in e9297b3
- Applied sourcery comments by @Hans-Chrstian in 8c9ac1a
- Update ckanext/fairdatapoint/harvesters/civity_harvester.py by @Hans-Christian in db97ce7
- chore(deps): update redis docker tag to v8 by @Renovate Bot in bf2dd95
- doc: update CHANGELOG.md for v1.3.6 by @LNDS-Sysadmins in 3d670e0


### Fixed
- fix(ut) gather objects by @Hans-Christian van der Werf in f873372
- fix(UT) Add correct fixture to get UT working by @Hans-Chrstian in 1b3d51a
- fix UT by @Hans-Chrstian in d5c05b5
- fix(harvester): ensure unique package name, proper current flag, and prevent duplicate harvest objects by @Hans-Chrstian in d8a0e67


## [v1.3.6] - 2025-04-10

### Added
- feat:(ART-14066) update release plan by @jadzlnds in 9261860
- feat:(ART-14066) update release plan by @jadzlnds in 14ac072
- feat:(ART-14066) update release plan by @jadzlnds in 37cbdcc


### Changed
- Update ckanext/fairdatapoint/harvesters/domain/identifier.py by @Hans-Christian in 2b02ace


### Fixed
- fix UT by @Hans-Chrstian in 2739d1e
- fix(identifier): correctly parse values containing '=' in Identifier by @Hans-Chrstian in 11d9354


## [v1.3.5] - 2025-04-04

### Changed
- chore(deps): update dependency setuptools to v77 by @Renovate Bot in 25359a4
- chore(deps): update dependency setuptools to v76 by @Renovate Bot in 11baacd



## [v1.3.4] - 2025-04-04

### Changed
- Review comments by @Hans-Chrstian in 710cbc5
- simplify root response FDP without catalogs by @Hans-Chrstian in 3602365
- Refactor based on Sourcery comments by @Hans-Chrstian in 9152807
- refactor(domain): restructure FDP processing to use LDP hierarchy by @Hans-Chrstian in 49fc206


### Fixed
- fix license fdprecord by @Hans-Chrstian in 0c35768



## [v1.3.3] - 2025-04-04

### Added
- feat: integrate Health DCAT file on top of DCAT-AP 3 profile by @Hans-Chrstian in 5647b7c


### Changed
- Revert setuptools by @Hans-Chrstian in c3819c4
- use setuptools instead ckantoolkit by @Hans-Chrstian in 4a7a33d
- replace setuptools with ckantoolkit by @Hans-Chrstian in 69f482f
- chore(deps): update sonarsource/sonarcloud-github-action action to v4 by @Renovate Bot in d607991


### Removed
- Revert sonarcloud and removed six by @Hans-Chrstian in 8dfcf0e



### Added

## [v1.4.1] - 2024-11-21

### Fixed
* Fix: Resolve labels during harvesting by @Markus92 in

## [v1.4.0] - 2024-11-21

### What's Changed
* Dcat 2.1.0 by @hcvdwerf in https://github.com/GenomicDataInfrastructure/gdi-userportal-ckanext-fairdatapoint/pull/85
* Resolve labels during harvesting by @Markus92 in https://github.com/GenomicDataInfrastructure/gdi-userportal-ckanext-fairdatapoint/pull/83

### Security
* chore(deps): update dependency rdflib to ~=7.1.0 by @LNDS-Sysadmins in https://github.com/GenomicDataInfrastructure/gdi-userportal-ckanext-fairdatapoint/pull/82
* chore(deps): update fsfe/reuse-action action to v5 by @LNDS-Sysadmins in https://github.com/GenomicDataInfrastructure/gdi-userportal-ckanext-fairdatapoint/pull/84


## [v1.2.2] - 2024-06-28

### Added
- feat(ci): integrate SonarCloud analysis and coverage report closes #18
- fix: Security alert requests closes #30
- doc: Improved Readme.md