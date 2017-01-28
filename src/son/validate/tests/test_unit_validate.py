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
import os
import son.validate.validate as val
from son.validate.util import CountCalls
from son.validate.validate import Validator
from son.workspace.workspace import Workspace, Project

SAMPLES_DIR = os.path.join('src', 'son', 'validate', 'tests', 'samples')


class UnitValidateTests(unittest.TestCase):

    def __init__(self, *args, **kwargs):
        super(UnitValidateTests, self).__init__(*args, **kwargs)

        # tap log functions to count for errors and warnings
        self._workspace = Workspace('.', log_level='debug')
        val.log.error = CountCalls(val.log.error)
        val.log.warning = CountCalls(val.log.warning)

    @staticmethod
    def reset_counters():
        val.log.error.counter = 0
        val.log.warning.counter = 0

    def test_validate_package_valid(self):
        """
        Tests the validation of a valid SONATA package.
        """
        self.reset_counters()
        pkg_path = os.path.join(SAMPLES_DIR, 'packages',
                                'sonata-demo-valid.son')
        validator = Validator(workspace=self._workspace)
        validator.validate_package(pkg_path)

        self.assertEqual(val.log.error.counter, 0)
        self.assertEqual(val.log.warning.counter, 0)

    def test_validate_package_invalid_struct(self):
        """
        Tests the validation of a multiple SONATA packages with a bad file
        structure.
        """
        # invalid struct #1
        self.reset_counters()
        pkg_path = os.path.join(SAMPLES_DIR, 'packages',
                                'sonata-demo-invalid-struct-1.son')
        validator = Validator(workspace=self._workspace)
        validator.validate_package(pkg_path)
        self.assertEqual(val.log.error.counter, 1)

        # invalid struct #2
        self.reset_counters()
        pkg_path = os.path.join(SAMPLES_DIR, 'packages',
                                'sonata-demo-invalid-struct-2.son')
        validator = Validator(workspace=self._workspace)
        validator.validate_package(pkg_path)
        self.assertEqual(val.log.error.counter, 1)


    def test_validate_package_invalid_md5(self):
        """
        Tests the validation of a SONATA package with incorrect MD5 sums
        """
        self.reset_counters()
        pkg_path = os.path.join(SAMPLES_DIR, 'packages',
                                'sonata-demo-invalid-md5.son')
        validator = Validator(workspace=self._workspace)
        validator.validate_package(pkg_path)

        self.assertEqual(val.log.error.counter, 0)
        self.assertEqual(val.log.warning.counter, 4)

    def test_validate_package_invalid_integrigy(self):
        """
        Tests the validation of several SONATA packages with incorrect
        integrity.
        """
        # invalid integrity #1
        self.reset_counters()
        pkg_path = os.path.join(SAMPLES_DIR, 'packages',
                                'sonata-demo-invalid-integrity-1.son')
        validator = Validator(workspace=self._workspace)
        validator.validate_package(pkg_path)
        self.assertEqual(val.log.error.counter, 1)
        self.assertEqual(val.log.warning.counter, 0)

        # invalid integrity #2
        self.reset_counters()
        pkg_path = os.path.join(SAMPLES_DIR, 'packages',
                                'sonata-demo-invalid-integrity-2.son')
        validator = Validator(workspace=self._workspace)
        validator.validate_package(pkg_path)
        self.assertEqual(val.log.error.counter, 1)
        self.assertEqual(val.log.warning.counter, 0)

    def test_validate_project_valid(self):
        """
        Tests the validation of a valid SONATA project.
        """
        self.reset_counters()
        prj_path = os.path.join(SAMPLES_DIR, 'sample_project_valid')
        project = Project(self._workspace, prj_path)
        validator = Validator(workspace=self._workspace)
        validator.validate_project(project)

        self.assertEqual(val.log.error.counter, 0)
        self.assertEqual(val.log.warning.counter, 0)

    def test_validate_project_invalid(self):
        """
        Tests the validation of an invalid SONATA project.
        """
        self.reset_counters()
        prj_path = os.path.join(SAMPLES_DIR, 'sample_project_invalid')
        project = Project(self._workspace, prj_path)
        validator = Validator(workspace=self._workspace)
        validator.validate_project(project)

        self.assertGreater(val.log.error.counter, 0)

    def test_validate_project_warning(self):
        """
        Tests the validation of a SONATA project with warnings.
        """
        self.reset_counters()
        prj_path = os.path.join(SAMPLES_DIR, 'sample_project_warning')
        project = Project(self._workspace, prj_path)
        validator = Validator(workspace=self._workspace)
        validator.validate_project(project)

        self.assertEqual(val.log.error.counter, 0)
        self.assertGreater(val.log.warning.counter, 0)

    def test_validate_service_valid(self):
        """
        Tests the validation of a valid SONATA service.
        """
        self.reset_counters()
        service_path = os.path.join(SAMPLES_DIR, 'services', 'valid.yml')
        functions_path = os.path.join(SAMPLES_DIR, 'functions', 'valid')

        validator = Validator()
        validator.configure(dpath=functions_path)
        validator.validate_service(service_path)

        self.assertEqual(val.log.error.counter, 0)
        self.assertEqual(val.log.warning.counter, 0)

    def test_validate_service_invalid_syntax(self):
        """
        Tests the validation of an syntax-invalid SONATA service.
        """
        self.reset_counters()
        service_path = os.path.join(SAMPLES_DIR, 'services',
                                    'invalid_syntax.yml')

        validator = Validator()
        validator.configure(syntax=True, integrity=False, topology=False)
        validator.validate_service(service_path)

        self.assertGreater(val.log.error.counter, 0)

    def test_validate_service_invalid_integrity(self):
        """
        Test the validation of an integrity-invalid SONATA service.
        It ensures that syntax is valid.
        """
        self.reset_counters()
        service_path = os.path.join(SAMPLES_DIR, 'services',
                                    'invalid_integrity.yml')
        functions_path = os.path.join(SAMPLES_DIR, 'functions', 'valid')

        validator = Validator()

        # syntax validation -> should return OK
        validator.configure(dpath=functions_path,
                            syntax=True, integrity=False, topology=False)
        validator.validate_service(service_path)
        self.assertEqual(val.log.error.counter, 0)
        self.assertEqual(val.log.warning.counter, 0)

        # syntax and integrity validation -> should return ERROR(S)
        validator.configure(integrity=True)
        validator.validate_service(service_path)
        self.assertGreater(val.log.error.counter, 0)

    def test_validate_service_invalid_topology(self):
        """
        Test the validation of an integrity-invalid SONATA service.
        It ensures that syntax is valid.
        It ensures that integrity is valid.
        """
        self.reset_counters()
        service_path = os.path.join(SAMPLES_DIR, 'services',
                                    'invalid_topology.yml')
        functions_path = os.path.join(SAMPLES_DIR, 'functions', 'valid')

        validator = Validator()

        # syntax and integrity validation -> should return OK
        validator.configure(dpath=functions_path,
                            syntax=True, integrity=True, topology=False)
        validator.validate_service(service_path)
        self.assertEqual(val.log.error.counter, 0)
        self.assertEqual(val.log.warning.counter, 0)

        # syntax, integrity and topology validation -> should return ERROR(S)
        validator.configure(topology=True)
        validator.validate_service(service_path)
        self.assertGreater(val.log.error.counter, 0)

    def test_validate_function_valid(self):
        """
        Tests the validation of a valid SONATA function.
        """
        self.reset_counters()
        functions_path = os.path.join(SAMPLES_DIR, 'functions', 'valid')
        validator = Validator()
        validator.configure(syntax=True, integrity=True, topology=True)
        validator.validate_function(functions_path)

        self.assertEqual(val.log.error.counter, 0)
        self.assertEqual(val.log.warning.counter, 0)

    def test_validate_function_invalid_syntax(self):
        """
        Tests the validation of a syntax-invalid SONATA function.
        """
        self.reset_counters()
        functions_path = os.path.join(SAMPLES_DIR, 'functions',
                                      'invalid_syntax')

        validator = Validator()
        validator.configure(syntax=True, integrity=False, topology=False)
        validator.validate_function(functions_path)

        self.assertGreater(val.log.error.counter, 0)

    def test_validate_function_invalid_integrity(self):
        """
        Tests the validation of a integrity-invalid SONATA function.
        It ensures that syntax is valid.
        """
        self.reset_counters()
        functions_path = os.path.join(SAMPLES_DIR, 'functions',
                                      'invalid_integrity')
        validator = Validator()

        # syntax validation -> should return OK
        validator.configure(syntax=True, integrity=False, topology=False)
        validator.validate_function(functions_path)
        self.assertEqual(val.log.error.counter, 0)
        self.assertEqual(val.log.warning.counter, 0)

        # syntax and integrity validation -> should return ERROR(S)
        validator.configure(integrity=True)
        validator.validate_function(functions_path)
        self.assertGreater(val.log.error.counter, 0)

    def test_validate_function_invalid_topology(self):
        # TODO TBD: how is a topology invalid in a function?
        pass


