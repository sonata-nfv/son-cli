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
from json import loads

log = logging.getLogger(__name__)


class Push:
    """
    This is an updated implementation of the son-push tool
    to re-use son-publish/CatalogueClient and push components.

    This tool is responsible of POSTing descriptors.

    This tool connects to a REST api of the SONATA Service
    Platform Gatekeeper. As these API's are still under
    construction, functionality as well as implementation
    of this module probably change continuously.

    This version currently interoperates with the dummy
    gatekeeper provided by the son-emu tool.
    """
    def __init__(self):
        pass

        '''
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
                      "failed".format(CatalogueClient.CAT_URI_VNF))
            return
    '''

    '''
    def post_ns(self, nsd_data):
        """
        Publishes a NS descriptor to the catalogue server
        :param nsd_data:
        :return:
        """
        response = self.__post_cat_object__(
            CatalogueClient.CAT_URI_NS, nsd_data)

        if response and response.status_code != requests.codes.ok:
            log.error("Publishing failed. "
                      "HTTP code: {}".format(response.status_code))
            return

        return response
    '''

    '''
    def post_vnf(self, vnf_data):
        """
        Publishes a VNF descriptor to the catalogue server
        :param vnf_data:
        :return:
        """
        response = self.__post_cat_object__(
            CatalogueClient.CAT_URI_VNF, vnf_data)
        if response is not None and response.status_code != requests.codes.ok:
            log.error("Publishing failed. "
                      "HTTP code: {}".format(response.status_code))
            return

        return response
    '''