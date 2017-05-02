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
import copy
import time
from son.profile.helper import read_yaml, write_yaml, relative_path, ensure_dir
from son.workspace.project import Project
from son.workspace.workspace import Workspace
from son.package.package import Packager


LOG = logging.getLogger(__name__)


class SonataServicePackage(object):
    """
    Reflects a SONATA service package and its contents, like NSD and VNFDs.
    """

    def __init__(self, pkg_service_path, manifest, nsd, vnfd_list):
        self.pkg_service_path = pkg_service_path
        self.pkg_package_path = None
        self.pkg_file_size = 0
        self.manifest = manifest
        self.nsd = nsd
        self.vnfd_list = vnfd_list
        self.metadata = dict()  # profiling specific information
        self.pack_time = 0

    def __repr__(self):
        return self.manifest.get("name")

    @staticmethod
    def load(pkg_path):
        """
        Loads the service package contents from the given path.
        :param pkg_path: path to a folder with service package contents.
        :return: SonataServicePackage object.
        """
        # load manifest
        manifest = read_yaml(
            os.path.join(pkg_path, "META-INF/MANIFEST.MF"))
        # load nsd
        nsd = read_yaml(
            os.path.join(
                pkg_path,
                relative_path(manifest.get("entry_service_template"))))
        # load vnfds
        vnfd_list = list()
        for ctx in manifest.get("package_content"):
            if "function_descriptor" in ctx.get("content-type"):
                vnfd_list.append(
                    read_yaml(
                        os.path.join(pkg_path,
                                     relative_path(ctx.get("name")))))
        LOG.info("Loaded SONATA service package contents (%d VNFDs)." % len(vnfd_list))
        # create SonataServicePackage object
        return SonataServicePackage(pkg_path, manifest, nsd, vnfd_list)

    def copy(self):
        """
        Create a real copy of this service object.
        :return: object
        """
        return copy.deepcopy(self)

    def annotate(self, exname, run_cfg):
        """
        Add profiling specific annotations to this service.
        :param run_cfg:
        :return:
        """
        self.metadata["exname"] = exname
        self.metadata["run_id"] = run_cfg.run_id
        self.metadata["repetition"] = run_cfg.configuration.get("repetition")
        # TODO: We should store these somewhere in the final service package as "meta data" in a way that it does not affect the deployment of the package.

    def write(self, service_project_path):
        """
        Write all files needed to describe this service (NSD, VNFDs).
        :param service_project_path: destination folder
        :return:
        """
        # update package path to reflect new location
        self.pkg_service_path = os.path.join(service_project_path, self.pkg_name())
        # create output folder
        ensure_dir(self.pkg_service_path)
        # write project yml
        write_yaml(os.path.join(self.pkg_service_path, "project.yml"), self.get_project_descriptor())
        # write nsd
        nsd_dir = os.path.join(self.pkg_service_path, "sources/nsd")
        ensure_dir(nsd_dir)
        write_yaml(os.path.join(nsd_dir,  "%s.yml" % self.nsd.get("name")), self.nsd)
        # write all vnfds
        vnf_dir = os.path.join(self.pkg_service_path, "sources/vnf")
        for vnfd in self.vnfd_list:
            d = os.path.join(vnf_dir, vnfd.get("name"))
            ensure_dir(d)
            write_yaml(os.path.join(d, "%s.yml" % vnfd.get("name")), vnfd)
        # LOG.debug("Written service %r to %r" % (self, slef.pkg_service_path))

    def pack(self, output_path):
        """
        Use son-package to pack the given packet.
        :param output_path: resulting packages are placed in output_path
        :return: package path
        """
        start_time = time.time()
        # be sure the target directory exists
        ensure_dir(output_path)
        # obtain workspace
        # TODO have workspace dir as command line argument
        workspace = Workspace.__create_from_descriptor__(Workspace.DEFAULT_WORKSPACE_DIR)
        if workspace is None:
            LOG.error("Couldn't initialize workspace: %r. Abort." % Workspace.DEFAULT_WORKSPACE_DIR)
            exit(1)
        # obtain project
        project = Project.__create_from_descriptor__(workspace, self.pkg_service_path)
        if project is None:
            LOG.error("Packager couldn't load service project: %r. Abort." % self.pkg_service_path)
            exit(1)
        # initialize and run packager
        pck = Packager(workspace, project, dst_path=output_path)
        pck.generate_package(os.path.join(output_path, self.pkg_name()))
        self.pkg_package_path = os.path.join(output_path, self.pkg_name()) + ".son"
        self.pkg_file_size = os.path.getsize(self.pkg_package_path)
        self.pack_time = time.time() - start_time
        return self.pkg_package_path

    def get_project_descriptor(self):
        """
        We need to create a project.yml from the contents of the MANIFEST file to be able
        to re-package the generated services using the son-package tool.
        :return: dictionary with project.yml information
        """
        d = dict()
        d["descriptor_extension"] = "yml"
        d["version"] = "0.5"
        p = dict()
        p["description"] = self.manifest.get("description")
        p["maintainer"] = self.manifest.get("maintainer")
        p["name"] = self.manifest.get("name")
        p["vendor"] = self.manifest.get("vendor")
        p["version"] = self.manifest.get("version")
        d["package"] = p
        return d

    def pkg_name(self):
        """
        Generate name used for generated service project folder and package.
        :return: string
        """
        return "%s_%05d" % (self.metadata.get("exname"), self.metadata.get("run_id"))

    def find_vnfd(self, fun_id):
        """
        Tries to find VNFD using vendor name version string.
        :param fun_id: VNFD identifier
        :return: VNFD structure
        """
        for vnfd in self.vnfd_list:
            if self.get_id(vnfd) == fun_id:
                return vnfd
        return None

    def get_id(self, d):
        return "%s.%s.%s" % (d.get("vendor"), d.get("name"), d.get("version"))



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


