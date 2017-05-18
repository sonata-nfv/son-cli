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
           list     List available resources (service, functions, packages,...)
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
                        the ID in 'default_service_platform'
  --debug               Set logging level to debug
"""


import logging
import requests
import yaml
import json
import sys
import jwt
import coloredlogs
import os
import time
from os.path import expanduser
from argparse import ArgumentParser
from Crypto.PublicKey import RSA
from Crypto.Hash import SHA256
from son.workspace.workspace import Workspace
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
    ACCESS_VERSION = "0.5"

    DEFAULT_ACCESS_DIR = os.path.join(expanduser("~"), ".son-access")

    # TODO: Connect to the real GateKeeper API URLs or read
    # form configuration file

    GK_API_VERSION = "/api/v2"    # "/api/v1"
    GK_API_BASE = "/"
    # GK_URI_REG = "/register"    # Register is not allowed from the SDK Access
    GK_URI_LOGIN = "/sessions"    # POST
    GK_URI_LOGOUT = "/sessions"   # DELETE
    GK_URI_PB_KEY = "/micro-services/public-key"
    # GK_URI_UPDT_PB_KEY = "/signatures"
    GK_URI_UPDT_PB_KEY = "/users"   # PATCH .../api/v2/users/:username

    def __init__(self, workspace, platform_id=None, log_level='INFO'):
        """
        Header
        The JWT Header declares that the encoded object is a JSON Web Token 
        (JWT) and the JWT is a JWS that is MACed
        using the HMAC SHA-256 algorithm
        """
        self.workspace = workspace
        self.platform_id = platform_id
        self.platform_public_key = self.get_platform_public_key()
        self.access_token = None
        self.username = None
        self.dev_public_key = None
        self.dev_private_key = None
        self.dev_certificate = None
        if self.platform_id:
            self.platform = self.workspace.get_service_platform(platform_id)
        else:
            self.platform_id = self.workspace.default_service_platform
            self.platform = self.workspace.get_service_platform(
                self.platform_id)

        try:
            # retrieve token from workspace
            platform_dir = os.path.join(self.workspace.workspace_root,
                                        self.workspace.platforms_dir)
            token_path = os.path.join(
                platform_dir, self.platform['credentials']['token_file'])

            if os.path.isfile(token_path):
                with open(token_path, 'rb') as token_file:
                    self.access_token = token_file.read()
        except:
            self.access_token = None

        try:
            # retrieve keypair from workspace
            platform_dir = os.path.join(self.workspace.workspace_root,
                                        self.workspace.platforms_dir)
            pub_path = os.path.join(platform_dir,
                                    self.platform['signature']['pub_key'])
            prv_path = os.path.join(platform_dir,
                                    self.platform['signature']['prv_key'])

            if os.path.isfile(pub_path):
                with open(pub_path, 'rb') as pub_key_file:
                    self.dev_public_key = pub_key_file.read()
            if os.path.isfile(prv_path):
                with open(prv_path, 'rb') as prv_key_file:
                    self.dev_private_key = prv_key_file.read()

        except:
            self.dev_public_key = None
            self.dev_private_key = None

        # retrieve certificate from workspace
        try:
            platform_dir = os.path.join(self.workspace.workspace_root,
                                        self.workspace.platforms_dir)
            cert_path = os.path.join(platform_dir,
                                     self.platform['signature']['cert'])
            if os.path.isfile(cert_path):
                with open(cert_path, 'rb') as cert_key_file:
                    self.dev_certificate = cert_key_file.read()

        except:
            self.dev_certificate = None

        try:
            # retrieve token from workspace
            self.platform_dir = os.path.join(self.workspace.workspace_root,
                                             self.workspace.platforms_dir)
        except:
            self.platform_dir = os.path.join(self.workspace.workspace_root)

        # Create a push and pull client for available Service Platforms
        self.pull = dict()
        self.push = dict()
        for p_id, platform in self.workspace.service_platforms.items():
            self.pull[p_id] = Pull(platform['url'])
            self.push[p_id] = Push(platform['url'], pb_key=self.dev_public_key,
                                   pr_key=self.dev_private_key,
                                   cert=self.dev_certificate)

        self.log_level = log_level
        coloredlogs.install(level=log_level)

        # TODO: Deprecated
        # try:
        #    # Platform URL is found in self.platform['url']
        #    self.URL = 'http://' + str(GK_ADDRESS) + ':' + str(GK_PORT)
        # except:
        #    print("Platform url is required in config file")

        # Ensure parameters are valid
        # assert validators.url(self.URL), \
        #    "Failed to init access client. Invalid URL: '{}'" \
        #        .format(self.URL)

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
    # def client_register(self, username, password):
    #    """
    #    Request registration form on the Service Platform
    #    :param username: user identifier
    #    :param password: user password
    #    :return: Initial JWT access_token? Or HTTP Code to
    #             confirm registration
    #    """
    #    form_data = {
    #        'username': username,
    #        'password': password
    #    }
    #
    #    url = self.URL + self.GK_API_VERSION + self.GK_URI_REG
    #
    #    response = requests.post(url, data=form_data, verify=False)
    #    print("Registration response: ", mcolors.OKGREEN + response.text + \
    #  "\n", mcolors.ENDC)
    #    # Create userdata file? Check KEYCLOAK register form
    #    return response

    def client_login(self, username=None, password=None):
        """
        Make a POST request with username and password
        :param username: user identifier
        :param password: user password
        :return: JWT Access Token is returned from the GK server
        """

        default_sp = self.workspace.default_service_platform
        # url = self.workspace.get_service_platform(default_sp)['url'] +  \
        # self.GK_API_VERSION + self.GK_URI_PB_KEY
        url = self.workspace.get_service_platform(default_sp)['url'] + \
              self.GK_API_VERSION + self.GK_URI_LOGIN

        if not username:
            username = self.platform['credentials']['username']

        if not password:
            password = self.platform['credentials']['password']

        # Construct the POST login request
        # credentials = (str(username) + ':' + str(password)).encode('utf-8')
        credentials = json.dumps({'username': username, 'password': password})
        # encoded_creds = b64encode(credentials)
        # headers = {'Authorization': 'Basic %s' %
        # (encoded_creds.decode('utf-8'))}

        response = requests.post(url, data=credentials, verify=False)
        # response = requests.post(url, headers=headers, verify=False
        if not response.status_code in (200, 201):
            log.debug('Error {0}'.format(response.status_code))
            return response.text

        log.debug("Access Token received: '{0}'".format(response.text))

        token_file = self.platform['credentials']['token_file']
        if not token_file:
            token_file = 'token.' + str(time.time())
            self.workspace.config_service_platform(self.platform_id,
                                                   token=token_file)
            self.platform['credentials']['token_file'] = token_file

        token_path = os.path.join(
            self.workspace.workspace_root,
            self.workspace.config['platforms_dir'],
            # self.workspace.dirs[Workspace.CONFIG_STR_PLATFORMS_DIR],
            token_file)

        # token = response.text.replace('\n', '')
        token = json.loads(response.text)['token']['access_token']
        # print('token=', token)

        if not os.path.exists(os.path.dirname(token_path)):
            try:
                os.makedirs(os.path.dirname(token_path))
            except OSError as exc:  # Guard against race condition
                raise

        with open(token_path, "w+") as _file:
            _file.write(token)
            self.access_token = token

        return response.text

    def client_logout(self):
        """
        Send request to /logout interface to end user session
        :return: HTTP Code 204
        """
        default_sp = self.workspace.default_service_platform
        url = self.workspace.get_service_platform(default_sp)['url'] + \
            self.GK_API_VERSION + self.GK_URI_LOGOUT

        result = self.check_token_status()
        if not result:
            print("Access session expired, log-in again")
            return

        if self.access_token is None:
            token_file = self.platform['credentials']['token_file']
            token_path = os.path.join(
                self.workspace.workspace_root,
                self.workspace.platforms_dir,
                token_file)

            # Construct the POST logout request
            with open(token_path, "r") as _file:
                self.access_token = _file.read

        # print(self.access_token.decode('utf-8'))
        headers = {'Authorization': 'Bearer %s' %
                                    (self.access_token.decode('utf-8'))}

        response = requests.post(url, headers=headers, verify=False)
        if response.status_code not in (200, 204):
            log.debug('Error {0}'.format(response.status_code))
            return response.text
        log.debug("Successfully logged-out: '{0}'".format(response.text))
        return response.status_code

    # Token validation is done client-side using the Platform Public Key
    def check_token_status(self):
        """
        Simple request to check if session has expired (TBD)
        :return: Token status
        """

        # print('access_token=', self.access_token)
        # print('platform_key=', self.platform_public_key)

        if self.access_token is None:
            try:
                token_file = self.platform['credentials']['token_file']
                token_path = os.path.join(
                    self.workspace.workspace_root,
                    self.workspace.platforms_dir,
                    # self.workspace.dirs[Workspace.CONFIG_STR_PLATFORMS_DIR],
                    token_file)

                # Construct the POST login request
                with open(token_path, "r") as _file:
                    self.access_token = _file.read
            except:
                return True

        if self.platform_public_key is None:
            return True

        try:
            decoded = jwt.decode(self.access_token, self.platform_public_key,
                                 True, algorithms='RS256', audience='adapter')
            # options={'verify_aud': False})
            print('contents', decoded)
            try:
                self.username = decoded['preferred_username']
                return True
            except:
                return True
        except jwt.DecodeError:
            print('Token cannot be decoded because it failed validation')
            return False
        except jwt.ExpiredSignatureError:
            print('Signature has expired')
            return False
        except jwt.InvalidIssuerError:
            return False
        except jwt.InvalidIssuedAtError:
            return False

    def get_platform_public_key(self):
        """
        Simple request to request the Platform Public Key
        :return: Public Key, HTTP code 200
        """
        default_sp = self.workspace.default_service_platform
        url = self.workspace.get_service_platform(default_sp)['url'] + \
              self.GK_API_VERSION + self.GK_URI_PB_KEY

        try:
            response = requests.get(url, verify=False)
            parsed_key = json.loads(response.text)
            parsed_key = parsed_key['items']['public-key']
            # print('parsed_key=', parsed_key)
            platform_public_key = "-----BEGIN PUBLIC KEY-----\n"
            platform_public_key += parsed_key
            platform_public_key += "\n-----END PUBLIC KEY-----\n"
            # print(platform_public_key)
            return RSA.importKey(platform_public_key).exportKey('PEM')

        except:
            # If the platform public key is not available, disable authentication and return None
            log.warning("Service Platform Public Key not found. Authentication is disabled.")
            return None

    def generate_keypair(self, platform_dir):
        """
        Generates User's Private Key and Public Key
        :param platform_dir: Path to the location where keys will be saved
        :returns: Private key, Public Key
        """
        # KeyPair = NamedTuple('KeyPair', [('public', str), ('private', str)])
        algorithm = 'RS256'

        key = RSA.generate(2048)
        public = key.publickey().exportKey('PEM').decode('ascii')
        private = key.exportKey('PEM').decode('ascii')

        # print("public=", public)
        # print("private=", private)

        self.dev_public_key = public
        self.dev_private_key = private

        # Stores the keypair in the workspace configured platform dir
        try:
            simple_public = public.replace('-----BEGIN PUBLIC KEY-----', '')
            simple_public = simple_public.replace('-----END PUBLIC KEY-----',
                                                  '')

            # print("simple_public=", simple_public)

            default_sp = self.workspace.default_service_platform

            url = self.workspace.get_service_platform(default_sp)['url'] + \
                  self.GK_API_VERSION + self.GK_URI_UPDT_PB_KEY + '/' + \
                  self.username   # TODO: Connect to the real GK API url

            print("url=", url)

            headers = {'Content-type': 'application/json',
                      'Authorization': 'Bearer %s' %
                                       (self.access_token.decode('utf-8'))}

            body = json.dumps({'public_key': simple_public})

            print("url=", url)
            print("body=", body)

            r = requests.patch(url, headers=headers, data=body)
            # r = requests.put(url, headers=headers, data=body)

            print("r.status_code=", r.status_code)

            if int(r.status_code) != 200:
                log.error("Updating User's Public Key in remote "
                          "Platform failed!")
                return False

            try:
                pb_key_path = os.path.join(
                    platform_dir, self.platform['signature']['pub_key'])
                prv_key_path = os.path.join(
                    platform_dir, self.platform['signature']['prv_key'])
                # print("pb_key_path=", pb_key_path)
                # print("prv_key_path=", prv_key_path)
            except:
                log.error("Error: User's Public and Private keys are not "
                          "configured in the workspace!")
                return False

            with open(pb_key_path, mode="w+") as pb_file:
                pb_file.write(self.dev_public_key)
            with open(prv_key_path, mode="w+") as pr_file:
                pr_file.write(self.dev_private_key)

            log.info("User's Public and Private keys generated and saved "
                     "successfully")
            return True

        except:
            log.error("Error generating new keypair for the user")
            return False

    def push_package(self, path, sign=False):
        """
        Call push feature to upload a package to the SP Catalogue
        :param path: location of the package to submit
        :param sign: setting to state if the package is going to be signed
        :return: HTTP code 201 or 40X
        """

        print("Pushing package")
        print("SIGN =", sign)

        # TODO: Implement token expiry evaluation
        result = self.check_token_status()
        if not result:
            print("Access session expired, log-in again")
            return

        elif sign:
            if self.platform_public_key is None:
                log.error("Error: Authentication is disabled. "
                          "It is not possible to sign.")
                return

            if not (self.dev_public_key and self.dev_private_key):
                #  Generates keypair for the developer
                result = self.generate_keypair(self.platform_dir)
                if not result:
                    return
            # IN PROGRESS: CALL SIGN METHOD
            # Push son-package to the Service Platform
            sign = self.sign_package(path)
            print(self.default_push.upload_package
                  (self.access_token, path, sign))

        else:
            # Push son-package to the Service Platform
            print(self.default_push.upload_package(self.access_token, path))

    def sign_package(self, path, private_key=None):
        """
        Sign package feature using SHA256 hash and RSA keypair
        :param path: location of the package to submit
        :param private_key: optional private_key used in signature 
                           (default None)
        :return: string containing an int representation of the 
                 package's signature
        """
        if private_key:
            # Private key used to test
            private_key_obj = RSA.importKey(private_key)
        else:
            private_key_obj = RSA.importKey(self.dev_private_key)
        try:
            with open(path, 'rb') as fhandle:
                package_content = fhandle.read()
        except IOError as err:
            print("I/O error: {0}".format(err))
        # File read as binary, it's not necessary to encode 'utf-8' to hash
        package_hash = SHA256.new(package_content).digest()
        # Signature is a tuple containing an integer as first entry
        signature = private_key_obj.sign(package_hash, '')
        return str(signature[0])

    def deploy_service(self, service_id):
        """
        Call push feature to request a service instantiation to the 
        SP Catalogue
        :param service_id: unique identifier of the service to be instanced
        :return: HTTP code 20X or 40X
        """
        print(self.default_push.instantiate_service(service_id))

    def pull_resource(self, resource_type, identifier=None, uuid=False,
                      platform_id=None):
        """
        Call pull feature to request a resource from the SP Catalogue
        :param resource_type: a valid resource classifier 
                              (services, functions, packages)
        :param identifier: resource identifier which can be of two types:
        name.trio id ('vendor=%s&name=%s&version=%s') or uuid (xxx-xxxx-xxxx..)
        :param uuid: boolean that indicates the identifier 
                     is 'uuid-type' if True
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

        # TODO: Implement token expiry evaluation
        result = self.check_token_status()
        if not result:
            print("Access session expired, log-in again")
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
            self.workspace.workspace_root,
            self.workspace.ns_catalogue_dir,
            str(time.time())
        )
        self.write_descriptor(store_path, nsd)

    def store_vnfd(self, vnfd):
        store_path = os.path.join(
            self.workspace.workspace_root,
            self.workspace.vnf_catalogue_dir,
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
           list     List available resources (service, functions, packages,...)
           push     Submit a son-package or request a service instantiation
           pull     Request resources (services, functions, packages, ...)
           config   Configure access parameters
        """
        examples = """Example usage:
            access auth -u tester -p 1234
            access auth --logout
            access push --upload samples/sonata-demo.son
            access push --upload samples/sonata-demo.son --sign
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
                 "in 'default_service_platform'",
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

        self.subarg_idx = command_idx + 1
        args = parser.parse_args(sys.argv[1: self.subarg_idx])

        # handle workspace
        if args.workspace:
            workspace_root = args.workspace
        else:
            workspace_root = Workspace.DEFAULT_WORKSPACE_DIR
        self.workspace = Workspace.__create_from_descriptor__(workspace_root)
        if not self.workspace:
            print("Invalid workspace: ", workspace_root)
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
        parser.add_argument(
            "--logout",
            help="Logout the access token",
            action='store_true',
            required=False
        )
        args = parser.parse_args(sys.argv[self.subarg_idx:])

        if args.logout:
            rsp = self.ac.client_logout()
            print("Authentication response: %s" % rsp)
        else:
            rsp = self.ac.client_login(username=args.username,
                                       password=args.password)
            print("Authentication response: %s" % rsp)

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

        mutex_parser = parser.add_mutually_exclusive_group(
            required=False
        )
        # Optional argument to set package signing on
        mutex_parser.add_argument(
            "--sign",
            help="Sign the package option to submit a signed package",
            dest="sign",
            action='store_true',
            required=False
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
            if args.sign:
                package_path = args.upload
                print(package_path)
                self.ac.push_package(package_path, sign=True)
            else:
                package_path = args.upload
                print(package_path)
                self.ac.push_package(package_path, sign=False)

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
        # parser.add_argument(
        #    "--token",
        #    help="Configure token filename",
        #    type=str,
        #    required=False,
        #    metavar="TOKEN_FILE"
        # )
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
                      "specified: (--url | --username | --password "
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
                                               # token=args.token,
                                               default=args.default)

        log.info("Service Platform ID='{0}':\n{1}"
                 .format(args.platform_id,
                         self.workspace.get_service_platform(args.platform_id)))


def main():
    AccessArgParse()


if __name__ == '__main__':
    # TODO: Call 'fake' User Management Auth on mock.py while real User Management module is WIP
    main()
