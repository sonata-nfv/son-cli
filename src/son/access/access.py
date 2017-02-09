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
usage: son-access [optional] command [<args>]
        The supported commands are:
           auth     Authenticate a user
           list     List available resources (service, functions, packages, ...)
           push     Submit a son-package or request a service instantiation
           pull     Request resources (services, functions, packages, ...)
           config   Configure access parameters


Authenticates users to submit and request resources from SONATA Service
Platform

positional arguments:
  command               Command to run

optional arguments:
  -h, --help            show this help message and exit
  -w WORKSPACE_PATH, --workspace WORKSPACE_PATH
                        Specify workspace to work on. If not specified will
                        assume '/root/.son-workspace'
  -p PLATFORM_ID, --platform PLATFORM_ID
                        Specify the ID of the Service Platform to use from
                        workspace configuration. If not specified will assume
                        the IDin 'default_service_platform'
  --debug               Set logging level to debug
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
import time
from son.access.helpers.helpers import json_response
from son.access.models.models import User
from son.access.config.config import GK_ADDRESS, GK_PORT
from argparse import ArgumentParser, RawDescriptionHelpFormatter
from son.access.pull import Pull
from son.access.push import Push

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

    def __init__(self, workspace, platform_id=None, log_level='INFO'):
        """
        Header
        The JWT Header declares that the encoded object is a JSON Web Token (JWT) and the JWT is a JWS that is MACed
        using the HMAC SHA-256 algorithm
        """
        self.workspace = workspace
        self.platform_id = platform_id
        if self.platform_id:
            self.platform = self.workspace.get_service_platform(platform_id)
        else:
            self.platform_id = self.workspace.default_service_platform
            self.platform = self.workspace.get_service_platform(
                self.platform_id)

        try:
            # retrieve token from workspace
            platform_dir = os.path.join(self.workspace.ws_root,
                                        self.workspace.dirs[
                                            workspace.CONFIG_STR_PLATFORMS_DIR])
            token_path = os.path.join(platform_dir,
                                      self.platform['credentials']['token_file'])

            access_token = None
            if os.path.isfile(token_path):
                with open(token_path, 'rb') as token_file:
                    access_token = token_file.read()
                    access_token = access_token[1:-1]
        except:
            access_token = None

        # Create a push and pull client for available Service Platforms
        self.pull = dict()
        self.push = dict()
        for p_id, platform in self.workspace.service_platforms.items():
            self.pull[p_id] = Pull(platform['url'], auth_token=access_token)
            self.push[p_id] = Push(platform['url'], auth_token=access_token)

        self.log_level = log_level
        coloredlogs.install(level=log_level)
        self.JWT_SECRET = 'secret'
        self.JWT_ALGORITHM = 'HS256'
        self.JWT_EXP_DELTA_SECONDS = 20

        # TODO: Deprecated?
        try:
            self.URL = 'http://' + str(GK_ADDRESS) + ':' + str(GK_PORT)
        except:
            print("Platform url is required in config file")

        # Ensure parameters are valid
        assert validators.url(self.URL),\
            "Failed to init access client. Invalid URL: '{}'"\
            .format(self.URL)

    @property
    def default_push(self):
        """
        Push client for default service platform
        :return: Push object
        """
        return self.push[self.platform_id]

    @property
    def default_pull(self):
        """
        Pull client for default service platform
        :return: Pull object
        """
        return self.pull[self.platform_id] \
            if self.platform_id else None

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

    def client_login(self, username=None, password=None):
        """
        Make a POST request with username and password
        :param username: user identifier
        :param password: user password
        :return: JW Access Token is returned from the GK server
        """

        url = self.platform['url'] + self.GK_API_VERSION + self.GK_URI_LOG

        if not username:
            username = self.platform['credentials']['username']

        if not password:
            password = self.platform['credentials']['password']

        # Construct the POST request
        form_data = {
            'username': username,
            'password': password
        }

        response = requests.post(url, data=form_data, verify=False)
        log.debug("Access Token received: '{0}'".format(response.text))

        token_file = self.platform['credentials']['token_file']
        if not token_file:
            token_file = 'token.' + str(time.time())
            self.workspace.config_service_platform(self.platform_id,
                                                   token=token_file)
        token_path = os.path.join(
            self.workspace.ws_root,
            self.workspace.dirs[Workspace.CONFIG_STR_PLATFORMS_DIR],
            token_file)

        token = response.text.replace('\n', '')
        with open(token_path, "wb") as _file:
            _file.write(token)

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
        print(self.default_push.upload_package(path))

    def deploy_service(self, service_id):
        """
        Call push feature to request a service instantiation to the SP Catalogue
        :return: HTTP code 20X or 40X
        """
        print(self.default_push.instantiate_service(service_id))

    def pull_resource(self, resource_type, identifier=None, uuid=False,
                      platform_id=None):
        """
        Call pull feature to request a resource from the SP Catalogue
        :param resource_type: a valid resource classifier (services, functions, packages)
        :param identifier: resource identifier which can be of two types:
        name.trio id ('vendor=%s&name=%s&version=%s') or uuid (xxx-xxxx-xxxx...)
        :param uuid: boolean that indicates the identifier is 'uuid-type' if True
        :param platform_id: specify from which Service Platform should the
        resource be pulled. If not specified, the default will be used.
        :return: A valid resource (Package, descriptor)
        """
        # mode = "pull"
        # url = "http://sp.int3.sonata-nfv.eu:32001"  # Read from config

        # assign pull client
        pull = self.default_pull if not platform_id else self.pull[platform_id]
        if not pull:
            log.error("Service Platform not defined. Aborting")
            return

        # resources by id
        if identifier and uuid is False:
            if resource_type == 'services':
                log.debug("Retrieving service id='{}'".format(identifier))
                nsd = pull.get_ns_by_id(identifier)
                self.store_nsd(nsd)
                print(nsd)

            elif resource_type == 'functions':
                log.debug("Retrieving function id='{}'".format(identifier))
                vnfd = pull.get_vnf_by_id(identifier)
                self.store_vnfd(vnfd)
                print(vnfd)

            elif resource_type == 'packages':
                log.debug("Retrieving package id='{}'".format(identifier))
                print(pull.get_package_by_id(identifier))

        # resources by uuid
        elif identifier and uuid is True:
            if resource_type == 'services':
                log.debug("Retrieving service uuid='{}'".format(identifier))
                nsd = pull.get_ns_by_uuid(identifier)
                self.store_nsd(nsd)
                print(nsd)

            elif resource_type == 'functions':
                log.debug("Retrieving function uuid='{}'".format(identifier))
                vnfd = pull.get_vnf_by_uuid(identifier)
                self.store_vnfd(vnfd)
                print(vnfd)

            elif resource_type == 'packages':
                log.debug("Retrieving package uuid='{}'".format(identifier))
                print(pull.get_package_by_uuid(identifier))

        # resources list
        else:
            if resource_type == 'services':
                log.info("Listing all services from '{}'"
                         .format(self.platform['url']))
                print(pull.get_all_nss())

            elif resource_type == 'functions':
                log.info("Listing all functions from '{}'"
                         .format(self.platform['url']))
                print(pull.get_all_vnfs())

            elif resource_type == 'packages':
                log.info("Listing all packages from '{}'"
                         .format(self.platform['url']))
                print(pull.get_all_packages())

    def store_nsd(self, nsd):
        store_path = os.path.join(
            self.workspace.ws_root,
            self.workspace.dirs[self.workspace.CONFIG_STR_CATALOGUE_NS_DIR],
            str(time.time())
        )
        self.write_descriptor(store_path, nsd)

    def store_vnfd(self, vnfd):
        store_path = os.path.join(
            self.workspace.ws_root,
            self.workspace.dirs[self.workspace.CONFIG_STR_CATALOGUE_VNF_DIR],
            str(time.time())
        )
        self.write_descriptor(store_path, vnfd)

    @staticmethod
    def write_descriptor(filename, descriptor):
        with open(filename, "w") as _file:
            _file.write(yaml.dump(descriptor, default_flow_style=False))


class AccessArgParse(object):

    def __init__(self):
        usage = """son-access [optional] command [<args>]
        The supported commands are:
           auth     Authenticate a user
           list     List available resources (service, functions, packages, ...)
           push     Submit a son-package or request a service instantiation
           pull     Request resources (services, functions, packages, ...)
           config   Configure access parameters
        """
        examples = """Example usage:
            access auth -u tester -p 1234
            access push --upload samples/sonata-demo.son
            access list services
            access pull packages --uuid 65b416a6-46c0-4596-a9e9-0a9b04ed34ea
            access pull services --id sonata.eu firewall-vnf 1.0
            access -p sp1 push --deploy 65b416a6-46c0-4596-a9e9-0a9b04ed34ea
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
            help="Specify workspace to work on. If not specified will "
                 "assume '{}'".format(Workspace.DEFAULT_WORKSPACE_DIR),
            required=False
        )
        parser.add_argument(
            "-p", "--platform",
            type=str,
            metavar="PLATFORM_ID",
            help="Specify the ID of the Service Platform to use from "
                 "workspace configuration. If not specified will assume the ID"
                 "in '{}'".format(Workspace.CONFIG_STR_DEF_SERVICE_PLATFORM),
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
            if (v == "-w" or v == "--workspace" or
               v == '-p' or v == "--platform"):
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

        self.ac = AccessClient(self.workspace, platform_id=args.platform,
                               log_level=log_level)

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
            required=False
        )
        parser.add_argument(
            "-p", "--password",
            type=str,
            metavar="PASSWORD",
            dest="password",
            help="Specify password of the user",
            required=False
        )
        args = parser.parse_args(sys.argv[self.subarg_idx:])

        rsp = self.ac.client_login(username=args.username,
                                   password=args.password)
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
            "--upload",
            type=str,
            help="Specify package path to submit",
            required=False,
            metavar="PACKAGE_PATH"
        )
        parser.add_argument(
            "--deploy",
            type=str,
            help="Specify service identifier to instantiate",
            required=False,
            metavar="SERVICE_ID"
        )
        args = parser.parse_args(sys.argv[self.subarg_idx:])

        if not (args.upload or args.deploy):
            log.error("At least one of the following arguments must be "
                      "specified: (--upload | --deploy)")
            exit(1)

        if args.upload:
            # TODO: Check token expiration
            package_path = args.upload
            print(package_path)
            self.ac.push_package(package_path)

        elif args.deploy:
            service_uuid = args.deploy
            print(service_uuid)
            self.ac.deploy_service(service_uuid)

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

    def config(self):
        parser = ArgumentParser(
            prog="son-access [..] config",
            description="Configure access parameters",
        )
        mutex_parser = parser.add_mutually_exclusive_group(
            required=True,
        )
        mutex_parser.add_argument(
            "--platform_id",
            help="Specify the Service Platform ID to configure",
            type=str,
            required=False,
            metavar="SP_ID"
        )
        mutex_parser.add_argument(
            "--list",
            help="List all Service Platform configuration entries",
            required=False,
            action="store_true"
        )
        parser.add_argument(
            "--new",
            help="Create a new access entry to a Service Platform",
            action="store_true",
            required=False
        )
        parser.add_argument(
            "--url",
            help="Configure URL of Service Platform",
            type=str,
            required=False,
            metavar="URL"
        )
        parser.add_argument(
            "-u", "--username",
            help="Configure username",
            type=str,
            required=False,
            metavar="USERNAME"
        )
        parser.add_argument(
            "-p", "--password",
            help="Configure password",
            type=str,
            required=False,
            metavar="PASSWORD"
        )
        parser.add_argument(
            "--token",
            help="Configure token filename",
            type=str,
            required=False,
            metavar="TOKEN_FILE"
        )
        parser.add_argument(
            "--default",
            help="Set Service Platform as default",
            required=False,
            action="store_true",
        )

        args = parser.parse_args(sys.argv[self.subarg_idx:])

        # list configuration
        if args.list:
            entries = ''
            for sp_id, sp in self.workspace.service_platforms.items():
                entries += "[%s]: %s\n" % (sp_id, sp)

            log.info("Service Platform entries (default='{0}'):\n{1}"
                     .format(self.workspace.default_service_platform,
                             entries))
            exit(0)

        if not (args.url or args.username or args.password or args.token or
                args.default):
            log.error("At least one of the following arguments must be "
                      "specified: (--url | --username | --password | --token "
                      "| --default)")
            exit(1)

        # new SP entry in workspace configuration
        if args.new:
            if self.workspace.get_service_platform(args.platform_id):
                log.error("Couldn't add entry. Service Platform ID='{}' "
                          "already exists.".format(args.platform_id))
                exit(1)
            self.workspace.add_service_platform(args.platform_id)

        # already existent entry
        else:
            if not self.workspace.get_service_platform(args.platform_id):
                log.error("Couldn't modify entry. Service Platform ID='{}' "
                          "doesn't exist.".format(args.platform_id))
                exit(1)

        # modify entry
        self.workspace.config_service_platform(args.platform_id,
                                               url=args.url,
                                               username=args.username,
                                               password=args.password,
                                               token=args.token,
                                               default=args.default)

        log.info("Service Platform ID='{0}':\n{1}"
                 .format(args.platform_id,
                         self.workspace.get_service_platform(args.platform_id)))


def main():
    AccessArgParse()

if __name__ == '__main__':
    #TODO: Call 'fake' User Management Auth on mock.py while real User Management module is WIP
    main()
