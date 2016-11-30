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
import yaml
import logging
import coloredlogs
import networkx as nx
from son.schema.validator import SchemaValidator
from son.workspace.workspace import Workspace, Project


log = logging.getLogger(__name__)


class Validator(object):

    DEFAULT_DEXT = 'yml'
    DEFAULT_DPATH = '.'
    DEFAULT_LOG_LEVEL = 'debug'

    def __init__(self, workspace=None, log_level=DEFAULT_LOG_LEVEL):

        self._workspace = workspace
        self._log_level = log_level

        # create "virtual" workspace if not provided (don't actually create
        # file structure)
        if not self._workspace:
            self._workspace = Workspace('.', log_level=self._log_level)

        # load configuration from workspace
        self._dext = self._workspace.default_descriptor_extension
        self._dpath = self.DEFAULT_DPATH
        self._log_level = self._workspace.log_level

        # configure logs
        coloredlogs.install(level=self._log_level)

        # keep loaded descriptors
        self._loaded_vnfds = {}

        # keep descriptors
        self._nsd_file = None
        self._nsd = None
        self._vnfd_files = {}
        self._vnfds = {}
        self._prj_vnfds = {}

        # syntax validation
        self._schema_validator = SchemaValidator(self._workspace)

    def configure(self, dext=DEFAULT_DEXT, dpath=DEFAULT_DPATH,
                  log_level=DEFAULT_LOG_LEVEL):
        self._dext = dext
        self._dpath = dpath
        coloredlogs.set_level(log_level)

    def validate_project(self, project,syntax=True, integrity=True,
                         topology=True):
        """
        Validate a SONATA project.
        By default, it performs the following validations: syntax, integrity
        and network topology.
        :param project: SONATA project
        :param syntax: specifies whether to validate syntax
        :param integrity: specifies whether to validate integrity
        :param topology: specifies whether to validate network topology
        :return: True if all validations were successful, False otherwise
        """

        # load all project descriptors present at source directory
        log.info("Loading project descriptors")
        if not self._load_project_descriptors():
            return False

        # validate syntax
        log.info("Validating syntax of descriptors")
        if not self._validate_service_syntax():
            return False

        # correlate/check reference integrity between descriptors
        self._validate_service_integrity()

        # validate topology
        log.info("Validating service network topology")
        if not self._validate_service_topology():
            return False

        log.info("SUCCESS")
        return True

    def validate_service(self, nsd_file, dpath=None, syntax=True,
                         integrity=True, topology=True):
        """
        Validate a SONATA service.
        By default, it performs the following validations: syntax, integrity
        and network topology.
        :param nsd_file: service descriptor filename
        :param dpath: directory to search for function descriptors (VNFDs)
        :param syntax: specifies whether to validate syntax
        :param integrity: specifies whether to validate integrity
        :param topology: specifies whether to validate network topology
        :return: True if all validations were successful, False otherwise
        """

        # load service descriptor and referenced function descriptors
        self._load_service_descriptors()

        pass

    def validate_function(self, vnfd_file, syntax=True, integrity=True,
                          topology=True):
        """
        Validate a SONATA function (VNF).
        By default, it performs the following validations: syntax, integrity
        and network topology.
        :param vnf_file: function descriptor (VNFD) filename
        :param syntax: specifies whether to validate syntax
        :param integrity: specifies whether to validate integrity
        :param topology: specifies whether to validate network topology
        :return: True if all validations were successful, False otherwise
        """

        # load function descriptor
        vnfd = self._load_function_descriptor(vnfd_file)
        if not vnfd:
            return

        if syntax and not self._validate_function_syntax(vnfd):
            return

        if integrity and not self._validate_function_integrity(vnfd):
            return

        if topology and not self._validate_function_topology(vnfd):
            return

        return True

    def _load_project_descriptors(self, project):
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

        return self._load_service_descriptors(nsd_files[0],
                                              dpath=project.vnfd_root)


        # read VNFD files in project source
        vnfd_files = project.get_vnf_descriptors()
        prj_vnfds = self._load_vnfd_files(vnfd_files)

        if not prj_vnfds:
            log.warning("Project source does not contain VNF descriptors")

        # read NSD file and get its referenced function descriptors (VNFDS)
        self._vnfds = {}

        if len(self._nsd['network_functions']) > 0 and len(prj_vnfds) == 0:

            return

        for vnf in self._nsd['network_functions']:
            vnf_combo_id = self._build_vnf_combo_id(vnf['vnf_vendor'],
                                                    vnf['vnf_name'],
                                                    vnf['vnf_version'])
            if vnf_combo_id not in prj_vnfds.keys():
                log.error("Referenced VNF descriptor '{0}' could not be found"
                          .format(vnf_combo_id))
                return
            self._vnfds[vnf['vnf_id']] = prj_vnfds.pop(vnf_combo_id)
            self._vnfd_files[vnf['vnf_id']] = prj_vnfd_files.pop(vnf_combo_id)

        if len(prj_vnfds) > 0:
            log.warning("The following VNFs are present in project sources "
                        "but are not referenced in the service descriptor: {0}"
                        .format(prj_vnfds.keys()))
        return True

    def _load_service_descriptors(self, nsd_file, dpath='.'):
        log.debug("Loading service descriptor from file '{0}'"
                  .format(nsd_file))

        if not nsd_file:
            log.critical("Provided service descriptor file is invalid.")
            return False

        # load service descriptor
        self._load_service_descriptor(nsd_file)

        # load VNFDs at provided path
        vnfd_files = self._get_vnfd_files_from_dir(dpath)
        path_vnfds = self._load_vnfd_files(vnfd_files)

        # get referenced VNFDs
        self._vnfds = {}
        nsd_functions = self._nsd['network_functions']
        if not nsd_functions:
            log.warning("Service '{0}' does not have functions")
            return

        if not path_vnfds or len(path_vnfds) == 0:
            return

        if len(nsd_functions) > 0 and len(path_vnfds) == 0:
            log.error("Service '{0}' references function "
                      "descriptors (VNFs) but none were found in  the path "
                      "'{1}'."
                      .format(nsd_file, dpath))
            return False

        for vnf in nsd_functions:
            vnf_combo_id = self._build_vnf_combo_id(vnf['vnf_vendor'],
                                                    vnf['vnf_name'],
                                                    vnf['vnf_version'])
            if vnf_combo_id not in path_vnfds.keys():
                log.error("Referenced VNF descriptor '{0}' could not be "
                          "found in path '{1}'"
                          .format(vnf_combo_id, dpath))
                return False



## TODO: different id, same combo_id! This is integrity!

    def _load_function_descriptor(self, vnfd_file):
        vnfd = self._read_descriptor_file(vnfd_file)
        if not vnfd:
            return
        return vnfd


    def _load_service_descriptor(self, nsd_file):
        with open(nsd_file, 'r') as _file:
            self._nsd = yaml.load(_file)
            if not self._nsd:
                log.error("Couldn't read service descriptor file: '{0}'"
                          .format(nsd_file))
                return
            self._nsd_file = nsd_file



    def _list_vnfd_files(self, path):
        """
        Retrieves a list of function descriptor files (VNFDs) in a given
        directory path.
        :param path: directory to search for VNF descriptor files
        :return: list of VNF descriptor files
        """
        vnfd_files = []
        for root, dirs, files in os.walk(path):
            for file in files:
                if file.endswith(self._dext):
                    vnfd_files.append(os.path.join(root, file))
        return vnfd_files

    def _read_descriptor_files(self, vnfd_files):
        """
        Loads the VNF descriptors provided in the file list. It builds a
        dictionary of the loaded VNF descriptor files. Each entry has the
        key of the VNF combo ID, in the format 'vendor.name.version'.
        :param vnfd_files: filename list of VNF descriptors
        :return: Dictionary of VNF descriptor dictionaries. None if
        unsuccessful.
        """
        vnfd_dict = {}
        for vnfd_file in vnfd_files:
            vnfd = Validator._read_descriptor_file(vnfd_file)
            if not vnfd:
                continue
            vnf_combo_id = self._get_vnf_combo_id(vnfd)

            if vnf_combo_id in vnfd_dict:
                log.error("Duplicate VNF descriptor in file: '{0}'"
                          .format(vnfd_file))
                continue
            vnfd_dict[vnf_combo_id] = vnfd
        return vnfd_dict

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
            return descriptor

    def _validate_service_syntax(self):
        """
        Validate a the syntax of a service and all of its descriptors.
        :return:
        """

        log.debug("Validate syntax of Service Descriptor file '{0}'"
                  .format(self._nsd_file))
        if not self._schema_validator.validate(
              self._nsd, SchemaValidator.SCHEMA_SERVICE_DESCRIPTOR):
            log.error("Bad Service Descriptor file: '{0}'"
                      .format(self._nsd_file))
            return

        log.debug("Validate syntax of Function Descriptor files:")
        for vnfd in self._vnfds.keys():
            log.debug("... '{0}'".format(self._vnfd_files[vnfd]))
            if not self._schema_validator.validate(
                  self._vnfds[vnfd],
                    SchemaValidator.SCHEMA_FUNCTION_DESCRIPTOR):
                log.error("Bad Function Descriptor file: {0}"
                          .format(self._vnfd_files[vnfd]))
                return

        return True

    def _validate_function_syntax(self, vnfd):
        """
        Validate the syntax of a function (VNF) against its schema.
        :param vnfd: function descriptor dictionary
        :return: True if syntax is correct
        """
        vnf_combo_id = self._get_vnf_combo_id(vnfd)
        log.debug("Validating syntax of function descriptor '{0}'"
                  .format(vnf_combo_id))
        if not self._schema_validator.validate(
              vnfd, SchemaValidator.SCHEMA_FUNCTION_DESCRIPTOR):
            log.error("Invalid syntax in function descriptor '{0}'"
                      .format(vnf_combo_id))
            return

        return True

    def _validate_function_integrity(self, vnfd):
        """
        Validate the integrity of a function (VNF).
        It checks for inconsistencies in the identifiers of connection
        points, virtual deployment units (VDUs), ...
        :param vnfd: function descriptor dictionary
        :return: True if integrity is correct
        """
        vnf_combo_id = self._get_vnf_combo_id(vnfd)
        log.debug("Validating integrity of function descriptor '{0}'"
                  .format(vnf_combo_id))

        # get connection points of VNF
        cxpts = []
        for cxp in vnfd['connection_points']:
            if cxp['id'] in cxpts:
                log.error("[VNF: {0}] Duplicate connection point: '{1}'"
                          .format(vnf_combo_id, cxp['id']))
                return
            cxpts.append(cxp['id'])

        # get connection points of VDUs
        for vdu in vnfd['virtual_deployment_units']:
            for cxp in vdu['connection_points']:
                if cxp['id'] in cxpts:
                    log.error("[VNF: {0}, VDU: {1}] Duplicate connection "
                              "point: '{2}'"
                              .format(vnf_combo_id, vdu['id'], cxp['id']))
                    return
                cxpts.append(cxp['id'])

        return True

    def _validate_function_topology(self, vnfd):
        """
        Validate the network topology of a function.
        It builds the network graph of the function, including VDU connections.
        :param vnfd: function descriptor dictionary
        :return: True if topology doesn't present issues
        """
        # build function network graph
        fg = self._build_function_graph(vnfd)

        # check for path cycles



    def _validate_service_topology(self):
        """
        Validate the network topology of a service.
        :return:
        """
        # build service network graph
        sg = self._build_service_graph()
        if not sg:
            return

        # check for forwarding cycles
        Validator._find_graph_cycles(sg, sg.nodes()[0])

        return True

    def _build_function_graph(self, vnfd):
        """
        Build the network graph of a function.
        This graph will be later used to check for invalid or cyclic paths.
        :return:
        """
        vnf_combo_id = self._get_vnf_combo_id(vnfd)

        # function network graph
        fg = nx.Graph()

        if not Validator._assign_nodes(fg, vnf_combo_id, vnfd, level=1):
            return

        if not Validator._assign_nodes(fg, vnf_combo_id, vnfd, level=2):
            return

        # add edges to the graph by reading the virtual links
        if not Validator._assign_edges(fg, vnf_combo_id, vnfd, level=2):
            return

        return True

    @staticmethod
    def _assign_nodes(graph, descriptor_id, descriptor, level=1):
        print(level)
        # assign nodes
        if level == 1:
            # add connection points as nodes to the function graph
            for cxp in descriptor['connection_points']:
                if cxp['type'] == 'interface':
                    log.debug("[VNF: {0}] Adding node '{1}'"
                              .format(descriptor_id, cxp['id']))
                    graph.add_node(cxp['id'], attr_dict={'level': 1})

        elif level == 2:
            for vdu in descriptor['virtual_deployment_units']:
                for cxp in vdu['connection_points']:
                    if cxp['type'] == 'interface':
                        log.debug("[VNF: {0}, VDU: {1}] Adding node '{2}'"
                                  .format(descriptor_id,
                                          vdu['id'],
                                          descriptor_id + '-' + cxp['id']))
                        graph.add_node(descriptor_id + '-' + cxp['id'],
                                       attr_dict={'level': 2,
                                                  'parent': descriptor_id})

        # remove nodes associated with E-LAN links
        for vlink in descriptor['virtual_links']:
            if vlink['connectivity_type'] != 'E-LAN':
                continue
            for ref_cxp in vlink['connection_points_reference']:
                    if ref_cxp in graph.nodes():
                        graph.remove_node(ref_cxp)
                    elif descriptor_id + '-' + ref_cxp in graph.nodes():
                        graph.remove_node(descriptor_id + '-' + ref_cxp)

        return True

    def _build_service_graph(self):
        """
        Build the network graph of a service.
        This graph will be later used for checking invalid or cyclic
        paths.
        :return:
        """
        # service network graph
        sg = nx.Graph()

        # add connection points as nodes to the service graph
        for cxp in self._nsd['connection_points']:
            if cxp['type'] == 'interface':
                sg.add_node(cxp['id'], attr_dict={'level': 0})
        for vnf_id in self._vnfds.keys():
            for cxp in self._vnfds[vnf_id]['connection_points']:
                if cxp['type'] == 'interface':
                    sg.add_node(vnf_id + ':' + cxp['id'],
                                attr_dict={'level': 1, 'parents': vnf_id})

        # eliminate all connection points associated with bridged (E-LAN) links
        for vlink in self._nsd['virtual_links']:
            if vlink['connectivity_type'] != 'E-LAN':
                continue
            cxpoints = vlink['connection_points_reference']
            for cxp in cxpoints:
                sg.remove_node(cxp)

        # add edges between functions to the graph
        if not Validator._assign_edges(sg, 'ns', self._nsd):
            return

        # add VDU nodes and edges between them, within each function
        for vnf_id in self._vnfds.keys():
            vnfd = self._vnfds[vnf_id]

            # add VDU connection points as nodes
            for vdu in vnfd['virtual_deployment_units']:
                for cxp in vdu['connection_points']:
                    if cxp['type'] == 'interface':
                        cxp_id = vnf_id + '-' + cxp['id']
                        log.debug("Adding node '{0}'".format(cxp_id))
                        sg.add_node(cxp_id, attr_dict={'level': 2,
                                                       'parents':
                                                           vnf_id + '.' +
                                                           vdu['id']})

            # eliminate all connection points associated with E-LAN links
            for vlink in vnfd['virtual_links']:
                if vlink['connectivity_type'] != 'E-LAN':
                    continue
                cxpoints = vlink['connection_points_reference']
                for cxp in cxpoints:
                    if vnf_id + '-' + cxp in sg.nodes():
                        sg.remove_node(vnf_id + '-' + cxp)

            # add edges based on virtual links of the VNF
            if not Validator._assign_edges(sg, vnf_id, vnfd, level=2):
                return

            # add edges within VDU interfaces (VDUs cannot be decomposed)
            for node_x in sg.nodes(data=True):
                n_x = node_x[0]
                attr_x = dict(node_x[1])
                if attr_x['level'] != 2:
                    continue
                for node_y in sg.nodes(data=True):
                    n_y = node_y[0]
                    attr_y = dict(node_y[1])
                    if attr_y['level'] != 2 or n_x == n_y:
                        continue
                    if attr_x['parents'] == attr_y['parents']:
                        log.debug("Adding intra VDU edge: {0}<->{1}"
                                  .format(n_x, n_y))
                        sg.add_edge(n_x, n_y, attr_dict={'scope': 'intra'})

        # TODO: remove temporary export of the graph
        nx.write_graphml(sg, 'sample.graphml')

        return sg

    @staticmethod
    def _assign_edges(graph, descriptor_id, descriptor, level=1):
        for vlink in descriptor['virtual_links']:
            ctype = vlink['connectivity_type']
            # TODO: add support for 'E-Tree': topology not defined in schema!
            if ctype != 'E-Line':
                continue
            cxp_ref = vlink['connection_points_reference']
            if len(cxp_ref) != 2:
                log.error("The virtual link '{0}' of type 'E-Line' must only "
                          "comprise 2 connection points"
                          .format(vlink['id']))
                return

            for idx, cxp in enumerate(cxp_ref):

                if not graph.has_node(cxp):
                    parent_cxp = descriptor_id + ':' + cxp
                    vdu_cxp = descriptor_id + '-' + cxp
                    if level == 2 and graph.has_node(parent_cxp):
                        cxp_ref[idx] = parent_cxp
                    elif level == 2 and graph.has_node(vdu_cxp):
                        cxp_ref[idx] = vdu_cxp
                    else:
                        log.error("[Level: {0}] The connection point '{1}' "
                                  "defined in virtual link '{2}' is not "
                                  "defined."
                                  .format(level, cxp, vlink['id']))
                        return
            log.debug("Adding edge between connection points: {0}<->{1}"
                      .format(cxp_ref[0],
                              cxp_ref[1]))
            graph.add_edge(cxp_ref[0],
                           cxp_ref[1])
        return True

    @staticmethod
    def _get_vnf_combo_id(vnfd):
        return Validator._build_vnf_combo_id(vnfd['vendor'], vnfd['name'],
                                             vnfd['version'])

    @staticmethod
    def _build_vnf_combo_id(vnf_vendor, vnf_name, vnf_version):
        return vnf_vendor + '.' + vnf_name + '.' + vnf_version

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
        son-validate --service ./nsd_file.yml --path ./vnfds/
        son-validate --function ./vnfd_file.yml
        son-validate --function ./vnfds/
        """,
    )

    parser.add_argument(
        "--workspace",
        dest="workspace_path",
        help="Specify the directory of the SDK workspace for validation of "
             "an SDK project. If not specified will assume the directory: '{}'"
             .format(Workspace.DEFAULT_WORKSPACE_DIR),
        required=False
    )
    parser.add_argument(
        "--project",
        dest="project_path",
        help="Validate the service of the specified SDK project. If "
             "not specified will assume the current directory: '{}'\n"
             .format(os.getcwd()),
        required=False
    )
    parser.add_argument(
        "--package",
        dest="pd",
        help="Validate the specified package descriptor. "
    )
    parser.add_argument(
        "--service",
        dest="nsd",
        help="Validate the specified service descriptor. "
             "The directory of descriptors referenced in the service "
             "descriptor should be specified using the argument '--path'.",
        required=False
    )
    parser.add_argument(
        "--function",
        dest="vnfd",
        help="Validate the specified function descriptor. If a directory is "
             "specified, it will search for descriptor files with extension "
             "defined in '--dformat' or default '{0}'",
        required=False
    )
    parser.add_argument(
        "--path",
        help="Specify a directory to search for descriptors. Particularly "
             "useful when using the '--service' argument.",
        required=False
    )
    parser.add_argument(
        "--dformat",
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

    # parse arguments
    args = parser.parse_args()

    # by default, perform all validations
    if not args.syntax and not args.integrity and not args.topology:
        args.syntax = args.integrity = args.topology = True

    validator = None

    if args.project_path and not (args.pd or args.nsd or args.vnfd):

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

        validator = Validator(workspace, project=project)

    elif args.pd and not (args.project_path or args.nsd or args.vnfd):
        pass

    elif args.nsd and not (args.project_path or args.pd or args.vnfd):
        pass

    elif args.vnfd and not (args.project_path or args.pd or args.nsd):
        validator = Validator()
        validator.validate_function(args.vnfd)

    else:
        parser.error("One of the following arguments must be exclusively "
                     "specified:"
                     "\n\t--project"
                     "\n\t--package"
                     "\n\t--service"""
                     "\n\t--function\n")
        exit(1)


