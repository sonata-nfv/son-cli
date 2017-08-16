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
import shutil
import socket
from son.validate.validate import Validator
from son.workspace.workspace import Workspace, Project
from son.validate.event import EventLogger
from Crypto.PublicKey import RSA
from Crypto import Random
from Crypto.Hash import SHA256
import subprocess
import time
import signal
import requests
from requests_toolbelt import MultipartEncoder

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
        eventdict = EventLogger.load_eventcfg()
        invalid_md5_config = str(eventdict['evt_pd_itg_invalid_md5']).lower()
        if invalid_md5_config == 'error':
            error_count = 1
            warn_count = 1
        elif invalid_md5_config == 'warning':
            error_count = 0
            warn_count = 2
        elif invalid_md5_config == 'none':
            error_count = 0
            warn_count = 1
        else:
            self.fail("Invalid value of event 'evt_pd_itg_invalid_md5'")

        self.assertEqual(validator.error_count, error_count)
        self.assertEqual(validator.warning_count, warn_count)

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

    def test_event_config_cli(self):
        """
        Tests the custom event configuration meant to be used with the CLI
        """

        # backup current user eventcfg (if exists)
        if os.path.isfile('eventcfg.yml'):
            shutil.move('eventcfg.yml', '.eventcfg.yml.original')

        # load eventdict
        eventdict = EventLogger.load_eventcfg()

        # report unmatched file hashes as error
        eventdict['evt_pd_itg_invalid_md5'] = 'error'
        # report vdu image not found as error
        eventdict['evt_vnfd_itg_vdu_image_not_found'] = 'error'

        # write eventdict
        EventLogger.dump_eventcfg(eventdict)

        # perform validation test
        pkg_path = os.path.join(SAMPLES_DIR, 'packages',
                                'sonata-demo-invalid-md5.son')
        validator = Validator(workspace=self._workspace)
        validator.validate_package(pkg_path)

        # should return 1 error
        self.assertEqual(validator.error_count, 2)
        self.assertEqual(validator.warning_count, 0)

        # report unmatched file hashes as warning
        eventdict['evt_pd_itg_invalid_md5'] = 'warning'
        # do not report vdu image not found
        eventdict['evt_vnfd_itg_vdu_image_not_found'] = 'none'

        # write eventdict
        EventLogger.dump_eventcfg(eventdict)

        # perform validation test
        pkg_path = os.path.join(SAMPLES_DIR, 'packages',
                                'sonata-demo-invalid-md5.son')
        validator = Validator(workspace=self._workspace)
        validator.validate_package(pkg_path)

        # should return 1 warning
        self.assertEqual(validator.error_count, 0)
        self.assertEqual(validator.warning_count, 1)

        # delete temporary eventcfg
        os.remove('eventcfg.yml')

        # restore user eventcfg
        if os.path.isfile('.eventcfg.yml.original'):
            shutil.move('.eventcfg.yml.original', 'eventcfg.yml')

    def test_event_config_api(self):
        """
        Tests the dynamic event configuration to be used with the API
        """
        # backup current user eventcfg (if exists)
        if os.path.isfile('eventcfg.yml'):
            shutil.move('eventcfg.yml', '.eventcfg.yml.original')

        # start validate service and wait for it to start
        proc = subprocess.Popen(["bin/son-validate-api",
                                 "--host", "127.0.0.1",
                                 "--port", "7777",
                                 "--mode", "stateless", "--debug"])

        # wait for validate service to start
        result = 1
        max_retries = 5
        while result != 0:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(5)  # 2 Second Timeout
            time.sleep(2)
            result = sock.connect_ex(('127.0.0.1', 7777))
            if result == 0:
                print("son-validate-api available. "
                      "Starting connectivity tests")
                sock.close()
            else:
                print("Waiting for son-validate-api...")
                max_retries -= 1
                if max_retries == 0:
                    # avoid test failure if it doesn't connect
                    print("Can't connect to local son-validate-api. "
                          "Ignoring test")
                    return

        # test '/events/list' endpoint
        url = "http://127.0.0.1:7777/events/list"
        r = requests.get(url)
        self.assertEqual(r.status_code, 200)
        self.assertIs(type(r.json()), dict)

        # post an event configuration
        # - report unmatched file hashes as an error
        # - report vdu image not found as error
        url = "http://127.0.0.1:7777/events/config"
        data = {'evt_pd_itg_invalid_md5': 'error',
                'evt_vnfd_itg_vdu_image_not_found': 'error'}
        r = requests.post(url, data=data)
        self.assertEqual(r.status_code, 200)

        # perform validation test
        url = "http://127.0.0.1:7777/validate/package"
        pkg_path = os.path.join(SAMPLES_DIR, 'packages',
                                'sonata-demo-invalid-md5.son')
        file = open(pkg_path, 'rb')
        data = {'source': "embedded",
                'syntax': 'true',
                'integrity': 'true',
                'topology': 'true',
                'file': (file.name, file, 'application/octet-stream')
                }
        multi = MultipartEncoder(data)
        headers = {'Content-Type': multi.content_type}
        r = requests.post(url, headers=headers, data=multi)
        self.assertEqual(r.status_code, 200)
        self.assertIs(type(r.json()), dict)
        result = r.json()
        self.assertEqual(result['error_count'], 2)
        self.assertEqual(result['warning_count'], 0)

        # post an event configuration
        # - report unmatched file hashes as an warning
        # - do not report vdu image not found
        url = "http://127.0.0.1:7777/events/config"
        data = {'evt_pd_itg_invalid_md5': 'warning',
                'evt_vnfd_itg_vdu_image_not_found': 'none'}
        r = requests.post(url, data=data)
        self.assertEqual(r.status_code, 200)

        # perform validation test
        url = "http://127.0.0.1:7777/validate/package"
        pkg_path = os.path.join(SAMPLES_DIR, 'packages',
                                'sonata-demo-invalid-md5.son')
        file = open(pkg_path, 'rb')
        data = {'source': "embedded",
                'syntax': 'true',
                'integrity': 'true',
                'topology': 'true',
                'file': (file.name, file, 'application/octet-stream')
                }
        multi = MultipartEncoder(data)
        headers = {'Content-Type': multi.content_type}
        r = requests.post(url, headers=headers, data=multi)
        self.assertEqual(r.status_code, 200)
        self.assertIs(type(r.json()), dict)
        result = r.json()
        self.assertEqual(result['error_count'], 0)
        self.assertEqual(result['warning_count'], 1)

        # stop validate service
        proc.send_signal(signal.SIGINT)

        # delete temporary eventcfg
        os.remove('eventcfg.yml')

        # restore user eventcfg
        if os.path.isfile('.eventcfg.yml.original'):
            shutil.move('.eventcfg.yml.original', 'eventcfg.yml')
