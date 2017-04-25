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
from son.profile.generator import ServiceConfigurationGenerator
from son.workspace.project import Project
from son.workspace.workspace import Workspace
from son.package.package import Packager


LOG = logging.getLogger(__name__)

# working directories created in "output_path"
SON_BASE_DIR = ".tmp_base_service"  # temp folder with input package contents
SON_GEN_SERVICES = ".tmp_gen_services"  # temp folder holding the unpacked generated services

class SonataServiceConfigurationGenerator(ServiceConfigurationGenerator):
    """
    SONATA Service Configuration Generator.
    Input: SONATA service package.
    Output: SONATA service packages.
    """

    def __init__(self):
        LOG.info("SONATA service configuration generator initialized")

    def generate(self, input_reference, function_experiments, service_experiments, working_path):
        """
        Generates service configurations according to the inputs.
        Returns a list of identifiers / paths to the generated service configurations.
        """
        # load base service using PED reference (to a *.son file)
        base_service_obj = self._load(input_reference, working_path)
        # generate one SonataService for each experiment
        gen_conf_obj_list = list()
        gen_conf_obj_list += self._generate_function_experiments(
            base_service_obj, function_experiments)
        gen_conf_obj_list += self._generate_service_experiments(
            base_service_obj, service_experiments)
        # pack all generated services and write them to disk
        return self._pack(working_path, gen_conf_obj_list)

    def _extract(self, input_reference, working_path):
        """
        Unzips a SONATA service package and stores all its contents
        to working_path + SON_BASE_DIR
        """
        # prepare working directory
        base_service_path = os.path.join(working_path, SON_BASE_DIR)
        ensure_dir(base_service_path)
        # locate referenced *.son file
        if not os.path.exists(input_reference):
            raise BaseException("Couldn't find referenced SONATA package: %r" % input_reference)
        # extract *.son file and put it into base_service_path
        LOG.debug("Unzipping: {} to {}".format(input_reference, base_service_path))
        with zipfile.ZipFile(input_reference, "r") as z:
            z.extractall(base_service_path)
        LOG.info("Extracted SONATA service package: {}".format(input_reference))
        return base_service_path

    def _load(self, input_reference, working_path):
        """
        Load a SONATA from the specified package (*.son).
        Creates temporary files in working_path.
        Returns SonataService objecct.
        """
        # extract service project from SONATA package
        base_service_path = self._extract(input_reference, working_path)
        return SonataService.load(base_service_path)

    def _generate_function_experiments(self, base_service_obj, experiments):
        LOG.warning("SONATA function experiment generation not implemented.")
        return list()

    def _generate_service_experiments(self, base_service_obj, experiments):
        LOG.warning("SONATA service experiment generation not implemented.")
        return list()

    def _write(self, output_path, conf_obj_list):
        LOG.warning("SONATA write not implemented.")

    def _pack(self, output_path, conf_obj_list):
        LOG.warning("SONATA pack not implemented.")


class SonataService(object):

    @staticmethod
    def load(path):
        """
        Loads the service package contents from the given path.
        :param path: path to a folder with service package contents.
        :return: SonataService object.
        """
        # load manifest
        manifest = read_yaml(
            os.path.join(path, "META-INF/MANIFEST.MF"))
        # load nsd
        nsd = read_yaml(
            os.path.join(
                path,
                relative_path(manifest.get("entry_service_template"))))
        # load vnfds
        vnfd_list = list()
        for ctx in manifest.get("package_content"):
            if "function_descriptor" in ctx.get("content-type"):
                vnfd_list.append(
                    read_yaml(
                        os.path.join(path,
                                     relative_path(ctx.get("name")))))
        LOG.info(
            "Loaded SONATA service package contents. Service: '{}' ({} VNFDs).".format(
                nsd.get("name"), len(vnfd_list)))
        # create SonataServicePackage object
        return SonataService()  # TODO initialize service object


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


