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
from config.config import GK_ADDRESS, GK_PORT

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
    ACCESS_VERSION = "0.2"

    DEFAULT_ACCESS_DIR = os.path.join(expanduser("~"), ".son-access")

    GK_API_VERSION = "/api/v2"
    GK_API_BASE = "/"
    GK_URI_REG = "/register"
    GK_URI_LOG = "/login"
    GK_URI_AUT = "TBD"
    GK_URI_REF = "/refresh"
    GK_URI_TKV = "TBD"

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
        try:
            self.URL = 'http://' + str(GK_ADDRESS) + ':' + str(GK_PORT)
        except:
            print("Platform url is required in config file")

        # Ensure parameters are valid
        assert validators.url(self.URL),\
            "Failed to init catalogue client. Invalid URL: '{}'"\
            .format(self.URL)

    def client_register(self, username, password):
        """
        Request registration form on the Service Platform
        :param username: user identifier
        :param password: user password
        :return: Initial JWT access_token? Or HTTP Code to confirm registration
        """
        form_data = {
            'username': username,
            'password': password
        }

        url = self.URL + self.GK_API_VERSION + self.GK_URI_REG

        response = requests.post(url, data=form_data, verify=False)
        print "Registration response: ", mcolors.OKGREEN + response.text + "\n", mcolors.ENDC
        # TODO: Create userdata file? Check KEYCLOAK register form
        return response

    def client_login(self, username, password):
        """
        Make a POST request with username and password
        :param username: user identifier
        :param password: user password
        :return: JW Access Token is returned from the GK server
        """

        url = "http://" + self.URL + self.GK_API_VERSION + self.GK_URI_LOG

        # Construct the POST request
        form_data = {
            'username': username,
            'password': password
        }

        response = requests.post(url, data=form_data, verify=False)
        print("Access Token received: ", mcolors.OKGREEN + response.text + "\n", mcolors.ENDC)
        token = response.text.replace('\n', '')
        with open("config/token.txt", "wb") as token_file:
            token_file.write(token)

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

    def push_package(self, path):
        """
        Call push feature to upload a package to the SP Catalogue
        :return: HTTP code 201 or 40X
        """
        # mode = "push"
        # url = "http://sp.int3.sonata-nfv.eu:32001"  # Read from config
        # path = "samples/sonata-demo.son"

        # Push son-package to the Service Platform
        command = "sudo python push.py -U %s" % path
        print("Calling: ", mcolors.OKGREEN + command + "\n", mcolors.ENDC)
        result = os.popen(command).read()
        print("Response: ", mcolors.OKGREEN + result + "\n", mcolors.ENDC)

    def pull_resource(self, resource_type, id=None):
        """
        Call pull feature to request a resource from the SP Catalogue
        :param resource_type: a valid resource classifier (services, functions, packages)
        :param id: resource identifier
        :return: A valid resource (Package, descriptor)
        """
        # mode = "pull"
        # url = "http://sp.int3.sonata-nfv.eu:32001"  # Read from config

        if id:
            if resource_type == 'services':
                command = "sudo python pull.py --get_service %s" % id
                print("Calling: ", mcolors.OKGREEN + command + "\n", mcolors.ENDC)
                result = os.popen(command).read()
                print("Response: ", mcolors.OKGREEN + result + "\n", mcolors.ENDC)

            elif resource_type == 'functions':
                command = "sudo python pull.py --get_function %s" % id
                print("Calling: ", mcolors.OKGREEN + command + "\n", mcolors.ENDC)
                result = os.popen(command).read()
                print("Response: ", mcolors.OKGREEN + result + "\n", mcolors.ENDC)

            else:
                command = "sudo python pull.py --get_package %s" % id
                print("Calling: ", mcolors.OKGREEN + command + "\n", mcolors.ENDC)
                result = os.popen(command).read()
                print("Response: ", mcolors.OKGREEN + result + "\n", mcolors.ENDC)


        else:
            if resource_type == 'services':
                command = "sudo python pull.py -S"
                print("Calling: ", mcolors.OKGREEN + command + "\n", mcolors.ENDC)
                result = os.popen(command).read()
                print("Response: ", mcolors.OKGREEN + result + "\n", mcolors.ENDC)


            elif resource_type == 'functions':
                command = "sudo python pull.py -F"
                print("Calling: ", mcolors.OKGREEN + command + "\n", mcolors.ENDC)
                result = os.popen(command).read()
                print("Response: ", mcolors.OKGREEN + result + "\n", mcolors.ENDC)

            else:
                command = "sudo python pull.py -P"
                print("Calling: ", mcolors.OKGREEN + command + "\n", mcolors.ENDC)
                result = os.popen(command).read()
                print("Response: ", mcolors.OKGREEN + result + "\n", mcolors.ENDC)


def main():
    import argparse

    from argparse import ArgumentParser, RawDescriptionHelpFormatter
    print(mcolors.OKGREEN + "Running ACCESS\n", mcolors.ENDC)

    examples = """Example usage:

    access --auth -u tester -p 1234
    access --push samples/sonata-demo.son
    access --list services
    access --pull packages 65b416a6-46c0-4596-a9e9-0a9b04ed34ea
    """

    parser = ArgumentParser(
        description="Authenticates users to submit and request resources from SONATA Service Platform",
        formatter_class=RawDescriptionHelpFormatter,
        epilog=examples)

    parser.add_argument(
        "--auth",
        help="authenticates a user, requires -u username -p password",
        action="store_true")

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
        metavar="PACKAGE_PATH",
        help="submits a son-package to the SP",
        required=False)

    parser.add_argument(
        "--list",
        type=str,
        metavar="RESOURCE_TYPE",
        help="lists resources based on its type (services, functions, packages, file)",
        required=False)

    parser.add_argument(
        "--pull",
        type=str,
        nargs=2,
        metavar=("RESOURCE_TYPE", "ID"),
        help="requests a resource based on its type (services, functions, packages, file)"
             " to the SP by its Identifier",
        required=False)

    parser.add_argument(
        "--debug",
        help="increases logging level to debug",
        required=False,
        action="store_true")

    args = parser.parse_args()

    log_level = "INFO"
    ac = AccessClient(log_level)

    if args.debug:
        log_level = "DEBUG"
        coloredlogs.install(level=log_level)

    if args.auth:
        print("args.auth", args.auth)
        # Ensure that both arguments are given (USERNAME and PASSWORD)
        if all(i is not None for i in [args.u, args.p]):
            usr = args.u
            pwd = args.p
            response = ac.client_login(usr, pwd)
            print("Authentication is successful: %s" % response)
        elif any(i is not None for i in [args.u, args.p]):
            parser.error(mcolors.FAIL + "Both Username and Password are required!" + mcolors.ENDC)
            parser.print_help()
            return
        else:
            parser.error(mcolors.FAIL + "Both Username and Password are required!" + mcolors.ENDC)
            parser.print_help()
            return

    if args.push:
        # TODO: Check token expiration
        package_path = args.push
        print(package_path)
        ac.push_package(package_path)

    if args.list:
        # TODO: Check token expiration
        print("args.list", args.list)
        # Ensure that argument given is a valid type (services, functions, packages)
        if args.list not in ['services', 'functions', 'packages']:
            parser.error(mcolors.FAIL + "Valid resource types are: services, functions, packages" + mcolors.ENDC)
        else:
            ac.pull_resource(args.list)

    if args.pull:
        # TODO: Check token expiration
        print("args.pull", args.pull)

        # Ensure that both arguments are given (RESOURCE_TYPE and ID)
        res_type = args.pull[0]
        identifier = args.pull[1]

        # Ensure that argument given is a valid type (services, functions, packages)
        if res_type not in ['services', 'functions', 'packages']:
            parser.error(mcolors.FAIL + "Valid resource types are: services, functions, packages" + mcolors.ENDC)
        else:
            ac.pull_resource(res_type, id=identifier)

    else:
        return


if __name__ == '__main__':
    #TODO: Call 'fake' User Management Auth on mock.py while real User Management module is WIP
    main()









