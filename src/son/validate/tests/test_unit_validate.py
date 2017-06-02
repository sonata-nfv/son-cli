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
from son.validate.validate import Validator
from son.workspace.workspace import Workspace, Project
from Crypto.PublicKey import RSA
from Crypto import Random
from Crypto.Hash import SHA256

SAMPLES_DIR = os.path.join('src', 'son', 'validate', 'tests', 'samples')


class UnitValidateTests(unittest.TestCase):

    def __init__(self, *args, **kwargs):
        super(UnitValidateTests, self).__init__(*args, **kwargs)

        # tap log functions to count for errors and warnings
        self._workspace = Workspace('.', log_level='debug')

    def test_validate_package_valid(self):
        """
        Tests the validation of a valid SONATA package.
        """

        pkg_path = os.path.join(SAMPLES_DIR, 'packages',
                                'sonata-demo-valid.son')
        validator = Validator(workspace=self._workspace)
        validator.validate_package(pkg_path)

        self.assertEqual(validator.error_count, 0)
        self.assertEqual(validator.warning_count, 0)

    def test_validate_package_invalid_struct(self):
        """
        Tests the validation of a multiple SONATA packages with a bad file
        structure.
        """
        # invalid struct #1
        pkg_path = os.path.join(SAMPLES_DIR, 'packages',
                                'sonata-demo-invalid-struct-1.son')
        validator = Validator(workspace=self._workspace)
        validator.validate_package(pkg_path)
        self.assertEqual(validator.error_count, 1)

        # invalid struct #2
        pkg_path = os.path.join(SAMPLES_DIR, 'packages',
                                'sonata-demo-invalid-struct-2.son')
        validator = Validator(workspace=self._workspace)
        validator.validate_package(pkg_path)
        self.assertEqual(validator.error_count, 1)

    def test_validate_package_signature(self):
        """
        Tests the package signature validation function of son-validate.
        To accomplish this:
            1) a private/public key pair is generated
            2) a signature is created based on a private key and a package file
            3) the signature validation function is called with the generated
               signature and the public key
        """
        # generate private/public key pair
        random_generator = Random.new().read
        key = RSA.generate(1024, random_generator)
        self.assertTrue(key.can_encrypt())
        self.assertTrue(key.can_sign())
        self.assertTrue(key.has_private())

        # create signature of a file
        pkg_path = os.path.join(SAMPLES_DIR, 'packages',
                                'sonata-demo-valid.son')
        file_data = None
        try:
            with open(pkg_path, 'rb') as _file:
                file_data = _file.read()
        except IOError as err:
            print("I/O error: {0}".format(err))
        pkg_hash = SHA256.new(file_data).digest()
        signature = str(key.sign(pkg_hash, '')[0])
        pubkey = key.publickey().exportKey('DER')  # export in binary encoding

        # call signature validation function
        validator = Validator(workspace=self._workspace)
        result = validator.validate_package_signature(pkg_path,
                                                      signature,
                                                      pubkey)
        # signature must be valid
        self.assertTrue(result)

        # call signature validation with a different file
        pkg_path = os.path.join(SAMPLES_DIR, 'packages',
                                'sonata-demo-invalid-md5.son')
        validator = Validator(workspace=self._workspace)
        result = validator.validate_package_signature(pkg_path,
                                                      signature,
                                                      pubkey)
        # signature must be invalid
        self.assertFalse(result)

    def test_validate_package_invalid_md5(self):
        """
        Tests the validation of a SONATA package with incorrect MD5 sums
        """
        pkg_path = os.path.join(SAMPLES_DIR, 'packages',
                                'sonata-demo-invalid-md5.son')
        validator = Validator(workspace=self._workspace)
        validator.validate_package(pkg_path)

        self.assertEqual(validator.error_count, 0)
        #TODO: check eventcfg first!

    def test_validate_package_invalid_integrigy(self):
        """
        Tests the validation of several SONATA packages with incorrect
        integrity.
        """
        # invalid integrity #1
        pkg_path = os.path.join(SAMPLES_DIR, 'packages',
                                'sonata-demo-invalid-integrity-1.son')
        validator = Validator(workspace=self._workspace)
        validator.validate_package(pkg_path)
        self.assertEqual(validator.error_count, 1)
        self.assertEqual(validator.warning_count, 0)

        # invalid integrity #2
        pkg_path = os.path.join(SAMPLES_DIR, 'packages',
                                'sonata-demo-invalid-integrity-2.son')
        validator = Validator(workspace=self._workspace)
        validator.validate_package(pkg_path)
        self.assertEqual(validator.error_count, 1)
        self.assertEqual(validator.warning_count, 0)

    def test_validate_project_valid(self):
        """
        Tests the validation of a valid SONATA project.
        """
        prj_path = os.path.join(SAMPLES_DIR, 'sample_project_valid')
        project = Project(self._workspace, prj_path)
        validator = Validator(workspace=self._workspace)
        validator.validate_project(project)

        self.assertEqual(validator.error_count, 0)
        self.assertEqual(validator.warning_count, 0)

    def test_validate_project_invalid(self):
        """
        Tests the validation of an invalid SONATA project.
        """
        prj_path = os.path.join(SAMPLES_DIR, 'sample_project_invalid')
        project = Project(self._workspace, prj_path)
        validator = Validator(workspace=self._workspace)
        validator.validate_project(project)

        self.assertGreater(validator.error_count, 0)

    def test_validate_project_warning(self):
        """
        Tests the validation of a SONATA project with warnings.
        """
        prj_path = os.path.join(SAMPLES_DIR, 'sample_project_warning')
        project = Project(self._workspace, prj_path)
        validator = Validator(workspace=self._workspace)
        validator.validate_project(project)

        self.assertEqual(validator.error_count, 0)
        self.assertGreater(validator.warning_count, 0)

    def test_validate_service_valid(self):
        """
        Tests the validation of a valid SONATA service.
        """
        service_path = os.path.join(SAMPLES_DIR, 'services', 'valid.yml')
        functions_path = os.path.join(SAMPLES_DIR, 'functions', 'valid')

        validator = Validator()
        validator.configure(dpath=functions_path)
        validator.validate_service(service_path)

        self.assertEqual(validator.error_count, 0)
        self.assertEqual(validator.warning_count, 0)

    def test_validate_service_invalid_syntax(self):
        """
        Tests the validation of an syntax-invalid SONATA service.
        """
        service_path = os.path.join(SAMPLES_DIR, 'services',
                                    'invalid_syntax.yml')

        validator = Validator()
        validator.configure(syntax=True, integrity=False, topology=False)
        validator.validate_service(service_path)

        self.assertGreater(validator.error_count, 0)

    def test_validate_service_invalid_integrity(self):
        """
        Test the validation of an integrity-invalid SONATA service.
        It ensures that syntax is valid.
        """
        service_path = os.path.join(SAMPLES_DIR, 'services',
                                    'invalid_integrity.yml')
        functions_path = os.path.join(SAMPLES_DIR, 'functions', 'valid')

        validator = Validator()

        # syntax validation -> should return OK
        validator.configure(dpath=functions_path,
                            syntax=True, integrity=False, topology=False)
        validator.validate_service(service_path)
        self.assertEqual(validator.error_count, 0)
        self.assertEqual(validator.warning_count, 0)

        # syntax and integrity validation -> should return ERROR(S)
        validator.configure(integrity=True)
        validator.validate_service(service_path)
        self.assertGreater(validator.error_count, 0)

    def test_validate_service_invalid_topology(self):
        """
        Test the validation of an integrity-invalid SONATA service.
        It ensures that syntax is valid.
        It ensures that integrity is valid.
        """
        service_path = os.path.join(SAMPLES_DIR, 'services',
                                    'invalid_topology.yml')
        functions_path = os.path.join(SAMPLES_DIR, 'functions', 'valid')

        validator = Validator()

        # syntax and integrity validation -> should return OK
        validator.configure(dpath=functions_path,
                            syntax=True, integrity=True, topology=False)
        validator.validate_service(service_path)
        self.assertEqual(validator.error_count, 0)
        self.assertEqual(validator.warning_count, 0)

        # syntax, integrity and topology validation -> should return ERROR(S)
        validator.configure(topology=True)
        validator.validate_service(service_path)
        self.assertGreater(validator.error_count, 0)

    def test_validate_function_valid(self):
        """
        Tests the validation of a valid SONATA function.
        """
        functions_path = os.path.join(SAMPLES_DIR, 'functions', 'valid')
        validator = Validator()
        validator.configure(syntax=True, integrity=True, topology=True)
        validator.validate_function(functions_path)

        self.assertEqual(validator.error_count, 0)
        self.assertEqual(validator.warning_count, 0)

    def test_validate_function_invalid_syntax(self):
        """
        Tests the validation of a syntax-invalid SONATA function.
        """
        functions_path = os.path.join(SAMPLES_DIR, 'functions',
                                      'invalid_syntax')

        validator = Validator()
        validator.configure(syntax=True, integrity=False, topology=False)
        validator.validate_function(functions_path)

        self.assertGreater(validator.error_count, 0)

    def test_validate_function_invalid_integrity(self):
        """
        Tests the validation of a integrity-invalid SONATA function.
        It ensures that syntax is valid.
        """
        functions_path = os.path.join(SAMPLES_DIR, 'functions',
                                      'invalid_integrity')
        validator = Validator()

        # syntax validation -> should return OK
        validator.configure(syntax=True, integrity=False, topology=False)
        validator.validate_function(functions_path)
        self.assertEqual(validator.error_count, 0)
        self.assertEqual(validator.warning_count, 0)

        # syntax and integrity validation -> should return ERROR(S)
        validator.configure(integrity=True)
        validator.validate_function(functions_path)
        self.assertGreater(validator.error_count, 0)
