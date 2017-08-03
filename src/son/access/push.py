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
import sys
from son.access.config.config import GK_ADDRESS, GK_PORT

log = logging.getLogger(__name__)


class mcolors:
     OKGREEN = '\033[92m'
     FAIL = '\033[91m'
     ENDC = '\033[0m'

     def disable(self):
         self.OKGREEN = ''
         self.FAIL = ''
         self.ENDC = ''


class Push(object):
    """
    This is an updated implementation of the son-push tool
    to re-use son-publish/CatalogueClient and push components.
    Modified CatalogueClient class is integrated to communicate
    to SP Catalogue component through son-gtkapi on SP Gatekeeper
    (only descriptors).

    This tool is responsible of POSTing descriptors.

    This tool connects to a REST API of the SONATA Service
    Platform Gatekeeper. As these API's are still under
    construction, functionality as well as implementation
    of this module probably change continuously.
    """

    # Gatekeeper API URLs configuration
    GK_API_VERSION = "/api/v2"
    CAT_URI_BASE = "/"
    CAT_URI_NS = "/services?"               # NS submitting endpoint
    CAT_URI_VNF = "/functions?"             # VNF submitting endpoint
    CAT_URI_PD = "/packages?"               # Package submitting endpoint
    GK_URI_INST = "/requests?"

    def __init__(self, base_url, pb_key=None, pr_key=None, cert=None):

        # Assign parameters
        self._base_url = base_url
        self._headers = {'Content-Type': 'application/json'}
        # {'Content-Type': 'application/x-yaml'}
        self._keys = {'public_key': pb_key, 'private_key': pr_key, 'certificate': cert}

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
        url = self._base_url + Push.CAT_URI_BASE
        try:
            response = requests.get(url,
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

    def __post_cat_object__(self, cat_uri, obj_data):
        """
        Generic POST function.
        :param cat_uri: Platform GKAPI address
        :param obj_data: Resource to be submitted
        :return: response code of the SP
        """
        url = self._base_url + self.GK_API_VERSION + cat_uri
        log.debug("Object POST to: {}\n{}".format(url, obj_data))

        try:
            response = requests.post(url, data=obj_data, headers=self._headers)
            return response

        except requests.exceptions.ConnectionError:
            log.error("Connection error to server '{}'. Publishing "
                      "failed".format(cat_uri))
            return

    def post_ns(self, nsd_data):
        """
        Publishes a NS descriptor to the catalogue server
        :param nsd_data:
        :return:
        """
        response = self.__post_cat_object__(
            Push.CAT_URI_NS, nsd_data)

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
            Push.CAT_URI_VNF, vnf_data)
        if response is not None and response.status_code != requests.codes.ok:
            log.error("Publishing failed. "
                      "HTTP code: {}".format(response.status_code))
            return

        return response

    def upload_package(self, access_token, package_file_name, signature=None):
        """
        Upload package to platform

        :param access_token: authentication token that enables
                             access to the SONATA service
                             platform/gatekeeper or emulator
                             to upload package to

        :param package_file_name: filename including full
                                  path of the package
                                  to be uploaded

        :param signature: Sets to True or False if the package is signed
                     before pushing it to the Platform

        :returns: text response message of the server or
                  error message
        """
        import os

        if not os.path.isfile(package_file_name):
            return package_file_name, "is not a file."

        # Packages on GK
        url = self._base_url + self.GK_API_VERSION + self.CAT_URI_PD
        # son-packages on catalogue

        if not validators.url(url):
            return url, "is not a valid url."

        try:
            with open(package_file_name, 'rb') as pkg_file:
                payload = {'package': pkg_file}
                if access_token:
                    headers = {'Authorization': "Bearer %s" % access_token}
                else:
                    headers = {}
                if signature:
                    # Including signature header in case it's passed as param
                    print("SIGNATURE= ", signature)
                    headers['signature'] = signature
                r = requests.post(url, headers=headers, files=payload)
                if r.status_code == 201:
                    msg = "Upload succeeded"
                elif r.status_code == 409:
                    msg = "Package already exists"
                else:
                    msg = "Upload error"
                return "%s (%d): %r" % (msg, r.status_code, r.text)

        except Exception as e:
            return "Service package upload failed. " + str(e)

    def unsign_package(self, signed_package: str, **kwargs) -> dict:
        """
        Verifies a signed received package Hash
        :param signed_package: Path to the location where keys will be saved
        :param public_key: Path to the location where public key is stored in order to verify the signature
        :returns: Private key, Public Key
        """
        # Package verification is performed by son-validator component

        # try:
        #    return jwt.decode(token, self.keypair.public, algorithms=[self.algorithm], **kwargs)
        # except jwt.exceptions.InvalidTokenError as e:
        #    raise InvalidAuthenticationToken

    def instantiate_service(self, service_uuid="", access_token=None):
        """
        Instantiate service on SONATA service platform

        :param service_uuid: uuid of the service package
                             (requires it to be available
                             on the platform)
        :param access_token: authentication token that enables
                             access to the SONATA service
                             platform/gatekeeper or emulator
                             to upload package to

        :returns: text response message of the server
        """
        try:
            url = self._base_url + self.GK_API_VERSION + self.GK_URI_INST

            log.info("Deployment URL='{}'".format(url))

            if access_token:
                headers = {'Authorization': "Bearer %s" % access_token}
            else:
                headers = {}

            r = requests.post(url, headers=headers, json={"service_uuid": service_uuid})
            return r.text

        except Exception as e:
            return "Service could not be instantiated. " + str(e)


def main():
    from argparse import ArgumentParser, RawDescriptionHelpFormatter
    print(mcolors.OKGREEN + "Running PUSH\n", mcolors.ENDC)

    description = """
    Push packages to the SONATA service platform/emulator or list
    packages/instances available on the SONATA platform/emulator.
    """
    examples = """Example usage:

    son-push http://127.0.0.1:5000 -U sonata-demo.son
    son-push http://127.0.0.1:5000 --deploy_package <uuid>
    """
    parser = ArgumentParser(
        description=description,
        formatter_class=RawDescriptionHelpFormatter,
        epilog=examples)

    parser.add_argument(
        "-U", "--upload_package",
        help="Filename incl. path of package to be uploaded")

    parser.add_argument(
        "-D", "--deploy_service_uuid",
        help="UUID of service to be instantiated (must be available at platform)")

    args = parser.parse_args()

    platform_url = 'http://' + str(GK_ADDRESS) + ':' + str(GK_PORT)

    if not platform_url:
        print("Platform url is required in config file")

    push_client = Push(base_url=platform_url)

    if args.upload_package:
        print(mcolors.OKGREEN + "PUSH - Uploading Package...\n", mcolors.ENDC)
        print(push_client.upload_package(args.upload_package))

    if args.deploy_service_uuid:
        print(mcolors.OKGREEN + "PUSH - Instantiating Service...\n", mcolors.ENDC)
        print(push_client.instantiate_service(args.service_uuid))

if __name__ == '__main__':
    main()
