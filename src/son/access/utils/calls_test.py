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

from pull import Pull
from push import Push
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

