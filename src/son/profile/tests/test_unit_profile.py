#  Copyright (c) 2015 SONATA-NFV, Paderborn University
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

import os
import unittest
from son.profile.helper import compute_cartesian_product
from son.profile.profile import ProfileManager, parse_args, extract_son_package


TEST_PED_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "misc/example_ped1.yml")


class UnitProfileTests(unittest.TestCase):

    def test_input_package_unzipping(self):
        """
        Loads test PED file and tries to extract the linked *.son package.
        Checks if the basic package structure is available in the work_dir after extraction.
        :return:
        """
        args = parse_args(["-c", TEST_PED_FILE, "-v"])
        p = ProfileManager(args)
        extract_son_package(p._load_ped_file(p.args.config), p.son_pkg_input_dir)
        self.assertTrue(os.path.exists(os.path.join(p.son_pkg_input_dir, "META-INF")))
        self.assertTrue(os.path.exists(os.path.join(p.son_pkg_input_dir, "META-INF/MANIFEST.MF")))
        self.assertTrue(os.path.exists(os.path.join(p.son_pkg_input_dir, "function_descriptors")))
        self.assertTrue(os.path.exists(os.path.join(p.son_pkg_input_dir, "service_descriptors")))

    def test_input_package_content_loading(self):
        # TODO implement real test
        self.assertTrue(True)

    def test_experiment_specification_population(self):
        # TODO implement real test
        self.assertTrue(True)

    def test_output_service_generation(self):
        # TODO implement real test
        self.assertTrue(True)

    def test_output_service_write_to_disk(self):
        # TODO implement real test
        self.assertTrue(True)

    def test_output_service_packaging(self):
        # TODO implement real test
        self.assertTrue(True)


class UnitHelperTests(unittest.TestCase):

    def test_cartesian_product(self):
        """
        Test the function which computes the cartesian product
        of a dictionary of lists.
        This one is used to explore the complete parameter space specifeid
        in a PED file.
        :return:
        """

        def _dict_is_in_list(d, l):
            for d1 in l:
                if d1 == d:
                    return True
            return False

        INPUT = {"x": [1, 2, 3], "y": ["value1", "value2"]}
        OUTPUT = [
            {"x": 1, "y": "value1"},
            {"x": 1, "y": "value2"},
            {"x": 2, "y": "value1"},
            {"x": 2, "y": "value2"},
            {"x": 3, "y": "value1"},
            {"x": 3, "y": "value2"}
        ]
        # calculate Cartesian product
        result = compute_cartesian_product(INPUT)
        # check if results are as expected
        self.assertEqual(len(result), len(OUTPUT))
        for d in result:
            self.assertTrue(_dict_is_in_list(d, OUTPUT))
