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
import logging
import networkx as nx
from collections import OrderedDict
from son.validate.util import descriptor_id, read_descriptor_file
from son.validate import event

log = logging.getLogger(__name__)
evtlog = event.get_logger('validator.events')


class DescriptorStorage(object):

    def __init__(self):
        """
        Initialize an object to store descriptors.
        """
        # dictionaries for services, functions and units
        self._packages = {}
        self._services = {}
        self._functions = {}
        self._units = {}

    @property
    def packages(self):
        """
        Provides the stored packages.
        :return: dictionary of packages.
        """
        return self._packages

    @property
    def services(self):
        """
        Provides the stored services.
        :return: dictionary of services.
        """
        return self._services

    @property
    def functions(self):
        """
        Provides the stored functions.
        :return: dictionary of functions.
        """
        return self._functions

    def service(self, sid):
        """
        Obtain the service for the provided service id
        :param sid: service id
        :return: service descriptor object
        """
        if sid not in self.services:
            log.error("Service id='{0}' is not stored.".format(sid))
            return
        return self.services[sid]

    def create_package(self, descriptor_file):
        """
        Create and store a package based on the provided descriptor filename.
        If a package is already stored with the same id, it will return the
        stored package.
        :param descriptor_file: package descriptor filename
        :return: created package object or, if id exists, the stored package.
        """
        if not os.path.isfile(descriptor_file):
            return
        new_package = Package(descriptor_file)
        if new_package.id in self._packages:
            return self._packages[new_package.id]

        self._packages[new_package.id] = new_package
        return new_package

    def create_service(self, descriptor_file):
        """
        Create and store a service based on the provided descriptor filename.
        If a service is already stored with the same id, it will return the
        stored service.
        :param descriptor_file: service descriptor filename
        :return: created service object or, if id exists, the stored service.
        """
        if not os.path.isfile(descriptor_file):
            return
        new_service = Service(descriptor_file)
        if not new_service.content or not new_service.id:
            return

        if new_service.id in self._services:
            return self._services[new_service.id]

        self._services[new_service.id] = new_service
        return new_service

    def function(self, fid):
        """
        Obtain the function for the provided function id
        :param fid: function id
        :return: function descriptor object
        """
        if fid not in self._functions[fid]:
            log.error("Function id='{0}' is not stored.".format(fid))
            return
        return self.functions[fid]

    def create_function(self, descriptor_file):
        """
        Create and store a function based on the provided descriptor filename.
        If a function is already stored with the same id, it will return the
        stored function.
        :param descriptor_file: function descriptor filename
        :return: created function object or, if id exists, the stored function.
        """
        if not os.path.isfile(descriptor_file):
            return
        new_function = Function(descriptor_file)
        if new_function.id in self._functions.keys():
            return self._functions[new_function.id]

        self._functions[new_function.id] = new_function
        return new_function


class Node:
    def __init__(self, nid):
        """
        Initialize a node object.
        Typically, a node holds multiple network interfaces.
        :param nid: node id
        """
        self._id = nid
        self._interfaces = []

    @property
    def id(self):
        """
        Identifier of the node.
        :return: node id
        """
        return self._id

    @property
    def interfaces(self):
        """
        Provides a list of interfaces associated with the node.
        :return: interface list
        """
        return self._interfaces

    @interfaces.setter
    def interfaces(self, value):
        self._interfaces = value

    def add_interface(self, interface):
        """
        Associate a new interface to the node.
        :param interface: interface id
        """
        if interface in self.interfaces:
            evtlog.log("Duplicate connection point",
                       "The interface id='{0}' is already stored in node "
                       "id='{1}'".format(interface, self.id),
                       self.id,
                       'evt_duplicate_cpoint')
            return
        log.debug("Node id='{0}': adding connection point '{1}'"
                  .format(self.id, interface))
        self._interfaces.append(interface)

        return True


class Link:
    def __init__(self, link_id, iface_u, iface_v):
        """
        Initialize a link object.
        A link defines a connection between two interfaces.
        :param link_id: link id
        :param iface_u: interface u
        :param iface_v: interface v
        """
        self._id = link_id
        self._iface_pair = [iface_u, iface_v]

    def __repr__(self):
        return self.__str__()

    def __str__(self):
        return "{} -- {}".format(self.id, self.iface_u, self.iface_v)

    @property
    def id(self):
        return self._id

    @property
    def interfaces(self):
        """
        The two interfaces composing the link in a list format [u, v]
        :return: interface list
        """
        return self._iface_pair

    @property
    def iface_u(self):
        """
        Interface u
        :return: interface u
        """
        return self._iface_pair[0]

    @property
    def iface_v(self):
        """
        Interface v
        :return: interface v
        """
        return self._iface_pair[1]


class Bridge:
    def __init__(self, bridge_id, interfaces):
        """
        Initialize a bridge object.
        A bridge contains a list of N associated interfaces.
        """
        assert bridge_id
        assert interfaces

        self._id = bridge_id
        self._interfaces = interfaces

    def __repr__(self):
        return self.__str__()

    def __str__(self):
        return "{}".format(self.interfaces)

    @property
    def id(self):
        return self._id

    @property
    def interfaces(self):
        return self._interfaces


class Descriptor(Node):
    def __init__(self, descriptor_file):
        """
        Initialize a generic descriptor object.
        This object inherits the node object.
        All descriptor objects contains the following properties:
            - id
            - content: descriptor dictionary
            - filename: filename of the descriptor
        :param descriptor_file: filename of the descriptor
        """
        self._id = None
        self._content = None
        self._filename = None
        self.filename = descriptor_file
        super().__init__(self.id)
        self._complete_graph = None
        self._graph = None
        self._links = {}
        self._bridges = {}

    @property
    def id(self):
        """
        Identification of descriptor
        :return: descriptor id
        """
        return self._id

    @property
    def content(self):
        """
        Descriptor dictionary.
        :return: descriptor dict
        """
        return self._content

    @content.setter
    def content(self, value):
        """
        Sets the descriptor dictionary.
        This modification will impact the id of the descriptor.
        :param value: descriptor dict
        """
        self._content = value
        self._id = descriptor_id(self._content)

    @property
    def filename(self):
        """
        Filename of the descriptor
        :return: descriptor filename
        """
        return self._filename

    @filename.setter
    def filename(self, value):
        """
        Sets the descriptor filename.
        This modification will impact the content and id of the descriptor.
        :param value: descriptor filename
        """
        self._filename = value
        content = read_descriptor_file(self._filename)
        if content:
            self.content = content

    @property
    def links(self):
        """
        Provides the links associated with the descriptor.
        :return: dictionary of link objects
        """
        return self._links

    @property
    def bridges(self):
        """
        Provides the bridges associated with the descriptor.
        :return: dictionary of bridge objects
        """
        return self._bridges

    @property
    def link_interfaces(self):

        link_interfaces = []
        for lid, link in self.links.items():
            link_interfaces += link.interfaces

        return link_interfaces

    @property
    def bridge_interfaces(self):
        bridge_interfaces = []
        for bid, bridge in self.bridges.items():
            bridge_interfaces += bridge.interfaces
        return bridge_interfaces

    @property
    def graph(self):
        """
        Network topology graph of the descriptor.
        :return: topology graph (networkx.Graph)
        """
        return self._graph

    @graph.setter
    def graph(self, value):
        """
        Sets the topology graph of the descriptor.
        :param value: topology graph (networkx.Graph)
        :return:
        """
        self._graph = value

    @property
    def complete_graph(self):
        return self._complete_graph

    @complete_graph.setter
    def complete_graph(self, value):
        self._complete_graph = value

    def load_interfaces(self):
        """
        Load interfaces of the descriptor.
        It reads the section 'connection_points' of the descriptor contents.
        """
        for cxpt in self.content['connection_points']:
            if not self.add_interface(cxpt['id']):
                return
        return True

    def add_bridge(self, bid, interfaces):
        """
        Add bridge to the descriptor.

        :param bid:
        :param interfaces:
        :return:
        """
        assert bid
        assert len(interfaces) > 0
        assert bid not in self.bridges.keys()

        self._bridges[bid] = Bridge(bid, interfaces)

    def add_link(self, lid, interfaces):
        """
        Add link to the descriptor.
        Associate a connection, between two interfaces.
        :param lid: link id
        :param interfaces: interface pair list
        """
        assert lid
        assert len(interfaces) == 2
        assert lid not in self.links.keys()

        self._links[lid] = Link(lid, interfaces[0], interfaces[1])

    def load_virtual_links(self):
        """
        Load 'virtual_links' section of the descriptor.
        - 'e-line' virtual links will be stored in Link objects
        - 'e-lan' virtual links will be stored in Bridge objects
        """
        if 'virtual_links' not in self.content:
            return

        for link in self.content['virtual_links']:
            ltype = link['connectivity_type'].lower()
            if ltype == 'e-line':
                self.add_link(link['id'],
                              link['connection_points_reference'])

            elif ltype == 'e-lan':
                self.add_bridge(link['id'],
                                link['connection_points_reference'])
        return True

    def find_unused_interfaces(self):
        """
        Provides a list of interfaces that are not referenced by
        'virtual_links'. Should only be invoked after links are loaded.
        :return:
        """
        unused_ifaces = []
        for iface in self.interfaces:
            if iface not in self.link_interfaces and \
                    iface not in self.bridge_interfaces:
                unused_ifaces.append(iface)

        return unused_ifaces


class Package(Descriptor):

    def __init__(self, descriptor_file):
        """
        Initialize a package object. This inherits the descriptor object.
        :param descriptor_file: descriptor filename
        """
        super().__init__(descriptor_file)

    @property
    def entry_service_file(self):
        """
        Provides the entry point service of the package.
        :return: service id
        """
        return self.content['entry_service_template']

    @property
    def service_descriptors(self):
        """
        Provides a list of the service descriptor file names, referenced in
        the package.
        :return: list of service descriptor file names
        """
        service_list = []
        for item in self.content['package_content']:
            if item['content-type'] == \
                    'application/sonata.service_descriptor':
                service_list.append(item['name'])
        return service_list

    @property
    def function_descriptors(self):
        """
        Provides a list of the service descriptor file names, referenced in
        the package.
        :return: list of function descriptor file names
        """
        function_list = []
        for item in self.content['package_content']:
            if item['content-type'] == \
                    'application/sonata.function_descriptor':
                function_list.append(item['name'])
        return function_list

    @property
    def descriptors(self):
        """
        Provides a list of the descriptors, referenced in the package.
        :return: list of descriptor file names
        """
        return self.service_descriptors + self.function_descriptors

    def md5(self, descriptor_file):
        """
        Retrieves the MD5 hash defined in the package content of the specified
        descriptor
        :param descriptor_file: descriptor filename
        :return: md5 hash if descriptor found, None otherwise
        """
        descriptor_file = '/' + descriptor_file
        for item in self.content['package_content']:
            if item['name'] == descriptor_file:
                return item['md5']


class Service(Descriptor):

    def __init__(self, descriptor_file):
        """
        Initialize a service object. This inherits the descriptor object.
        :param descriptor_file: descriptor filename
        """
        super().__init__(descriptor_file)
        self._functions = {}
        self._vnf_id_map = {}
        self._fw_graphs = list()

    @property
    def functions(self):
        """
        Provides the functions specified in the service.
        :return: functions dict
        """
        return self._functions

    @property
    def fw_graphs(self):
        """
        Provides the forwarding paths specified in the service.
        :return: forwarding paths dict
        """
        return self._fw_graphs

    @property
    def all_function_interfaces(self):
        """
        Provides a list of interfaces from all functions of this service.
        """
        all_interfaces = []
        for fid, function in self.functions.items():
            for iface in function.interfaces:
                all_interfaces.append(self.vnf_id(function) + ':' + iface)
        return all_interfaces

    def mapped_function(self, vnf_id):
        """
        Provides the function associated with a 'vnf_id' defined in the
        service content.
        :param vnf_id: vnf id
        :return: function object
        """
        if vnf_id not in self._vnf_id_map or self._vnf_id_map[vnf_id] not in\
                self._functions:
            #log.error("Function of vnf_id='{}' is not mapped".format(vnf_id))
            return
        return self._functions[self._vnf_id_map[vnf_id]]

    def vnf_id(self, function):
        """
        Provides the vnf id associated with the provided function.
        :param function: function object
        :return: vnf id
        """
        for vnf_id, fid in self._vnf_id_map.items():
            if fid == function.id:
                return vnf_id
        return

    def function_of_interface(self, interface):
        """
        Provides the function associated with an interface.
        :param interface: interface str
        :return: function object
        """


        for fid, f in self.functions.items():
            for iface in f.interfaces:
                if iface == interface or \
                                (self.vnf_id(f) + ':' + iface) == interface:
                    return f

    def associate_function(self, function, vnf_id):
        """
        Associate a function to the service.
        :param function: function object
        :param vnf_id: vnf id, defined in the service descriptor content
        """
        if type(function) is not Function:
            log.error("The function (VNF) id='{0}' has an invalid type"
                      .format(function.id))
            return

        if function.id in self.functions:
            log.error("The function (VNF) id='{0}' is already associated with "
                      "service id='{1}'".format(function.id, self.id))
            return

        log.debug("Service '{0}': associating function id='{1}' with vnf_id="
                  "'{2}'".format(self.id, function.id, vnf_id))

        self._functions[function.id] = function
        self._vnf_id_map[vnf_id] = function.id

    def build_topology_graph(self, level=1, bridges=False,
                             vdu_inner_connections=True):
        """
        Build the network topology graph of the service.
        :param level: indicates the granulariy of the graph
                    0: service level (does not show VNF interfaces)
                    1: service level (with VNF interfaces) - default
                    2: VNF level (showing VDUs but not VDU interfaces)
                    3: VDU level (with VDU interfaces)

        :param deep: indicates the granularity of the graph
                     True - graph will include topology graphs of functions
                     False - graph will only include the service topology graph
        :param bridges: indicates whether bridges should be included in
                        the graph
        """
        assert 0 <= level <= 3  # level must be 0, 1, 2, 3

        graph = nx.Graph()

        def_node_attrs = {'label': '',
                          'level': level,
                          'parent_id': self.id,
                          'type': ''  # 'iface' | 'br-iface' | 'bridge'
                          }

        def_link_attrs = {'label': '',
                          'level': '',
                          'type': ''  # 'iface' | 'br-iface' | 'vdu_in'
                          }

        # assign nodes from service interfaces
        interfaces = self.link_interfaces
        if bridges:
            interfaces += self.bridge_interfaces

        for iface in interfaces:
            node_attrs = def_node_attrs.copy()
            node_attrs['label'] = iface
            s_iface = iface.split(':')
            function = self.mapped_function(s_iface[0])
            if len(s_iface) > 1 and function:

                node_attrs['parent_id'] = self.id
                node_attrs['level'] = 1
                node_attrs['node_id'] = function.id
                node_attrs['node_label'] = function.content['name']

            else:
                node_attrs['parent_id'] = ""
                node_attrs['level'] = 0
                node_attrs['node_id'] = self.id
                node_attrs['node_label'] = self.content['name']

            node_attrs['label'] = s_iface[1] if len(s_iface) > 1 else iface

            if iface in self.link_interfaces:
                node_attrs['type'] = 'iface'
            elif iface in self.bridge_interfaces:
                node_attrs['type'] = 'br-iface'

            graph.add_node(iface, attr_dict=node_attrs)

        prefixes = []
        # assign sub-graphs of functions
        for fid, function in self.functions.items():
            # TODO: temporarily apply vnf_id:interface prefix patch. must be
            # done to work with current descriptors of sonata demo
            prefix_map = {}
            prefix = self.vnf_id(function)

            if level <= 2:
                function.graph = function.build_topology_graph(parent_id=self.id,
                                                               bridges=bridges,
                                                               level=0,
                                                               vdu_inner_connections=vdu_inner_connections)
            else:
                function.graph = function.build_topology_graph(parent_id=self.id,
                                                               bridges=bridges,
                                                               level=1,
                                                               vdu_inner_connections=vdu_inner_connections)
            if level == 0:
                for node in function.graph.nodes():
                    pn = prefix + ':' + node
                    if graph.has_node(pn):
                        graph.remove_node(pn)
                prefixes.append(prefix)

            elif level == 1:
                prefixes.append(prefix)

            elif level >= 2:

                for node in function.graph.nodes():
                    prefix_map[node] = prefix + ':' + node

                re_f_graph = nx.relabel_nodes(function.graph, prefix_map, copy=True)
                graph.add_nodes_from(re_f_graph.nodes(data=True))
                graph.add_edges_from(re_f_graph.edges(data=True))

        # build links topology graph
        if not self.links and not self.bridges:
            log.warning("No links were found")

        for lid, link in self.links.items():

            if level >= 1:
                iface_u = link.iface_u
                iface_v = link.iface_v

            elif level == 0:
                iface_u = link.iface_u.split(':')
                iface_v = link.iface_v.split(':')

                if len(iface_u) > 1 and iface_u[0] in prefixes:
                    iface_u = iface_u[0]
                else:
                    iface_u = link.iface_u

                if len(iface_v) > 1 and iface_v[0] in prefixes:
                    iface_v = iface_v[0]
                else:
                    iface_v = link.iface_v
            else:
                return

            link_attrs = def_link_attrs.copy()
            link_attrs['label'] = link.id
            link_attrs['level'] = 0 if level == 0 else 1
            link_attrs['type'] = 'iface'

            graph.add_edge(iface_u, iface_v, attr_dict=link_attrs)

        # build bridge topology graph
        if bridges:
            for bid, bridge in self.bridges.items():
                brnode = 'br-' + bid
                node_attrs = def_node_attrs.copy()
                node_attrs['label'] = brnode
                node_attrs['level'] = 1
                node_attrs['type'] = 'bridge'

                # add 'router' node for this bridge
                graph.add_node(brnode, attr_dict=node_attrs)
                for iface in bridge.interfaces:
                    if level >= 1:
                        s_iface = iface
                    elif level == 0:
                        s_iface = iface.split(':')
                        if len(s_iface) > 1 and s_iface[0] in prefixes:
                            s_iface = s_iface[0]
                        else:
                            s_iface = iface
                    else:
                        return

                    link_attrs = def_link_attrs
                    link_attrs['label'] = bid
                    link_attrs['level'] = 0 if level == 0 else 1
                    link_attrs['type'] = 'br-iface'
                    graph.add_edge(brnode, s_iface, attr_dict=link_attrs)

        # inter-connect VNF interfaces
        if level == 1:
            for node_u in graph.nodes():
                node_u_tokens = node_u.split(':')
                if len(node_u_tokens) > 1 and node_u_tokens[0] in prefixes:
                    for node_v in graph.nodes():
                        if node_u == node_v:
                            continue
                        node_v_tokens = node_v.split(':')
                        if len(node_v_tokens) > 1 and \
                                node_v_tokens[0] == node_u_tokens[0]:

                            # verify internally if these interfaces are connected
                            function = self.mapped_function(node_v_tokens[0])
                            if (function.graph.has_node(node_u_tokens[1]) and
                                function.graph.has_node(node_v_tokens[1]) and
                                nx.has_path(function.graph,
                                            node_u_tokens[1],
                                            node_v_tokens[1])):
                                link_attrs = def_link_attrs
                                link_attrs['label'] = node_u + '-' + node_v
                                link_attrs['level'] = 1
                                link_attrs['type'] = 'iface'
                                graph.add_edge(node_u, node_v, attr_dict=link_attrs)

        return graph

    def load_forwarding_graphs(self):
        """
        Load all forwarding paths of all forwarding graphs, defined in the
        service content.
        """
        if 'forwarding_graphs' not in self.content:
            evtlog.log("Forwarding graphs not available",
                       "No forwarding graphs available in service id='{0}'"
                       .format(self.id),
                       self.id,
                       'evt_nsd_top_fwgraph_unavailable')
            return

        for fgraph in self.content['forwarding_graphs']:
            s_fwgraph = dict()
            s_fwgraph['fg_id'] = fgraph['fg_id']
            s_fwgraph['fw_paths'] = list()

            for fpath in fgraph['network_forwarding_paths']:
                s_fwpath = dict()
                s_fwpath['fp_id'] = fpath['fp_id']

                path_dict = {}
                for cxpt in fpath['connection_points']:
                    iface = cxpt['connection_point_ref']
                    pos = cxpt['position']
                    if iface not in self.interfaces and \
                       not self._interface_in_functions(iface):
                        evtlog.log("Undefined connection point",
                                   "Connection point '{0}' of forwarding path "
                                   "'{1}' is not defined"
                                   .format(iface, fpath['fp_id']),
                                   self.id,
                                   'evt_nsd_top_fwgraph_cpoint_undefined')
                        return
                    if pos in path_dict:
                        evtlog.log("Duplicate reference in FG",
                                   "Duplicate referenced position '{0}' "
                                   "in forwarding path id='{1}'. Ignoring "
                                   "connection point: '{2}'"
                                   .format(pos, fpath['fp_id'],
                                           path_dict[pos]),
                                   self.id,
                                   'evt_nsd_top_fwgraph_position_duplicate')
                    path_dict[pos] = iface
                d = OrderedDict(sorted(path_dict.items(),
                                       key=lambda t: t[0]))

                s_fwpath['path'] = list(d.values())
                s_fwgraph['fw_paths'].append(s_fwpath)

            self._fw_graphs.append(s_fwgraph)

        return True

    def _interface_in_functions(self, iface):
        """
        Indicates whether the provided interface is defined in the functions
        of the service.
        :param iface: interface
        :return: True, if a functions contains the interface
                 False, otherwise.
        """
        iface_tokens = iface.split(':')
        if len(iface_tokens) != 2:
            return False
        function = self.mapped_function(iface_tokens[0])
        if not function:
            return False
        if iface_tokens[1] not in function.interfaces:
            return False

        return True

    def trace_path(self, path):
        """
        Trace a forwarding path along the service topology.
        This function returns a list with the visited interfaces. In cases
        where the path contains 'impossible' links it will add the 'BREAK'
        keyword in the according position of the trace list.
        :param path: forwarding path ordered interface list
        :return: trace list
        """
        trace = []
        for x in range(len(path)-1):
            trace.append(path[x])
            if not self._graph.has_node(path[x]):
                trace.append("BREAK")
                continue
            neighbours = self._graph.neighbors(path[x])
            if path[x+1] not in neighbours:
                trace.append("BREAK")
        trace.append(path[-1])
        return trace

    def trace_path_pairs(self, path):
        trace = []
        for x in range(0, len(path), 2):
            if x+1 >= len(path):
                node_pair = {'break': False, 'from': path[x], 'to': None}
            else:
                node_pair = {'break': False, 'from': path[x], 'to': path[x+1]}
                if path[x+1] not in self._graph.neighbors(path[x]):
                    node_pair['break'] = True
            trace.append(node_pair)
        return trace

    def find_undeclared_interfaces(self, interfaces=None):
        """
        Provides a list of interfaces that are referenced in 'virtual_links'
        section but not declared in 'connection_points' of the Service and its
        Functions.
        """
        if interfaces:
            target_ifaces = interfaces
        else:
            target_ifaces = self.link_interfaces + self.bridge_interfaces

        function_ifaces = self.all_function_interfaces
        all_interfaces = self.interfaces.copy()
        all_interfaces += function_ifaces

        undeclared = []
        for iface in target_ifaces:
            if iface not in all_interfaces:
                undeclared.append(iface)

        return undeclared




class Function(Descriptor):

    def __init__(self, descriptor_file):
        """
        Initialize a function object. This inherits the descriptor object.
        :param descriptor_file: descriptor filename
        """
        super().__init__(descriptor_file)
        self._units = {}

    @property
    def units(self):
        """
        Provides the unit objects associated with the function.
        :return: units dict
        """
        return self._units

    def associate_unit(self, unit):
        """
        Associate a unit to the function.
        :param unit: unit object
        """
        if type(unit) is not Unit:
            return

        if unit.id in self.units:
            log.error("The unit (VDU) id='{0}' is already associated with "
                      "function (VNF) id='{1}'".format(unit.id, self.id))
            return

        self._units[unit.id] = unit

    def load_units(self):
        """
        Load units of the function descriptor content, section
        'virtual_deployment_units'
        """
        if 'virtual_deployment_units' not in self.content:
            log.error("Function id={0} is missing the "
                      "'virtual_deployment_units' section"
                      .format(self.id))
            return

        for vdu in self.content['virtual_deployment_units']:
            unit = Unit(vdu['id'])
            self.associate_unit(unit)

        return True

    def load_unit_interfaces(self):
        """
        Load interfaces of the units of the function.
        """
        for vdu in self.content['virtual_deployment_units']:
            if vdu['id'] not in self.units.keys():
                log.error("Unit id='{0}' is not associated with function "
                          "id='{1}".format(vdu['id'], self.id))
                return

            unit = self.units[vdu['id']]

            for cxpt in vdu['connection_points']:
                unit.add_interface(cxpt['id'])
                self.add_interface(cxpt['id'])

        return True

    def build_topology_graph(self, bridges=False, parent_id='', level=0,
                             vdu_inner_connections=True):
        """
        Build the network topology graph of the function.
        :param bridges: indicates if bridges should be included in the graph
        :param level: indicates the granularity of the graph
                    0: VNF level (showing VDUs but not VDU interfaces)
                    1: VDU level (with VDU interfaces)
        """
        graph = nx.Graph()

        def_node_attrs = {'label': '',
                          'level': level,
                          'parent_id': self.id,
                          'type': ''  # 'iface' | 'br-iface' | 'bridge'
                          }
        def_edge_attrs = {'label': '',
                          'level': '',
                          'type': ''}

        # assign nodes from function interfaces
        interfaces = self.link_interfaces
        if bridges:
            interfaces += self.bridge_interfaces

        for iface in interfaces:
            node_attrs = def_node_attrs.copy()
            s_iface = iface.split(':')
            unit = self.units[s_iface[0]] if s_iface[0] in self.units else None
            if len(s_iface) > 1 and unit:

                if level == 0:
                    iface = s_iface[0]
                node_attrs['parent_id'] = self.id
                node_attrs['level'] = 2
                node_attrs['node_id'] = unit.id
                node_attrs['node_label'] = unit.id
            else:
                node_attrs['parent_id'] = parent_id
                node_attrs['level'] = 1
                node_attrs['node_id'] = self.id
                node_attrs['node_label'] = self.content['name']

            node_attrs['label'] = s_iface[1] if len(s_iface) > 1 else iface

            if iface in self.link_interfaces:
                node_attrs['type'] = 'iface'
            elif iface in self.bridge_interfaces:
                node_attrs['type'] = 'br-iface'

            graph.add_node(iface, attr_dict=node_attrs)

        # build link topology graph
        for lid, link in self.links.items():

            edge_attrs = def_edge_attrs.copy()

            iface_u = link.iface_u.split(':')
            iface_v = link.iface_v.split(':')

            if level == 0:
                # unit interfaces not considered as nodes, just the unit itself
                if len(iface_u) > 1:
                    iface_u = iface_u[0]
                else:
                    iface_u = link.iface_u

                if len(iface_v) > 1:
                    iface_v = iface_v[0]
                else:
                    iface_v = link.iface_v

                edge_attrs['level'] = 1

            elif level == 1:
                # unit interfaces are nodes
                iface_u = link.iface_u
                iface_v = link.iface_v
                edge_attrs['level'] = 2

            edge_attrs['type'] = 'iface'
            edge_attrs['label'] = link.id
            graph.add_edge(iface_u, iface_v, attr_dict=edge_attrs)

        if vdu_inner_connections:
            # link vdu interfaces if level 1
            if level == 1:
                for uid, unit in self.units.items():
                    edge_attrs = def_edge_attrs.copy()
                    join_ifaces = []
                    for iface in unit.interfaces:
                        # patch for faulty descriptors regarding sep ':'
                        s_iface = iface.split(':')
                        if len(s_iface) > 1:
                            join_ifaces.append(iface)
                        else:
                            join_ifaces.append(uid + ':' + iface)

                    for u_iface in join_ifaces:
                        for v_iface in join_ifaces:
                            if u_iface == v_iface:
                                continue
                            if graph.has_edge(u_iface, v_iface):
                                continue
                            if not bridges and (
                                    u_iface in self.bridge_interfaces or
                                    v_iface in self.bridge_interfaces):
                                continue
                            edge_attrs['level'] = 2
                            edge_attrs['label'] = 'VDU_IN'
                            edge_attrs['type'] = 'vdu_in'

                            graph.add_edge(u_iface, v_iface)

        # build bridge topology graph
        if bridges:
            for bid, bridge in self.bridges.items():
                # add bridge router
                brnode = "br-" + bid
                node_attrs = def_node_attrs.copy()
                node_attrs['label'] = brnode
                node_attrs['level'] = 2
                node_attrs['type'] = 'bridge'
                graph.add_node(brnode, attr_dict=node_attrs)

                for iface in bridge.interfaces:
                    s_iface = iface.split(':')
                    if level == 0 and len(s_iface) > 1:
                        s_iface = s_iface[0]
                    else:
                        s_iface = iface

                    graph.add_edge(brnode, s_iface, attr_dict={'label': bid})

        return graph

    def find_undeclared_interfaces(self, interfaces=None):
        """
        Provides a list of interfaces that are referenced in 'virtual_links'
        section but not declared in 'connection_points' of the Service and its
        Functions.
        """
        if interfaces:
            target_ifaces = interfaces
        else:
            target_ifaces = self.link_interfaces + self.bridge_interfaces

        all_interfaces = self.interfaces.copy()

        undeclared = []
        for iface in target_ifaces:
            if iface not in all_interfaces:
                undeclared.append(iface)

        return undeclared


class Unit(Node):
    def __init__(self, uid):
        """
        Initialize a unit object. This inherits the node object.
        :param uid: unit id
        """
        self._id = uid
        super().__init__(self._id)

    @property
    def id(self):
        """
        Unit identifier
        :return: unit id
        """
        return self._id
