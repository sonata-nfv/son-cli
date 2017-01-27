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
usage: son-access [-h] [--auth] [-u USERNAME] [-p PASSWORD]
                  [--workspace WORKSPACE_PATH] [--push PACKAGE_PATH]
                  [--list RESOURCE_TYPE] [--pull RESOURCE_TYPE] [--uuid UUID]
                  [--id VENDOR NAME VERSION] [--debug]

Authenticates users to submit and request resources from SONATA Service Platform

optional arguments:
  -h, --help            show this help message and exit
  --auth                authenticates a user, requires -u username -p password
  -u USERNAME           specifies username of a user
  -p PASSWORD           specifies password of a user
  --workspace WORKSPACE_PATH
                        specifies workspace to work on. If not specified will
                        assume '/root/.son-workspace'
  --push PACKAGE_PATH   submits a son-package to the SP
  --list RESOURCE_TYPE  lists resources based on its type (services,
                        functions, packages, file)
  --pull RESOURCE_TYPE  requests a resource based on its type (services,
                        functions, packages, file), requires a query parameter
                        --uuid or --id
  --uuid UUID           Query value for SP identifiers (uuid-generated)
  --id VENDOR NAME VERSION
                        Query values for package identifiers (vendor name
                        version)
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
from son.workspace.workspace import Workspace
from son.access.helpers.helpers import json_response
from son.access.models.models import User
from son.access.config.config import GK_ADDRESS, GK_PORT
from argparse import ArgumentParser, RawDescriptionHelpFormatter

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
    ACCESS_VERSION = "0.3"

    DEFAULT_ACCESS_DIR = os.path.join(expanduser("~"), ".son-access")

    GK_API_VERSION = "/api/v2"
    GK_API_BASE = "/"
    GK_URI_REG = "/register"
    GK_URI_LOG = "/login"
    GK_URI_AUT = "TBD"
    GK_URI_REF = "/refresh"
    GK_URI_TKV = "TBD"

    def __init__(self, workspace, log_level='INFO'):
        """
        Header
        The JWT Header declares that the encoded object is a JSON Web Token (JWT) and the JWT is a JWS that is MACed
        using the HMAC SHA-256 algorithm
        """
        self.workspace = workspace
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

    # DEPRECATED -> Users will only be able to register through SON-GUI
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
        print("Registration response: ", mcolors.OKGREEN + response.text + "\n", mcolors.ENDC)
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

    def pull_resource(self, resource_type, identifier=None, uuid=False):
        """
        Call pull feature to request a resource from the SP Catalogue
        :param resource_type: a valid resource classifier (services, functions, packages)
        :param identifier: resource identifier which can be of two types:
        name.trio id ('vendor=%s&name=%s&version=%s') or uuid (xxx-xxxx-xxxx...)
        :param uuid: boolean that indicates the identifier is 'uuid-type' if True
        :return: A valid resource (Package, descriptor)
        """
        # mode = "pull"
        # url = "http://sp.int3.sonata-nfv.eu:32001"  # Read from config

        if identifier and uuid is False:
            if resource_type == 'services':
                command = "sudo python pull.py --get_service %s" % identifier
                print("Calling: ", mcolors.OKGREEN + command + "\n", mcolors.ENDC)
                result = os.popen(command).read()
                print("Response: ", mcolors.OKGREEN + result + "\n", mcolors.ENDC)

            elif resource_type == 'functions':
                command = "sudo python pull.py --get_function %s" % identifier
                print("Calling: ", mcolors.OKGREEN + command + "\n", mcolors.ENDC)
                result = os.popen(command).read()
                print("Response: ", mcolors.OKGREEN + result + "\n", mcolors.ENDC)

            else:
                command = "sudo python pull.py --get_package %s" % identifier
                print("Calling: ", mcolors.OKGREEN + command + "\n", mcolors.ENDC)
                result = os.popen(command).read()
                print("Response: ", mcolors.OKGREEN + result + "\n", mcolors.ENDC)

        elif identifier and uuid is True:
            if resource_type == 'services':
                command = "sudo python pull.py --get_service_uuid %s" % identifier
                print("Calling: ", mcolors.OKGREEN + command + "\n", mcolors.ENDC)
                result = os.popen(command).read()
                print("Response: ", mcolors.OKGREEN + result + "\n", mcolors.ENDC)

            elif resource_type == 'functions':
                command = "sudo python pull.py --get_function_uuid %s" % identifier
                print("Calling: ", mcolors.OKGREEN + command + "\n", mcolors.ENDC)
                result = os.popen(command).read()
                print("Response: ", mcolors.OKGREEN + result + "\n", mcolors.ENDC)

            else:
                command = "sudo python pull.py --get_package_uuid %s" % identifier
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


class AccessArgParse(object):

    def __init__(self):
        usage = """son-access [optional] command [<args>]
        The supported commands are:
           auth     Authenticate a user
           list     List available resources (service, functions, packages, ...)
           push     Submit a son-package
           pull     Request resources (services, functions, packages, ...)
        """
        examples = """Example usage:
            access auth -u tester -p 1234
            access push samples/sonata-demo.son
            access list services
            access pull packages --uuid 65b416a6-46c0-4596-a9e9-0a9b04ed34ea
            access pull services --id sonata.eu firewall-vnf 1.0
            """
        parser = ArgumentParser(
            description="Authenticates users to submit and request resources "
                        "from SONATA Service Platform",
            usage=usage,
        )
        parser.add_argument(
            "-w", "--workspace",
            type=str,
            metavar="WORKSPACE_PATH",
            help="specifies workspace to work on. If not specified will "
                 "assume '{}'".format(Workspace.DEFAULT_WORKSPACE_DIR),
            required=False
        )
        parser.add_argument(
            "--debug",
            help="Set logging level to debug",
            required=False,
            action="store_true"
        )

        parser.add_argument(
            "command",
            help="Command to run"
        )

        # align command index
        command_idx = 1
        for idx in range(1, len(sys.argv)):
            v = sys.argv[idx]
            if v == "-w" or v == "--workspace":
                command_idx += 2
            elif v == '--debug':
                command_idx += 1

        self.subarg_idx = command_idx+1
        args = parser.parse_args(sys.argv[1: self.subarg_idx])

        # handle workspace
        if args.workspace:
            ws_root = args.workspace
        else:
            ws_root = Workspace.DEFAULT_WORKSPACE_DIR
        self.workspace = Workspace.__create_from_descriptor__(ws_root)
        if not self.workspace:
            print("Invalid workspace: ", ws_root)
            return

        # handle debug
        log_level = 'info'
        if args.debug:
            log_level = 'debug'
            coloredlogs.install(level=log_level)

        if not hasattr(self, args.command):
            print("Invalid command: ", args.command)
            exit(1)

        self.ac = AccessClient(self.workspace, log_level=log_level)

        # call sub-command
        getattr(self, args.command)()

    def auth(self):
        parser = ArgumentParser(
            prog="son-access [..] auth",
            description="Authenticate a user"
        )
        parser.add_argument(
            "-u", "--username",
            type=str,
            metavar="USERNAME",
            dest="username",
            help="Specify username of the user",
            required=True
        )
        parser.add_argument(
            "-p", "--password",
            type=str,
            metavar="PASSWORD",
            dest="password",
            help="Specify password of the user",
            required=True
        )
        args = parser.parse_args(sys.argv[self.subarg_idx:])

        rsp = self.ac.client_login(args.username, args.password)
        print("Authentication is successful: %s" % rsp)

    def list(self):
        parser = ArgumentParser(
            prog="son-access [..] list",
            description="List available resources (services, functions, "
                        "packages, ...)"
        )
        parser.add_argument(
            "resource_type",
            help="(services | functions | packages)"
        )

        args = parser.parse_args(sys.argv[self.subarg_idx:])

        if args.resource_type not in ['services', 'functions', 'packages']:
            log.error("Invalid resource type: ", args.resource_type)
            exit(1)

        self.ac.pull_resource(args.resource_type)

    def push(self):
        parser = ArgumentParser(
            prog="son-access [..] push",
            description="Submit a son-package to the SP"
        )
        parser.add_argument(
            "package",
            type=str,
            help="Specify package to submit"
        )
        args = parser.parse_args(sys.argv[self.subarg_idx:])

        # TODO: Check token expiration
        package_path = args.package
        print(package_path)
        self.ac.push_package(package_path)

    def pull(self):
        parser = ArgumentParser(
            prog="son-access [..] pull",
            description="Request resources (services, functions, packages, "
                        "...)",
        )
        parser.add_argument(
            "resource_type",
            help="(services | functions | packages)"
        )

        mutex_parser = parser.add_mutually_exclusive_group(
            required=True
        )
        mutex_parser.add_argument(
            "--uuid",
            type=str,
            metavar="UUID",
            dest="uuid",
            help="Query value for SP identifiers (uuid-generated)",
            required=False)

        mutex_parser.add_argument(
            "--id",
            type=str,
            nargs=3,
            metavar=("VENDOR", "NAME", "VERSION"),
            help="Query values for package identifiers (vendor name version)",
            required=False)

        args = parser.parse_args(sys.argv[self.subarg_idx:])

        if args.resource_type not in ['services', 'functions', 'packages']:
            log.error("Invalid resource type: ", args.resource_type)
            exit(1)

        if args.uuid:
            self.ac.pull_resource(args.resource_type,
                                  identifier=args.uuid,
                                  uuid=True)
        elif args.id:
            resource_query = 'vendor=%s&name=%s&version=%s' % \
                             (args.id[0], args.id[1], args.id[2])
            self.ac.pull_resource(args.resource_type,
                                  identifier=resource_query,
                                  uuid=False)


def main():
    AccessArgParse()

if __name__ == '__main__':
    #TODO: Call 'fake' User Management Auth on mock.py while real User Management module is WIP
    main()









