import logging
import sys
import urllib
import zipfile
from contextlib import closing
from pathlib import Path

import os
import pkg_resources
import shutil
import yaml
from jsonschema import validate
import validators

from son.package.decorators import performance
from son.package.md5 import generate_hash
from son.workspace.project import Project
from son.workspace.workspace import Workspace

log = logging.getLogger(__name__)


class Packager(object):

    # Master URL location for schemas
    schemas_master_url = 'https://raw.githubusercontent.com/sonata-nfv/son-schema/master/'

    # References to remote schemas
    remote_schemas = {
        'PD': schemas_master_url + 'package-descriptor/pd-schema.yml',
        'NSD': schemas_master_url + 'service-descriptor/nsd-schema.yml',
        'VNFD': schemas_master_url + 'function-descriptor/vnfd-schema.yml'
    }

    # References to local file schemas
    local_schemas = {
        'PD': 'pd-schema.yaml',
        'NSD': 'nsd-schema.yaml',
        'VNFD': 'vnfd-schema.yaml'
    }

    def __init__(self, prj_path, dst_path=None, generate_pd=True, version="0.1"):
        # Log variable
        logging.basicConfig(level=logging.DEBUG)
        self._log = logging.getLogger(__name__)

        self._version = version
        self._package_descriptor = None

        self._project_path = prj_path

        # Keep track of VNF packaging referenced in NS
        self._ns_vnf_registry = {}

        # Keep a library of loaded schemas to avoid re-loading
        self._schemas_library = dict()

        # Clear and create package specific folder
        if generate_pd:
            self._dst_path = os.path.join(self._project_path, "target") if not dst_path else dst_path
            if os.path.exists(self._dst_path):
                shutil.rmtree(self._dst_path)
                os.makedirs(self._dst_path, exist_ok=False)
            self.package_descriptor = self._project_path

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

        # Add service descriptor
        pcs = self.generate_nsd()
        if pcs is None:
            return
        package_content_section += pcs

        # Add function descriptors
        pcs = self.generate_vnfds()
        if pcs is None:
            return
        package_content_section += pcs

        # Verify that all VNFs from NSD were packaged
        unpack_vnfs = self.get_unpackaged_sd_vnfs()
        if len(unpack_vnfs) > 0:
            log.error("Failed to package the following VNFs={}".format(unpack_vnfs))
            return

        # Set the package descriptor
        self._package_descriptor = gds
        self._package_descriptor.update(dict(package_content=package_content_section))

        # Create the manifest folder and file
        meta_inf = os.path.join(self._dst_path, "META-INF")
        os.makedirs(meta_inf, exist_ok=True)
        with open(os.path.join(meta_inf, "MANIFEST.MF"), "w") as manifest:
            manifest.write(yaml.dump(self.package_descriptor, default_flow_style=False))

        validate(self._package_descriptor, self.load_schema(Packager.remote_schemas['PD']))

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
    def generate_nsd(self, group=None):
        """
        Compile information for the service descriptor section.
        :param group:
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
        validate(nsd, self.load_schema(Packager.remote_schemas['NSD']))
        if group and nsd['ns_group'] != group:
            self._log.warning(
                "You are adding a NS with different group, Project group={} and NS group={}".format(
                    group, nsd['ns_group']))

        # Cycle through VNFs and register their names for later verification
        if 'network_functions' in nsd:
            vnf_list = [vnf for vnf in nsd['network_functions'] if vnf['vnf_name']]
            for vnf in vnf_list:
                self.register_sd_vnf(vnf['vnf_name'])

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

    @performance
    def generate_vnfds(self, group=None):
        """
        Compile information for the list of VNFs
        This function iterates over the different VNF entries
        :param group: (TBD)
        :return:
        """
        base_path = os.path.join(self._project_path, 'sources', 'vnf')
        vnf_folders = filter(lambda file: os.path.isdir(os.path.join(base_path, file)), os.listdir(base_path))
        pcs = []
        for vnf in vnf_folders:
            for pce in self.generate_vnfd_entry(os.path.join(base_path, vnf), vnf):
                pcs.append(pce)
        return pcs

    def generate_vnfd_entry(self, base_path, vnf, group=None):
        """
        Compile information for a specific VNF.
        The VNF descriptor is validated and added to the package.
        VDU image files, referenced in the VNF descriptor, are added to the package.
        :param base_path: The path where the VNF file is located
        :param vnf: The VNF reference path
        :param group: (TBD)
        :return:
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
            log.error("Only one yaml file per VNF source folder allowed")
            return
        else:
            with open(os.path.join(base_path, vnfd_list[0]), 'r') as _file:
                vnfd = yaml.load(_file)

        # Validate VNFD
        validate(vnfd, self.load_schema(Packager.remote_schemas['VNFD']))
        if group and vnfd['vnf_group'] != group:
            self._log.warning(
                "You are adding a VNF with different group, Project group={} and VNF group={}".format(
                    group, vnfd['vnf_group']))

        # Check if this VNF exists in the SD VNF registry. If does not, cancel its packaging
        if not self.check_in_sd_vnf(vnfd['vnf_name']):
            log.warning('VNF with name={} is not referenced in the service descriptor. '
                        'It will be excluded from the package'.format(vnfd['vnf_name']))
            return []

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
                bd = os.path.join(base_path, vdu['vm_image'])
                # vm_image can be a local File, a local Dir or a URL

                if os.path.exists(bd):  # local File or local Dir

                    if os.path.isfile(bd):
                        pce.append(self.__pce_img_gen__(base_path, vnf, vdu, vdu['vm_image'], dir_p='', dir_o=''))
                    elif os.path.isdir(bd):
                        img_format = 'raw' if not vdu['vm_image_format'] else vdu['vm_image_format']
                        bp = os.path.join(base_path, vdu['vm_image'])
                        for root, dirs, files in os.walk(bp):
                            dir_o = root[len(bp):]
                            dir_p = dir_o.replace(os.path.sep, "/")
                            for f in files:
                                if dir_o.startswith(os.path.sep):
                                    dir_o = dir_o[1:]
                                pce.append(self.__pce_img_gen__(root, vnf, vdu, f, dir_p=dir_p, dir_o=dir_o))

                    # TODO vm_image may be a URL
                    # What to do if vm_image is an URL. Download vm_image? Or about if the URL is private?
                    # Ignore for now!

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
            self._log.error("Missing package descriptor")
            return

        # Generate package file
        zip_name = os.path.join(self._dst_path, name + '.zip')
        with closing(zipfile.ZipFile(zip_name, 'w')) as pck:
            for base, dirs, files in os.walk(self._dst_path):
                for file_name in files:
                    full_path = os.path.join(base, file_name)
                    relative_path = full_path[len(self._dst_path) + len(os.sep):]
                    if not full_path == zip_name:
                        pck.write(full_path, relative_path)

    def register_sd_vnf(self, vnf_name):
        """
        Add a vnf to the SD VNF registry.
        :param vnf_name:
        :return: True for successful registry. False if the VNF already exists in the registry.
        """
        if vnf_name in self._ns_vnf_registry:
            return False

        self._ns_vnf_registry[vnf_name] = False
        return True

    def check_in_sd_vnf(self, vnf_name):
        """
        Marks a VNF as packaged in the SD VNF registry
        :param vnf_name:
        :return:
        """
        if vnf_name not in self._ns_vnf_registry:
            return False

        self._ns_vnf_registry[vnf_name] = True
        return True

    def get_unpackaged_sd_vnfs(self):
        """
        Obtain the a list of VNFs that were referenced by NS but weren't packaged
        :return:
        """
        u_vnfs = []
        for vnf in self._ns_vnf_registry:
            if not self._ns_vnf_registry[vnf]:
                u_vnfs.append(vnf)

        return u_vnfs

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
            return self._schemas_library[template]                           # return previously loaded schema

        # Check if template is a link to remote URL or local file schema
        if validators.url(template):
            self._schemas_library[template] = load_remote_schema(template)   # load remote schema

        elif pkg_resources.resource_exists(__name__, os.path.join('templates', template)):
            self._schemas_library[template] = load_local_schema(template)    # load local schema

        else:
            log.error("Failed to load schema={}. Invalid schema file or address.".format(template))
            return

        return self._schemas_library[template]


def load_local_schema(template):
    """
    Search for a given template on the schemas folder inside the current package.
    :param template: The name of the template to look for
    :return: The loaded schema as a dictionary
    """
    rp = __name__
    path = os.path.join('templates', template)
    tf = pkg_resources.resource_string(rp, path)
    schema = yaml.load(tf)
    assert isinstance(schema, dict)
    return schema


def load_remote_schema(template_url):
    """
    Retrieve a remote schema from the provided URL
    :param template_url: The URL of the required schema
    :return: The loaded schema as a dictionary
    """
    with urllib.request.urlopen(template_url) as response:
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
            print("{} must be a directory".format(path), file=sys.stderr)
            return False
    return True


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Generate new sonata package")
    parser.add_argument("--workspace", help="Specify workspace to generate the package", required=True)
    parser.add_argument("--project",
                        help="create a new package based on the project at the specified location", required=False)
    parser.add_argument("-d", "--destination", help="create the package on the specified location", required=False)
    parser.add_argument("-n", "--name", help="create the package with the specific name", required=False)

    log.debug("parsing arguments")
    args = parser.parse_args()
    ws = args.workspace
    prj = args.project if args.project else os.getcwd()

    # Validate given arguments
    path_ids = dict()
    path_ids[ws] = Workspace.__descriptor_name__
    path_ids[prj] = Project.__descriptor_name__
    if not __validate_directory__(paths=path_ids):
        return

    name = Path(prj).name if not args.name else args.name

    pck = Packager(prj, dst_path=args.destination)
    pck.generate_package(name)
