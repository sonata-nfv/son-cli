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
import logging
import coloredlogs
import networkx as nx
import zipfile
import time
import shutil
import atexit
from contextlib import closing
from son.package.md5 import generate_hash
from son.schema.validator import SchemaValidator
from son.workspace.workspace import Workspace, Project
from son.validate.storage import DescriptorStorage
from son.validate.util import read_descriptor_files, list_files, strip_root, \
    build_descriptor_id, CountCalls

log = logging.getLogger(__name__)


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

        # configure logs
        coloredlogs.install(level=self._log_level)

        # descriptors storage
        self._storage = DescriptorStorage()

        # syntax validation
        self._schema_validator = SchemaValidator(self._workspace)

        # wrapper to count number of errors and warnings
        log.error = CountCalls(log.error)
        log.warning = CountCalls(log.warning)

    @property
    def error_count(self):
        """
        Provides the number of errors given during validation.
        """
        return log.error.counter

    @property
    def warning_count(self):
        """
        Provides the number of warnings given during validation.
        """
        return log.warning.counter

    def configure(self, syntax=None, integrity=None, topology=None,
                  dpath=None, dext=None, debug=False):
        """
        Configure parameters for validation. It is recommended to call this
        function before performing a validation.
        :param syntax: specifies whether to validate syntax
        :param integrity: specifies whether to validate integrity
        :param topology: specifies whether to validate network topology
        :param dpath: directory to search for function descriptors (VNFDs)
        :param dext: extension of descriptor files (default: 'yml')
        :param debug: increase verbosity level of logger
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
        if debug:
            coloredlogs.install(level='debug')

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

        if not self._syntax:
            log.error("Nothing to validate. Aborting.")
            sys.exit(1)

        if caller == 'validate_package':
            pass

        elif caller == 'validate_project':
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

    def validate_package(self, package):
        """
        Validate a SONATA package.
        By default, it performs the following validations: syntax, integrity
        and network topology.
        :param package: SONATA package filename
        :return: True if all validations were successful, False otherwise
        """
        self._assert_configuration()

        log.info("Validating package '{0}'".format(os.path.abspath(package)))

        # check if package is packed in the correct format
        if not zipfile.is_zipfile(package):
            log.error("Invalid SONATA package '{}'".format(package))
            return

        package_dir = '.' + str(time.time())
        with closing(zipfile.ZipFile(package, 'r')) as pkg:
            # extract package contents
            pkg.extractall(package_dir)

            # set folder for deletion when program exits
            atexit.register(shutil.rmtree, package_dir)

        # validate package file structure
        if not self._validate_package_struct(package_dir):
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

        service = self._storage.create_service(nsd_file)
        if not service:
            log.error("Failed to read the service descriptor of file '{}'"
                      .format(nsd_file))
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
        self._assert_configuration()

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
            log.critical("Couldn't store VNF of file '{0}'".format(vnfd_path))
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
            log.error("A directory named 'META-INF' must exist, "
                      "located at the root of the package")
            return

        if len(os.listdir(meta_dir)) > 1:
            log.error("The 'META-INF' directory must only contain the file "
                      "'MANIFEST.MF'")
            return

        if not os.path.exists(os.path.join(meta_dir, 'MANIFEST.MF')):
            log.error("A file named 'MANIFEST.MF' must exist in directory "
                      "'META-INF'")
            return

        # validate directory 'service_descriptors'
        services_dir = os.path.join(package_dir, 'service_descriptors')
        if os.path.isdir(services_dir):
            if len(os.listdir(services_dir)) == 0:
                log.error("The 'service_descriptors' directory must contain at"
                          " least one service descriptor file")
                return

        # validate directory 'function_descriptors'
        functions_dir = os.path.join(package_dir, 'function_descriptors')
        if os.path.isdir(functions_dir):
            if len(os.listdir(functions_dir)) == 0:
                log.error("The 'function_descriptors' directory must contain "
                          "at least one function descriptor file")
                return

        return True

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
            log.error("Invalid syntax in MANIFEST of package: '{0}'"
                      .format(package.id))
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
            log.error("Invalid syntax in service: '{0}'".format(service.id))
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
            log.error("Invalid syntax in function '{0}'".format(function.id))
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
                log.error("Referenced descriptor file '{0}' is not "
                          "packaged.".format(f))
                return

            gen_md5 = generate_hash(filename)
            manif_md5 = package.md5(strip_root(f))
            if manif_md5 and gen_md5 != manif_md5:
                log.warning("MD5 hash of file '{0}' is not equal to the "
                            "defined in package descriptor:\nGen MD5:\t{1}\n"
                            "MANIF MD5:\t{2}"
                            .format(f, gen_md5, manif_md5))

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
            log.error("Failed to read service function descriptors")
            return

        # validate service function descriptors (VNFDs)
        for fid, function in service.functions.items():
            if not self.validate_function(function.filename):
                return

        # load service interfaces
        if not service.load_interfaces():
            log.error("Couldn't load the connection points of service id='{0}'"
                      .format(service.id))
            return

        # load service links
        if not service.load_virtual_links():
            log.error("Couldn't load virtual links of service id='{0}'"
                      .format(service.id))
            return

        undeclared = service.find_undeclared_interfaces()
        if undeclared:
            log.error("Virtual links section has undeclared connection "
                      "points: {0}".format(undeclared))
            return

        # check for unused interfaces
        unused_ifaces = service.find_unused_interfaces()
        if unused_ifaces:
            log.warning("Service has unused connection points: {0}"
                        .format(unused_ifaces))

        # verify integrity between vnf_ids and links
        for lid, link in service.links.items():
            for iface in link.interfaces:
                if iface not in service.interfaces:
                    iface_tokens = iface.split(':')
                    if len(iface_tokens) != 2:
                        log.error("Connection point '{0}' in virtual link "
                                  "'{1}' is not defined"
                                  .format(iface, lid))
                        return
                    vnf_id = iface_tokens[0]
                    function = service.mapped_function(vnf_id)
                    if not function:
                        log.error("Function (VNF) of vnf_id='{0}' declared "
                                  "in connection point '{0}' in virtual link "
                                  "'{1}' is not defined"
                                  .format(vnf_id, iface, lid))
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
            log.error("Couldn't load the interfaces of function id='{0}'"
                      .format(function.id))
            return

        # load units
        if not function.load_units():
            log.error("Couldn't load the units of function id='{0}'"
                      .format(function.id))
            return

        # load interfaces of units
        if not function.load_unit_interfaces():
            log.error("Couldn't load unit interfaces of function id='{0}'"
                      .format(function.id))
            return

        # load function links
        if not function.load_virtual_links():
            log.error("Couldn't load the links of function id='{0}'"
                      .format(function.id))
            return

        # check for undeclared interfaces
        undeclared = function.find_undeclared_interfaces()
        if undeclared:
            log.error("Virtual links section has undeclared connection "
                      "points: {0}".format(undeclared))
            return

        # check for unused interfaces
        unused_ifaces = function.find_unused_interfaces()
        if unused_ifaces:
            log.warning("Function has unused connection points: {0}"
                        .format(unused_ifaces))

        # verify integrity between unit interfaces and units
        for lid, link in function.links.items():
            for iface in link.interfaces:
                iface_tokens = iface.split(':')
                if len(iface_tokens) > 1:
                    if iface_tokens[0] not in function.units.keys():
                        log.error("Invalid interface id='{0}' of link id='{1}'"
                                  ": Unit id='{2}' is not defined"
                                  .format(iface, lid, iface_tokens[0]))
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
            log.error("Couldn't build topology graph of service '{0}'"
                      .format(service.id))
            return

        log.debug("Built topology graph of service '{0}': {1}"
                  .format(service.id, service.graph.edges()))

        # write service graphs with different levels and options
        self.write_service_graphs(service)

        if nx.is_connected(service.graph):
            log.debug("Topology graph of service '{0}' is connected"
                      .format(service.id))
        else:
            log.warning("Topology graph of service '{0}' is disconnected"
                        .format(service.id))

        # load forwarding paths
        if not service.load_forwarding_paths():
            log.error("Couldn't load service forwarding paths. "
                      "Aborting validation.")
            return

        # analyse forwarding paths
        for fpid, fw_path in service.fw_paths.items():
            log.debug("Building forwarding path id='{0}'".format(fpid))

            # check if number of connection points is odd
            if len(fw_path) % 2 != 0:
                log.warning("The forwarding path id='{0}' has an odd number "
                            "of connection points".format(fpid))

            trace = service.trace_path(fw_path)
            if 'BREAK' in trace:
                log.error("The forwarding path id='{0}' is invalid for the "
                          "specified topology. {1} breakpoint(s) "
                          "found the path: {2}"
                          .format(fpid, trace.count('BREAK'), trace))
                # skip further analysis on this path
                continue

            log.debug("Forwarding path id='{0}': {1}".format(fpid, trace))

            # path is valid in specified topology, let's check for cycles
            fpg = nx.Graph()
            fpg.add_path(trace)
            cycles = Validator._find_graph_cycles(fpg, fpg.nodes()[0])
            if cycles and len(cycles) > 0:
                log.warning("Found cycles forwarding path id={0}: {1}"
                            .format(fpid, cycles))

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
            log.error("Couldn't build topology graph of function '{0}'"
                      .format(function.id))
            return

        log.debug("Built topology graph of function '{0}': {1}"
                  .format(function.id, function.graph.edges()))

        # check for path cycles
        cycles = Validator._find_graph_cycles(function.graph,
                                              function.graph.nodes()[0])
        if cycles and len(cycles) > 0:
            log.warning("Found cycles in network graph of function "
                        "'{0}':\n{0}".format(function.id, cycles))

        return True

    def _load_service_functions(self, service):
        """
        Loads and stores functions (VNFs) referenced in the specified service
        :param service: service
        :return: True if successful, None otherwise
        """

        log.debug("Loading functions of the service.")

        # get VNFD file list from provided dpath
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
            log.error("Service references VNFs but none could be found in "
                      "'{0}'. Please specify another '--dpath'"
                      .format(self._dpath))
            return

        # store function descriptors referenced in the service
        for function in functions:
            fid = build_descriptor_id(function['vnf_vendor'],
                                      function['vnf_name'],
                                      function['vnf_version'])
            if fid not in path_vnfs.keys():
                log.error("Referenced function descriptor id='{0}' couldn't "
                          "be loaded".format(fid))
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

    def write_service_graphs(self, service):

        for lvl in range(0, 3):
            g = service.build_topology_graph(level=lvl, bridges=False)
            nx.write_graphml(g, os.path.join('graphs',
                                             "{0}-lvl{1}.graphml"
                                             .format(service.id, lvl)))
            g = service.build_topology_graph(level=lvl, bridges=True)
            nx.write_graphml(g, os.path.join('graphs',
                                             "{0}-lvl{1}-br.graphml"
                                             .format(service.id, lvl)))


def print_result(validator):

    if validator.error_count:
        log.error("Validation failed with {0} error(s) and {1} warning(s)"
                  .format(validator.error_count, validator.warning_count))
    elif validator.warning_count:
        log.warning("Validation completed with {0} warning(s)"
                    .format(validator.warning_count))
    else:
        log.info("Validation succeeded")


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
                            debug=args.debug)

        validator.validate_package(args.package_file)
        print_result(validator)

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

        validator.validate_project(project)
        print_result(validator)

    elif args.nsd:
        validator = Validator()
        validator.configure(dpath=args.dpath, dext=args.dext,
                            syntax=args.syntax,
                            integrity=args.integrity,
                            topology=args.topology,
                            debug=args.debug)

        validator.validate_service(args.nsd)
        print_result(validator)

    elif args.vnfd:
        validator = Validator()
        validator.configure(dext=args.dext,
                            syntax=args.syntax,
                            integrity=args.integrity,
                            topology=args.topology,
                            debug=args.debug)

        validator.validate_function(args.vnfd)
        print_result(validator)

    else:
        log.error("Invalid arguments.")
        exit(1)

    exit(0)
