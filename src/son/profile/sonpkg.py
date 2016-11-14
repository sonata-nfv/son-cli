#  Copyright (c) 2015 SONATA-NFV, Paderborn University
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

import logging
import zipfile
import os
from son.profile.helper import load_yaml, relative_path


LOG = logging.getLogger(__name__)


class SonataPackage(object):
    """
    Reflects a SONATA service package and its contents, like NSD and VNFDs.
    """

    def __init__(self, manifest, nsd, vnfd_list):
        self.manifest = manifest
        self.nsd = nsd
        self.vnfd_list = vnfd_list

    @staticmethod
    def load(pkg_path):
        """
        Loads the service package contents from the given path.
        :param pkg_path: path to a folder with service package contents.
        :return: SonataPackage object.
        """
        # load manifest
        manifest = load_yaml(
            os.path.join(pkg_path, "META-INF/MANIFEST.MF"))
        # load nsd
        nsd = load_yaml(
            os.path.join(
                pkg_path,
                relative_path(manifest.get("entry_service_template"))))
        # load vnfds
        vnfd_list = list()
        for ctx in manifest.get("package_content"):
            if "function_descriptor" in ctx.get("content-type"):
                vnfd_list.append(
                    load_yaml(
                        os.path.join(pkg_path,
                                     relative_path(ctx.get("name")))))
        LOG.info("Loaded SONATA service package contents (%d VNFDs)." % len(vnfd_list))
        # create SonataPackage object
        return SonataPackage(manifest, nsd, vnfd_list)


def extract_son_package(input_ped, input_path):
    """
    Unzips a SONATA service package and stores all its contents
    in the given folder.
    :param input_ped: PED file that references a *.son package.
    :param input_path: Path to which the package contents are extracted.
    :return:
    """
    # locate referenced *.son file
    pkg_name = input_ped.get("service_package", "service.son")
    son_path = os.path.join(os.path.dirname(input_ped.get("ped_path", "/")), pkg_name)
    if not os.path.exists(son_path):
        raise BaseException("Couldn't find referenced SONATA package: %r" % son_path)
    # extract *.son file and put it into WORK_DIR
    LOG.debug("Unzipping: %r to %r" % (son_path, input_path))
    with zipfile.ZipFile(son_path, "r") as z:
        z.extractall(input_path)
    LOG.info("Extracted SONATA service package: %r" % pkg_name)


