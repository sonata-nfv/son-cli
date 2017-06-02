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

import os
import inspect
import logging
import uuid

import coloredlogs
import networkx as nx
import zipfile
import time
import shutil
import atexit
import errno
import yaml
from son.validate import event
from son.validate.event import EventLogger
from contextlib import closing
from son.package.md5 import generate_hash
from son.schema.validator import SchemaValidator
from son.workspace.workspace import Workspace, Project
from son.validate.storage import DescriptorStorage
from son.validate.util import read_descriptor_files, list_files, strip_root, \
    build_descriptor_id
from Crypto.PublicKey import RSA
from Crypto.Hash import SHA256

log = logging.getLogger(__name__)
evtlog = event.get_logger('validator.events')


class Validator(object):

    def __init__(self, workspace=None):
        """
        Initialize the Validator.
        A workspace may be provided for an easy parameter configuration,
        such as location and extension of descriptors, verbosity level, etc.
        :param workspace: SONATA workspace object
        """
        self._workspace = workspace
        self._syntax = True
        self._integrity = True
        self._topology = True

        # create "virtual" workspace if not provided (don't actually create
        # file structure)
        if not self._workspace:
            self._workspace = Workspace('.', log_level='info')

        # load configurations from workspace
        self._dext = self._workspace.default_descriptor_extension
        self._dpath = '.'
        self._log_level = self._workspace.log_level

        # for package signature validation
        self._pkg_signature = None
        self._pkg_pubkey = None

        # configure logs
        coloredlogs.install(level=self._log_level)

        # descriptors storage
        self._storage = DescriptorStorage()

        # syntax validation
        self._schema_validator = SchemaValidator(self._workspace)

        # reset event logger
        evtlog.reset()

        self.evtid = None

        self._fwgraphs = dict()

    @property
    def errors(self):
        return EventLogger.normalize(evtlog.errors)

    @property
    def error_count(self):
        """
        Provides the number of errors given during validation.
        """
        return len(self.errors)

    @property
    def warnings(self):
        return EventLogger.normalize(evtlog.warnings)

    @property
    def warning_count(self):
        """
        Provides the number of warnings given during validation.
        """
        return len(self.warnings)

    @property
    def storage(self):
        """
        Provides access to the stored resources during validation process.
        :return: 
        """
        return self._storage

    @property
    def dpath(self):
        return self._dpath

    @dpath.setter
    def dpath(self, value):
        self._dpath = value

    def configure(self, syntax=None, integrity=None, topology=None,
                  dpath=None, dext=None, debug=None, pkg_signature=None,
                  pkg_pubkey=None):
        """
        Configure parameters for validation. It is recommended to call this
        function before performing a validation.
        :param syntax: specifies whether to validate syntax
        :param integrity: specifies whether to validate integrity
        :param topology: specifies whether to validate network topology
        :param dpath: directory to search for function descriptors (VNFDs)
        :param dext: extension of descriptor files (default: 'yml')
        :param debug: increase verbosity level of logger
        :param pkg_signature: String package signature to be validated
        :param pkg_pubkey: String package public key to verify signature
        """
        # assign parameters
        if syntax is not None:
            self._syntax = syntax
        if integrity is not None:
            self._integrity = integrity
        if topology is not None:
            self._topology = topology
        if dext is not None:
            self._dext = dext
        if dpath is not None:
            self._dpath = dpath
        if debug is True:
            self._workspace.log_level = 'debug'
            coloredlogs.install(level='debug')
        if debug is False:
            self._workspace.log_level = 'info'
            coloredlogs.install(level='info')
        if pkg_signature is not None:
            self._pkg_signature = pkg_signature
        if pkg_pubkey is not None:
            self._pkg_pubkey = pkg_pubkey

    def _assert_configuration(self):
        """
        Ensures that the current configuration is compatible with the
        validation to perform. If issues are found the application is
        interrupted with the appropriate error.
        This is an internal function which must be invoked only by:
            - 'validate_package'
            - 'validate_project'
            - 'validate_service'
            - 'validate_function'
        """
        # ensure this function is called by specific functions
        caller = inspect.stack()[1][3]
        if caller != 'validate_function' and caller != 'validate_service' and \
           caller != 'validate_project' and caller != 'validate_package':
            log.error("Cannot assert a correct configuration. Validation "
                      "scope couldn't be determined. Aborting")
            return

        # general rules - apply to all validations
        if self._integrity and not self._syntax:
            log.error("Cannot validate integrity without validating syntax "
                      "first. Aborting.")
            return

        if self._topology and not self._integrity:
            log.error("Cannot validate topology without validating integrity "
                      "first. Aborting.")
            return

        if not self._syntax:
            log.error("Nothing to validate. Aborting.")
            return

        if caller == 'validate_package':
            pass

        elif caller == 'validate_project':
            pass

        elif caller == 'validate_service':
            # check SERVICE validation parameters
            if (self._integrity or self._topology) and not \
               (self._dpath and self._dext):
                log.error("Invalid validation parameters. To validate the "
                          "integrity or topology of a service both "
                          "'--dpath' and '--dext' parameters must be "
                          "specified.")
                return

        elif caller == 'validate_function':
            pass

        return True

    def validate_package(self, package):
        """
        Validate a SONATA package.
        By default, it performs the following validations: syntax, integrity
        and network topology.
        :param package: SONATA package filename
        :return: True if all validations were successful, False otherwise
        """
        if not self._assert_configuration():
            return

        self.evtid = package

        log.info("Validating package '{0}'".format(os.path.abspath(package)))

        # check if package is packed in the correct format
        if not zipfile.is_zipfile(package):
            evtlog.log("Invalid SONATA package '{}'".format(package),
                       self.evtid,
                       'evt_package_format_invalid')
            return

        package_dir = '.' + str(time.time())
        with closing(zipfile.ZipFile(package, 'r')) as pkg:
            # extract package contents
            pkg.extractall(package_dir)

            # set folder for deletion when program exits
            atexit.register(shutil.rmtree, package_dir)

        # validate package file structure
        if not self._validate_package_struct(package_dir):
            evtlog.log("Invalid SONATA package structure '{}'".format(package),
                       self.evtid,
                       'evt_package_struct_invalid')
            return

        # validate package signature (optional)
        if (self._pkg_signature and self._pkg_pubkey) and (
                not self.validate_package_signature(package,
                                                    self._pkg_signature,
                                                    self._pkg_pubkey)):
            evtlog.log("Invalid signature of package '{}'".format(package),
                       self.evtid,
                       'evt_package_signature_invalid')
            return

        pd_filename = os.path.join(package_dir, 'META-INF', 'MANIFEST.MF')
        package = self._storage.create_package(pd_filename)

        if self._syntax and not self._validate_package_syntax(package):
            return

        if self._integrity and \
                not self._validate_package_integrity(package, package_dir):
            return

        return True

    def validate_project(self, project):
        """
        Validate a SONATA project.
        By default, it performs the following validations: syntax, integrity
        and network topology.
        :param project: SONATA project
        :return: True if all validations were successful, False otherwise
        """
        if not self._assert_configuration():
            return

        # consider cases when project is a path
        if type(project) is not Project and os.path.isdir(project):
            if not self._workspace:
                log.error("Workspace not defined. Unable to validate project")
                return

            project = Project.__create_from_descriptor__(self._workspace,
                                                         project)

        if type(project) is not Project:
            return

        log.info("Validating project '{0}'".format(project.project_root))
        log.info("... syntax: {0}, integrity: {1}, topology: {2}"
                 .format(self._syntax, self._integrity, self._topology))

        # retrieve project configuration
        self._dpath = project.vnfd_root
        self._dext = project.descriptor_extension

        # load all project descriptors present at source directory
        log.debug("Loading project service")
        nsd_file = Validator._load_project_service_file(project)
        if not nsd_file:
            return

        return self.validate_service(nsd_file)

    def validate_service(self, nsd_file):
        """
        Validate a SONATA service.
        By default, it performs the following validations: syntax, integrity
        and network topology.
        :param nsd_file: service descriptor filename
        :return: True if all validations were successful, False otherwise
        """
        if not self._assert_configuration():
            return

        log.info("Validating service '{0}'".format(nsd_file))
        log.info("... syntax: {0}, integrity: {1}, topology: {2}"
                 .format(self._syntax, self._integrity, self._topology))

        service = self._storage.create_service(nsd_file)
        if not service:
            evtlog.log("Failed to read the service descriptor of file '{}'"
                       .format(nsd_file),
                       nsd_file,
                       'evt_service_invalid_descriptor')
            return

        # validate service syntax
        if self._syntax and not self._validate_service_syntax(service):
            return

        if self._integrity and not self._validate_service_integrity(service):
            return

        if self._topology and not self._validate_service_topology(service):
            return

        return True

    def validate_function(self, vnfd_path):
        """
        Validate one or multiple SONATA functions (VNFs).
        By default, it performs the following validations: syntax, integrity
        and network topology.
        :param vnfd_path: function descriptor (VNFD) filename or
                          a directory to search for VNFDs
        :return: True if all validations were successful, False otherwise
        """
        if not self._assert_configuration():
            return

        # validate multiple VNFs
        if os.path.isdir(vnfd_path):
            log.info("Validating functions in path '{0}'".format(vnfd_path))

            vnfd_files = list_files(vnfd_path, self._dext)
            for vnfd_file in vnfd_files:
                if not self.validate_function(vnfd_file):
                    return
            return True

        log.info("Validating function '{0}'".format(vnfd_path))
        log.info("... syntax: {0}, integrity: {1}, topology: {2}"
                 .format(self._syntax, self._integrity, self._topology))

        function = self._storage.create_function(vnfd_path)
        if not function:
            evtlog.log("Couldn't store VNF of file '{0}'".format(vnfd_path),
                       vnfd_path,
                       'evt_function_invalid_descriptor')
            return

        if self._syntax and not self._validate_function_syntax(function):
            return

        if self._integrity and not self._validate_function_integrity(function):
            return

        if self._topology and not self._validate_function_topology(function):
            return

        return True

    def _validate_package_struct(self, package_dir):
        """
        Validate the file structure of a SONATA package.
        :param package_dir: directory of extracted package
        :return: True if successful, False otherwise
        """
        # validate directory 'META-INF'
        meta_dir = os.path.join(package_dir, 'META-INF')
        if not os.path.isdir(meta_dir):
            evtlog.log("A directory named 'META-INF' must exist, "
                       "located at the root of the package",
                       self.evtid,
                       'evt_package_struct_invalid')
            return

        if len(os.listdir(meta_dir)) > 1:
            evtlog.log("The 'META-INF' directory must only contain the file "
                       "'MANIFEST.MF'",
                       self.evtid,
                       'evt_package_struct_invalid')
            return

        if not os.path.exists(os.path.join(meta_dir, 'MANIFEST.MF')):
            evtlog.log("A file named 'MANIFEST.MF' must exist in directory "
                       "'META-INF'",
                       self.evtid,
                       'evt_package_struct_invalid')
            return

        # validate directory 'service_descriptors'
        services_dir = os.path.join(package_dir, 'service_descriptors')
        if os.path.isdir(services_dir):
            if len(os.listdir(services_dir)) == 0:
                evtlog.log("The 'service_descriptors' directory must contain "
                           "at least one service descriptor file",
                           self.evtid,
                           'evt_package_struct_invalid')
                return

        # validate directory 'function_descriptors'
        functions_dir = os.path.join(package_dir, 'function_descriptors')
        if os.path.isdir(functions_dir):
            if len(os.listdir(functions_dir)) == 0:
                evtlog.log("The 'function_descriptors' directory must contain "
                           "at least one function descriptor file",
                           self.evtid,
                           'evt_package_struct_invalid')
                return

        return True

    @staticmethod
    def validate_package_signature(package, signature, pubkey):
        """
        Verifies with the public key from whom the package file came that is 
        indeed signed by their private key
        :param package: path to package file
        :param signature: String signature to be verified
        :param pubkey: String public key
        :return: Boolean. True if valid signature, False otherwise. 
        """
        log.info("Validating signature of package '{0}'".format(package))
        file_data = None
        try:
            with open(package, 'rb') as _file:
                file_data = _file.read()
            pkg_hash = SHA256.new(file_data).digest()
            rsa_key = RSA.importKey(pubkey)
            signature = (eval(signature), )
            result = rsa_key.verify(pkg_hash, signature)
        except IOError as err:
            log.error("I/O error: {0}".format(err))
            return False
        except ValueError:
            log.error("Invalid key format")
            return False
        except Exception as err:  # override, so validator doesn't crash
            log.error("Exception error: {0}".format(err))
            return False

        return result

    def _validate_package_syntax(self, package):
        """
        Validate the syntax of the package descriptor of a SONATA
        package against its schema.
        :param package: package object to validate
        :return: True if syntax is correct, None otherwise
        """
        log.info("Validating syntax of package descriptor '{0}'"
                 .format(package.id))
        if not self._schema_validator.validate(
              package.content, SchemaValidator.SCHEMA_PACKAGE_DESCRIPTOR):
            evtlog.log("Invalid syntax in MANIFEST of package '{0}': {1}"
                       .format(package.id, self._schema_validator.error_msg),
                       package.id,
                       'evt_pd_stx_invalid')
            return
        return True

    def _validate_service_syntax(self, service):
        """
        Validate a the syntax of a service (NS) against its schema.
        :param service: service to validate
        :return: True if syntax is correct, None otherwise
        """
        log.info("Validating syntax of service '{0}'".format(service.id))
        if not self._schema_validator.validate(
              service.content, SchemaValidator.SCHEMA_SERVICE_DESCRIPTOR):
            evtlog.log("Invalid syntax in service '{0}': {1}"
                       .format(service.id, self._schema_validator.error_msg),
                       service.id,
                       'evt_nsd_stx_invalid')
            return
        return True

    def _validate_function_syntax(self, function):
        """
        Validate the syntax of a function (VNF) against its schema.
        :param function: function to validate
        :return: True if syntax is correct, None otherwise
        """
        log.info("Validating syntax of function '{0}'".format(function.id))
        if not self._schema_validator.validate(
              function.content, SchemaValidator.SCHEMA_FUNCTION_DESCRIPTOR):
            evtlog.log("Invalid syntax in function '{0}': {1}"
                       .format(function.id, self._schema_validator.error_msg),
                       function.id,
                       'evt_vnfd_stx_invalid')
            return
        return True

    def _validate_package_integrity(self, package, root_dir):
        """
        Validate the integrity of a package.
        It will validate the entry service of the package as well as its
        referenced functions.
        :param package: package object
        :return: True if syntax is correct, None otherwise
        """
        log.info("Validating integrity of package '{0}'".format(package.id))

        # load referenced service descriptor files
        for f in package.descriptors:
            filename = os.path.join(root_dir, strip_root(f))
            log.debug("Verifying file '{0}'".format(f))
            if not os.path.isfile(filename):
                evtlog.log("Referenced descriptor file '{0}' is not "
                           "packaged.".format(f),
                           package.id,
                           'evt_pd_itg_invalid_reference')
                return

            gen_md5 = generate_hash(filename)
            manif_md5 = package.md5(strip_root(f))
            if manif_md5 and gen_md5 != manif_md5:
                evtlog.log("MD5 hash of file '{0}' is not equal to the "
                           "defined in package descriptor. Gen MD5: {1}. "
                           "MANIF MD5: {2}"
                           .format(f, gen_md5, manif_md5),
                           package.id,
                           'evt_pd_itg_invalid_md5')

        # configure dpath for function referencing
        self.configure(dpath=os.path.join(root_dir, 'function_descriptors'))

        # finally, validate the package entry service file
        entry_service_file = os.path.join(
            root_dir, strip_root(package.entry_service_file))

        return self.validate_service(entry_service_file)

    def _validate_service_integrity(self, service):
        """
        Validate the integrity of a service (NS).
        It checks for inconsistencies in the identifiers of connection
        points, virtual links, etc.
        :param service: service to validate
        :return: True if integrity is correct
        :param service:
        :return:
        """
        log.info("Validating integrity of service '{0}'".format(service.id))

        # get referenced function descriptors (VNFDs)
        if not self._load_service_functions(service):
            evtlog.log("Failed to read service function descriptors",
                       service.id,
                       'evt_nsd_itg_function_unavailable')
            return

        # validate service function descriptors (VNFDs)
        for fid, function in service.functions.items():
            if not self.validate_function(function.filename):
                evtlog.log("Failed to validate function descriptor '{0}'"
                           .format(function.filename),
                           service.id,
                           'evt_nsd_itg_function_invalid')
                return

        # load service interfaces
        if not service.load_interfaces():
            evtlog.log("Couldn't load the connection points of service id='{0}'"
                       .format(service.id),
                       service.id,
                       'evt_nsd_itg_badsection_cpoints')
            return

        # load service links
        if not service.load_virtual_links():
            evtlog.log("Couldn't load virtual links of service id='{0}'"
                       .format(service.id),
                       service.id,
                       'evt_nsd_itg_badsection_vlinks')
            return

        undeclared = service.find_undeclared_interfaces()
        if undeclared:
            evtlog.log("Virtual links section has undeclared connection "
                       "points: {0}".format(undeclared),
                       service.id,
                       'evt_nsd_itg_undeclared_cpoint')
            return

        # check for unused interfaces
        unused_ifaces = service.find_unused_interfaces()
        if unused_ifaces:
            evtlog.log("Service has unused connection points: {0}"
                       .format(unused_ifaces),
                       service.id,
                       'evt_nsd_itg_unused_cpoint')

        # verify integrity between vnf_ids and links
        for lid, link in service.links.items():
            for iface in link.interfaces:
                if iface not in service.interfaces:
                    iface_tokens = iface.split(':')
                    if len(iface_tokens) != 2:
                        evtlog.log("Connection point '{0}' in virtual link "
                                   "'{1}' is not defined"
                                   .format(iface, lid),
                                   service.id,
                                   'evt_nsd_itg_undefined_cpoint')
                        return
                    vnf_id = iface_tokens[0]
                    function = service.mapped_function(vnf_id)
                    if not function:
                        evtlog.log("Function (VNF) of vnf_id='{0}' declared "
                                   "in connection point '{0}' in virtual link "
                                   "'{1}' is not defined"
                                   .format(vnf_id, iface, lid),
                                   service.id,
                                   'evt_nsd_itg_undefined_cpoint')
                        return

        return True

    def _validate_function_integrity(self, function):
        """
        Validate the integrity of a function (VNF).
        It checks for inconsistencies in the identifiers of connection
        points, virtual deployment units (VDUs), ...
        :param function: function to validate
        :return: True if integrity is correct
        """
        log.info("Validating integrity of function descriptor '{0}'"
                 .format(function.id))

        # load function interfaces
        if not function.load_interfaces():
            evtlog.log("Couldn't load the interfaces of function id='{0}'"
                       .format(function.id),
                       function.id,
                       'evt_vnfd_itg_badsection_cpoints')
            return

        # load units
        if not function.load_units():
            evtlog.log("Couldn't load the units of function id='{0}'"
                       .format(function.id),
                       function.id,
                       'evt_vnfd_itg_badsection_vdus')
            return

        # load interfaces of units
        if not function.load_unit_interfaces():
            evtlog.log("Couldn't load unit interfaces of function id='{0}'"
                       .format(function.id),
                       function.id,
                       'evt_vnfd_itg_vdu_badsection_cpoints')
            return

        # load function links
        if not function.load_virtual_links():
            evtlog.log("Couldn't load the links of function id='{0}'"
                       .format(function.id),
                       function.id,
                       'evt_vnfd_itg_badsection_vlinks')
            return

        # check for undeclared interfaces
        undeclared = function.find_undeclared_interfaces()
        if undeclared:
            evtlog.log("Virtual links section has undeclared connection "
                       "points: {0}".format(undeclared),
                       function.id,
                       'evt_vnfd_itg_undeclared_cpoint')
            return

        # check for unused interfaces
        unused_ifaces = function.find_unused_interfaces()
        if unused_ifaces:
            evtlog.log("Function has unused connection points: {0}"
                       .format(unused_ifaces),
                       function.id,
                       'evt_vnfd_itg_unused_cpoint')

        # verify integrity between unit interfaces and units
        for lid, link in function.links.items():
            for iface in link.interfaces:
                iface_tokens = iface.split(':')
                if len(iface_tokens) > 1:
                    if iface_tokens[0] not in function.units.keys():
                        evtlog.log("Invalid interface id='{0}' of link "
                                   "id='{1}': Unit id='{2}' is not defined"
                                   .format(iface, lid, iface_tokens[0]),
                                   function.id,
                                   'evt_vnfd_itg_undefined_cpoint')
                        return
        return True

    def _validate_service_topology(self, service):
        """
        Validate the network topology of a service.
        :return:
        """
        log.info("Validating topology of service '{0}'".format(service.id))

        # build service topology graph with VNF interfaces
        service.graph = service.build_topology_graph(level=1, bridges=False)
        if not service.graph:
            evtlog.log("Couldn't build topology graph of service '{0}'"
                       .format(service.id),
                       service.id,
                       'evt_nsd_top_topgraph_failed')
            return

        log.debug("Built topology graph of service '{0}': {1}"
                  .format(service.id, service.graph.edges()))

        # write service graphs with different levels and options
        self.write_service_graphs(service)

        if nx.is_connected(service.graph):
            log.debug("Topology graph of service '{0}' is connected"
                      .format(service.id))
        else:
            evtlog.log("Topology graph of service '{0}' is disconnected"
                       .format(service.id),
                       service.id,
                       'evt_nsd_top_topgraph_disconnected')

        # load forwarding graphs
        if not service.load_forwarding_graphs():
            evtlog.log("Couldn't load service forwarding graphs. ",
                       service.id,
                       'evt_nsd_top_badsection_fwgraph')
            return

        # analyse forwarding paths
        for fw_graph in service.fw_graphs:

            for fw_path in fw_graph['fw_paths']:

                # check if number of connection points is odd
                if len(fw_path['path']) % 2 != 0:
                    evtlog.log("The forwarding path fg_id='{0}', fp_id='{1}' "
                               "has an odd number of connection points".
                               format(fw_graph['fg_id'], fw_path['fp_id']),
                               service.id,
                               'evt_nsd_top_fwgraph_cpoints_odd')

                fw_path['trace'] = service.trace_path_pairs(fw_path['path'])

                if any(pair['break'] is True for pair in fw_path['trace']):
                    evtid = event.generate_evt_id()
                    evtlog.log("The forwarding path fg_id='{0}', fp_id='{1}' "
                               "is invalid for the specified topology. "
                               "{2} breakpoint(s) found the path: \n{3}"
                               .format(fw_graph['fg_id'],
                                       fw_path['fp_id'],
                                       sum(pair['break'] is True for pair in
                                           fw_path['trace']),
                                       yaml.dump(fw_path['trace'],
                                                 default_flow_style=False)),
                               evtid,
                               'evt_nsd_top_fwpath_invalid',
                               scope='multi')
                    fw_path['event_id'] = evtid

                    # skip further analysis
                    return

                log.debug("Forwarding path fg_id='{0}', fp_id='{1}': {2}"
                          .format(fw_graph['fg_id'], fw_path['fp_id'],
                                  fw_path['trace']))

            # cycles must be analysed at the vnf level, not interface level.
            # here, a directed graph between vnfs must be created,
            # containing the interfaces of each node and edges between nodes.
            # Each edge must contain the pair of interfaces that links the
            # two nodes.
            # Having this structure is possible to find cycles between vnfs
            # and more importantly, identify which are the links
            #  (interface pair) that integrate a particular cycle.

            fpg = nx.DiGraph()
            for fw_path in fw_graph['fw_paths']:
                prev_node = None
                prev_iface = None
                pair_complete = False

                # convert 'interface' path into vnf path
                for interface in fw_path['path']:
                    # find vnf_id of interface
                    func = None
                    if interface in service.all_function_interfaces:
                        func = service.function_of_interface(interface)
                        if not func:
                            log.error(
                                "Internal error: couldn't find corresponding"
                                " VNFs in forwarding path '{}'"
                                .format(fw_path['fp_id']))
                            return
                        node = service.vnf_id(func)

                    else:
                        node = interface

                        fpg.add_node(node)

                    if pair_complete:
                        if prev_node and prev_node == node:
                            evtlog.log("The forwarding path fg_id='{0}', "
                                       "fp_id='{1}' contains a path within the"
                                       " same VNF id='{2}'"
                                       .format(fw_graph['fg_id'],
                                               fw_path['fp_id'],
                                               node),
                                       func.id,
                                       'evt_nsd_top_fwpath_inside_vnf')

                            # reset trace and leave
                            fw_path['trace'] = []
                            return

                        fpg.add_edge(prev_node, node,
                                     attr_dict={'from': prev_iface,
                                                'to': interface})
                        pair_complete = False

                    else:
                        if prev_node and prev_node != node:
                            evtlog.log("The forwarding path fg_id='{0}', "
                                       "fp_id='{1}' is disrupted at the "
                                       "connection point: '{2}'"
                                       .format(fw_graph['fg_id'],
                                               fw_path['fp_id'],
                                               interface),
                                       service.id,
                                       'evt_nsd_top_fwpath_disrupted')

                        pair_complete = True

                    prev_node = node
                    prev_iface = interface

            # find cycles
            complete_cycles = list(nx.simple_cycles(fpg))

            # remove 1-hop cycles
            cycles = []
            for cycle in complete_cycles:
                if len(cycle) > 2:
                    cycles.append(cycle)

            # build cycles representative interface structure
            cycles_list = []
            for cycle in cycles:
                cycle_dict = {'cycle_id': str(uuid.uuid4()), 'cycle_path': []}

                for idx, node in enumerate(cycle):
                    link = {}

                    if idx+1 == len(cycle):  # at last element
                        next_node = cycle[0]
                    else:
                        next_node = cycle[idx+1]

                    neighbours = fpg.neighbors(node)
                    if next_node not in neighbours:
                        log.error("Internal error: couldn't find next hop "
                                  "when building structure of cycle: {}"
                                  .format(cycle))
                        continue

                    edge_data = fpg.get_edge_data(node, next_node)
                    link['from'] = edge_data['from']
                    link['to'] = edge_data['to']

                    cycle_dict['cycle_path'].append(link)
                cycles_list.append(cycle_dict)

            # report cycles
            if cycles_list and len(cycles_list) > 0:
                evtid = event.generate_evt_id()
                evtlog.log("Found {0} cycle(s) in forwarding graph "
                           "fg_id='{1}': \n{2}"
                           .format(len(cycles_list),
                                   fw_graph['fg_id'],
                                   yaml.dump(cycles_list,
                                             default_flow_style=False)),
                           evtid,
                           'evt_nsd_top_fwgraph_cycles',
                           scope='multi')
                fw_graph['cycles'] = cycles_list
                fw_graph['event_id'] = evtid

        return True

    def _validate_function_topology(self, function):
        """
        Validate the network topology of a function.
        It builds the topology graph of the function, including VDU
        connections.
        :param function: function to validate
        :return: True if topology doesn't present issues
        """
        log.info("Validating topology of function '{0}'"
                 .format(function.id))

        # build function topology graph
        function.graph = function.build_topology_graph(bridges=True)
        if not function.graph:
            evtlog.log("Couldn't build topology graph of function '{0}'"
                       .format(function.id),
                       function.id,
                       'evt_vnfd_top_topgraph_failed')
            return

        log.debug("Built topology graph of function '{0}': {1}"
                  .format(function.id, function.graph.edges()))

        # check for path cycles
        #cycles = Validator._find_graph_cycles(function.graph,
        #                                      function.graph.nodes()[0])
        #if cycles and len(cycles) > 0:
        #    log.warning("Found cycles in network graph of function "
        #                "'{0}':\n{0}".format(function.id, cycles))

        return True

    def _load_service_functions(self, service):
        """
        Loads and stores functions (VNFs) referenced in the specified service
        :param service: service
        :return: True if successful, None otherwise
        """

        log.debug("Loading functions of the service.")

        # get VNFD file list from provided dpath
        if not self._dpath:
            return

        vnfd_files = list_files(self._dpath, self._dext)
        log.debug("Found {0} descriptors in dpath='{2}': {1}"
                  .format(len(vnfd_files), vnfd_files, self._dpath))

        # load all VNFDs
        path_vnfs = read_descriptor_files(vnfd_files)

        # check for errors
        if 'network_functions' not in service.content:
            log.error("Service doesn't have any functions. "
                      "Missing 'network_functions' section.")
            return

        functions = service.content['network_functions']
        if functions and not path_vnfs:
            evtlog.log("Service references VNFs but none could be found in "
                       "'{0}'. Please specify another '--dpath'"
                       .format(self._dpath),
                       service.id,
                       'evt_nsd_itg_function_unavailable')
            return

        # store function descriptors referenced in the service
        for function in functions:
            fid = build_descriptor_id(function['vnf_vendor'],
                                      function['vnf_name'],
                                      function['vnf_version'])
            if fid not in path_vnfs.keys():
                evtlog.log("Referenced function descriptor id='{0}' couldn't "
                           "be loaded".format(fid),
                           service.id,
                           'evt_nsd_itg_function_unavailable')
                return

            vnf_id = function['vnf_id']
            new_func = self._storage.create_function(path_vnfs[fid])
            service.associate_function(new_func, vnf_id)

        return True

    @staticmethod
    def _load_project_service_file(project):
        """
        Load descriptors from a SONATA SDK project.
        :param project: SDK project
        :return: True if successful, False otherwise
        """

        # load project service descriptor (NSD)
        nsd_files = project.get_ns_descriptor()
        if not nsd_files:
            evtlog.log("Couldn't find a service descriptor in project '[0}'"
                       .format(project.project_root),
                       project.project_root,
                       'evt_project_service_invalid')
            return False

        if len(nsd_files) > 1:
            evtlog.log("Found multiple service descriptors in project "
                       "'{0}': {1}"
                       .format(project.project_root, nsd_files),
                       project.project_root,
                       'evt_project_service_multiple')
            return False

        return nsd_files[0]

    @staticmethod
    def _find_graph_cycles(graph, node, prev_node=None, backtrace=None):

        print(". {} <-- {}".format(node, backtrace))

        if not backtrace:
            backtrace = []

        # get node's neighbors
        neighbors = graph.neighbors(node)

        # remove previous node from neighbors
        if prev_node:
            neighbors.pop(neighbors.index(prev_node))

        # ensure node has neighbors
        if not len(neighbors) > 0:
            return None

        # check is this node was already visited
        if node in backtrace:
            cycle = backtrace[backtrace.index(node):]
            return cycle

        # mark this node as visited and trace it
        backtrace.append(node)

        # iterate through neighbor nodes
        for neighbor in neighbors:
            return Validator._find_graph_cycles(graph,
                                                neighbor,
                                                prev_node=node,
                                                backtrace=backtrace)
        return backtrace

    def write_service_graphs(self, service):
        graphsdir = 'graphs'
        try:
            os.makedirs(graphsdir)
        except OSError as exc:
            if exc.errno == errno.EEXIST and os.path.isdir(graphsdir):
                pass

        g = service.build_topology_graph(level=3, bridges=False)

        for lvl in range(0, 4):
            g = service.build_topology_graph(level=lvl, bridges=False)
            nx.write_graphml(g, os.path.join(graphsdir,
                                             "{0}-lvl{1}.graphml"
                                             .format(service.id, lvl)))
            g = service.build_topology_graph(level=lvl, bridges=True)
            nx.write_graphml(g, os.path.join(graphsdir,
                                             "{0}-lvl{1}-br.graphml"
                                             .format(service.id, lvl)))

        g = service.build_topology_graph(level=3, bridges=True,
                                         vdu_inner_connections=False)
        service.complete_graph = nx.generate_graphml(g, encoding='utf-8',
                                                     prettyprint=True)
        nx.write_graphml(g, os.path.join(graphsdir,
                                         "{0}-lvl3-complete.graphml"
                                         .format(service.id)))


def print_result(validator, result):

    if not result:
        log.critical("VALIDATION FAILED")
    else:
        log.info("VALIDATION SUCCEEDED")

    print("==== Statistics: {0} error(s) and {1} warning(s) ===="
          .format(validator.error_count, validator.warning_count))
    print("Errors: {0}".format(validator.errors))
    print("Warnings: {0}".format(validator.warnings))

    # if validator.error_count:
    #     log.error("Validation failed with {0} error(s) and {1} warning(s)"
    #               .format(validator.error_count, validator.warning_count))
    # elif validator.warning_count:
    #     log.warning("Validation completed with {0} warning(s)"
    #                 .format(validator.warning_count))
    # else:
    #     log.info("Validation succeeded")


def main():
    coloredlogs.install(level='info')

    import argparse

    # specify arguments
    parser = argparse.ArgumentParser(
        description="Validate a SONATA Service. By default it performs a "
                    "validation to the syntax, integrity and network "
                    "topology.\n",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""Example usage:
        son-validate --project /home/sonata/projects/project_X
                     --workspace /home/sonata/.son-workspace
        son-validate --service ./nsd_file.yml --path ./vnfds/ --dext yml
        son-validate --function ./vnfd_file.yml
        son-validate --function ./vnfds/ --dext yml
        """
    )

    exclusive_parser = parser.add_mutually_exclusive_group(
        required=True
    )

    parser.add_argument(
        "-w", "--workspace",
        dest="workspace_path",
        help="Specify the directory of the SDK workspace for validating the "
             "SDK project. If not specified will assume the directory: '{}'"
             .format(Workspace.DEFAULT_WORKSPACE_DIR),
        required=False
    )

    exclusive_parser.add_argument(
        "--project",
        dest="project_path",
        help="Validate the service of the specified SDK project. If "
             "not specified will assume the current directory: '{}'\n"
             .format(os.getcwd()),
        required=False
    )
    exclusive_parser.add_argument(
        "--package",
        dest="package_file",
        help="Validate the specified package descriptor. "
    )
    exclusive_parser.add_argument(
        "--service",
        dest="nsd",
        help="Validate the specified service descriptor. "
             "The directory of descriptors referenced in the service "
             "descriptor should be specified using the argument '--path'.",
        required=False
    )
    exclusive_parser.add_argument(
        "--function",
        dest="vnfd",
        help="Validate the specified function descriptor. If a directory is "
             "specified, it will search for descriptor files with extension "
             "defined in '--dext'",
        required=False
    )
    parser.add_argument(
        "--dpath",
        help="Specify a directory to search for descriptors. Particularly "
             "useful when using the '--service' argument.",
        required=False
    )
    parser.add_argument(
        "--dext",
        help="Specify the extension of descriptor files. Particularly "
             "useful when using the '--function' argument",
        required=False
    )
    parser.add_argument(
        "--syntax", "-s",
        help="Perform a syntax validation.",
        required=False,
        action="store_true",
        default=False
    )
    parser.add_argument(
        "--integrity", "-i",
        help="Perform an integrity validation.",
        required=False,
        action="store_true",
        default=False
    )
    parser.add_argument(
        "--topology", "-t",
        help="Perform a network topology validation.",
        required=False,
        action="store_true",
        default=False
    )
    parser.add_argument(
        "--debug",
        help="sets verbosity level to debug",
        required=False,
        action="store_true")

    # parse arguments
    args = parser.parse_args()

    # by default, perform all validations
    if not args.syntax and not args.integrity and not args.topology:
        args.syntax = args.integrity = args.topology = True

    if args.package_file:
        if not os.path.isfile(args.package_file):
            log.error("Provided package is not a valid file")
            exit(1)

        if args.workspace_path:
            ws_root = args.workspace_path
        else:
            ws_root = Workspace.DEFAULT_WORKSPACE_DIR

        # Obtain Workspace object
        workspace = Workspace.__create_from_descriptor__(ws_root)
        if not workspace:
            log.error("Invalid workspace path: '%s'\n" % ws_root)
            exit(1)

        validator = Validator(workspace=workspace)
        validator.configure(syntax=args.syntax,
                            integrity=args.integrity,
                            topology=args.topology,
                            debug=args.debug if args.debug else None)

        result = validator.validate_package(args.package_file)
        print_result(validator, result)

    elif args.project_path:

        if args.workspace_path:
            ws_root = args.workspace_path
        else:
            ws_root = Workspace.DEFAULT_WORKSPACE_DIR

        prj_root = args.project_path if args.project_path else os.getcwd()

        # Obtain Workspace object
        workspace = Workspace.__create_from_descriptor__(ws_root)
        if not workspace:
            log.error("Invalid workspace path: '%s'\n" % ws_root)
            exit(1)

        project = Project.__create_from_descriptor__(workspace, prj_root)
        if not project:
            log.error("Invalid project path: '%s'\n  " % prj_root)
            exit(1)

        validator = Validator(workspace=workspace)
        validator.configure(syntax=args.syntax,
                            integrity=args.integrity,
                            topology=args.topology,
                            debug=args.debug)

        result = validator.validate_project(project)
        print_result(validator, result)

    elif args.nsd:
        validator = Validator()
        validator.configure(dpath=args.dpath, dext=args.dext,
                            syntax=args.syntax,
                            integrity=args.integrity,
                            topology=args.topology,
                            debug=args.debug)

        result = validator.validate_service(args.nsd)
        print_result(validator, result)

    elif args.vnfd:
        validator = Validator()
        validator.configure(dext=args.dext,
                            syntax=args.syntax,
                            integrity=args.integrity,
                            topology=args.topology,
                            debug=args.debug)

        result = validator.validate_function(args.vnfd)
        print_result(validator, result)

    else:
        log.error("Invalid arguments.")
        exit(1)

    exit(0)
