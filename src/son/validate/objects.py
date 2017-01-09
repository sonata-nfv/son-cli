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

import coloredlogs
import networkx as nx
from collections import OrderedDict
from son.validate.util import *

log = logging.getLogger(__name__)


class DescriptorStorage(object):

    def __init__(self, log_level='debug'):
        """
        Initialize an object to store descriptors.
        :param log_level: verbosity level
        """
        # configure log
        self._log_level = log_level
        coloredlogs.install(level=self._log_level)

        # dictionaries for services, functions and units
        self._services = {}
        self._functions = {}
        self._units = {}

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

    def create_service(self, descriptor_file):
        """
        Create and store a service based on the provided descriptor filename.
        If a service is already stored with the same id, it will return the
        stored service.
        :param descriptor_file: service descriptor filename
        :return: created service object or, if id exists, the stored service.
        """
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
        self._interfaces.append(interface)


class Link:
    def __init__(self, u, v, ltype='e-line'):
        """
        Initialize a link object.
        A link defines a connection between two interfaces.
        :param u: interface u
        :param v: interface v
        :param ltype: type of link: 'e-line', 'e-tree' for direct links and
        'e-lan' to indicate a link is part of a bridge
        """
        self._type = ltype
        self._iface_pair = [u, v]

    def __repr__(self):
        return self.__str__()

    def __str__(self):
        return "<{}: {} -- {}>".format(self.type, self.iface_u, self.iface_v)

    @property
    def type(self):
        """
        :return: Link type
        """
        return self._type

    @property
    def iface_pair(self):
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
    def p2p_links(self):
        """
        Provides the direct links associated with the descriptor.
        :return: 'e-line' (direct) links
        """
        return {lid: self._links[lid] for lid, link in self._links.items()
                if link.type == 'e-line'}

    @property
    def bridge_links(self):
        """
        Provides the bridge links associated with the descriptor.
        :return: 'e-lan' (bridge) links
        """
        return {lid: self._links[lid] for lid, link in self._links.items()
                if link.type == 'e-lan'}

    def filter_links(self, link_type=None):
        """
        Provides the links associated with the descriptor, filtered by the
        provided link type.
        :param link_type: 'e-line' (direct) or 'e-lan' (bridge)
        :return: filtered links
        """
        if not link_type:
            return self.links

        if link_type.lower() == 'e-line' or link_type.lower() == 'e-tree':
            return self.p2p_links

        if link_type == 'e-lan':
            return self.bridge_links

    def filter_interfaces(self, link_type):
        """
        Provides the interfaces, associated with the descriptor/node,
        filtered by the link-type that they are associated with.
        :param link_type: 'e-line' (direct) or 'e-lan' (bridge)
        :return: filtered interfaces
        """
        finterfaces = []
        for interface in self.interfaces:
            eligible = False
            for lid, link in self.filter_links(link_type=link_type).items():
                if interface in link.iface_pair:
                    eligible = True
            if eligible:
                finterfaces.append(interface)
        return finterfaces

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
            self.add_interface(cxpt['id'])

    def add_link(self, lid, ltype, interfaces):
        """
        Add link to the descriptor.
        Associate a connection, between interfaces, of the provided type.
        If provided link type is direct, a list of two interfaces elements
        must be provided. If the link is a bridge, there is no limit on the
        number of interfaces.
        :param lid: link id
        :param ltype: link type  'e-line' (direct) or 'e-lan' (bridge)
        :param interfaces: interface list
        """
        if lid in self.links.keys():
            log.error("The link id='{0} is already stored in descriptor "
                      "id='{1}'".format(lid, self.id))
            return

        if ltype.lower() == 'e-line':  #TODO or link_type.lower()=='e-tree':
            self.links[lid] = Link(interfaces[0], interfaces[1])

        elif ltype.lower() == 'e-lan':
            for u_iface in interfaces:
                interfaces_inc = interfaces.copy()
                interfaces_inc.pop(interfaces_inc.index(u_iface))

                for v_iface in interfaces_inc:
                    self._links[lid + ':' + u_iface + '-' + v_iface] = \
                        Link(u_iface, v_iface, ltype='e-lan')

        else:
            log.error("Invalid link type='{0}' in link id='{1}' of "
                      "descriptor id='{2}'".format(ltype, lid, self.id))

    def load_links(self):
        """
        Load links of the descriptor, based on the 'virtual_links' section
        of its content.
        """
        if 'virtual_links' not in self.content:
            return

        for link in self.content['virtual_links']:
            self.add_link(link['id'], link['connectivity_type'],
                          link['connection_points_reference'])


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
                  "'{2}".format(self.id, function.id, vnf_id))

        self._functions[function.id] = function
        self._vnf_id_map[vnf_id] = function.id

    def build_topology_graph(self, deep=False, interfaces=False,
                             link_type=None):
        """
        Build the network topology graph of the service.
        :param deep: indicates the granularity of the graph
                     True - graph will include topology graphs of functions
                     False - graph will only include the service topology graph
        :param interfaces: indicates whether should nodes include interface
                           names
        :param link_type: filter by link type. 'e-line' (direct) or
                          'e-lan' (bridge)
        """

        self._graph = nx.Graph()

        # assign nodes from service interfaces
        self._graph.add_nodes_from(self.filter_interfaces(link_type))

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

        # build topology graph
        links = self.filter_links(link_type=link_type)
        for lid, link in links.items():

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
                                 attr_dict={'label': lid})

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
            log.error("No forwarding graphs available in service id='{0}'"
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
            return

        for vdu in self.content['virtual_deployment_units']:
            unit = Unit(vdu['id'])
            self.associate_unit(unit)

    def load_unit_interfaces(self):
        """
        Load interfaces of the units of the function.
        """
        if 'virtual_deployment_units' not in self.content:
            return

        for vdu in self.content['virtual_deployment_units']:
            if vdu['id'] not in self.units.keys():
                log.error("Unit id='{0}' is not associated with function "
                          "id='{1}".format(vdu['id'], self.id))
                return

            unit = self.units[vdu['id']]

            for cxpt in vdu['connection_points']:
                unit.add_interface(cxpt['id'])
                self.add_interface(cxpt['id'])

    def build_topology_graph(self, link_type=None):
        """
        Build the network topology graph of the function.
        :param link_type: filter by link type. 'e-line' (direct) or
                          'e-lan' (bridge)
        """
        self._graph = nx.Graph()

        # assign nodes from function interfaces
        self._graph.add_nodes_from(self.filter_interfaces(link_type))

        # assign nodes from units interfaces
        for uid, unit in self.units.items():
            self._graph.add_node(uid,
                                 attr_dict={'interfaces': unit.interfaces})

        # build topology graph
        links = self.filter_links(link_type=link_type)
        for lid, link in links.items():

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
                                 attr_dict={'label': lid})


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