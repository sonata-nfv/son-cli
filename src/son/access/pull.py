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
# Neither the name of the SONATA-NFV, UBIWHERE, i2CAT,
# nor the names of its contributors may be used to endorse or promote
# products derived from this software without specific prior written
# permission.
#
# This work has been performed in the framework of the SONATA project,
# funded by the European Commission under Grant number 671517 through
# the Horizon 2020 and 5G-PPP programmes. The authors would like to
# acknowledge the contributions of their colleagues of the SONATA
# partner consortium (www.sonata-nfv.eu).

import logging
import requests
import yaml
import sys
import validators
from son.workspace.workspace import Workspace
from son.access.config.config import GK_ADDRESS, GK_PORT
from json import loads

log = logging.getLogger(__name__)

class mcolors:
     OKGREEN = '\033[92m'
     FAIL = '\033[91m'
     ENDC = '\033[0m'

     def disable(self):
         self.OKGREEN = ''
         self.FAIL = ''
         self.ENDC = ''


class Pull(object):
    """
    Early implementation of the retrieving tool. It will be a
    extension/modification of CatalogueClient from SDK Catalogue
    API.Modified CatalogueClient class to communicate to SP Catalogue
    component through son-gtkapi on SP Gatekeeper (only descriptors).

    This tool is responsible of GETting descriptors.

    This tool connects to a REST api of the SONATA Service
    Platform Gatekeeper. As these API's are still under
    construction, functionality as well as implementation
    of this module probably change continuously.
    """

    # Gatekeeper API URLs configuration
    GK_API_VERSION = "/api/v2"
    CAT_URI_BASE = "/"
    CAT_URI_NS = "/services?"             # List all NS
    CAT_URI_NS_ID = "/services/"      # Get a specific NS by ID
    CAT_URI_NS_NAME = "/services?name="  # Get NS list by name
    CAT_URI_VNF = "/functions?"           # List all VNFs
    CAT_URI_VNF_ID = "/functions/"    # Get a specific VNF by id
    CAT_URI_VNF_NAME = "/functions?name="   # GET VNF list by name
    CAT_URI_PD = "/packages?"             # List all Packages
    CAT_URI_PD_ID = "/packages/"      # Get a specific Package by ID
    CAT_URI_PD_NAME = "/packages?name="  # Get Package list by name
    CAT_URI_SONP_ID = "/packages/"  # Get a specific SON-Package by ID

    def __init__(self, base_url, auth_token=None):
        # Assign parameters
        self._base_url = base_url
        self._headers = {'Content-Type': 'application/json'}
        if auth_token:
            self._headers["Authorization"] = "Bearer %s" % auth_token
        # {'Content-Type': 'application/x-yaml'}

        # Ensure parameters are valid
        assert validators.url(self._base_url),\
            "Failed to init catalogue client. Invalid URL: '{}'"\
            .format(self._base_url)

    @property
    def base_url(self):
        return self._base_url

    def alive(self):
        """
        Checks if the GK API server is alive and
        responding to requests
        :return: True=server OK,
                 False=server unavailable
        """
        url = self._base_url + self.CAT_URI_BASE
        try:
            response = requests.get(url,
                                    headers=self._headers)

        except requests.exceptions.InvalidURL:
            log.warning("Invalid URL: '{}'. Please specify "
                        "a valid address to a Gatekeeper server".format(url))
            return False

        except requests.exceptions.ConnectionError:
            log.warning("Connection Error while contacting '{}'. "
                        "Error message: '{}'".format(url, sys.exc_info()))
            return False

        except:
            log.warning("Unexpected Error connecting to '{}'. "
                        "Error message: '{}'".format(url, sys.exc_info()[0]))
            raise

        return response.status_code == requests.codes.ok

    def __get_cat_object__(self, cat_uri, obj_query, extra_uri=None):
        """
        Generic GET function to request a SONATA SP resource.
        :param cat_uri: catalogue to be queried
        :param obj_query: identifier of the resource
        :param extra_uri: additional path to catalogue endpoint
        :return: response of the SP
        """
        if extra_uri is None:
            url = self._base_url + self.GK_API_VERSION + cat_uri + obj_query
            response = requests.get(url, headers=self._headers)
            if not response.status_code == requests.codes.ok:
                return
            return response.text
        else:
            url = self._base_url + self.GK_API_VERSION + cat_uri + obj_query + extra_uri

            response = requests.get(url, headers=self._headers)
            if not response.status_code == requests.codes.ok:
                return
            return response.content

    def _get_from_url(self, url):
        """
        Generic/internal function to fetch content of a given URL

        :param url: url of the website to be queried
        :returns: text response of the server
        """
        if not validators.url(url):
            raise Exception(url+" is not a valid url.")

        try:
            r = requests.get(url)
            return r.text
        except:
            raise Exception("Content cannot be downloaded from "+url)

    def get_all_nss(self):
        return self.__get_cat_object__(self.CAT_URI_NS, "")

    def get_ns_by_uuid(self, ns_uuid):
        """
        Obtains a specific network service (NS)
        :param ns_uuid: UUID of NS in the form 'uuid-generated'
        :return: yaml object containing NS
        """
        cat_obj = self.__get_cat_object__(self.CAT_URI_NS_ID, ns_uuid)
        if cat_obj is None:
            log.error("Network service with UUID "
                      "\"{}\" is not found".format(ns_uuid))
            return
        if not isinstance(cat_obj, str) and len(cat_obj) > 1:
            log.error("Obtained multiple network "
                      "services using the ID '{}'".format(ns_uuid))
            return

        log.debug("Obtained NS schema:\n{}".format(cat_obj))

        nsd = yaml.load(cat_obj)

        return nsd

    def get_ns_by_id(self, ns_id):
        """
        Obtains a specific network service (NS)
        :param ns_id: ID of NS in the form 'vendor.ns_name.version'
        :return: yaml object containing NS
        """
        cat_obj = self.__get_cat_object__(self.CAT_URI_NS, ns_id)
        if not isinstance(cat_obj, str) and len(cat_obj) > 1:
            log.error("Obtained multiple network "
                      "services using the ID '{}'".format(ns_id))
            return

        log.debug("Obtained NS schema:\n{}".format(cat_obj))

        nsd = yaml.load(cat_obj)
        return nsd

    def get_ns_by_name(self, ns_name):
        """
        Obtains a list of network services matching the ns_name
        :param ns_name: name of network service
        :return: (str) list of network services
        """
        return self.__get_cat_object__(
            self.CAT_URI_NS_NAME, ns_name)

    def get_all_vnfs(self):
        return self.__get_cat_object__(self.CAT_URI_VNF, "")

    def get_vnf_by_uuid(self, vnf_uuid):
        """
        Obtains a specific VNF
        :param vnf_uuid: UUID of VNF in the form 'uuid-generated'
        :return: yaml object containing VNF
        """
        cat_obj = self.__get_cat_object__(
            self.CAT_URI_VNF_ID, vnf_uuid)
        if not cat_obj:
            return

        if not isinstance(cat_obj, str) and len(cat_obj) > 1:
            log.error("Obtained multiple VNFs using ID '{}'".format(vnf_uuid))
            return

        log.debug("Obtained VNF schema:\n{}".format(cat_obj))

        vnfd = yaml.load(cat_obj)

        return vnfd

    def get_vnf_by_id(self, vnf_id):
        """
        Obtains a specific VNF
        :param vnf_id: ID of VNF in the form 'vendor.name.version'
        :return: yaml object containing VNF
        """
        cat_obj = self.__get_cat_object__(
            self.CAT_URI_VNF, vnf_id)
        if not cat_obj:
            return

        if not isinstance(cat_obj, str) and len(cat_obj) > 1:
            log.error("Obtained multiple VNFs using ID '{}'".format(vnf_id))
            return

        log.debug("Obtained VNF schema:\n{}".format(cat_obj))

        vnfd = yaml.load(cat_obj)

        return vnfd

    def get_vnf_by_name(self, vnf_name):
        """
        Obtains a list of VNFs matching the vnf_name
        :param vnf_name: name of network service
        :return: (str) list of VNFs
        """
        return self.__get_cat_object__(
            self.CAT_URI_VNF_NAME, vnf_name)

    def get_all_packages(self):
        return self.__get_cat_object__(self.CAT_URI_PD, "")

    def get_package_by_uuid(self, package_uuid):
        """
        Obtains a specific package (PD)
        :param package_uuid: UUID of PD in the form 'uuid-generated'
        :return: yaml object containing PD
        """
        cat_obj = self.__get_cat_object__(self.CAT_URI_PD_ID, package_uuid)
        if not isinstance(cat_obj, str) and len(cat_obj) > 1:
            log.error("Obtained multiple packages "
                      "using the ID '{}'".format(package_uuid))
            return

        log.debug("Obtained NS schema:\n{}".format(cat_obj))
        return yaml.load(cat_obj)

    def get_package_by_id(self, package_id):
        """
        Obtains a specific package (PD)
        :param package_id: ID of PD in the form 'vendor.name.version'
        :return: yaml object containing PD
        """
        cat_obj = self.__get_cat_object__(self.CAT_URI_PD, package_id)
        if not isinstance(cat_obj, str) and len(cat_obj) > 1:
            log.error("Obtained multiple packages "
                      "using the ID '{}'".format(package_id))
            return

        log.debug("Obtained NS schema:\n{}".format(cat_obj))
        return yaml.load(cat_obj)

    def get_son_package_by_uuid(self, son_package_uuid):
        """
        Obtains a specific package (PD)
        :param son_package_uuid: UUID of SON-PACKAGE in the form 'uuid-generated'
        :return: SON file object containing NSDs, VNFDs, PD
        """
        cat_file = self.__get_cat_object__(self.CAT_URI_SONP_ID, son_package_uuid, '/download')
        return cat_file

    # def get_instances(url):
    #     return _get_from_url(url + "/instantiations")

    def package_list(self):
        return loads(self.get_all_packages()).get("service_uuid_list")

    # def instance_list(self, url):
    #     return loads(get_instances(url)).get("service_instantiations_list")


def main():
    from argparse import ArgumentParser, RawDescriptionHelpFormatter
    print(mcolors.OKGREEN + "Running PULL\n", mcolors.ENDC)

    description = """
    Pull resources (packages/descriptors) from the SONATA service platform/emulator
    or list packages/descriptors/instances available on the SONATA platform/emulator.
    """
    examples = """Example usage:

    son-pull --list_packages
    son-pull --url http://127.0.0.1:5000 -A
    """
    parser = ArgumentParser(
        description=description,
        formatter_class=RawDescriptionHelpFormatter,
        epilog=examples)

    parser.add_argument(
        "--workspace",
        type=str,
        metavar="WORKSPACE_PATH",
        help="specifies workspace to work on. If not specified will "
             "assume '{}'".format(Workspace.DEFAULT_WORKSPACE_DIR),
        required=False
    )

    parser.add_argument(
        "--url",
        type=str,
        metavar="URL",
        help="url of the gatekeeper/platform/emulator")

    parser.add_argument(
        "-A", "--alive",
        help="Checks connectivity with the GK",
        action="store_true")

    parser.add_argument(
        "-P", "--list_packages",
        help="List packages uploaded to the platform",
        action="store_true")

    parser.add_argument(
        "-F", "--list_functions",
        help="List functions uploaded to the platform",
        action="store_true")

    parser.add_argument(
        "-S", "--list_services",
        help="List services uploaded to the platform",
        action="store_true")

    parser.add_argument(
        "--get_package",
        type=str,
        metavar="ID",
        help="Pull package from the platform")

    parser.add_argument(
        "--get_function",
        type=str,
        metavar="ID",
        help="Pull function from the platform")

    parser.add_argument(
        "--get_service",
        type=str,
        metavar="ID",
        help="Pull service from the platform")

    parser.add_argument(
        "--get_package_uuid",
        type=str,
        metavar="UUID",
        help="Pull son_package from the platform")

    parser.add_argument(
        "--get_function_uuid",
        type=str,
        metavar="UUID",
        help="Pull function from the platform")

    parser.add_argument(
        "--get_service_uuid",
        type=str,
        metavar="UUID",
        help="Pull service from the platform")

    parser.add_argument(
        "--get_son_package",
        type=str,
        metavar="UUID",
        help="Pull son_package from the platform")

    parser.add_argument(
        "-I", "--list_instances",
        help="List deployed packages on the platform",
        action="store_true")

    args = parser.parse_args()

    # Obtain Workspace object
    if args.workspace:
        ws_root = args.workspace
    else:
        ws_root = Workspace.DEFAULT_WORKSPACE_DIR
    workspace = Workspace.__create_from_descriptor__(ws_root)

    if args.url:
        platform_url = str(args.url)
    else:
        platform_url = 'http://' + str(GK_ADDRESS) + ':' + str(GK_PORT)

    if not platform_url:
        print("Platform url is required in config file")

    access_token = None
    try:
        with open('config/token.txt', 'rb') as token_file:
            access_token = token_file.read()
            access_token = access_token[1:-1]
    except:
        pass

    pull_client = Pull(platform_url, auth_token=access_token)

    if args.alive:
        print(mcolors.OKGREEN + "PULL - Checking Platform connectivity...\n", mcolors.ENDC)
        print(pull_client.alive())

    if args.list_packages:
        print(mcolors.OKGREEN + "PULL - Getting Packages list...\n", mcolors.ENDC)
        print(pull_client.get_all_packages())

    if args.list_functions:
        print(mcolors.OKGREEN + "PULL - Getting Functions list...\n", mcolors.ENDC)
        print(pull_client.get_all_vnfs())

    if args.list_services:
        print(mcolors.OKGREEN + "PULL - Getting Services list...\n", mcolors.ENDC)
        print(pull_client.get_all_nss())

    if args.get_package_uuid:
        print(mcolors.OKGREEN + "PULL - Getting Package...\n", mcolors.ENDC)
        pull_client.get_package_by_uuid(args.get_package_uuid)

    if args.get_function_uuid:
        print(mcolors.OKGREEN + "PULL - Getting Function...\n", mcolors.ENDC)
        print(pull_client.get_vnf_by_uuid(args.get_function_uuid))

    if args.get_service_uuid:
        print(mcolors.OKGREEN + "PULL - Getting Service...\n", mcolors.ENDC)
        print(pull_client.get_ns_by_uuid(args.get_service_uuid))

    if args.get_package:
        print(mcolors.OKGREEN + "PULL - Getting Package...\n", mcolors.ENDC)
        pull_client.get_package_by_id(args.get_package)

    if args.get_function:
        print(mcolors.OKGREEN + "PULL - Getting Function...\n", mcolors.ENDC)
        print(pull_client.get_vnf_by_id(args.get_function))

    if args.get_service:
        print(mcolors.OKGREEN + "PULL - Getting Service...\n", mcolors.ENDC)
        print(pull_client.get_ns_by_id(args.get_service))

    if args.get_son_package:
        print(mcolors.OKGREEN + "PULL - Getting SON-Package...\n", mcolors.ENDC)
        binary_data = pull_client.get_son_package_by_uuid(args.get_son_package)

    # if args.list_instances:
    #    print(pull_client.get_instances(platform_url))


if __name__ == '__main__':
    main()
