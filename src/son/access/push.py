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

import validators
import requests
import logging
import yaml
import sys
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


class Push:
    """
    This is an updated implementation of the son-push tool
    to re-use son-publish/CatalogueClient and push components.

    This tool is responsible of POSTing descriptors.

    This tool connects to a REST API of the SONATA Service
    Platform Gatekeeper. As these API's are still under
    construction, functionality as well as implementation
    of this module probably change continuously.

    This version currently interoperates with the dummy
    gatekeeper provided by the son-emu tool.
    """
    def __init__(self):
        platform_url = "http://sp.int3.sonata-nfv.eu:32001/packages"
    pass

class PushCatalogueClient(object):
    """
    Modified CatalogueClient class to communicate to SP Catalogue component
    through son-gtkapi on SP Gatekeeper (only descriptors)
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
        Checks if the catalogue API server is alive and
        responding to requests
        :return: True=server OK,
                 False=server unavailable
        """
        url = self._base_url + PushCatalogueClient.CAT_URI_BASE
        try:
            response = requests.get(url,
                                    auth=self._auth,
                                    headers=self._headers)

        except requests.exceptions.InvalidURL:
            log.warning("Invalid URL: '{}'. Please specify "
                        "a valid address to a catalogue server".format(url))
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

    def post_ns(self, nsd_data):
        """
        Publishes a NS descriptor to the catalogue server
        :param nsd_data:
        :return:
        """
        response = self.__post_cat_object__(
            PushCatalogueClient.CAT_URI_NS, nsd_data)

        if response and response.status_code != requests.codes.ok:
            log.error("Publishing failed. "
                      "HTTP code: {}".format(response.status_code))
            return

        return response

    def post_vnf(self, vnf_data):
        """
        Publishes a VNF descriptor to the catalogue server
        :param vnf_data:
        :return:
        """
        response = self.__post_cat_object__(
            PushCatalogueClient.CAT_URI_VNF, vnf_data)
        if response is not None and response.status_code != requests.codes.ok:
            log.error("Publishing failed. "
                      "HTTP code: {}".format(response.status_code))
            return

        return response

    def __post_cat_object__(self, cat_uri, obj_data):
        """
        Generic POST function.
        :param cat_uri:
        :param obj_data:
        :return:
        """
        url = self._base_url + cat_uri
        log.debug("Object POST to: {}\n{}".format(url, obj_data))

        try:
            response = requests.post(url,
                                     data=obj_data,
                                     auth=self._auth,
                                     headers=self._headers)
            return response

        except requests.exceptions.ConnectionError:
            log.error("Connection error to server '{}'. VNF publishing "
                      "failed".format(PushCatalogueClient.CAT_URI_VNF))
            return


def upload_package(platform_url, package_file_name):
    """
    Upload package to platform

    :param platform_url: url of the SONATA service
                         platform/gatekeeper or emulator
                         to upload package to

    :param package_file_name: filename including full
                              path of the package
                              to be uploaded

    :returns: text response message of the server or
              error message
    """
    import os

    if not os.path.isfile(package_file_name):
        return package_file_name, "is not a file."

    # Packages on GK
    url = platform_url + "/packages"
    # son-packages on catalogue
    #url = platform_url + "/son-packages"

    if not validators.url(url):
        return url, "is not a valid url."

    print mcolors.OKGREEN + "Uploading package " + package_file_name + " to " + url + "\n", mcolors.ENDC
    try:
        with open(package_file_name, 'rb') as pkg_file:
            r = requests.post(url, files={'package': pkg_file})
            if r.status_code == 201:
                msg = "Upload succeeded"
            elif r.status_code == 409:
                msg = "Package already exists"
            else:
                msg = "Upload error"
            return "%s (%d): %r" % (msg, r.status_code, r.text)

    except Exception as e:
        return "Service package upload failed. " + e

'''
def instantiate_package(platform_url, service_uuid=""):
    """
    Instantiate service on SONATA service platform

    :param platform_url: url of the SONATA service
                         platform/gatekeeper or emulator
                         to upload package to

    :param service_uuid: uuid of the service package
                         (requires it to be available
                         on the platform)

    :returns: text response message of the server
    """
    # TODO: to be removed (default choice) after testing
    try:
        if len(service_uuid) == 0:
            service_uuid = package_list(platform_url)[0]
        if service_uuid == "last":
            service_uuid = package_list(platform_url)[0]

        if service_uuid not in package_list(platform_url):
            return "Given service uuid does not exist on the platform."

        url = platform_url+"/instantiations"

        r = requests.post(url, json={"service_uuid": service_uuid})

        return r.text

    except Exception as e:
        return "Service could not be instantiated. " + e
'''


def _get_from_url(url):
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


def get_packages(url):
    return _get_from_url(url+"/packages")

'''
def get_instances(url):
    return _get_from_url(url + "/instantiations")

'''

def package_list(url):
    return loads(get_packages(url)).get("service_uuid_list")

'''
def instance_list(url):
    return loads(get_instances(url)).get("service_instantiations_list")
'''

def main():
    from argparse import ArgumentParser, RawDescriptionHelpFormatter
    print mcolors.OKGREEN + "Running PUSH\n", mcolors.ENDC

    description = """
    Push packages to the SONATA service platform/emulator or list
    packages/instances available on the SONATA platform/emulator.
    """
    examples = """Example usage:

    son-push http://127.0.0.1:5000 -U sonata-demo.son
    son-push http://127.0.0.1:5000 --list_packages
    son-push http://127.0.0.1:5000 --deploy_package <uuid>
    son-push http://127.0.0.1:5000 -I
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

    parser.add_argument(
        "-U", "--upload_package",
        help="Filename incl. path of package to be uploaded")

    parser.add_argument(
        "-D", "--deploy_package_uuid",
        help="UUID of package to be deployed (must be available at platform)")

    args = parser.parse_args()

    if not args.platform_url:
        print("Platform url is required.")

    if args.list_packages:
        print mcolors.OKGREEN + "PUSH - Getting Package list...\n", mcolors.ENDC
        print(get_packages(args.platform_url))

    #if args.list_instances:
    #    print(get_instances(args.platform_url))

    if args.upload_package:
        print mcolors.OKGREEN + "PUSH - Uploading Package...\n", mcolors.ENDC
        print(upload_package(args.platform_url, args.upload_package))

    #if args.deploy_package_uuid:
    #    print(instantiate_package(args.platform_url, args.deploy_package_uuid))

if __name__ == '__main__':
    main()
