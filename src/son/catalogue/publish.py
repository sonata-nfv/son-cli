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

import sys
import os
import logging
import coloredlogs
import yaml
from os.path import expanduser
from son.workspace.workspace import Workspace
from son.workspace.project import Project
from son.catalogue.catalogue_client import CatalogueClient
from son.schema.validator import SchemaValidator

log = logging.getLogger(__name__)


class Publisher(object):

    def __init__(self, workspace, project=None, component=None,
                 catalogue=None):

        # Assign parameters
        coloredlogs.install(level=workspace.log_level)
        self._workspace = workspace
        self._project = project
        self._component = component
        self._catalogue = catalogue
        self._catalogue_clients = []

        # Instantiate catalogue clients
        self.create_catalogue_clients()

        # Create a schema validator
        self._schema_validator = SchemaValidator(workspace)

    def create_catalogue_clients(self):
        """
        Instantiates catalogue clients for selected catalogue servers
        :return:
        """
        log.debug("Creating catalogue clients...")

        # If catalogue argument was specified
        # ignore default publish catalogues
        if self._catalogue:
            # Get corresponding catalogue from workspace config
            cat = self._workspace.get_catalogue_server(self._catalogue)
            print(type(cat))
            if not cat:
                log.warning("The specified catalogue ID '{}' "
                            "does not exist in workspace configuration"
                            .format(self._catalogue))
                return

            # Instantiate catalogue client with the obtained address
            self._catalogue_clients.append(CatalogueClient(cat['url']))

        # If catalogue argument is absent -> get default publish catalogues
        else:
            # Get publish catalogues from workspace config

            for cat in self._workspace.catalogue_servers:
                if cat['publish'].lower() == 'yes':
                    self._catalogue_clients.append(CatalogueClient(cat['url']))

        # Ensure there are catalogues available
        if not len(self._catalogue_clients) > 0:
            log.warning("There are no catalogue servers "
                        "configured for publishing")
            return

        log.debug("Added {} catalogue clients"
                  .format(len(self._catalogue_clients)))

    def publish_project(self):
        """
        Publish all components of a project to the available catalogue servers
        :return:
        """
        log.info("Publishing project: '{}'".format(self._project.project_root))

        # Ensure project was defined and its valid
        if not self._project or not Project.__is_valid__(self._project):
            log.error("Publish failed. Invalid or undefined project.")
            return

        # Retrieve project NSD and VNFDs files
        comp_list = self._project.get_ns_descriptor() + \
            self._project.get_vnf_descriptors()

        log.debug("The following project components "
                  "will be published: {}".format(comp_list))

        # Publish project components
        for comp in comp_list:
            self.publish_component(comp)

    def publish_component(self, filename=None):
        """
        Publish a single component file (e.g. descriptor)
        to the available catalogue servers
        :param filename:
        :return:
        """

        # If filename parameter is absent, assume the component of object init
        if not filename:
            filename = self._component

        log.info("Publishing component: '{}'".format(filename))

        # Check if file exists
        if not os.path.isfile(filename):
            log.error("Publish failed. File '{}' does not exist."
                      .format(filename))
            return

        # Check that catalogue clients exist
        if not len(self._catalogue_clients) > 0:
            log.error("Publish failed. "
                      "There are no catalogue clients available.")
            return

        # Load component descriptor
        with open(filename, 'r') as compf:
            compd = yaml.load(compf)

        # Determine descriptor type of component
        descriptor_type = self._schema_validator.get_descriptor_type(compd)

        comp_data = yaml.dump(compd)

        # Publish to the catalogue servers based on the descriptor type
        errors_publishing = False
        for cat_client in self._catalogue_clients:
            if descriptor_type is SchemaValidator.SCHEMA_PACKAGE_DESCRIPTOR:
                log.debug("Publishing Package Descriptor: {}".format(filename))
                if not cat_client.post_pd(comp_data):
                    errors_publishing = True

            elif descriptor_type is SchemaValidator.SCHEMA_SERVICE_DESCRIPTOR:
                log.debug("Publishing Service Descriptor: {}"
                          .format(filename))
                if not cat_client.post_ns(comp_data):
                    errors_publishing = True

            elif descriptor_type is SchemaValidator.SCHEMA_FUNCTION_DESCRIPTOR:
                log.debug("Publishing Function Descriptor: {}"
                          .format(filename))

                if not cat_client.post_vnf(comp_data):
                    errors_publishing = True

        if errors_publishing:
            log.critical("The publishing of one or more components has failed")
            exit(1)


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="Publish a project or component to the catalogue server")

    parser.add_argument(
        "--workspace", help="Specify workspace. Default is located at '{}'"
        .format(Workspace.DEFAULT_WORKSPACE_DIR),
        required=False)

    parser.add_argument(
        "--project", help="Specify project to be published",
        required=False)

    parser.add_argument(
        "-d", "--component", help="Project component to be published.",
        required=False)

    parser.add_argument("-c", "--catalogue",
                        help="Catalogue ID where to publish. "
                             "Overrides defaults in workspace config.")

    args = parser.parse_args()

    # Ensure that either --component or --project
    # argument is given, but not the two simultaneously (XOR)
    if bool(args.component) == bool(args.project):
        parser.print_help()
        return

    # If workspace arg is not given, specify workspace as the default location
    if not args.workspace:
        ws_root = Workspace.DEFAULT_WORKSPACE_DIR
    else:
        ws_root = expanduser(args.workspace)

    # Create the Workspace object
    ws = Workspace.__create_from_descriptor__(ws_root)
    if not ws:
        print("Could not find a SONATA SDK workspace at '{}'"
              .format(ws_root),
              file=sys.stderr)
        exit(1)

    if args.project:
        prj_root = os.path.expanduser(args.project)
        proj = Project(ws, prj_root)
        if not proj:
            print("Could not find a SONATA SDK project at '{}'"
                  .format(prj_root),
                  file=sys.stderr)
            exit(1)

        pub = Publisher(ws, project=proj, catalogue=args.catalogue)
        pub.publish_project()

    if args.component:
        comp_file = os.path.expanduser(args.component)
        if not os.path.isfile(comp_file):
            print("'{}' is not a valid file"
                  .format(comp_file),
                  file=sys.stderr)
            exit(1)

        pub = Publisher(ws, component=comp_file, catalogue=args.catalogue)
        pub.publish_component()
