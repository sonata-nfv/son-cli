#  Copyright (c) 2015 SONATA-NFV, UBIWHERE, i2CAT,
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
# Neither the name of the SONATA-NFV, UBIWHERE, i2CAT
# nor the names of its contributors may be used to endorse or promote
# products derived from this software without specific prior written
# permission.
#
# This work has been performed in the framework of the SONATA project,
# funded by the European Commission under Grant number 671517 through
# the Horizon 2020 and 5G-PPP programmes. The authors would like to
# acknowledge the contributions of their colleagues of the SONATA
# partner consortium (www.sonata-nfv.eu).

"""
usage: son-access [-h]
                  [--auth URL] [-u USERNAME] [-p PASSWORD]
                  [--push TOKEN_PATH PACKAGE_PATH]
                  [--pull TOKEN_PATH PACKAGE_ID]
                  [--pull TOKEN_PATH DESCRIPTOR_ID]
                  [--debug]

  -h, --help                        show this help message and exit
  --auth URL                        requests an Access token to authenticate the user,
                                    it requires platform url to login,
  -u USERNAME                       username of the user,
  -p PASSWORD                       password of the user
  --push TOKEN_PATH PACKAGE_PATH    submits a package to the SP, requires path to the token file and package
  --pull TOKEN_PATH PACKAGE_ID      requests a package or descriptor to the SP by its identifier,
                    DESCRIPTOR_ID   requires path to the token file
  --debug               increases logging level to debug
"""

import requests
import logging
import requests
import yaml
import sys
import validators
from datetime import datetime, timedelta
import jwt
import coloredlogs
import os
from os.path import expanduser
from helpers.helpers import json_response
from models.models import User

log = logging.getLogger(__name__)


class mcolors:
     OKGREEN = '\033[92m'
     FAIL = '\033[91m'
     ENDC = '\033[0m'


     def disable(self):
         self.OKGREEN = ''
         self.FAIL = ''
         self.ENDC = ''


class AccessClient:
    ACCESS_VERSION = "0.01"

    DEFAULT_ACCESS_DIR = os.path.join(expanduser("~"), ".son-access")

    def __init__(self, log_level='INFO'):
        """
        Header
        The JWT Header declares that the encoded object is a JSON Web Token (JWT) and the JWT is a JWS that is MACed
        using the HMAC SHA-256 algorithm
        """
        self.log_level = log_level
        coloredlogs.install(level=log_level)
        self.JWT_SECRET = 'secret'
        self.JWT_ALGORITHM = 'HS256'
        self.JWT_EXP_DELTA_SECONDS = 20
        self.URL = 'https://api.github.com/some/endpoint'

    def client_register(self, url, username, pwd):
        """
        Request registration from on the Service Platform
        :return: Initial JWT access_token? Or HTTP Code to confirm registration
        """
        form_data = {
            'username': username,
            'password': pwd
        }

        response = requests.post(url, data=form_data, verify=False)
        print "Registration response: ", mcolors.OKGREEN + response.text + "\n", mcolors.ENDC
        # TODO: Create userdata file?
        return response

    def client_login(self, address, username, pwd):
        """
        Make a POST request with username and password
        :return: JW Access Token is returned from the GK server
        """

        url = "http://" + address + "/login"

        # Construct the POST request
        form_data = {
            'username': username,
            'password': pwd
        }

        response = requests.post(url, data=form_data, verify=False)
        print "Access Token received: ", mcolors.OKGREEN + (response.text) + "\n", mcolors.ENDC
        # TODO: Write temp file with Access token
        return response.text

    def client_logout(self):
        """
        Send request to /logout interface to end user session
        :return: HTTP Code?
        """
        pass

    def client_authenticate(self):
        """
        Send access_token in Authorization headers with
        request to the restricted source (SP) to exchange for a
        authenticity token (This method might be removed)
        :return: HTTP code?
        """
        pass

    def check_token_validity(self):
        """
        Simple request to check if session has expired (TBD)
        :return: HTTP code?
        """
        pass

    def push_package(self, token, path):
        """
        tbd
        :return: 
        """
        mode = "push"
        url = "http://sp.int3.sonata-nfv.eu:32001"  # Read from config
        #path = "samples/sonata-demo.son"

        # Push son-package to the Service Platform
        raise NotImplementedError
        command = "sudo python %s.py %s -U %s" % (mode, url, path)
        print "Calling: ", mcolors.OKGREEN + command + "\n", mcolors.ENDC
        result = os.popen(command).read()
        print "Response: ", mcolors.OKGREEN + result + "\n", mcolors.ENDC

    def pull_resource(self, token, id):
        """
        tbd
        :return:
        """
        mode = "pull"
        url = "http://sp.int3.sonata-nfv.eu:32001"  # Read from config

        # Push son-package to the Service Platform
        raise NotImplementedError
        command = "sudo python %s.py %s -U %s" % (mode, url, id)
        print "Calling: ", mcolors.OKGREEN + command + "\n", mcolors.ENDC
        result = os.popen(command).read()
        print "Response: ", mcolors.OKGREEN + result + "\n", mcolors.ENDC


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="Authenticates users to submit and request resources from SONATA Service Platform")

    parser.add_argument(
        "--auth",
        type=str,
        #nargs=3,
        metavar="URL",
        help="authenticates a user to specific url",)

    parser.add_argument(
        "-u",
        type=str,
        metavar="USERNAME",
        help="specifies username of a user",
        required=False)

    parser.add_argument(
        "-p",
        type=str,
        metavar="PASSWORD",
        help="specifies password of a user",
        required=False)

    parser.add_argument(
        "--push",
        type=str,
        nargs=2,
        metavar=("TOKEN_PATH", "PACKAGE_PATH"),
        help="submits a package to the SP",
        required=False)

    parser.add_argument(
        "--pull",
        type=str,
        nargs=2,
        metavar=("TOKEN_PATH", "ID"),
        help="requests a package or descriptor to the SP by its id",
        required=False)

    parser.add_argument(
        "--debug",
        help="increases logging level to debug",
        required=False,
        action="store_true")

    args = parser.parse_args()

    log_level = "INFO"
    if args.debug:
        log_level = "DEBUG"
        coloredlogs.install(level=log_level)

    if args.auth:
        # Ensure that three arguments are given (URL, USERNAME and PASSWORD)
        if all(i is not None for i in [args.u, args.p]):
            usrname = args.u
            pwd = args.p
            ac = AccessClient(log_level)
            response = ac.client_login(args.auth, usrname, pwd)
        elif any(i is not None for i in [args.u, args.p]):
            parser.error(mcolors.FAIL + "Both Username and Password are required!" + mcolors.ENDC)
            parser.print_help()
            return
        else:
            parser.error(mcolors.FAIL + "Both Username and Password are required!" + mcolors.ENDC)
            parser.print_help()
            return

    if args.push:
        token_path = args.push[0]
        package_path = args.push[1]
        print token_path
        print package_path
        raise NotImplementedError

    if args.pull:
        token_path = args.pull[0]
        identifier = args.pull[1]
        print token_path
        print identifier
        raise NotImplementedError

    else:
        return


if __name__ == '__main__':
    #TODO: Call 'fake' User Management Auth on mock.py
    main()









