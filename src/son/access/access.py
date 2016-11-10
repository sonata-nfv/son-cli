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

import requests
import logging
import requests
import yaml
import sys
import validators
from datetime import datetime, timedelta
import jwt
from helpers.helpers import json_response
from models.models import User

log = logging.getLogger(__name__)


class AccessClient:

    def __init__(self):
        """
        Header
        The JWT Header declares that the encoded object is a JSON Web Token (JWT) and the JWT is a JWS that is MACed
        using the HMAC SHA-256 algorithm
        """
        JWT_SECRET = 'secret'
        JWT_ALGORITHM = 'HS256'
        JWT_EXP_DELTA_SECONDS = 20
        URL = 'https://api.github.com/some/endpoint'

    def client_register(self):
        """
        Request registration from on the Service Platform
        :return: Initial JWT access_token? Or HTTP Code to confirm registration
        """
        pass

    def client_login(self, request):
        """
        Make a POST request with username and password
        :return: JW Access Token is returned from the GK server
        """
        # route = ('POST', '/login')
        # payload = {'some': 'data'}
        # r = requests.post(url, json=payload)

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







