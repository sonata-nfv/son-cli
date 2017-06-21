#  Copyright (c) 2015 SONATA-NFV, UBIWHERE
# ALL RIGHTS RESERVED.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# Neither the name of the SONATA-NFV, UBIWHERE
# nor the names of its contributors may be used to endorse or promote
# products derived from this software without specific prior written
# permission.
#
# This work has been performed in the framework of the SONATA project,
# funded by the European Commission under Grant number 671517 through
# the Horizon 2020 and 5G-PPP programmes. The authors would like to
# acknowledge the contributions of their colleagues of the SONATA
# partner consortium (www.sonata-nfv.eu).

from setuptools import setup, find_packages
import codecs
import os.path as path

# buildout build system 
# http://www.buildout.org/en/latest/docs/tutorial.html

# setup() documentation: 
# http://python-packaging-user-guide.readthedocs.org/en/
# latest/distributing/#setup-py


cwd = path.dirname(__file__)
longdesc = codecs.open(path.join(cwd, 'README.md'), 'r', 'utf-8').read()

name = 'sonata-cli'
setup(
        name=name,
        license='Apache License, Version 2.0',
        version='0.9',
        url='https://github.com/sonata-nfv/son-cli',
        author_email='sonata-dev@sonata-nfv.eu',
        long_description=longdesc,
        package_dir={'': 'src'},
        packages=find_packages('src'),  # dependency resolution
        namespace_packages=['son', ],
        include_package_data=True,
        package_data= {
            'son': ['schema/tests/son-schema/*', 'workspace/samples/*',
                    'monitor/docker_compose_files/*', 'monitor/grafana/*',
                    'monitor/prometheus/*', 'monitor/*.exp',
                    'validate/eventcfg.yml']
        },
        # in jenkins, the last package in the list is installed first
        install_requires=['setuptools', 'pyaml', 'jsonschema', 'validators',
                          'requests>2.4.2', 'coloredlogs<=5.1.1', 'paramiko',
                          'termcolor', 'tabulate', 'networkx', 'PyJWT>=1.4.2',
                          'Flask', 'docker==2.0.2', 'scipy', 'numpy',
                          'watchdog', 'Flask-Cors', 'flask_cache', 'redis',
                          'pycrypto', 'matplotlib', 'prometheus_client'],
        zip_safe=False,
        entry_points={
            'console_scripts': [
                'son-workspace=son.workspace.workspace:main',
                'son-package=son.package.package:main',
                'son-monitor=son.monitor.monitor:main',
                'son-profile=son.profile.profile:main',
                'son-validate=son.validate.validate:main',
                'son-validate-api=son.validate.api.api:main',
                'son-validate-watchdog=son.validate.api.watchdog:main',
                'son-access=son.access.access:main'
            ],
        },
        test_suite='son',
        setup_requires=['pytest-runner'],
        tests_require=['pytest']
    )
