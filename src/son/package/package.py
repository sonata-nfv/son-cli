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

import logging
import os
import pathlib
import shutil
import sys
import zipfile
import coloredlogs
import requests
import validators
import yaml
import time
import atexit
from contextlib import closing
from son.validate.validate import Validator
from son.package.decorators import performance
from son.package.md5 import generate_hash
from son.workspace.project import Project
from son.workspace.workspace import Workspace
from son.schema.validator import SchemaValidator
from son.access.access import AccessClient

log = logging.getLogger(__name__)


class Packager(object):

    def __init__(self, workspace, project=None, services=None, functions=None,
                 dst_path=None, generate_pd=True, version="1.0"):

        # Assign parameters
        coloredlogs.install(level=workspace.log_level)
        self._version = version
        self._package_descriptor = None
        self._workspace = workspace
        self._project = project
        self._services = services
        self._functions = functions

        # Create a son-access client
        self._access = AccessClient(self._workspace,
                                    log_level=self._workspace.log_level)

        # Create a validator
        self._validator = Validator(workspace=workspace)
        self._validator.configure(syntax=True, integrity=False, topology=False)

        # Create a schema validator
        self._schema_validator = SchemaValidator(workspace)

        # Keep track of VNF packaging referenced in NS
        self._ns_vnf_registry = {}

        # location to write the package
        self._dst_path = dst_path if dst_path else '.'

        # temporary working directory
        self._workdir = '.package-' + str(time.time())

        # Specifies THE service template of this package
        self._entry_service_template = None

        # Keep a list of repositories and
        # catalogue servers that this package depend on.
        # This will be included in the Package Resolver Section
        self._package_resolvers = []

        # Keep a list of external artifact
        # dependencies that this package depends up on
        # This will be included in the Artifact Dependencies Section
        self._artifact_dependencies = []

        # States if this package is self-contained,
        # i.e. if contains all its relevant artifacts
        self._sealed = True

        # Clear and create package specific folder
        if generate_pd:
            self.init_package_skeleton()
            self.build_package()

    def init_package_skeleton(self):
        """
        Validate and initialize the destination folder
        for the creation of the package artifacts.
        """
        if os.path.isdir(self._workdir):
            log.error("Internal error. Temporary workdir already exists.")
            return

        # workdir
        os.mkdir(self._workdir)
        atexit.register(shutil.rmtree, os.path.abspath(self._workdir))

        # destination path
        if not os.path.isdir(self._dst_path):
            os.mkdir(self._dst_path)

    @property
    def package_descriptor(self):
        return self._package_descriptor

    def build_package(self):
        """
        Create and set the full package descriptor as a dictionary.
        It process the file by each individual section.
        """
        log.info('Create Package Content Section')
        package_content = self.package_pcs()

        log.info('Create Package Resolver Section')
        package_resolver = self.package_prs()

        log.info('Create Package Dependencies Section')
        package_dependencies = self.package_pds()

        log.info('Create Artifact Dependencies Section')
        artifact_dependencies = self.package_ads()

        # The general section must be created last,
        # some fields depend on prior processing
        log.info('Create General Description section')
        if self._project:
            general_description = self.package_gds(
                prj_descriptor=self._project.project_config)
        else:
            general_description = self.package_gds()

        if not general_description:
            log.error("Failed to package General Description Section.")
            return

        # Compile all sections in package descriptor
        self._package_descriptor = general_description

        if not package_content:
            log.error("Failed to package Package Content Section. "
                      "Could not find a network service and/or its "
                      "referenced function descriptors")
            self._package_descriptor = None
            return

        self._package_descriptor.update(package_content)
        self._package_descriptor.update(package_resolver)
        self._package_descriptor.update(package_dependencies)
        self._package_descriptor.update(artifact_dependencies)

        # Create the manifest folder and file
        meta_inf = os.path.join(self._workdir, "META-INF")
        os.makedirs(meta_inf, exist_ok=True)
        with open(os.path.join(meta_inf, "MANIFEST.MF"), "w") as manifest:
            manifest.write(yaml.dump(self.package_descriptor,
                                     default_flow_style=False))

    @performance
    def package_gds(self, prj_descriptor=None):
        """
        Compile information for the General Description Section.
        This section is exclusively filled by the project descriptor
        file located on the root of every project.
        """
        # List of mandatory fields to be included in the GDS
        gds_fields = ['vendor', 'name', 'version',
                      'maintainer', 'description']
        gds = dict()
        gds['descriptor_version'] = self._version
        gds['schema'] = self._schema_validator.get_remote_schema(
            SchemaValidator.SCHEMA_PACKAGE_DESCRIPTOR)

        gds['sealed'] = self._sealed
        if prj_descriptor:
            gds['entry_service_template'] = self._entry_service_template

            if 'package' not in prj_descriptor.keys():
                log.error("Please define 'package' section in {}"
                          .format(Project.__descriptor_name__))
                return

            errors = []
            for field in gds_fields:
                if field not in prj_descriptor['package'].keys():
                    errors.append(field)
                else:
                    gds[field] = prj_descriptor['package'][field]

            if errors:
                log.error('Please define {} in the package section of {}'
                          .format(', '.join(errors),
                                  Project.__descriptor_name__))
                return
        else:
            # TODO: what properties to set in a custom package? TBD...
            gds['vendor'] = 'custom'
            gds['name'] = 'package'
            gds['version'] = '1.0'
            gds['maintainer'] = 'developer'
            gds['description'] = 'custom generated package'

        return gds

    @performance
    def package_pcs(self):
        """
        Compile information for the Package Content Section.
        This section contains all the artifacts that are
        contained and shipped by the package.
        """
        pcs = []

        # Load and add service descriptor
        if self._project:
            nsd = self.generate_project_nsd()

            if not nsd or len(nsd) == 0:
                log.error("Failed to package service descriptor")
                return
            pcs += nsd
        elif self._services:
            nsds = self.generate_custom_nsds()
            if not nsds:
                log.error("Failed to package service descriptors")
                return
            pcs += nsds

        # Load and add the function descriptors
        if self._project:
            vnfds = self.generate_project_vnfds()
            if not vnfds or len(vnfds) == 0:
                log.error("Failed to package function descriptors")
                return
            pcs += vnfds
        elif self._functions:
            vnfds = self.generate_custom_vnfds()
            if not vnfds:
                log.error("Failed to package function descriptors")
                return
            pcs += vnfds

        return dict(package_content=pcs)

    @performance
    def package_prs(self):
        """
        Compile information for the Package Resolver Section.
        This section contains information about catalogues
        and repositories needed to resolve the dependencies
        specified in this package descriptor.
        """
        if len(self._package_resolvers) == 0:
            log.debug("There are no required Package Resolvers. "
                      "This section will not be included.")
            return dict()

        return dict(package_resolvers=self._package_resolvers)

    @performance
    def package_pds(self):
        """
        Compile information for the Package Dependencies
        Section. This section specifies additional packages
        that this package depends up on.
        """
        log.debug("There are no required Package Dependencies. "
                  "This section will not be included.")
        return dict()

    @performance
    def package_ads(self):
        """
        Compile information for the Artifact Dependencies
        Section. This section contains components that are
        not included in the package but are referenced in
        its descriptors. For instance, it includes the url
        of vm_images used by network functions.
        """
        if len(self._artifact_dependencies) == 0:
            log.debug("There are no required Artifact Dependencies. "
                      "This section will not be included.")
            return dict()

        return dict(artifact_dependencies=self._artifact_dependencies)

    def generate_project_nsd(self):
        """
        Compile information for the service descriptor section.
        """
        base_path = os.path.join(self._project.project_root, 'sources', 'nsd')
        if not os.path.isdir(base_path):
            log.error("Missing NS directory '{}'".format(base_path))
            return

        # Ensure that only one NS descriptor exists
        nsd_list = [file for file in os.listdir(base_path)
                    if os.path.isfile(os.path.join(base_path, file)) and
                    file.endswith(self._project.descriptor_extension)]

        check = len(nsd_list)

        if check == 0:
            log.error("Missing NS Descriptor file.")
            return
        elif check > 1:
            log.error("Only one NS Descriptor file is allowed.")
            return
        else:
            nsd_filename = nsd_list[0]
            with open(os.path.join(base_path, nsd_filename), 'r') as _file:
                nsd = yaml.load(_file)

        # Validate NSD
        log.debug("Validating Service Descriptor NSD='{}'"
                  .format(nsd_filename))

        if not self._validator.validate_service(os.path.join(base_path,
                                                             nsd_filename)):
            log.error("Failed to validate Service Descriptor '{}'. "
                      "Aborting package creation".format(nsd_filename))
            return

        # Cycle through VNFs and register their IDs for later dependency check
        if 'network_functions' in nsd:
            vnf_list = \
                [vnf for vnf in nsd['network_functions'] if vnf['vnf_name']]

            for vnf in vnf_list:
                self.register_ns_vnf(get_vnf_id_full(vnf['vnf_vendor'],
                                                     vnf['vnf_name'],
                                                     vnf['vnf_version']))

        # Create SD location
        nsd = os.path.join(base_path, nsd_filename)
        sd_path = os.path.join(self._workdir, "service_descriptors")
        os.makedirs(sd_path, exist_ok=True)

        # Copy service descriptor file
        sd = os.path.join(sd_path, nsd_filename)
        self.copy_descriptor_file(nsd, sd)

        # Generate NSD package content entry
        pce = []
        pce_sd = dict()
        pce_sd["content-type"] = "application/sonata.service_descriptor"
        pce_sd["name"] = "/service_descriptors/{}".format(nsd_filename)
        pce_sd["md5"] = generate_hash(sd)
        pce.append(pce_sd)

        # Specify the NSD as THE entry service template of package descriptor
        self._entry_service_template = pce_sd['name']

        return pce

    def generate_custom_nsds(self):
        """
        Compile information for the service descriptors, when creating a
        custom package.
        """
        log.info("Packaging service descriptors...")
        for nsd_filename in self._services:
            if not self._validator.validate_service(nsd_filename):
                log.error("Failed to package service '{}'"
                          .format(nsd_filename))
                return

        # Create SD location
        sd_path = os.path.join(self._workdir, "service_descriptors")
        os.makedirs(sd_path, exist_ok=True)

        # Copy service descriptors and generate their entry points
        pce = []
        for nsd_filename in self._services:
            nsd_basename = os.path.basename(nsd_filename)
            sd = os.path.join(sd_path, nsd_basename)
            self.copy_descriptor_file(nsd_filename, sd)
            pce_sd = dict()
            pce_sd["content-type"] = "application/sonata.service_descriptor"
            pce_sd["name"] = "/service_descriptors/{}".format(nsd_basename)
            pce_sd["md5"] = generate_hash(sd)
            pce.append(pce_sd)

        return pce

    def generate_project_vnfds(self):
        """
        Compile information for the function descriptors, when packaging an
        SDK project.
        """
        # Add VNFs from project source
        log.info("Packaging VNF descriptors from project source...")
        pcs = self.generate_project_source_vnfds(os.path.join(
            self._project.project_root, 'sources', 'vnf'))

        # Verify that all VNFs from NSD were packaged
        unpack_vnfs = self.get_unpackaged_ns_vnfs()
        if len(unpack_vnfs) > 0:
            # Load function descriptors (VNFDs) from external sources
            log.info("Solving dependencies for VNF descriptors...")
            if not self.load_external_vnfds(unpack_vnfs):
                log.error("Unable to solve all dependencies "
                          "required by the service descriptor.")
                return

            log.info("Packaging VNF descriptors from external source...")
            pcs_ext = self.generate_external_vnfds(os.path.join(
                self._workspace.workspace_root,
                self._workspace.vnf_catalogue_dir),
                unpack_vnfs)

            if not pcs_ext or len(pcs_ext) == 0:
                return

            pcs += pcs_ext

            # Verify again if all VNFs were correctly packaged
            unpack_vnfs = self.get_unpackaged_ns_vnfs()
            if len(unpack_vnfs) > 0:
                log.error("Unable to validate all VNFs "
                          "required by the service descriptor.")
                return

        return pcs

    def generate_custom_vnfds(self):
        """
        Compile information for the function descriptors, when creating a
        custom package.
        """
        log.info("Packaging VNF descriptors...")
        for vnfd_filename in self._functions:
            if not self._validator.validate_function(vnfd_filename):
                log.error("Failed to package function '{}'"
                          .format(vnfd_filename))
                return

        # Create FD location
        sd_path = os.path.join(self._workdir, "function_descriptors")
        os.makedirs(sd_path, exist_ok=True)

        # Copy function descriptors and generate their entry points
        pce = []
        for vnfd_filename in self._functions:
            vnfd_basename = os.path.basename(vnfd_filename)
            sd = os.path.join(sd_path, vnfd_basename)
            self.copy_descriptor_file(vnfd_filename, sd)
            pce_sd = dict()
            pce_sd["content-type"] = "application/sonata.function_descriptor"
            pce_sd["name"] = "/service_descriptors/{}".format(vnfd_basename)
            pce_sd["md5"] = generate_hash(sd)
            pce.append(pce_sd)

        return pce

    def load_external_vnfds(self, vnf_id_list):
        """
        This method is responsible to load all VNFs, required
        by the NS, that are not part of project source.
        VNFs can be loaded from the Workspace catalog or/and
        from the catalogue servers.

        :param vnf_id_list: List of VNF ID to solve
        :return: True for success, False for failure
        """
        log.debug("Loading the following VNF descriptors: {}"
                  .format(vnf_id_list))

        # Iterate through the VNFs required by the NS
        for vnf_id in vnf_id_list:

            log.debug("Probing workspace catalogue for VNF id='{}'..."
                      .format(vnf_id))

            # >> First, check if this VNF is in the workspace catalogue
            catalogue_path = os.path.join(
                self._workspace.workspace_root,
                self._workspace.vnf_catalogue_dir,
                vnf_id)

            if os.path.isdir(catalogue_path):
                # Exists! Save catalogue path of this vnf for later packaging
                log.debug("Found VNF id='{}' in workspace catalogue '{}'"
                          .format(vnf_id, catalogue_path))
                continue

            log.debug("VNF id='{}' is not present in workspace catalogue. "
                      "Contacting SP Catalogue...".format(vnf_id))

            # If not in WS catalogue, get the VNF from the SP Catalogues
            vnfd = None
            self.retrieve_external_vnf(vnf_id)
            if not vnfd:
                log.warning("VNF id='{}' is not present in SP Catalogue"
                            .format(vnf_id))
                return False

            # Create dir to hold the retrieved VNF in workspace catalogue
            log.debug("VNF id='{}' retrieved from the SP Catalogue. "
                      "Loading to workspace cache.".format(vnf_id))

            os.mkdir(catalogue_path)
            vnfd_f = open(os.path.join(catalogue_path,
                                       vnfd['name'] +
                                       "." +
                                       self._project.descriptor_extension),
                          'w')

            yaml.dump(vnfd, vnfd_f, default_flow_style=False)

        return True

    def generate_project_source_vnfds(self, base_path):
        """
        Compile information for the list of VNFs
        This function iterates over the different VNF entries
        :param base_path: base dir location of VNF descriptors
        :return:
        """
        vnf_folders = filter(
            lambda file: os.path.isdir(os.path.join(base_path, file)),
            os.listdir(base_path))

        pcs = []
        for vnf in vnf_folders:
            pc_entries = self.generate_vnfd_entry(
                os.path.join(base_path, vnf), vnf)

            if not pc_entries or len(pc_entries) == 0:
                continue
            for pce in iter(pc_entries):
                pcs.append(pce)

        return pcs

    def generate_external_vnfds(self, base_path, vnf_ids):
        vnf_folders = filter(
            lambda file: os.path.isdir(os.path.join(base_path, file)) and
            file in vnf_ids, os.listdir(base_path))

        pcs = []
        for vnf in vnf_folders:
            pc_entries = self.generate_vnfd_entry(os.path.join(
                base_path, vnf), vnf)

            if not pc_entries or len(pc_entries) == 0:
                continue
            for pce in iter(pc_entries):
                pcs.append(pce)

        return pcs

    def generate_vnfd_entry(self, base_path, vnf):
        """
        Compile information for a specific VNF.
        The VNF descriptor is validated and added to the
        package.VDU image files, referenced in the VNF
        descriptor, are added to the package.

        :param base_path: The path where the VNF file is located
        :param vnf: The VNF reference path
        :return: The package content entries.
        """

        # Locate VNFD
        vnfd_list = [file for file in os.listdir(base_path)
                     if os.path.isfile(os.path.join(base_path, file)) and
                     file.endswith(self._project.descriptor_extension)]

        # Validate number of Yaml files
        check = len(vnfd_list)
        if check == 0:
            log.warning("Missing VNF descriptor file in path '{}'. "
                        "A descriptor with '{}' extension should be "
                        "in this path"
                        .format(base_path,
                                self._project.descriptor_extension))
            return

        elif check > 1:
            log.warning("Multiple YAML descriptors found in '{}'. "
                        "Ignoring path.".format(os.path.basename(base_path)))
            return

        else:
            with open(os.path.join(base_path, vnfd_list[0]), 'r') as _file:
                vnfd = yaml.load(_file)

        vnfd_path = os.path.join(os.path.basename(base_path), vnfd_list[0])

        # Validate VNFD
        log.debug("Validating VNF descriptor file='{}'".format(vnfd_path))
        if not self._validator.validate_function(os.path.join(base_path,
                                                              vnfd_list[0])):
            log.exception("Failed to validate VNF descriptor '{}'"
                          .format(vnfd_path))
            return

        # Check if this VNF exists in the ns_vnf registry.
        # If does not, cancel its packaging
        if not self.check_in_ns_vnf(get_vnf_id(vnfd)):
            log.warning("VNF id='{}' file='{}' is not referenced in the "
                        "service descriptor. It will be excluded from "
                        "the package"
                        .format(get_vnf_id(vnfd), vnfd_path))
            return

        pce = []
        # Create fd location
        fd_path = os.path.join(self._workdir, "function_descriptors")
        os.makedirs(fd_path, exist_ok=True)

        # Copy the descriptor file
        fd = os.path.join(fd_path, vnfd_list[0])
        self.copy_descriptor_file(os.path.join(base_path, vnfd_list[0]), fd)

        # Generate VNFD Entry
        pce_fd = dict()
        pce_fd["content-type"] = "application/sonata.function_descriptor"
        pce_fd["name"] = "/function_descriptors/{}".format(vnfd_list[0])
        pce_fd["md5"] = generate_hash(fd)
        pce.append(pce_fd)

        if 'virtual_deployment_units' in vnfd:
            vdu_list = [vdu for vdu in vnfd['virtual_deployment_units']
                        if vdu['vm_image']]

            for vdu in vdu_list:

                # vm_image can be a local File, a local Dir,
                # a URL or a reference to docker image
                vdu_image_path = vdu['vm_image']

                if validators.url(vdu_image_path):  # Check if is URL/URI.
                    try:
                        # Check if the image URL exists with a short Timeout
                        requests.head(vdu_image_path, timeout=1)

                    except (requests.Timeout, requests.ConnectionError):
                        log.warning("Failed to verify the "
                                    "existence of vm_image '{}'"
                                    .format(vdu['vm_image']))

                    # Add image URL to artifact dependencies
                    self._add_artifact_dependency(
                        name=vnfd['name'] + '-' + vdu['id'] + '-vm_image',
                        vendor=vnfd['vendor'],
                        version=vnfd['version'],
                        url=vdu['vm_image'],
                        md5='02236f2ae558018ed14b5222ef1bd9f1')
                    # TODO: remote url must provide md5? This is dummy!

                    continue

                else:  # Check for URL local (e.g. file:///...)
                    ptokens = pathlib.Path(vdu_image_path).parts
                    if ptokens[0] == 'file:':  # URL to local file
                        bd = os.path.join(base_path, ptokens[1])

                    else:  # regular filename/path
                        bd = os.path.join(base_path, vdu['vm_image'])

                if os.path.exists(bd):  # local File or local Dir

                    if os.path.isfile(bd):
                        pce.append(self.__pce_img_gen__(
                            base_path, vnf, vdu, vdu['vm_image'],
                            dir_p='', dir_o=''))

                    elif os.path.isdir(bd):
                        for root, dirs, files in os.walk(bd):
                            dir_o = root[len(bd):]
                            dir_p = dir_o.replace(os.path.sep, "/")
                            for f in files:
                                if dir_o.startswith(os.path.sep):
                                    dir_o = dir_o[1:]
                                pce.append(self.__pce_img_gen__(
                                    root, vnf, vdu, f,
                                    dir_p=dir_p, dir_o=dir_o))

                elif vdu['vm_image_format'] == 'docker':
                    log.debug("Referenced vm_image is docker '{}'"
                              .format(vdu['vm_image']))

        return pce

    @staticmethod
    def copy_descriptor_file(src_descriptor, dst_descriptor):
        """
        Copy a descriptor file. Instead of just copying the file,
        it parses and reads the content of the source file, then it creates
        a new file and writes in it the digested content.
        :param src_descriptor:
        :param dst_descriptor:
        :return:
        """
        with open(src_descriptor, "r") as vnfd_file:
            vnf_content = yaml.load(vnfd_file)

        with open(dst_descriptor, "w") as vnfd_file:
            vnfd_file.write(yaml.dump(vnf_content, default_flow_style=False))

    def __pce_img_gen__(self, bd, vnf, vdu, f, dir_p='', dir_o=''):
        pce = dict()
        img_format = 'raw' \
            if not vdu['vm_image_format'] \
            else vdu['vm_image_format']

        pce["content-type"] = "application/sonata.{}_files".format(img_format)
        pce["name"] = "/{}_files/{}{}/{}".format(img_format, vnf, dir_p, f)
        pce["md5"] = self.__pce_img_gen_fc__(img_format, vnf, f, bd, dir_o)

        return pce

    def __pce_img_gen_fc__(self, img_format, vnf, f, root, dir_o=''):
        fd_path = os.path.join("{}_files".format(img_format), vnf, dir_o)
        fd_path = os.path.join(self._workdir, fd_path)
        os.makedirs(fd_path, exist_ok=True)
        fd = os.path.join(fd_path, f)
        shutil.copyfile(os.path.join(root, f), fd)
        return generate_hash(fd)

    def generate_package(self, name):
        """
        Generate the final package version.
        :param name: The name of the final version of the package,
        the project name will be used if no name provided
        """

        # Validate all needed information
        if not self._package_descriptor:
            log.critical("Missing package descriptor. "
                         "Failed to generate package.")
            exit(1)

        if not name:
            name = self._package_descriptor['vendor'] + "." + \
                self._package_descriptor['name'] + "." + \
                self._package_descriptor['version']

        # Generate package file
        zip_name = os.path.join(self._dst_path, name + '.son')
        with closing(zipfile.ZipFile(zip_name, 'w')) as pck:
            for base, dirs, files in os.walk(self._workdir):
                for file_name in files:
                    full_path = os.path.join(base, file_name)
                    relative_path = \
                        full_path[len(self._workdir) + len(os.sep):]

                    if not full_path == zip_name:
                        pck.write(full_path, relative_path)

        # Validate PD
        log.debug("Validating Package")
        if not self._validator.validate_package(zip_name):
            log.debug("Failed to validate Package Descriptor. "
                      "Aborting package creation.")
            self._package_descriptor = None
            return

        package_md5 = generate_hash(zip_name)
        log.info("Package generated successfully.\nFile: {}\nMD5: {}\n"
                 .format(os.path.abspath(zip_name), package_md5))

    def register_ns_vnf(self, vnf_id):
        """
        Add a vnf to the NS VNF registry.
        :param vnf_id:
        :return: True for successful registry.
                 False if the VNF already exists in the registry.
        """
        if vnf_id in self._ns_vnf_registry:
            return False

        self._ns_vnf_registry[vnf_id] = False
        return True

    def check_in_ns_vnf(self, vnf_id):
        """Marks a VNF as packaged in the SD VNF registry."""
        if vnf_id not in self._ns_vnf_registry:
            return False

        self._ns_vnf_registry[vnf_id] = True
        return True

    def get_unpackaged_ns_vnfs(self):
        """
        Obtain the a list of VNFs that were referenced
        by NS but weren't packaged.
        """
        u_vnfs = []
        for vnf in self._ns_vnf_registry:
            if not self._ns_vnf_registry[vnf]:
                u_vnfs.append(vnf)

        return u_vnfs

    def retrieve_external_vnf(self, descriptor_id):
        """
        Retrieve descriptor from the service Platform catalogue.
        It will loop through available Service Plaforms to retrieve the
        required descriptor
        :return: descriptor content
        """
        # first, contact the default platform
        vnfd = self._access.pull_resource('functions',
                                          identifier=descriptor_id,
                                          uuid=False)
        if vnfd:
            return vnfd

        # if not retrieved, loop through remaining platforms
        for platform, p_id in self._workspace.service_platforms.items():
            # ignore default platform
            if p_id == self._workspace.default_service_platform:
                continue
            vnfd = self._access.pull_resource('functions',
                                              identifier=descriptor_id,
                                              uuid=False,
                                              platform_id=p_id)
            if vnfd:
                return vnfd

    def _add_package_resolver(self, name, username='username',
                              password='password'):

        log.debug("Adding package resolver entry '{}'".format(name))

        # Check if already included
        for pr_entry in self._package_resolvers:
            if pr_entry['name'] == name:
                log.debug("Package resolver entry '{}' "
                          "was previously added. Ignoring."
                          .format(name))
                return

        pr_entry = {'name': name,
                    'credentials': {
                        'username': username,
                        'password': password
                    }}

        self._package_resolvers.append(pr_entry)

    def _add_artifact_dependency(self, name, vendor, version, url, md5,
                                 username='username', password='password'):

        log.debug("Adding artifact dependency entry '{}'".format(name))

        # Check if already included
        for ad_entry in self._artifact_dependencies:
            if ad_entry['name'] == name:
                log.debug("Artifact dependency entry '{}' "
                          "was previously added. Ignoring."
                          .format(name))
                return

        ad_entry = {'name': name,
                    'vendor': vendor,
                    'version': version,
                    'url': url,
                    'md5': md5,
                    'credentials': {
                        'username': username,
                        'password': password
                    }}
        self._artifact_dependencies.append(ad_entry)

        # Set package sealed to false as it will not be self-contained
        self._sealed = False


def get_vnf_id(vnfd):
    return get_vnf_id_full(vnfd['vendor'], vnfd['name'], vnfd['version'])


def get_vnf_id_full(vnf_vendor, vnf_name, vnf_version):
    return vnf_vendor + '.' + vnf_name + '.' + vnf_version


def __validate_directory__(paths):
    """
    Validates the given path, it first check if it's a directory,
    then validates if contains a specific identifier.

    :param paths: dictionary with path and path identifier
    """
    for path, file in paths.items():
        if not os.path.isdir(path) or file and \
                not os.path.isfile(os.path.join(path, file)):
            print("'{}' is not a valid workspace or project directory"
                  .format(path), file=sys.stderr)
            return False

    return True


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="Generate new sonata package")

    parser.add_argument(
        "--workspace",
        help="Specify workspace to generate the package. If not specified "
             "will assume '{}'".format(Workspace.DEFAULT_WORKSPACE_DIR),
        required=False)

    exclusive_parser = parser.add_mutually_exclusive_group(
        required=True
    )

    exclusive_parser.add_argument(
        "--project",
        dest="project",
        help="create a new package based on the project at the specified "
             "location. If not specified will assume current directory '{}'"
             .format(os.getcwd()),
        required=False)

    exclusive_parser.add_argument(
        "--custom",
        dest="custom",
        help="Create a custom package. Contents and descriptors can be added "
             "using the '--service' and '--function' arguments.",
        action="store_true",
        required=False
    )
    parser.add_argument(
        "--service",
        dest="service",
        nargs='*',
        help="Only applicable to custom packages. Add a service descriptor "
             "to the package. Multiple services may be specified separated "
             "with a space",
        required=False
    )
    parser.add_argument(
        "--function",
        dest="function",
        nargs='*',
        help="Only applicable to custom packages. Add a function descriptor "
             "to the package. Multiple functions may be specified separated "
             "with a space",
        required=False
    )
    parser.add_argument(
        "-d", "--destination",
        help="create the package on the specified location",
        required=False)

    parser.add_argument(
        "-n", "--name",
        help="create the package with the specific name",
        required=False)

    args = parser.parse_args()

    if args.workspace:
        ws_root = args.workspace
    else:
        ws_root = Workspace.DEFAULT_WORKSPACE_DIR

    # Obtain Workspace object
    workspace = Workspace.__create_from_descriptor__(ws_root)

    prj_root = args.project if args.project else os.getcwd()

    if args.project:

        # Validate given arguments
        path_ids = dict()
        path_ids[ws_root] = Workspace.__descriptor_name__
        path_ids[prj_root] = Project.__descriptor_name__
        if not __validate_directory__(paths=path_ids):
            return

        project = Project.__create_from_descriptor__(workspace, prj_root)

        pck = Packager(workspace, project=project, dst_path=args.destination)
        pck.generate_package(args.name)

    elif args.custom:

        if not (args.service or args.function):
            log.error("To create a custom package, the arguments '--service' "
                      "and/or '--function' must be used.")
            exit(1)

        pck = Packager(workspace, services=args.service,
                       functions=args.function, dst_path=args.destination)
        pck.generate_package(args.name)
