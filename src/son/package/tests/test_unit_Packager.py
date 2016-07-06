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

import unittest
from unittest.mock import patch
from unittest.mock import Mock
from unittest import mock
from son.package.package import Packager
from son.workspace.workspace import Workspace
from son.workspace.workspace import Project


class UnitCreatePackageTests(unittest.TestCase):

    @patch('son.package.package.os.path.join')
    @patch('son.package.package.zipfile')
    def test_generate_package(self, m_zipfile, m_join):
        """
        Ensures that a package file is created with correct name and location
        """
        # First, create a workspace to give to Packager
        workspace = Workspace("ws/root", ws_name="ws_test", log_level='debug')

        # Create project
        project = Project(workspace, 'prj/path')

        # Instantiate a Packager instance
        packager = Packager(workspace=workspace, project=project, generate_pd=False, dst_path="dst/path")
        packager._package_descriptor = True

        # Prepare mocks
        context_manager_mock = Mock()
        m_zipfile.ZipFile.return_value = context_manager_mock
        enter_mock = Mock()
        exit_mock = Mock()
        setattr(context_manager_mock, '__enter__', enter_mock)
        setattr(context_manager_mock, '__exit__', exit_mock)

        # execute
        packager.generate_package("package_name")

        # make assertions
        self.assertEqual(m_join.call_args_list[-1], mock.call('dst/path', 'package_name.son'))

    def test_package_gds(self):
        """
        Test the validation of the project general description section
        """
        # First, create a workspace to give to Packager
        workspace = Workspace("ws/root", ws_name="ws_test", log_level='debug')

        # Create project
        project = Project(workspace, 'prj/path')

        # Instantiate a Packager instance
        packager = Packager(workspace=workspace, project=project, generate_pd=False, dst_path="dst/path")
        packager._package_descriptor = True

        # Create fake project configuration
        prj_config = {
            'catalogues': '[personal]',
            'description': 'Project description',
            'vendor': 'eu.sonata.project',
            'maintainer': 'Name, Company, Contact',
            'publish_to': '[personal]',
            'version': '0.0.1'
            }

        # Remove keys, one by one...
        for key in prj_config:
            value = prj_config.pop(key)
            self.assertFalse(packager.package_gds(prj_config))
            prj_config[key] = value

        # Make prj_config complete...
        prj_config['name'] = 'sonata - project - sample'

        self.assertTrue(packager.package_gds(prj_config))



