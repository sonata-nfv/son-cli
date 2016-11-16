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

    def __init__(self, workspace, project):
        self._workspace = workspace
        self._project = project
        coloredlogs.install(level=workspace.log_level)

        # keep project descriptors
        self._nsd_file = None
        self._nsd = None
        self._vnfd_files = {}
        self._vnfds = {}

        # syntax validation
        self._schema_validator = SchemaValidator(self._workspace)

    def validate(self):
        """
        Validate a project.
        It performs the syntax and network topology validation of a service.
        :return:
        """
        success = True

        # load and correlate project descriptors
        log.info("Loading project descriptors")
        if not self._load_project_descriptors():
            return False

        # validate syntax
        log.info("Validating syntax of descriptors")
        if not self._validate_service_syntax():
            return False

        # validate topology
        log.info("Validating service network topology")
        if not self._validate_service_graph():
            return False

        log.info("SUCCESS")
        return True

    def _load_project_descriptors(self):

        # load project service descriptor (NSD)
        nsd_files = self._project.get_ns_descriptor()
        if not nsd_files:
            return

        if len(nsd_files) > 1:
            log.error("Found multiple service descriptors in project '{0}': "
                      "{1}".format(self._project.project_root, nsd_files))
            return

        entry_nsd_file = nsd_files[0]
        with open(entry_nsd_file, 'r') as _file:
            self._nsd = yaml.load(_file)
            if not self._nsd:
                log.error("Couldn't read service descriptor file: '{0}'"
                          .format(entry_nsd_file))
                return
            self._nsd_file = entry_nsd_file

        # read VNFD files in project source
        prj_vnfds = {}
        prj_vnfd_files = {}
        vnfd_files = self._project.get_vnf_descriptors()
        if vnfd_files:
            for vnfd_file in vnfd_files:
                with open(vnfd_file, 'r') as _file:
                    vnfd = yaml.load(_file)
                    if not vnfd:
                        log.error("Couldn't read VNF descriptor file: '{0}'"
                                  .format(vnfd_file))
                        return

                    vnf_combo_id = vnfd['vendor'] + '.' + vnfd['name'] + '.' \
                        + vnfd['version']

                    if vnf_combo_id in prj_vnfds:
                        log.error("Duplicate VNF descriptor in file: '{0}'"
                                  .format(vnfd_file))
                        return

                    prj_vnfds[vnf_combo_id] = vnfd
                    prj_vnfd_files[vnf_combo_id] = vnfd_file

        if not prj_vnfds:
            log.warning("Project source does not contain VNF descriptors")

        # read NSD file and get its referenced function descriptors (VNFDS)
        self._vnfds = {}

        if len(self._nsd['network_functions']) > 0 and len(prj_vnfds) == 0:
            log.error("Service descriptor '{0}' references function "
                      "descriptors (VNFs) but none were found in project "
                      "sources."
                      .format(entry_nsd_file))
            return

        for vnf in self._nsd['network_functions']:
            vnf_combo_id = vnf['vnf_vendor'] + '.' + vnf['vnf_name'] + \
                           '.' + vnf['vnf_version']
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

    def _validate_service_graph(self):
        """
        Validate the network topology of a service.
        :return:
        """
        # build service network graph
        sg = self._build_service_graph()

        # check for forwarding cycles
        Validator.__find_graph_cycles__(sg, sg.nodes()[0])

        return True

    def _build_service_graph(self):
        """
        Build the network graph of a service.
        This graph will be later utilized for checking invalid or cyclic
        paths.
        :return:
        """
        # service network graph
        sg = nx.Graph()

        # add connection points as nodes to the service graph
        for cxp in self._nsd['connection_points']:
            if cxp['type'] == 'interface':
                sg.add_node(cxp['id'], attr_dict={'group': None})
        for vnf_id in self._vnfds.keys():
            for cxp in self._vnfds[vnf_id]['connection_points']:
                if cxp['type'] == 'interface':
                    sg.add_node(vnf_id + ':' + cxp['id'],
                                attr_dict={'group': vnf_id})

        # eliminate all connection points associated with bridged (E-LAN) links
        for vlink in self._nsd['virtual_links']:
            if vlink['connectivity_type'] != 'E-LAN':
                continue

            cxpoints = vlink['connection_points_reference']
            for cxp in cxpoints:
                sg.remove_node(cxp)

        # add edges between functions to the graph
        for vlink in self._nsd['virtual_links']:
            ctype = vlink['connectivity_type']
            if ctype != 'E-Line':  # TODO: add support for 'E-Tree'
                continue

            cxp_ref = vlink['connection_points_reference']
            if len(cxp_ref) != 2:
                log.error("The virtual link '{0}' of type 'E-Line' must only "
                          "comprise 2 connection points"
                          .format(vlink['id']))
                return

            for cxp in cxp_ref:
                if not sg.has_node(cxp):
                    log.error("The connection point '{0}' defined in "
                              "virtual link '{1}' is not defined."
                              .format(cxp, vlink['id']))
                    return
            sg.add_edge(cxp_ref[0], cxp_ref[1])

        # add edges between nodes of the same group TODO: go deeper into VDUs
        for node_x in sg.nodes(data=True):
            print(node_x)
            if not node_x[1]['group']:
                continue

            for node_y in sg.nodes(data=True):
                if node_x[0] == node_y[0]:
                    continue
                if node_x[1]['group'] == node_y[1]['group']:
                    print("adding edge: {0} <> {1}".format(node_x[0],
                                                           node_y[0]))
                    sg.add_edge(node_x[0], node_y[0])

        return sg

    @staticmethod
    def __find_graph_cycles__(graph, node, prev_node=None, backtrace=None):

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
            return Validator.__find_graph_cycles__(graph, neighbor,
                                                   prev_node=node,
                                                   backtrace=backtrace)
        return backtrace


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="Validate a SONATA project service")

    parser.add_argument(
        "--workspace",
        help="Specify workspace. If not specified "
             "will assume '{}'".format(Workspace.DEFAULT_WORKSPACE_DIR),
        required=False)

    parser.add_argument(
        "--project",
        help="Validate the project at the specified location. "
             "If not specified will assume current directory '{}'"
             .format(os.getcwd()),
        required=False)

    args = parser.parse_args()

    if args.workspace:
        ws_root = args.workspace
    else:
        ws_root = Workspace.DEFAULT_WORKSPACE_DIR

    prj_root = args.project if args.project else os.getcwd()

    # Obtain Workspace object
    workspace = Workspace.__create_from_descriptor__(ws_root)
    if not workspace:
        sys.stderr.write("Invalid workspace path: '%s'\n" % ws_root)
        exit(1)

    project = Project.__create_from_descriptor__(workspace, prj_root)
    if not project:
        sys.stderr.write("Invalid project path: '%s'\n  " % prj_root)
        exit(1)

    val = Validator(workspace, project)
    val.validate()
