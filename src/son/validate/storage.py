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

log = logging.getLogger(__name__)


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
            log.error("The interface id='{0}' is already stored in node "
                      "id='{1}'".format(interface, self.id))
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
        self.content = read_descriptor_file(self._filename)

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
        """
        Provides the interfaces that are associated with links.
        Interfaces that are exclusively associated with bridges are removed.
        """
        f_ifaces = self.interfaces.copy()

        for iface in self.interfaces:

            for lid, link in self.links.items():
                if iface in link.interfaces:
                    break    # in links, continue to next iface

            for bid, bridge in self.bridges.items():
                if iface in bridge.interfaces:
                    index = f_ifaces.index(iface)
                    f_ifaces.pop(index)
                    break    # exclude this interface, continue to the next

        return f_ifaces

    @property
    def bridge_interfaces(self):
        """
        Provides the interfaces that are associated with bridges.
        Interfaces that are exclusively associated with links are removed.
        """
        f_ifaces = self.interfaces.copy()

        for iface in self.interfaces:

            for bid, bridge in self.bridges.items():
                if iface in bridge.interfaces:
                    break   # in bridges, continue to next iface

            for lid, link in self.links.items():
                if iface in link.interfaces:
                    index = f_ifaces.index(iface)
                    f_ifaces.pop(index)
                    break   # exclude iface, continue to next

        return f_ifaces

    #
    # def filter_interfaces(self, link_type):
    #     """
    #     Provides the interfaces, associated with the descriptor/node,
    #     filtered by the link-type that they are associated with.
    #     :param link_type: 'e-line' (direct) or 'e-lan' (bridge)
    #     :return: filtered interfaces
    #     """
    #     finterfaces = []
    #     for interface in self.interfaces:
    #         eligible = False
    #         for lid, link in self.filter_links(link_type=link_type).items():
    #             if interface in link.iface_pair:
    #                 eligible = True
    #         if eligible:
    #             finterfaces.append(interface)
    #     return finterfaces

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
        self._fw_paths = {}
        self._fw_path_graphs = {}

    @property
    def functions(self):
        """
        Provides the functions specified in the service.
        :return: functions dict
        """
        return self._functions

    @property
    def fw_paths(self):
        """
        Provides the forwarding paths specified in the service.
        :return: forwarding paths dict
        """
        return self._fw_paths

    def mapped_function(self, vnf_id):
        """
        Provides the function associated with a 'vnf_id' defined in the
        service content.
        :param vnf_id: vnf id
        :return: function object
        """
        if vnf_id not in self._vnf_id_map or self._vnf_id_map[vnf_id] not in\
                self._functions:
            log.error("Function of vnf_id='{}' is not mapped".format(vnf_id))
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

    def build_topology_graph(self, deep=False, interfaces=False,
                             bridges=False):
        """
        Build the network topology graph of the service.
        :param deep: indicates the granularity of the graph
                     True - graph will include topology graphs of functions
                     False - graph will only include the service topology graph
        :param interfaces: indicates whether should nodes include interface
                           names
        :param bridges: indicates whether bridges should be included in
                        the graph
        """

        self._graph = nx.Graph()

        # assign nodes from service interfaces
        if not bridges:
            self._graph.add_nodes_from(self.link_interfaces)

        prefixes = []
        # assign sub-graphs of functions
        for fid, function in self.functions.items():
            # TODO: temporarily apply vnf_id:interface prefix patch. must be
            # done to work with current descriptors of sonata demo
            prefix_map = {}
            prefix = self.vnf_id(function)
            for node in function.graph.nodes():
                prefix_map[node] = prefix + ':' + node

            function_graph = nx.relabel_nodes(function.graph,
                                              prefix_map,
                                              copy=True)
            if deep:
                self._graph.add_edges_from(function_graph.edges())
            else:
                prefixes.append(prefix)

        # build links topology graph
        if not self.links:
            log.warning("No links were found")

        for lid, link in self.links .items():

            if deep or interfaces:
                iface_u = link.iface_u
                iface_v = link.iface_v

            else:
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

            self._graph.add_edge(iface_u, iface_v,
                                 attr_dict={'label': link.id})

        # if show interfaces, link interfaces within each function
        if interfaces:
            for node_u in self._graph.nodes():
                node_u_tokens = node_u.split(':')
                if len(node_u_tokens) > 1 and node_u_tokens[0] in prefixes:
                    for node_v in self._graph.nodes():
                        if node_u == node_v:
                            continue
                        node_v_tokens = node_v.split(':')
                        if len(node_v_tokens) > 1 and \
                                node_v_tokens[0] == node_u_tokens[0]:
                            self._graph.add_edge(node_u, node_v)

    def load_forwarding_paths(self):
        """
        Load all forwarding paths of all forwarding graphs, defined in the
        service content.
        """
        if 'forwarding_graphs' not in self.content:
            log.debug("No forwarding graphs available in service id='{0}'"
                      .format(self.id))
            return

        for fgraph in self.content['forwarding_graphs']:
            for fpath in fgraph['network_forwarding_paths']:
                path_dict = {}
                for cxpt in fpath['connection_points']:
                    iface = cxpt['connection_point_ref']
                    pos = cxpt['position']
                    if iface not in self.interfaces and \
                       not self._interface_in_functions(iface):
                        log.error("Connection point '{0}' of forwarding path "
                                  "'{1}' is not defined"
                                  .format(iface, fpath['fp_id']))
                        return
                    if pos in path_dict:
                        log.warning("Duplicate referenced position '{0}' "
                                    "in forwarding path id='{1}'. Ignoring "
                                    "connection point: '{2}'"
                                    .format(pos, fpath['fp_id'], path_dict[pos]))
                    path_dict[pos] = iface
                d = OrderedDict(sorted(path_dict.items(),
                                       key=lambda t: t[0]))
                self._fw_paths[fpath['fp_id']] = list(d.values())

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
            neighbours = self._graph.neighbors(path[x])
            if path[x+1] not in neighbours:
                trace.append("BREAK")
        trace.append(path[-1])
        return trace


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

    def build_topology_graph(self, bridges=False):
        """
        Build the network topology graph of the function.
        :param bridges: indicates if bridges should be included in the graph
        """
        self._graph = nx.Graph()

        # assign nodes from function interfaces
        if not bridges:
            self._graph.add_nodes_from(self.link_interfaces)

        # assign nodes from units interfaces
        for uid, unit in self.units.items():
            self._graph.add_node(uid,
                                 attr_dict={'interfaces': unit.interfaces})

        # build topology graph
        for lid, link in self.links.items():

            # unit interfaces are not considered as nodes, just the unit itself
            iface_u = link.iface_u.split(':')
            iface_v = link.iface_v.split(':')

            if len(iface_u) > 1:
                iface_u = iface_u[0]
            else:
                iface_u = link.iface_u

            if len(iface_v) > 1:
                iface_v = iface_v[0]
            else:
                iface_v = link.iface_v

            self._graph.add_edge(iface_u, iface_v,
                                 attr_dict={'label': link.id})


    # def find_undeclared_interfaces(self):
    #     """
    #     Provides a list of interfaces that are referenced in 'virtual_links'
    #     but not declared in the function and respective units
    #     'connection_points' sections.
    #     :return: list of undeclared interfaces
    #     """
    #
    #     for iface in self.link_interfaces:
    #         if iface
    #
    #     undeclared_ifaces = []
    #     for link in self.links:
    #
    #         if iface not in self.link_interfaces and \
    #                 iface not in self.bridge_interfaces:
    #
    #         for iface in link.interfaces:
    #             if iface not in self.interfaces:
    #                 log.error("Undeclared connection point '{0}' in "
    #                           "virtual link id='{1}'"
    #                           .format(iface, lid))
    #                 if iface not in undeclared_ifaces:
    #                     undeclared_ifaces.append(iface)
    #     return undeclared_ifaces


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
