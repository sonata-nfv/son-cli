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

    def __init__(self, base_url, auth=('', '')):
        # Assign parameters
        self._base_url = base_url
        self._auth = auth   # Just basic auth for now
        self._headers = {'Content-Type': 'application/x-yaml'}

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
                                    auth=self._auth,
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

    def get_list_all_ns(self):
        return self.__get_cat_object__(self.CAT_URI_NS, "")

    def get_ns(self, ns_id):
        """
        Obtains a specific network service (NS)
        :param ns_id: ID of NS in the form 'vendor.ns_name.version'
        :return: yaml object containing NS
        """
        cat_obj = self.__get_cat_object__(self.CAT_URI_NS_ID, ns_id)
        if not isinstance(cat_obj, str) and len(cat_obj) > 1:
            log.error("Obtained multiple network "
                      "services using the ID '{}'".format(ns_id))
            return

        log.debug("Obtained NS schema:\n{}".format(cat_obj))
        return yaml.load(cat_obj)

    def get_ns_by_name(self, ns_name):
        """
        Obtains a list of network services matching the ns_name
        :param ns_name: name of network service
        :return: (str) list of network services
        """
        return self.__get_cat_object__(
            self.CAT_URI_NS_NAME, ns_name)


    def get_list_all_vnf(self):
        return self.__get_cat_object__(self.CAT_URI_VNF, "")

    def get_vnf(self, vnf_id):
        """
        Obtains a specific VNF
        :param vnf_id: ID of VNF in the form 'vendor.ns_name.version'
        :return: yaml object containing VNF
        """
        cat_obj = self.__get_cat_object__(
            self.CAT_URI_VNF_ID, vnf_id)
        if not cat_obj:
            return

        if not isinstance(cat_obj, str) and len(cat_obj) > 1:
            log.error("Obtained multiple VNFs using ID '{}'".format(vnf_id))
            return

        log.debug("Obtained VNF schema:\n{}".format(cat_obj))
        return yaml.load(cat_obj)

    def get_vnf_by_name(self, vnf_name):
        """
        Obtains a list of VNFs matching the vnf_name
        :param vnf_name: name of network service
        :return: (str) list of VNFs
        """
        return self.__get_cat_object__(
            self.CAT_URI_VNF_NAME, vnf_name)

    def __get_cat_object__(self, cat_uri, obj_id):
        """
        Generic GET function.
        :param cat_uri:
        :param obj_id:
        :return:
        """
        url = self._base_url + cat_uri + obj_id
        response = requests.get(url, auth=self._auth, headers=self._headers)
        if not response.status_code == requests.codes.ok:
            return
        return response.text

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

    def get_packages(self, url):
        return self._get_from_url(url+"/packages")

    '''
    def get_instances(url):
        return _get_from_url(url + "/instantiations")

    '''

    def package_list(self, url):
        return loads(self.get_packages(url)).get("service_uuid_list")

    '''
    def instance_list(self, url):
        return loads(get_instances(url)).get("service_instantiations_list")
    '''


def main():
    from argparse import ArgumentParser, RawDescriptionHelpFormatter
    print mcolors.OKGREEN + "Running PULL\n", mcolors.ENDC

    description = """
    Pull resources (packages/descriptors) from the SONATA service platform/emulator
    or list packages/descriptors/instances available on the SONATA platform/emulator.
    """
    examples = """Example usage:

    son-pull http://127.0.0.1:5000 -U sonata-demo.son
    son-pull http://127.0.0.1:5000 --list_packages
    son-pull http://127.0.0.1:5000 -I
    """
    parser = ArgumentParser(
        description=description,
        formatter_class=RawDescriptionHelpFormatter,
        epilog=examples)

    parser.add_argument(
        "platform_url",
        help="url of the gatekeeper/platform/emulator")

    parser.add_argument(
        "-P", "--list_packages",
        help="List packages uploaded to the platform",
        action="store_true")

    parser.add_argument(
        "-I", "--list_instances",
        help="List deployed packages on the platform",
        action="store_true")

    args = parser.parse_args()

    if not args.platform_url:
        print("Platform url is required.")

    # TODO: Add url -> Read from settings
    pull_client = Pull(base_url=args.platform_url)
    # pull_client = Pull(base_url="http://sp.int3.sonata-nfv.eu:32001")

    if args.list_packages:
        print mcolors.OKGREEN + "PUSH - Getting Package list...\n", mcolors.ENDC
        print(pull_client.get_packages(args.platform_url))

    #if args.list_instances:
    #    print(pull_client.get_instances(args.platform_url))


if __name__ == '__main__':
    main()
