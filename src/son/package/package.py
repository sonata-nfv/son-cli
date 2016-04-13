import logging
import coloredlogs
import sys
import urllib
import zipfile
from contextlib import closing
from pathlib import Path

import os
import shutil
import yaml
import pathlib
from jsonschema import validate
from jsonschema import ValidationError
from jsonschema import SchemaError
import validators
from urllib.request import URLError

from son.package.decorators import performance
from son.package.md5 import generate_hash
from son.workspace.project import Project
from son.workspace.workspace import Workspace
from son.package.catalogue_client import CatalogueClient

log = logging.getLogger(__name__)

class Packager(object):

    # ID of schema templates
    SCHEMA_PACKAGE_DESCRIPTOR = 'PD'
    SCHEMA_SERVICE_DESCRIPTOR = 'NSD'
    SCHEMA_FUNCTION_DESCRIPTOR = 'VNFD'

    def __init__(self, prj_path, workspace, dst_path=None, generate_pd=True, version="0.1"):
        # Log variable
        coloredlogs.install(level=workspace.log_level)
        self._version = version
        self._package_descriptor = None
        self._project_path = prj_path
        self._workspace = workspace
        self._catalogueClients = []
        self.schemas_local_master = workspace.dirs[Workspace.CONFIG_STR_SCHEMAS_LOCAL_MASTER]
        self.schemas_remote_master = workspace.dirs[Workspace.CONFIG_STR_SCHEMAS_REMOTE_MASTER]

        self.schemas = {}
        self.config_schema_locations()

        # Read catalogue servers from workspace config file and create clients
        for cat_address in workspace.catalogue_servers:
            self._catalogueClients.append(CatalogueClient(cat_address))

        # Keep track of VNF packaging referenced in NS
        self._ns_vnf_registry = {}

        # Keep a library of loaded schemas to avoid re-loading
        self._schemas_library = dict()
        # Clear and create package specific folder
        if generate_pd:

            if not dst_path:
                self._dst_path = os.path.join(self._project_path, "target")

            elif os.path.isdir(dst_path):   # dir exists?

                if len(os.listdir(dst_path)) > 0: # dir not empty?
                    log.error("Destination directory '{}' is not empty".format(os.path.abspath(dst_path)))
                    sys.stderr.write("ERROR: Destination directory '{}' is not empty\n"
                                     .format(os.path.abspath(dst_path)))
                    exit(1)

                self._dst_path = os.path.abspath(dst_path)

            else:
                self._dst_path = os.path.abspath(dst_path)

            if os.path.exists(self._dst_path):
                shutil.rmtree(self._dst_path)
                os.makedirs(self._dst_path, exist_ok=False)
            self.package_descriptor = self._project_path

    def config_schema_locations(self):
        self.schemas = \
            {self.SCHEMA_PACKAGE_DESCRIPTOR: {'local': os.path.join(self.schemas_local_master, 'pd-schema.yml'),
                                              'remote': self.schemas_remote_master +
                                              'package-descriptor/pd-schema.yml'},
             self.SCHEMA_SERVICE_DESCRIPTOR: {'local': os.path.join(self.schemas_local_master, 'nsd-schema.yml'),
                                              'remote': self.schemas_remote_master +
                                              'service-descriptor/nsd-schema.yml'},
             self.SCHEMA_FUNCTION_DESCRIPTOR: {'local': os.path.join(self.schemas_local_master, 'vnfd-schema.yml'),
                                               'remote': self.schemas_remote_master +
                                               'function-descriptor/vnfd-schema.yml'}}

    @property
    def package_descriptor(self):
        return self._package_descriptor

    @package_descriptor.setter
    def package_descriptor(self, prj_path):
        """
        Create and set the full package descriptor as a dictionary.
        It process the file by each individual section.
        :param prj_path: The project path to load the project yaml file
        """
        log.info('Loading Project file')
        prj_file = os.path.join(prj_path, Project.__descriptor_name__)
        with open(prj_file, 'r') as prj_file:
            prj = yaml.load(prj_file)

        log.info('Create General Description section')
        gds = self.package_gds(prj)

        package_content_section = []

        # Load and add service descriptor
        pcs = self.generate_nsd()
        if not pcs or len(pcs) == 0:
            log.error("Failed to package service descriptor")
            return
        package_content_section += pcs

        # Load and add the function descriptors
        pcs = self.generate_vnfds()
        if not pcs or len(pcs) == 0:
            log.error("Failed to package function descriptors")
            return
        package_content_section += pcs

        # Set the package descriptor
        self._package_descriptor = gds
        self._package_descriptor.update(dict(package_content=package_content_section))

        # Create the manifest folder and file
        meta_inf = os.path.join(self._dst_path, "META-INF")
        os.makedirs(meta_inf, exist_ok=True)
        with open(os.path.join(meta_inf, "MANIFEST.MF"), "w") as manifest:
            manifest.write(yaml.dump(self.package_descriptor, default_flow_style=False))

        # Validate PD
        log.debug("Validating Package Descriptor")
        try:
            validate(self._package_descriptor, self.load_schema(Packager.SCHEMA_PACKAGE_DESCRIPTOR))

        except ValidationError as e:
            log.error("Failed to validate Package Descriptor. Aborting package creation.")
            log.debug(e)
            return
        except SchemaError as e:
            log.error("Invalid Package Descriptor Schema.")
            log.debug(e)
            return

    @performance
    def package_gds(self, prj_descriptor):
        """
        Compile information for the general description section.
        This section is exclusively filled by the project descriptor
        file located on the root of every project.

        :param prj_descriptor: The file to gather all needed information.
        """
        gds_fields = ['group', 'name', 'version', 'maintainer', 'description']
        gds = dict()
        gds['descriptor_version'] = self._version

        errors = []
        for field in gds_fields:
            if field not in prj_descriptor.keys():
                errors.append(field)
            else:
                gds['package_' + field] = prj_descriptor[field]

        if errors:
            print('Please define {} on {}'.format(', '.join(errors), Project.__descriptor_name__),
                  file=sys.stderr)
            return False
        return gds

    @performance
    def generate_nsd(self, vendor=None):
        """
        Compile information for the service descriptor section.
        :param vendor:
        :return:
        """
        base_path = os.path.join(self._project_path, 'sources', 'nsd')
        if not os.path.isdir(base_path):
            log.error("Missing NS directory '{}'".format(base_path))
            return

        # Ensure that only one NS descriptor exists
        nsd_list = [file for file in os.listdir(base_path)
                    if os.path.isfile(os.path.join(base_path, file)) and file.endswith('yml') or file.endswith('yaml')]

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
        log.debug("Validating Service Descriptor NSD='{}'".format(nsd_filename))
        try:
            validate(nsd, self.load_schema(Packager.SCHEMA_SERVICE_DESCRIPTOR))

        except ValidationError as e:
            log.error("Failed to validate Service Descriptor NSD='{}'. Aborting package creation.".format(nsd_filename))
            log.debug(e)
            return
        except SchemaError as e:
            log.error("Invalid Service Descriptor Schema.")
            log.debug(e)
            return

        if vendor and nsd['vendor'] != vendor:
            self._log.warning(
                "You are adding a NS with different vendor, Project vendor={} and NS vendor={}".format(
                    vendor, nsd['vendor']))

        # Cycle through VNFs and register their names later dependency check
        if 'network_functions' in nsd:
            vnf_list = [vnf for vnf in nsd['network_functions'] if vnf['vnf_name']]
            for vnf in vnf_list:
                self.register_ns_vnf(get_vnf_id_full(vnf['vnf_vendor'], vnf['vnf_name'], vnf['vnf_version']))

        # Create SD location
        nsd = os.path.join(base_path, nsd_filename)
        sd_path = os.path.join(self._dst_path, "service_descriptor")
        os.makedirs(sd_path, exist_ok=True)
        # Copy NSD file
        sd = os.path.join(sd_path, nsd_filename)
        shutil.copyfile(nsd, sd)

        # Generate NSD package content entry
        pce = []
        pce_sd = dict()
        pce_sd["content-type"] = "application/sonata.service_descriptors"
        pce_sd["name"] = "/service_descriptors/{}".format(nsd_filename)
        pce_sd["md5"] = generate_hash(nsd)
        pce.append(pce_sd)

        return pce

    def generate_vnfds(self):
        """
        Compile information for the function descriptors.
        This function
        :return:
        """
        # Add VNFs from project source
        log.info("Packaging VNF descriptors from project source...")
        pcs = self.generate_project_source_vnfds(os.path.join(self._project_path, 'sources', 'vnf'))

        # Verify that all VNFs from NSD were packaged
        unpack_vnfs = self.get_unpackaged_ns_vnfs()
        if len(unpack_vnfs) > 0:
            # Load function descriptors (VNFDs) from external sources
            log.info("Solving dependencies for VNF descriptors...")
            if not self.load_external_vnfds(unpack_vnfs):
                log.error("Unable to solve all dependencies required by the service descriptor.")
                return

            log.info("Packaging VNF descriptors from external source...")
            pcs_ext = self.generate_external_vnfds(os.path.join(
                self._workspace.ws_root, self._workspace.dirs[Workspace.CONFIG_STR_CATALOGUE_VNF_DIR]), unpack_vnfs)

            if not pcs_ext or len(pcs_ext) == 0:
                return

            pcs += pcs_ext

            # Verify again if all VNFs were correctly packaged (if not, validation failed)
            unpack_vnfs = self.get_unpackaged_ns_vnfs()
            if len(unpack_vnfs) > 0:
                log.error("Unable to validate all VNFs required by the service descriptor.")
                return

        return pcs

    def load_external_vnfds(self, vnf_id_list):
        """
        This method is responsible to load all VNFs, required by the NS, that are not part of project source.
        VNFs can be loaded from the Workspace catalog or/and from the catalogue servers.
        :param vnf_id_list: List of VNF ID to solve
        :return: True for success, False for failure
        """
        log.debug("Loading the following VNF descriptors: {}".format(vnf_id_list))

        # Iterate through the VNFs required by the NS
        for vnf_id in vnf_id_list:

            log.debug("Probing workspace catalogue for VNF id='{}'...".format(vnf_id))

            # >> First, check if this VNF is in the workspace catalogue
            catalogue_path = os.path.join(self._workspace.ws_root,
                                          self._workspace.dirs[Workspace.CONFIG_STR_CATALOGUE_VNF_DIR],
                                          vnf_id)
            if os.path.isdir(catalogue_path):
                # Exists! Save catalogue path of this vnf for later packaging
                log.debug("Found VNF id='{}' in workspace catalogue '{}'".format(vnf_id, catalogue_path))
                continue

            log.debug("VNF id='{}' is not present in workspace catalogue. "
                      "Contacting catalogue servers...".format(vnf_id))
            # >> If not in WS catalogue, get the VNF from the catalogue servers!
            vnfd = self.load_vnf_from_catalogue_server(vnf_id)

            if not vnfd:
                log.warning("VNF id='{}' is not present in catalogue servers.".format(vnf_id))
                return False

            # Create dir to hold the retrieved VNF in workspace catalogue
            log.debug("VNF id='{}' retrieved from the catalogue servers. Loading to workspace cache.".format(vnf_id))
            os.mkdir(catalogue_path)
            vnfd_f = open(os.path.join(catalogue_path, vnfd['name'] + ".yml"), 'w')
            yaml.dump(vnfd, vnfd_f, default_flow_style=False)

        return True

    @performance
    def generate_project_source_vnfds(self, base_path, vendor=None):
        """
        Compile information for the list of VNFs
        This function iterates over the different VNF entries
        :param vendor: (TBD)
        :return:
        """
        vnf_folders = filter(lambda file: os.path.isdir(os.path.join(base_path, file)), os.listdir(base_path))
        pcs = []
        for vnf in vnf_folders:
            pc_entries = self.generate_vnfd_entry(os.path.join(base_path, vnf), vnf)
            if not pc_entries or len(pc_entries) == 0:
                continue
            for pce in pc_entries:
                pcs.append(pce)

        return pcs

    @performance
    def generate_external_vnfds(self, base_path, vnf_ids, vendor=None):
        vnf_folders = filter(lambda file: os.path.isdir(os.path.join(base_path, file)) and
                             file in vnf_ids, os.listdir(base_path))
        pcs = []
        for vnf in vnf_folders:
            pc_entries = self.generate_vnfd_entry(os.path.join(base_path, vnf), vnf)
            if not pc_entries or len(pc_entries) == 0:
                continue
            for pce in pc_entries:
                pcs.append(pce)

        return pcs

    def generate_vnfd_entry(self, base_path, vnf, vendor=None):
        """
        Compile information for a specific VNF.
        The VNF descriptor is validated and added to the package.
        VDU image files, referenced in the VNF descriptor, are added to the package.
        :param base_path: The path where the VNF file is located
        :param vnf: The VNF reference path
        :param vendor: (TBD)
        :return: The package content entries. One VNFD can have multiple entries (e.g. VDU images)
        """
        # Locate VNFD
        vnfd_list = [file for file in os.listdir(base_path)
                     if os.path.isfile(os.path.join(base_path, file)) and file.endswith('yml') or file.endswith('yaml')]

        # Validate number of Yaml files
        check = len(vnfd_list)
        if check == 0:
            log.error("Missing VNF descriptor file")
            return
        elif check > 1:
            log.warning("Multiple YAML descriptors found in '{}'. Ignoring path.".format(os.path.basename(base_path)))
            return
        else:
            with open(os.path.join(base_path, vnfd_list[0]), 'r') as _file:
                vnfd = yaml.load(_file)

        vnfd_path = os.path.join(os.path.basename(base_path), vnfd_list[0])

        # Validate VNFD
        log.debug("Validating VNF descriptor file='{}'".format(vnfd_path))
        try:
            validate(vnfd, self.load_schema(Packager.SCHEMA_FUNCTION_DESCRIPTOR))

        except ValidationError:
            log.exception("Failed to validate VNF descriptor file '{}'".format(vnfd_path))
            return

        except SchemaError:
            log.exception("Failed to validate VNF descriptor file '{}'".format(vnfd_path))
            return

        if vendor and vnfd['vendor'] != vendor:
            self._log.warning("You are adding a VNF with different group, Project vendor={} and VNF vendor={}"
                              .format(vendor, vnfd['vendor']))

        # Check if this VNF exists in the ns_vnf registry. If does not, cancel its packaging
        if not self.check_in_ns_vnf(get_vnf_id(vnfd)):
            log.warning("VNF id='{}' file='{}' is not referenced in the service descriptor."
                        "It will be excluded from the package".format(get_vnf_id(vnfd), vnfd_path))
            return

        pce = []
        # Create fd location
        fd_path = os.path.join(self._dst_path, "function_descriptors")
        os.makedirs(fd_path, exist_ok=True)

        # Copy VNFD file
        fd = os.path.join(fd_path, vnfd_list[0])
        shutil.copyfile(os.path.join(base_path, vnfd_list[0]), fd)

        # Generate VNFD Entry
        pce_fd = dict()
        pce_fd["content-type"] = "application/sonata.function_descriptor"
        pce_fd["name"] = "/function_descriptors/{}".format(vnfd_list[0])
        pce_fd["md5"] = generate_hash(fd)
        pce.append(pce_fd)

        if 'virtual_deployment_units' in vnfd:
            vdu_list = [vdu for vdu in vnfd['virtual_deployment_units'] if vdu['vm_image']]
            for vdu in vdu_list:

                # vm_image can be a local File, a local Dir, a URL or a URI
                vdu_image_path = vdu['vm_image']

                if validators.url(vdu_image_path):  # Check if is URL/URI. Can still be local (file:///...)
                    # TODO vm_image may be a URL
                    # What to do if vm_image is an URL. Download vm_image? Or about if the URL is private?
                    # Ignore for now!
                    return

                else:  # Check for URL local (e.g. file:///...)
                    ptokens = pathlib.Path(vdu_image_path).parts
                    if ptokens[0] == 'file:':  # URL to local file
                        bd = os.path.join(base_path, ptokens[1])

                    else:  # regular filename/path
                        bd = os.path.join(base_path, vdu['vm_image'])

                if os.path.exists(bd):  # local File or local Dir

                    if os.path.isfile(bd):
                        pce.append(self.__pce_img_gen__(base_path, vnf, vdu, vdu['vm_image'], dir_p='', dir_o=''))

                    elif os.path.isdir(bd):
                        img_format = 'raw' if not vdu['vm_image_format'] else vdu['vm_image_format']
                        for root, dirs, files in os.walk(bd):
                            dir_o = root[len(bd):]
                            dir_p = dir_o.replace(os.path.sep, "/")
                            for f in files:
                                if dir_o.startswith(os.path.sep):
                                    dir_o = dir_o[1:]
                                pce.append(self.__pce_img_gen__(root, vnf, vdu, f, dir_p=dir_p, dir_o=dir_o))

                else:  # Invalid vm_image
                    log.error("Cannot find vm_image={} referenced in [VNFD={}, VDU id={}]".format(
                        bd, vnfd_list[0], vdu['id']))
                    return

        return pce

    def __pce_img_gen__(self, bd, vnf, vdu, f, dir_p='', dir_o=''):
        pce = dict()
        img_format = 'raw' if not vdu['vm_image_format'] else vdu['vm_image_format']
        pce["content-type"] = "application/sonata.{}_files".format(img_format)
        pce["name"] = "/{}_files/{}{}/{}".format(img_format, vnf, dir_p, f)
        pce["md5"] = self.__pce_img_gen_fc__(pce, img_format, vnf, f, bd, dir_o)

        return pce

    def __pce_img_gen_fc__(self, pce, img_format, vnf, f, root, dir_o=''):
        fd_path = os.path.join("{}_files".format(img_format), vnf, dir_o)
        fd_path = os.path.join(self._dst_path, fd_path)
        os.makedirs(fd_path, exist_ok=True)
        fd = os.path.join(fd_path, f)
        shutil.copyfile(os.path.join(root, f), fd)
        return generate_hash(fd)

    def generate_package(self, name):
        """
        Generate the final package version.
        :param dst_path; The path were the package will be generated
        :param name: The name of the final version of the package, the project name will be used if no name provided
        """

        # Validate all needed information
        if not self._package_descriptor:
            self._log.error("Missing package descriptor. Failed to generate package.")
            return

        # Generate package file
        zip_name = os.path.join(self._dst_path, name + '.son')
        with closing(zipfile.ZipFile(zip_name, 'w')) as pck:
            for base, dirs, files in os.walk(self._dst_path):
                for file_name in files:
                    full_path = os.path.join(base, file_name)
                    relative_path = full_path[len(self._dst_path) + len(os.sep):]
                    if not full_path == zip_name:
                        pck.write(full_path, relative_path)

        log.info("Package generated successfully ({})".format(zip_name))

    def register_ns_vnf(self, vnf_id):
        """
        Add a vnf to the NS VNF registry.
        :param vnf_id:
        :return: True for successful registry. False if the VNF already exists in the registry.
        """
        if vnf_id in self._ns_vnf_registry:
            return False

        self._ns_vnf_registry[vnf_id] = False
        return True

    def check_in_ns_vnf(self, vnf_id):
        """
        Marks a VNF as packaged in the SD VNF registry
        :param vnf_id:
        :return:
        """
        if vnf_id not in self._ns_vnf_registry:
            return False

        self._ns_vnf_registry[vnf_id] = True
        return True

    def get_unpackaged_ns_vnfs(self):
        """
        Obtain the a list of VNFs that were referenced by NS but weren't packaged
        :return:
        """
        u_vnfs = []
        for vnf in self._ns_vnf_registry:
            if not self._ns_vnf_registry[vnf]:
                u_vnfs.append(vnf)

        return u_vnfs

    def load_vnf_from_catalogue_server(self, vnf_id):

        # Check if there are catalogue clients available
        if not len(self._catalogueClients) > 0:
            log.warning("No catalogue servers available! Please check the workspace configuration.")
            return

        # For now, perform sequential requests.
        # In the future, this should be parallel -> the first to arrive, the first to be consumed!
        for client in self._catalogueClients:

            log.debug("Contacting catalogue server '{}'...".format(client.base_url))
            # Check if catalogue server is alive!
            if not client.alive():
                log.warning("Catalogue server '{}' is not available.".format(client.base_url))
                continue

            vnfd = client.get_vnf(vnf_id)
            if not vnfd:
                continue
            return vnfd

        return


    def load_schema(self, template, reload=False):
        """
        Load schema from a local file or a remote URL.
        If the same schema was previously loaded and reload=False it will return the schema stored in cache. If
        reload=True it will force the reload of the schema.
        :param template: Name of local file or URL to remote schema
        :param reload: Force the reload, even if it was previously loaded
        :return: The loaded schema as a dictionary
        """
        # Check if template is already loaded and present in _schemas_library
        if template in self._schemas_library and not reload:
            log.debug("Loading previous stored schema={}".format(template))
            return self._schemas_library[template]                           # return previously loaded schema

        # Load Online Schema
        schema_addr = self.schemas[template]['remote']
        if validators.url(schema_addr):
            try:
                log.debug("Loading schema '{}' from remote location '{}'".format(template, schema_addr))
                # Load schema from remote source
                self._schemas_library[template] = load_remote_schema(schema_addr)

                # Update the corresponding local schema file
                write_local_schema(self.schemas_local_master, self.schemas[template]['local'],
                                   self._schemas_library[template])

                return self._schemas_library[template]

            except URLError:
                log.warning("Could not load schema '{}' from remote location '{}'".format(template, schema_addr))
        else:
            log.warning("Invalid schema URL '{}'".format(schema_addr))

        # Load Offline Schema
        schema_addr = self.schemas[template]['local']
        if os.path.isfile(schema_addr):
            try:
                log.debug("Loading schema '{}' from local file '{}'".format(template, schema_addr))
                self._schemas_library[template] = load_local_schema(schema_addr)
                return self._schemas_library[template]
            except FileNotFoundError:
                log.warning("Could not load schema '{}' from local file '{}'".format(template, schema_addr))
        else:
            log.warning("Schema file '{}' not found.".format(schema_addr))

        log.error("Failed to load schema '{}'".format(template))


def get_vnf_id(vnfd):
    return get_vnf_id_full(vnfd['vendor'], vnfd['name'], vnfd['version'])


def get_vnf_id_full(vnf_vendor, vnf_name, vnf_version):
    return vnf_vendor + '.' + vnf_name + '.' + vnf_version


def write_local_schema(schemas_root, filename, schema):
    """
    Writes a schema to a local file.
    :param schemas_root: The location of schema descriptor
    :param filename: The name of the schema file to be written.
    :param schema: The schema content as a dictionary.
    :return:
    """
    # Verify if local dir structure already exists! If not, create it.
    if not os.path.isdir(schemas_root):
        log.debug("Schema directory '{}' not found. Creating it.".format(schemas_root))
        os.mkdir(schemas_root)

    if os.path.isfile(filename):
        log.debug("Replacing schema file '{}'".format(filename))
    else:
        log.debug("Writing schema file '{}'".format(filename))

    schema_f = open(filename, 'w')
    yaml.dump(schema, schema_f)
    schema_f.close()


def load_local_schema(filename):
    """
    Search for a given template on the schemas folder inside the current package.
    :param filename: The name of the schema file to look for
    :return: The loaded schema as a dictionary
    """
    # Confirm that schema file exists
    if not os.path.isfile(filename):
        log.warning("Schema file '{}' does not exist.".format(filename))
        raise FileNotFoundError

    # Read schema file and return the schema as a dictionary
    schema_f = open(filename, 'r')
    schema = yaml.load(schema_f)
    assert isinstance(schema, dict), "Failed to load schema file '{}'. Not a dictionary.".format(filename)
    return schema


def load_remote_schema(template_url):
    """
    Retrieve a remote schema from the provided URL
    :param template_url: The URL of the required schema
    :return: The loaded schema as a dictionary
    """
    response = urllib.request.urlopen(template_url)
    tf = response.read().decode(response.headers.get_content_charset())
    schema = yaml.load(tf)
    assert isinstance(schema, dict)
    return schema


def __validate_directory__(paths):
    """
    Validates the given path, it first check if it's a directory,
    then validates if contains a specific identifier.

    :param paths: dictionary with path and path identifier
    """
    for path, file in paths.items():
        if not os.path.isdir(path) or file and not os.path.isfile(os.path.join(path, file)):
            print("'{}' is not a valid project directory".format(path), file=sys.stderr)
            return False
    return True


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Generate new sonata package")
    parser.add_argument("--workspace", help="Specify workspace to generate the package. If not specified "
                        "will assume '{}'".format(Workspace.DEFAULT_WORKSPACE_DIR),
                        required=False)
    parser.add_argument("--project",
                        help="create a new package based on the project at the specified location. If not specified "
                        "will assume the current directory '{}'".format(os.getcwd()), required=False)
    parser.add_argument("-d", "--destination", help="create the package on the specified location", required=False)
    parser.add_argument("-n", "--name", help="create the package with the specific name", required=False)

    args = parser.parse_args()

    if args.workspace:
        ws_root = args.workspace
    else:
        ws_root = Workspace.DEFAULT_WORKSPACE_DIR

    prj = args.project if args.project else os.getcwd()

    # Validate given arguments
    path_ids = dict()
    path_ids[ws_root] = Workspace.__descriptor_name__
    path_ids[prj] = Project.__descriptor_name__
    if not __validate_directory__(paths=path_ids):
        return

    # Obtain Workspace object
    workspace = Workspace.__create_from_descriptor__(ws_root)

    name = Path(prj).name if not args.name else args.name

    pck = Packager(prj, workspace, dst_path=args.destination)
    pck.generate_package(name)
