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

import os
import sys; print('Python %s on %s' % (sys.version, sys.platform))

dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.extend([str(dir)])

from son.access.pull import Pull
from son.access.push import Push
# from son.access.config.config import GK_ADDRESS, GK_PORT

def pull_tests():
    # platform_url = 'http://' + str(GK_ADDRESS) + ':' + str(GK_PORT)
    pull_client = Pull(base_url="http://sp.int.sonata-nfv.eu:32001")

    # resource = pull_client.get_vnf("eu.sonata-nfv.firewall-vnf.0.2")
    # resource = pull_client.get_vnf("name=firewall-vnf&vendor=eu.sonata-nfv&version=0.2")
    # resource = pull_client.get_package("97b2e5e9-048a-44f5-b91e-69a90f525f2a")

    resource = pull_client.get_all_nss()
    print("NSS RESPONSE", resource)

    resource = pull_client.get_all_vnfs()
    print("VFNS RESPONSE", resource)

    resource = pull_client.get_all_packages()
    print("PACKAGES RESPONSE", resource)

    resource = pull_client.get_ns("a6707125-bf8d-4c6f-999d-2a5990311762")
    print("NS RESPONSE", resource)

    resource = pull_client.get_vnf("dce3cffd-4957-40fe-adcc-cdc41c97a805")
    print("VNF RESPONSE", resource)

    #resource = pull_client.get_package("e84cf007-3e68-45a2-8f05-d1718c767220")
    #print "Package RESPONSE", resource


def push_tests():
    # platform_url = 'http://' + str(GK_ADDRESS) + ':' + str(GK_PORT)
    access_token = None
    try:
        with open('config/token.txt', 'rb') as token_file:
            access_token = token_file.read()
            access_token = access_token[1:-1]
    except:
        pass

    push_client = Push(base_url="http://sp.int.sonata-nfv.eu:32001", auth_token=access_token)
    print(push_client.upload_package("../samples/sonata-demo.son"))


def generate_keypair():
    from Crypto.PublicKey import RSA
    algorithm = 'RS256'

    key = RSA.generate(2048)
    public = key.publickey().exportKey('PEM').decode('ascii')
    private = key.exportKey('PEM').decode('ascii')

    print("public=", public)
    print("private=", private)

    with open("private_key", mode="w") as pr_file:
            pr_file.write(private)
    with open("public_key", mode="w") as pb_file:
            pb_file.write(public)

def user_login(username, password):
    import requests
    import json
    from base64 import b64encode, b64decode

    # Construct the POST login request
    creds = (str(username) + ':' + str(password)).encode("utf-8")
    print(str(username) + ':' + str(password))
    print(creds)
    encoded_password = b64encode(creds)
    print(b64decode(encoded_password))
    headers = {'Authorization': 'Basic %s' % encoded_password}

    url = "http://sp.int3.sonata-nfv.eu:5600/api/v1/login/user"

    response = requests.post(url, headers=headers, verify=False)
    if not response.status_code in (200, 201):
        return response.text
    token = json.loads(response.text)['access_token']
    return token

def get_platform_public_key():
    """
    Simple request to request the Platform Public Key
    :return: Public Key, HTTP code 200
    """
    from Crypto.PublicKey import RSA
    import requests
    import json

    url = 'http://sp.int3.sonata-nfv.eu:5600/api/v1/public-key'
    response = requests.get(url, verify=False)
    # print(response.status_code, response.text)
    parsed_key = json.loads(response.text)['public-key']
    print(parsed_key)
    platform_public_key = "-----BEGIN PUBLIC KEY-----\n"
    platform_public_key += parsed_key
    platform_public_key += "\n-----END PUBLIC KEY-----\n"
    print(platform_public_key)
    key = RSA.importKey(platform_public_key).exportKey('PEM')
    print(key)
    return key


def check_token(key):
    import jwt
    """
    Simple request to check if session has expired (TBD)
    :return: Token status
    """
    access_token = 'eyJhbGciOiJSUzI1NiIsInR5cCIgOiAiSldUIiwia2lkIiA6ICJPelpfa1VoUzAwNlF0SFVKTWtPWUxtV2NRaFNyTlgwV0p1aFNVMTZHR1NFIn0.eyJqdGkiOiJjYTU0MjM0NC1hMTgxLTRkYmEtOWU5Yi1mOGM5ZjMwOWY2NDkiLCJleHAiOjE0OTIwMDc2NjIsIm5iZiI6MCwiaWF0IjoxNDkyMDA3MzYyLCJpc3MiOiJodHRwOi8vc29uLWtleWNsb2FrOjU2MDEvYXV0aC9yZWFsbXMvc29uYXRhIiwiYXVkIjoiYWRhcHRlciIsInN1YiI6IjllNzMwZWJlLTk3MzgtNGY1ZC05OTNiLTEzYjlmOGJjOTFlZiIsInR5cCI6IkJlYXJlciIsImF6cCI6ImFkYXB0ZXIiLCJhdXRoX3RpbWUiOjAsInNlc3Npb25fc3RhdGUiOiIwMzU3YmNiYS03ZjFiLTRjNzYtOTBjZi1hOTA2MjViNDIxZTMiLCJhY3IiOiIxIiwiY2xpZW50X3Nlc3Npb24iOiJkNGNmZWFhNS1iMDE3LTRlYmQtOTA3MS0xMGNhZTIxNzMxYzAiLCJhbGxvd2VkLW9yaWdpbnMiOlsiaHR0cDovL2xvY2FsaG9zdDo4MDgxIl0sInJlYWxtX2FjY2VzcyI6eyJyb2xlcyI6WyJkZXZlbG9wZXIiLCJ1bWFfYXV0aG9yaXphdGlvbiJdfSwicmVzb3VyY2VfYWNjZXNzIjp7ImFjY291bnQiOnsicm9sZXMiOlsibWFuYWdlLWFjY291bnQiLCJtYW5hZ2UtYWNjb3VudC1saW5rcyIsInZpZXctcHJvZmlsZSJdfX0sIm5hbWUiOiJVc2VyIFNhbXBsZSIsInByZWZlcnJlZF91c2VybmFtZSI6InVzZXIwMSIsImdpdmVuX25hbWUiOiJVc2VyIiwiZmFtaWx5X25hbWUiOiJTYW1wbGUiLCJlbWFpbCI6InVzZXIuc2FtcGxlQGVtYWlsLmNvbSJ9.Q_vh4QenmJjf1MFPHSWsLQFsU6u0VB37YUMC8tN7prqFRSHe8EztYXhfixh1pxkqb8doaxTcR2DWC4orhzWc-3srFwbAHI5y_ZiZ54gFQBwUW3mAEhSsLkD-MJTqLJ9hexHYj0I2zpSGBsWdbMCeg0AVUnWt7BGTfJ8CUQo5GJWyWnusJ95WFr9XgZ5QR_bxJLqYzoh1QnLxN1kXEYGeTYuL36Miaf5KOzY2FiQyKnj4arSEScJFQQy2FVjxSD3yOXTBl6pcMPvdKOGIIdcPw1Maf0dATTcT1dprX-HEonaE0nduCXYquCedB_fJr21WHRMs62ZagL7cEgU7eXoowA'
    try:
        contents = jwt.decode(access_token, key, True, algorithms='RS256', audience='adapter')  # options={'verify_aud': False})
        print('contents', contents)
        return True
    except jwt.ExpiredSignatureError:
        print('Signature has expired')
        return False


# generate_keypair()
# token = user_login('user04', '1234')
# print(token)
# key = get_platform_public_key()
# check_token(key)
