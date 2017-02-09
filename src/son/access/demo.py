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
PORTO F2F Meeting short demo on features:
- Access token
- Push package function
"""

import os
import sys; print('Python %s on %s' % (sys.version, sys.platform))
import time
import requests
from multiprocessing import Process
from son.access.utils.mock import main as mocked

# dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
# sys.path.extend([str(dir)])

class mcolors:
     OKGREEN = '\033[92m'
     FAIL = '\033[91m'
     ENDC = '\033[0m'

     def disable(self):
         self.OKGREEN = ''
         self.FAIL = ''
         self.ENDC = ''


def main():
    print("\n")
    print("=== ", mcolors.OKGREEN + "SON-ACCESS AUTHENTICATION ", mcolors.ENDC + "===\n")
    print(mcolors.OKGREEN + "Logging in with USERNAME: tester\n", mcolors.ENDC)
    url = "http://0.0.0.0:5001/login"

    # Construct the POST request
    form_data = {
        'username': 'tester',
        'password': '1234'
    }

    response = requests.post(url, data=form_data, verify=False)
    print("Access Token received: ", mcolors.OKGREEN + response.text + "\n", mcolors.ENDC)

    time.sleep(3)

    print("=== ", mcolors.OKGREEN + "SON-ACCESS PUSH SON-PACKAGE ", mcolors.ENDC + "===\n")

    mode = "push"
    url = "http://sp.int3.sonata-nfv.eu:32001"
    pkg = "samples/sonata-demo.son"

    # Push son-package to the Service Platform
    command = "sudo python %s.py -U %s" % (mode, pkg)
    print("Calling: ", mcolors.OKGREEN + command + "\n", mcolors.ENDC)
    result = os.popen(command).read()
    print("Response: ", mcolors.OKGREEN + result + "\n", mcolors.ENDC)

    time.sleep(3)

    # Get son-packages list from the Service Platform to check submitted son-package
    mode = "pull"
    command = "sudo python %s.py --list_packages" % mode
    print("Calling: ", mcolors.OKGREEN + command + "\n", mcolors.ENDC)
    result = os.popen(command).read()
    print("Response: ", mcolors.OKGREEN + result + "\n", mcolors.ENDC)

processes = []

# Run fake user management module
print(mcolors.FAIL + "Starting 'fake' User Management module", mcolors.ENDC)
p = Process(target=mocked,)
time.sleep(0.5)
p.start()
processes.append(p)
time.sleep(3)

# Run demo main process
p = Process(target=main,)
p.start()
processes.append(p)
time.sleep(1)

try:
    for process in processes:
        process.join()
except KeyboardInterrupt:
    print("Keyboard interrupt in main")
except Exception as e:
    print("ERROR: ", e)
finally:
    print("Cleaning up Main")



