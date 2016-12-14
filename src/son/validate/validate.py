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
import sys
import inspect
import yaml
import logging
import coloredlogs
import networkx as nx
from son.schema.validator import SchemaValidator
from son.workspace.workspace import Workspace, Project


log = logging.getLogger(__name__)


class Validator(object):

    CXPT_KEY_SEPARATOR = ':'         # connection point key separator

    def __init__(self, workspace=None, log_level='debug'):

        self._workspace = workspace
        self._log_level = log_level
        self._syntax = True
        self._integrity = True
        self._topology = True

        # create "virtual" workspace if not provided (don't actually create
        # file structure)
        if not self._workspace:
            self._workspace = Workspace('.', log_level=log_level)

        # load configuration from workspace
        self._dext = self._workspace.default_descriptor_extension
        self._dpath = '.'
        self._log_level = self._workspace.log_level

        # configure logs
        coloredlogs.install(level=self._log_level)

        # keep loaded descriptors
        self._nss = {}          # store services [id][descriptor, file, graph]
        self._vnfs = {}         # store functions [id][descriptor, file, graph]
        self._vnf_cid_map = {}  # bridge vnf_id in NSD to vnf_combo_id in VNFD

        # syntax validation
        self._schema_validator = SchemaValidator(self._workspace)

        # number of warnings
        self._warnings_count = 0

    @property
    def warnings_count(self):
        return self._warnings_count

    def configure(self, syntax=None, integrity=None, topology=None,
                  dpath=None, dext=None, log_level=None):
        """
        Configure parameters for validation. It is recommended to call this
        function before performing a validation.
        :param syntax: specifies whether to validate syntax
        :param integrity: specifies whether to validate integrity
        :param topology: specifies whether to validate network topology
        :param dpath: directory to search for function descriptors (VNFDs)
        :param dext: extension of descriptor files (default: 'yml')
        :param log_level: verbosity level of logger
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
        if log_level:
            coloredlogs.set_level(log_level)

    def _assert_configuration(self):
        """
        Ensures that the current configuration is compatible with the
        validation to perform. If issues are found the application is
        interrupted with the appropriate error.
        This is an internal function which must be invoked only by:
            - 'validate_project'
            - 'validate_service'
            - 'validate_function'

        """
        # ensure this function is called by specific functions
        caller = inspect.stack()[1][3]
        if caller != 'validate_function' and caller != 'validate_service' and \
           caller != 'validate_project':
            log.error("Cannot assert a correct configuration. Validation "
                      "scope couldn't be determined. Aborting")
            sys.exit(1)

        # general rules - apply to all validations
        if self._integrity and not self._syntax:
            log.error("Cannot validate integrity without validating syntax "
                      "first. Aborting.")
            sys.exit(1)

        if self._topology and not self._integrity:
            log.error("Cannot validate topology without validating integrity "
                      "first. Aborting.")
            sys.exit(1)

        if caller == 'validate_project':
            pass

        elif caller == 'validate_service':
            # check SERVICE validation parameters
            if (self._integrity or self._topology) and not \
               (self._dpath and self._dext):
                log.critical("Invalid validation parameters. To validate the "
                             "integrity or topology of a service both "
                             "'--dpath' and '--dext' parameters must be "
                             "specified.")
                sys.exit(1)

        elif caller == 'validate_function':
            pass

    def validate_project(self, project):
        """
        Validate a SONATA project.
        By default, it performs the following validations: syntax, integrity
        and network topology.
        :param project: SONATA project
        :return: True if all validations were successful, False otherwise
        """
        self._assert_configuration()

        log.info("Validating project '{0}'".format(project.project_root))
        log.info("... syntax: {0}, integrity: {1}, topology: {2}"
                 .format(self._syntax, self._integrity, self._topology))

        # retrieve project configuration
        self._dpath = project.vnfd_root
        self._dext = project.descriptor_extension

        # load all project descriptors present at source directory
        log.debug("Loading project service")
        nsd_file = Validator._load_project_service_file(project)

        return self.validate_service(nsd_file)

    def validate_service(self, nsd_file):
        """
        Validate a SONATA service.
        By default, it performs the following validations: syntax, integrity
        and network topology.
        :param nsd_file: service descriptor filename
        :return: True if all validations were successful, False otherwise
        """
        self._assert_configuration()

        log.info("Validating service '{0}'".format(nsd_file))
        log.info("... syntax: {0}, integrity: {1}, topology: {2}"
                 .format(self._syntax, self._integrity, self._topology))

        # load service descriptor
        nsd = self._read_descriptor_file(nsd_file)
        if not nsd:
            log.critical("Failed to read service descriptor.")
            return

        ns_cid = self._store_service(nsd_file, nsd)
        if not ns_cid:
            log.critical("Couldn't store the service. ")
            return

        # validate service syntax
        if self._syntax and not self._validate_service_syntax(ns_cid):
            return

        if self._integrity and not self._validate_service_integrity(ns_cid):
            return

        if self._topology and not self._validate_service_topology(ns_cid):
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
        self._assert_configuration()

        # validate multiple VNFs
        if os.path.isdir(vnfd_path):
            vnfd_files = Validator._list_files(vnfd_path, self._dext)
            for vnfd_file in vnfd_files:
                if not self.validate_function(vnfd_file):
                    return
            return True

        log.info("Validating function '{0}'".format(vnfd_path))
        log.info("... syntax: {0}, integrity: {1}, topology: {2}"
                 .format(self._syntax, self._integrity, self._topology))

        # load function descriptor
        vnfd = self._read_descriptor_file(vnfd_path)
        if not vnfd:
            log.critical("Failed to read function descriptor.")
            return

        # store function descriptor in cache for later usage
        vnf_cid = self._store_function(vnfd_path, vnfd)
        if not vnf_cid:
            log.critical("Couldn't store VNF of file '{0}'".format(vnfd_path))
            return

        if self._syntax and not self._validate_function_syntax(vnf_cid):
            return

        if self._integrity and not self._validate_function_integrity(vnf_cid):
            return

        if self._topology and not self._validate_function_topology(vnf_cid):
            return

        return True

    def _validate_service_syntax(self, ns_cid):
        """
        Validate a the syntax of a service (NS) against its schema.
        :param ns_cid: service identifier
        :return: True if syntax is correct, None otherwise
        """
        log.info("Validating syntax of service '{0}'".format(ns_cid))
        nsd = self._get_stored_service(ns_cid)['descriptor']
        if not self._schema_validator.validate(
              nsd, SchemaValidator.SCHEMA_SERVICE_DESCRIPTOR):
            log.error("Invalid syntax in service: '{0}'".format(ns_cid))
            return
        return True

    def _validate_function_syntax(self, vnf_cid):
        """
        Validate the syntax of a function (VNF) against its schema.
        :param vnf_cid: function identifier
        :return: True if syntax is correct, None otherwise
        """
        log.info("Validating syntax of function '{0}'".format(vnf_cid))
        vnfd = self._get_stored_function(vnf_cid)['descriptor']
        if not self._schema_validator.validate(
              vnfd, SchemaValidator.SCHEMA_FUNCTION_DESCRIPTOR):
            log.error("Invalid syntax in function '{0}'".format(vnf_cid))
            return
        return True

    def _validate_service_integrity(self, ns_cid):

        log.info("Validating integrity of service '{0}'".format(ns_cid))

        # get referenced function descriptors (VNFDs)
        if not self._load_service_functions(ns_cid):
            log.critical("Failed to read service function descriptors")
            return

        # validate referenced function descriptors (VNFDs)
        for vnf_cid in self._vnfs.keys():
            vnfd_file = self._vnfs[vnf_cid]['file']
            if not self.validate_function(vnfd_file):
                return

        return True

    def _validate_function_integrity(self, vnf_cid):
        """
        Validate the integrity of a function (VNF).
        It checks for inconsistencies in the identifiers of connection
        points, virtual deployment units (VDUs), ...
        :param vnf_cid: function identifier
        :return: True if integrity is correct
        """
        log.info("Validating integrity of function descriptor '{0}'"
                 .format(vnf_cid))
        vnfd = self._get_stored_function(vnf_cid)['descriptor']

        # get connection points of VNF
        cxpts = []
        for cxp in vnfd['connection_points']:
            if cxp['id'] in cxpts:
                log.error("[VNF: {0}] Duplicate connection point: '{1}'"
                          .format(vnf_cid, cxp['id']))
                return
            cxpts.append(cxp['id'])

        # get connection points of VDUs
        for vdu in vnfd['virtual_deployment_units']:
            for cxp in vdu['connection_points']:
                if cxp['id'] in cxpts:
                    log.error("[VNF: {0}, VDU: {1}] Duplicate connection "
                              "point: '{2}'"
                              .format(vnf_cid, vdu['id'], cxp['id']))
                    return
                cxpts.append(cxp['id'])

        return True

    def _validate_service_topology(self, ns_cid):
        """
        Validate the network topology of a service.
        :return:
        """
        log.info("Validating topology of service '{0}'".format(ns_cid))

        # build service network graph
        nsg = self._build_service_graph(ns_cid)
        if not nsg:
            return

        log.debug("Built network graph of service '{0}': {1}"
                  .format(ns_cid, nsg.edges()))

        # store service graph
        self._update_service(ns_cid, ns_graph=nsg)

        # check for forwarding cycles
        cycles = Validator._find_graph_cycles(nsg, nsg.nodes()[0])
        if cycles and len(cycles) > 0:
            log.warning("Found cycles in network graph of service "
                        "'{0}':\n{0}".format(ns_cid, cycles))
            self._warnings_count += 1

        return True

    def _validate_function_topology(self, vnf_cid):
        """
        Validate the network topology of a function.
        It builds the network graph of the function, including VDU connections.
        :param vnf_cid: function identifier
        :return: True if topology doesn't present issues
        """
        log.info("Validating topology of function '{0}'"
                 .format(vnf_cid))

        # build function network graph
        vnfg = self._build_function_graph(vnf_cid)
        if not vnfg:
            return

        log.debug("Built network graph of function '{0}': {1}"
                  .format(vnf_cid, vnfg.edges()))

        # store function graph
        self._update_function(vnf_cid, vnf_graph=vnfg)

        # check for path cycles
        cycles = Validator._find_graph_cycles(vnfg, vnfg.nodes()[0])
        if cycles and len(cycles) > 0:
            log.warning("Found cycles in network graph of function "
                        "'{0}':\n{0}".format(vnf_cid, cycles))
            self._warnings_count += 1

        return True

    def _load_service_functions(self, ns_cid):
        """
        Loads and stores functions (VNFs) referenced in the specified service
        :param ns_cid: service identifier
        :return: True if successful, None otherwise
        """
        nsd = self._get_stored_service(ns_cid)['descriptor']

        log.debug("Loading functions of the service.")

        # get VNFD file list from provided dpath
        vnfd_files = Validator._list_files(self._dpath, self._dext)
        log.debug("Found {0} descriptors in dpath='{2}': {1}"
                  .format(len(vnfd_files), vnfd_files, self._dpath))

        # load all VNFDs
        path_vnfs = Validator._read_descriptor_files(vnfd_files)

        # check for errors
        if 'network_functions' not in nsd:
            log.error("Service doesn't have any functions. "
                      "Missing 'network_functions' section.")
            return

        functions = nsd['network_functions']
        if functions and not path_vnfs:
            log.error("Service references VNFs but none could be found in "
                      "'{0}'. Please specify another '--dpath'"
                      .format(self._dpath))
            return

        # store function descriptors referenced in the service
        for function in functions:
            vnf_cid = Validator._build_combo_id(function['vnf_vendor'],
                                                function['vnf_name'],
                                                function['vnf_version'])
            if vnf_cid not in path_vnfs.keys():
                log.error("Referenced VNF descriptor '{0}' couldn't be "
                          "found in path '{1}'".format(vnf_cid, self._dpath))
                return

            vnf_id = function['vnf_id']
            self._store_function(path_vnfs[vnf_cid]['file'],
                                 path_vnfs[vnf_cid]['descriptor'],
                                 ns_vnf_id=vnf_id,
                                 parent=ns_cid)
        return True

    def _build_service_graph(self, ns_cid):
        """
        Build the network graph of a service.
        This graph will be later used for checking invalid or cyclic
        paths.
        :return:
        """
        nsd = self._get_stored_service(ns_cid)['descriptor']

        # create service network graph
        sg = nx.Graph()

        self._assign_nodes(sg, ns_cid, nsd, 0)
        self._assign_edges(sg, nsd, 0)

        return sg

    def _build_function_graph(self, vnf_cid):
        """
        Build the network graph of a function.
        This graph will be later used to check for invalid or cyclic paths.
        :return:
        """
        log.debug("Building graph of vnf_cid='{}'".format(vnf_cid))

        vnfd = self._get_stored_function(vnf_cid)['descriptor']

        # function network graph
        vnfg = nx.Graph()

        # assign connection points as nodes, lvl=1 (VNF level)
        if not self._assign_nodes(vnfg, vnf_cid, vnfd, 1):
            return

        if not self._assign_nodes(vnfg, vnf_cid, vnfd, 2):
            return

        # add edges to the graph by reading the virtual links
        if not self._assign_edges(vnfg, vnfd, 2):
            return

        return vnfg

    def _store_service(self, nsd_file, nsd, ns_graph=None):
        ns_cid = Validator._get_ns_combo_id(nsd)
        if ns_cid in self._nss and \
                (self._nss[ns_cid]['descriptor'] != nsd or
                 self._nss[ns_cid]['file'] != nsd_file):
            log.error("The service '{0}' was already stored in cache with "
                      "different values. Aborting."
                      .format(ns_cid))
            return

        self._nss[ns_cid] = {}
        self._nss[ns_cid]['descriptor'] = nsd
        self._nss[ns_cid]['file'] = nsd_file
        self._nss[ns_cid]['graph'] = ns_graph
        return ns_cid

    def _update_service(self, ns_cid, ns_file=None, nsd=None,
                        ns_graph=None, parent=None):
        if ns_cid not in self._nss.keys():
            log.error("Update failure. Service '{0}' is not stored in cache."
                      .format(ns_cid))
            return

        if ns_file:
            self._nss[ns_cid]['file'] = ns_file
        if nsd:
            self._nss[ns_cid]['descriptor'] = ns_file
        if ns_graph:
            self._nss[ns_cid]['graph'] = ns_graph
        if parent:
            self._nss[ns_cid]['parent'] = parent

        return True

    def _get_stored_service(self, ns_cid):
        if ns_cid not in self._nss:
            log.error("Service '{0}' is not stored in cache.".format(ns_cid))
            return
        return self._nss[ns_cid]

    def _clear_stored_services(self):
        self._nss.clear()

    def _store_function(self, vnfd_file, vnfd, ns_vnf_id=None,
                        vnf_graph=None, parent=None):
        vnf_cid = Validator._get_vnf_combo_id(vnfd)

        # verify if entry already exists and if its equal
        if vnf_cid in self._vnfs.keys() and \
                (self._vnfs[vnf_cid]['descriptor'] != vnfd or
                 self._vnfs[vnf_cid]['file'] != vnfd_file):
            log.error("VNF '{0}' is already stored in cache with different "
                      "values. Aborting."
                      .format(vnf_cid))
            return

        if vnf_cid not in self._vnfs.keys():
            self._vnfs[vnf_cid] = {}

        self._update_function(vnf_cid, vnf_file=vnfd_file, vnfd=vnfd,
                              vnf_graph=vnf_graph, parent=parent)

        # map service vnf_id to vnf_cid, if available
        if ns_vnf_id:
            self._map_vnf_cid(ns_vnf_id, vnf_cid)

        return vnf_cid

    def _update_function(self, vnf_cid, vnf_file=None, vnfd=None,
                         vnf_graph=None, parent=None):
        if vnf_cid not in self._vnfs.keys():
            log.error("Update failure. VNF '{0}' is not stored in cache."
                      .format(vnf_cid))
            return

        if vnf_file:
            self._vnfs[vnf_cid]['file'] = vnf_file
        if vnfd:
            self._vnfs[vnf_cid]['descriptor'] = vnfd
        if vnf_graph:
            self._vnfs[vnf_cid]['graph'] = vnf_graph
        if parent:
            self._vnfs[vnf_cid]['parent'] = parent

        return True

    def _get_stored_function(self, vnf_cid):
        if vnf_cid not in self._vnfs.keys():
            log.error("Function '{0}' is not stored in cache."
                      .format(vnf_cid))
            return
        return self._vnfs[vnf_cid]

    def _clear_stored_functions(self):
        self._vnfs.clear()

    def _map_vnf_cid(self, ns_vnf_id, vnf_cid):
        """
        Maps a vnf_id referenced in section 'network_functions' of a service
        to the vnf_cid (vendor.name.version).
        :param ns_vnf_id: vnf identifier in service descriptor
        :param vnf_cid: vnf combo identifier of function
        :return: True if successful, None otherwise
        """
        if ns_vnf_id in self._vnf_cid_map.keys():
            log.error("vnf_id='{0}' is already mapped to vnf_cid="
                      "'{1}'. Aborting."
                      .format(ns_vnf_id, self._get_mapped_vnf_cid(ns_vnf_id)))
            return
        self._vnf_cid_map[ns_vnf_id] = vnf_cid
        return True

    def _get_mapped_vnf_cid(self, ns_vnf_id, ):
        """
        Obtains the vnf_cid (vendor.name.version) of a function previously
        mapped to a vnf_id of a service
        :param ns_vnf_id: vnf identifier in service descriptor
        :return: vnf combo identifier of function
        """
        if ns_vnf_id not in self._vnf_cid_map.keys():
            log.error("vnf_id='{0}' is not mapped".format(ns_vnf_id))
            return
        return self._vnf_cid_map[ns_vnf_id]

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
            log.critical("Couldn't find a service descriptor in project '[0}'"
                         .format(project.project_root))
            return False

        if len(nsd_files) > 1:
            log.critical("Found multiple service descriptors in project "
                         "'{0}': {1}"
                         .format(project.project_root, nsd_files))
            return False

        return nsd_files[0]

    @staticmethod
    def _list_files(path, extension):
        """
        Retrieves a list of files with the specified extension in a given
        directory path.
        :param path: directory to search for VNF descriptor files
        :return: list of VNF descriptor files
        """
        file_list = []
        for root, dirs, files in os.walk(path):
            for file in files:
                if file.endswith(extension):
                    file_list.append(os.path.join(root, file))
        return file_list

    @staticmethod
    def _read_descriptor_files(files):
        """
        Loads the VNF descriptors provided in the file list. It builds a
        dictionary of the loaded VNF descriptor files. Each entry has the
        key of the VNF combo ID, in the format 'vendor.name.version'.
        :param files: filename list of descriptors
        :return: Dictionary of VNF descriptor dictionaries. None if
        unsuccessful.
        """
        descriptors = {}
        for file in files:
            vnfd = Validator._read_descriptor_file(file)
            if not vnfd:
                continue
            desc_cid = Validator._get_vnf_combo_id(vnfd)

            if desc_cid in descriptors.keys():
                log.error("Duplicate descriptor in files: '{0}' <==> {1}"
                          .format(file, descriptors[desc_cid]['file']))
                continue
            descriptors[desc_cid] = {}
            descriptors[desc_cid]['descriptor'] = vnfd
            descriptors[desc_cid]['file'] = file
        return descriptors

    @staticmethod
    def _read_descriptor_file(file):
        """
        Reads a SONATA descriptor from a file.
        :param file: descriptor filename
        :return: descriptor dictionary
        """
        with open(file, 'r') as _file:
            descriptor = yaml.load(_file)
            if not descriptor:
                log.error("Couldn't read descriptor file: '{0}'"
                          .format(file))
                return
            if 'vendor' not in descriptor or \
                    'name' not in descriptor or \
                    'version' not in descriptor:
                log.warning("Invalid SONATA descriptor file: '{0}'. Ignoring."
                            .format(file))
                return
            return descriptor

    @staticmethod
    def _assign_nodes(graph, descriptor_id, descriptor, level):

        # ensure 'connection_points' section exists in service or function
        if 'connection_points' not in descriptor:
            log.error("Descriptor='{}' is missing 'connection_points' section"
                      .format(descriptor_id))
            return

        nodes = []
        # gather nodes from connection points of services and functions
        if level == 0 or level == 1:  # service (NS) and function levels (VNF)
            nodes = (cxpt['id']
                     for cxpt in descriptor['connection_points']
                     if cxpt['type'] == 'interface')
            if not nodes:
                log.error("Descriptor='{}' doesn't have interface connection "
                          "points".format(descriptor_id))
                return

        # gather nodes from connection points of VDUs
        elif level == 2:  # unit level (VDU)
            if 'virtual_deployment_units' not in descriptor:
                log.error("Descriptor='{0}', doesn't contain a "
                          "'virtual_deployment_units' section"
                          .format(descriptor_id))
                return

            for vdu in descriptor['virtual_deployment_units']:
                nodes += (cxpt['id']
                          for cxpt in vdu['connection_points']
                          if cxpt['type'] == 'interface')
                if not nodes:
                    log.error("Descriptor='{0}', VDU='{1}' doesn't have "
                              "interface connection points"
                              .format(descriptor_id, vdu['id']))
                    return

        # assign nodes to graph
        for node in nodes:
            log.debug("[vnf_id: {0}] Adding node '{1}'"
                      .format(descriptor_id, node))

            graph.add_node(node,
                           attr_dict={'level': level, 'parent': descriptor_id})

        # remove nodes associated with E-LAN links (TODO: temp!!)
        for vlink in descriptor['virtual_links']:
            if vlink['connectivity_type'] != 'E-LAN':
                continue
            for ref_cxp in vlink['connection_points_reference']:
                    if ref_cxp in graph.nodes():
                        log.debug("Removing node '{0}' due to being "
                                  "associated with an E-LAN link"
                                  .format(ref_cxp))
                        graph.remove_node(ref_cxp)

        return True

    def _assign_edges(self, graph, descriptor, level=0):
        log.debug("Assigning edges to the graph with nodes: {0}"
                  .format(graph.nodes()))

        for vlink in descriptor['virtual_links']:
            ctype = vlink['connectivity_type']

            # TODO: add support for 'E-Tree': topology not defined in schema!
            if ctype != 'E-Line':
                continue

            cxpt_pair = vlink['connection_points_reference']
            if len(cxpt_pair) != 2:
                log.error("The virtual link '{0}' of type 'E-Line' must only "
                          "comprise 2 connection points"
                          .format(vlink['id']))
                return

            for idx, cxpt in enumerate(cxpt_pair):

                # ensure cxpt exists in the graph
                if not graph.has_node(cxpt):
                    cxpt_keys = cxpt.split(Validator.CXPT_KEY_SEPARATOR)

                    if len(cxpt_keys) == 1:
                        log.error("The connection point '{0}' defined in "
                                  "virtual link '{1}' is not defined"
                                  .format(cxpt, vlink['id']))
                        return

                    # should be a cxpt in format: 'vnf_id:cxpt_id' in NS level
                    elif len(cxpt_keys) == 2 and level == 0:

                        vnf_id = cxpt_keys[0]
                        cxpt_id = cxpt_keys[1]

                        # retrieve graph from the obtained vnf_id
                        vnf_cid = self._get_mapped_vnf_cid(vnf_id)
                        vnf = self._get_stored_function(vnf_cid)
                        if 'graph' not in vnf:
                            log.error("Couldn't retrieve stored graph for "
                                      "VNF with ID='{0}' specified in "
                                      "virtual link '{1}"
                                      .format(vnf_id, vlink['id']))
                            return
                        vnf_graph = vnf['graph']

                        # ensure cxpt exists within this VNF
                        if cxpt_id not in vnf_graph.nodes():
                            log.error("Couldn't retrieve connection point "
                                      "'{0}' of VNF with ID='{1}' "
                                      "specified in virtual link '{2}'"
                                      .format(cxpt_id, vnf_id,
                                              vlink['id']))
                            return

                        # add nodes to service graph with vnf_cid prefix
                        prefix = vnf_cid + '/'
                        prefix_map = dict.fromkeys(vnf_graph.nodes(),
                                                   prefix)
                        vnf_graph_copy = nx.relabel_nodes(vnf_graph,
                                                          prefix_map,
                                                          copy=True)
                        graph.add_nodes_from(vnf_graph_copy)

                        # change cxpt with the correct prefix
                        cxpt_pair[idx] = prefix + cxpt

                    else:
                        log.error("The virtual link '{0}' contains an "
                                  "invalid connection point: '{1}'"
                                  .format(vlink['id'], cxpt))
                        return

            # add edge to the graph
            log.debug("Adding edge '{0}' <---> '{1}'"
                      .format(cxpt_pair[0], cxpt_pair[1]))
            graph.add_edge(cxpt_pair[0], cxpt_pair[1])

        # in VDU level, assign edges of interfaces within each VDU
        if level == 2 and 'virtual_deployment_units' in descriptor:
            vdu_nodes = []
            vdus = descriptor['virtual_deployment_units']
            for vdu in vdus:
                if 'connection_points' not in vdu:
                    log.error("VDU '{0} has no connection points"
                              .format(vdu['id']))
                    return
                vdu_cxpts = vdu['connection_points']
                for cxpt in vdu_cxpts:
                    if cxpt['id'] not in graph.nodes():
                        continue
                    vdu_nodes.append(cxpt['id'])

            for idx, node_a in enumerate(vdu_nodes):
                sub_vdu_nodes = vdu_nodes.copy()
                sub_vdu_nodes.pop(idx)
                for node_b in sub_vdu_nodes:
                    if graph.has_edge(node_a, node_b):
                        continue
                    log.debug("Adding inner VDU edge '{0}' <---> '{1}'"
                              .format(node_a, node_b))
                    graph.add_edge(node_a, node_b)

        return True

    @staticmethod
    def _dot_join(a, b):
        if not a or not b:
            return
        return a + '.' + b

    @staticmethod
    def _get_ns_combo_id(nsd):
        return Validator._build_combo_id(nsd['vendor'],
                                         nsd['name'],
                                         nsd['version'])

    @staticmethod
    def _get_vnf_combo_id(vnfd):
        return Validator._build_combo_id(vnfd['vendor'],
                                         vnfd['name'],
                                         vnfd['version'])

    @staticmethod
    def _build_combo_id(vendor, name, version):
        return vendor + '.' + name + '.' + version

    @staticmethod
    def _find_graph_cycles(graph, node, prev_node=None, backtrace=None):

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


def main():
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
        dest="pd",
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

    if args.project_path:

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
                            log_level=args.debug)

        if not validator.validate_project(project):
            log.critical("Project validation has failed.")
            exit(1)
        if validator.warnings_count == 0:
            log.info("Validation of project '{0}' has succeeded."
                     .format(project.project_root))
        else:
            log.warning("Validation of project '{0}' returned {1} warning(s)"
                        .format(project.project_root,
                                validator.warnings_count))
    elif args.pd:
        pass

    elif args.nsd:
        validator = Validator()
        validator.configure(dpath=args.dpath, dext=args.dext,
                            syntax=args.syntax,
                            integrity=args.integrity,
                            topology=args.topology,
                            log_level=args.debug)

        if not validator.validate_service(args.nsd):
            log.critical("Project validation has failed.")
            exit(1)
        if validator.warnings_count == 0:
            log.info("Validation of service '{0}' has succeeded."
                     .format(args.nsd))
        else:
            log.warning("Validation of service '{0}' returned {1} warning(s)"
                        .format(args.nsd, validator.warnings_count))

    elif args.vnfd:
        validator = Validator()
        validator.configure(dext=args.dext,
                            syntax=args.syntax,
                            integrity=args.integrity,
                            topology=args.topology,
                            log_level=args.debug)

        if not validator.validate_function(args.vnfd):
            log.critical("Function validation has failed.")
            exit(1)
        if validator.warnings_count == 0:
            log.info("Validation of function '{0}' has succeeded."
                     .format(args.vnfd))
        else:
            log.warning("Validation of service '{0}' returned {1} warning(s)"
                        .format(args.vnfd, validator.warnings_count))
    else:
        log.error("Provided arguments are invalid.")
        exit(1)

    log.info("Done.")
    exit(0)
