# SPDX-FileCopyrightText: 2024 Stichting Health-RI
#
# SPDX-License-Identifier: AGPL-3.0-only

FROM ckan/ckan-dev:2.10

WORKDIR /opt

RUN  pip install -e 'git+https://github.com/ckan/ckanext-scheming.git@release-3.0.0#egg=ckanext-scheming[requirements]'
RUN  pip install -e 'git+https://github.com/ckan/ckanext-harvest.git@v1.5.6#egg=ckanext-harvest[requirements]'
RUN  pip install -e 'git+https://github.com/ckan/ckanext-dcat.git@v1.5.1#egg=ckanext-dcat[requirements]'
RUN  pip install -r https://raw.githubusercontent.com/ckan/ckanext-dcat/v1.5.1/requirements.txt

COPY . /opt/fdp
WORKDIR /opt/fdp

RUN pip install -r requirements.txt
RUN pip install -r dev-requirements.txt
RUN pip install --upgrade pytest-rerunfailures

RUN python3 setup.py develop
# Replace default path to CKAN core config file with the one on the container
RUN sed -i -e 's/use = config:.*/use = config:\/srv\/app\/src\/ckan\/test-core.ini/' test.ini

CMD ./ckanext/fairdatapoint/tests/run_tests.sh