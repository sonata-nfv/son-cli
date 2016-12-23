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
from tests.mock import main as mocked

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
    print "\n"
    print "=== ", mcolors.OKGREEN + "SON-ACCESS AUTHENTICATION ", mcolors.ENDC + "===\n"
    print mcolors.OKGREEN + "Logging in with USERNAME: tester\n", mcolors.ENDC
    url = "http://0.0.0.0:5001/login"

    # Construct the POST request
    form_data = {
        'username': 'tester',
        'password': '1234'
    }

    response = requests.post(url, data=form_data, verify=False)
    print "Access Token received: ", mcolors.OKGREEN + (response.text) + "\n", mcolors.ENDC

    time.sleep(3)

    print "=== ", mcolors.OKGREEN + "SON-ACCESS PUSH SON-PACKAGE ", mcolors.ENDC + "===\n"

    mode = "push"
    url = "http://sp.int3.sonata-nfv.eu:32001"
    pkg = "samples/sonata-demo.son"

    # Push son-package to the Service Platform
    command = "sudo python %s.py %s -U %s" % (mode, url, pkg)
    print "Calling: ", mcolors.OKGREEN + command + "\n", mcolors.ENDC
    result = os.popen(command).read()
    print "Response: ", mcolors.OKGREEN + result + "\n", mcolors.ENDC

    time.sleep(3)

    # Get son-packages list from the Service Platform to check submitted son-package
    mode = "pull"
    command = "sudo python %s.py %s --list_packages" % (mode, url)
    print "Calling: ", mcolors.OKGREEN + command + "\n", mcolors.ENDC
    result = os.popen(command).read()
    print "Response: ", mcolors.OKGREEN + result + "\n", mcolors.ENDC

processes = []

# Run fake user management module
print mcolors.FAIL + "Starting 'fake' User Management module", mcolors.ENDC
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
    print "Keyboard interrupt in main"
except Exception as e:
    print("ERROR: ", e)
finally:
    print "Cleaning up Main"



