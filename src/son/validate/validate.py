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

        self._schema_validator = SchemaValidator(self._workspace)

    def validate(self):
        """
        Validate a project.
        It performs the syntax and network topology validation of a service.
        :return:
        """
        # validate syntax
        self._validate_service_syntax()

        # validate topology
        self._validate_service_graph()

    def _validate_service_syntax(self):
        """
        Validate a the syntax of a service and all of its descriptors.
        :return:
        """
        pass

    def _validate_service_graph(self):
        """
        Validate the network topology of a service.
        :return:
        """
        # build service network graph
        self._build_service_graph()

        # check for forwarding cycles
        self._find_service_graph_cycles()

    def _build_service_graph(self):
        """
        Build the network graph of a service.
        This graph will be later utilized for checking invalid or cyclic
        paths.
        :return:
        """

        # init service network graph
        sg = nx.Graph()

        # load project service descriptor
        nsd_file = self._project.get_ns_descriptor()[0]
        with open(nsd_file, 'r') as _file:
            nsd = yaml.load(_file)
            assert nsd is not None

        # load all project function descriptors
        prj_vnfds = {}
        vnfd_files = self._project.get_vnf_descriptors()
        for vnfd_file in vnfd_files:
            with open(vnfd_file, 'r') as _file:
                vnfd = yaml.load(_file)
                assert vnfd is not None
                vnf_combo_id = vnfd['vendor'] + '.' + vnfd['name'] + '.' + \
                               vnfd['version']
                prj_vnfds[vnf_combo_id] = vnfd

        # assign vnf descriptors referenced in the service descriptor
        ref_vnfds = {}
        for func in nsd['network_functions']:
            vnf_combo_id = func['vnf_vendor'] + '.' + func['vnf_name'] + \
                           '.' + func['vnf_version']
            if vnf_combo_id in prj_vnfds.keys():
                ref_vnfds[func['vnf_id']] = prj_vnfds[vnf_combo_id]

        # add connection points as nodes to the service graph
        for cp in nsd['connection_points']:
            if cp['type'] == 'interface':
                sg.add_node(cp['id'], attr_dict={'used': False})
        for vnf_id in ref_vnfds.keys():
            for cp in ref_vnfds[vnf_id]['connection_points']:
                if cp['type'] == 'interface':
                    sg.add_node(vnf_id + ':' + cp['id'], attr_dict={'used':
                                                                    False})

        # add edges to the graph
        for vlink in nsd['virtual_links']:
            ctype = vlink['connectivity_type']
            if ctype != 'E-Line':  # TODO: add support for 'E-Tree'
                continue

            cp_ref = vlink['connection_points_reference']
            if len(cp_ref) != 2:
                log.error("[virtual_link id: '{}'] E-Line must only comprise 2"
                          " connection points"
                          .format(vlink['id']))
                return

            for cp in cp_ref:
                if not sg.has_node(cp):
                    log.error("[virtual_link id: '{}'] The following "
                              "connection point is not defined: {}"
                              .format(vlink['id'], cp))
                    return

            sg.add_edge(cp_ref[0], cp_ref[1])

    def _find_service_graph_cycles(self):
        """
        Check if network graph has simple cycles.
        :return:
        """
        pass


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
