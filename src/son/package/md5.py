#  Copyright (c) 2015 SONATA-NFV, UBIWHERE
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
# Neither the name of the SONATA-NFV, UBIWHERE
# nor the names of its contributors may be used to endorse or promote
# products derived from this software without specific prior written
# permission.
#
# This work has been performed in the framework of the SONATA project,
# funded by the European Commission under Grant number 671517 through
# the Horizon 2020 and 5G-PPP programmes. The authors would like to
# acknowledge the contributions of their colleagues of the SONATA
# partner consortium (www.sonata-nfv.eu).

import hashlib
import os


def generate_hash(f, cs=128):
    print("... generating hash of '{0}'".format(f))
    return __generate_hash__(f, cs) \
        if os.path.isfile(f) \
        else __generate_hash_path__(f, cs)


def __generate_hash__(f, cs=128):
    hash = hashlib.md5()
    with open(f, "rb") as file:
        for chunk in iter(lambda: file.read(cs), b''):
            hash.update(chunk)
    return hash.hexdigest()


def __generate_hash_path__(p, cs=128):
    print("... >>>> hash path <<<<")
    hashes = []
    for root, dirs, files in os.walk(p):
        for f in sorted(files):  # guarantee same order to obtain same hash
            hashes.append(__generate_hash__(os.path.join(root, f), cs))
        for d in sorted(dirs):  # guarantee same order to obtain same hash
            hashes.append(__generate_hash_path__(os.path.join(root, d), cs))
        break
    return _reduce_hash(hashes)


def _reduce_hash(hashlist):
    hash = hashlib.md5()
    for hashvalue in sorted(hashlist):
        hash.update(hashvalue.encode('utf-8'))
    return hash.hexdigest()
