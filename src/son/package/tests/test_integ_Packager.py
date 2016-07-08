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
from son.package.package import Packager
from son.workspace.workspace import Workspace
from son.workspace.workspace import Project


class IntPDTester(unittest.TestCase):

    __pfd__ = {
        'name': 'sonata-project-sample',
        'vendor': 'com.sonata.project',
        'version': '0.0.1',
        'maintainer': 'Name, Company, Contact',
        'description': 'Project description',
        'catalogues': ['personal'],
        'publish_to': ['personal']
    }

    def __init__(self, *args, **kwargs):
        super(IntPDTester, self).__init__(*args, **kwargs)
        ws = Workspace("")
        prj = Project(ws, '/')
        self.pck = Packager(workspace=ws, project=prj, generate_pd=False)

    def test_correct_gds(self):
        """ Test the correct general description section """
        gsd = self.pck.package_gds(IntPDTester.__pfd__)
        self.assertNotEqual(gsd, False)

    def test_incomplete_gds(self):
        """
        Test the returning message when the provided
        project has incomplete information.
        """
        pfd = IntPDTester.__pfd__
        pfd.pop('name')
        gsd = self.pck.package_gds(pfd)
        self.assertEqual(gsd, False)
