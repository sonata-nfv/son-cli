import sys
import os
import logging
import coloredlogs
import yaml
from os.path import expanduser
from son.workspace.workspace import Workspace
from son.workspace.project import Project
from son.catalogue.catalogue_client import CatalogueClient
from jsonschema import validate

log = logging.getLogger(__name__)


class Publisher(object):

    def __init__(self, workspace, project=None, component=None, catalogue=None):
        # Assign parameters
        coloredlogs.install(level=workspace.log_level)
        self._workspace = workspace
        self._project = project
        self._component = component
        self._catalogue = catalogue
        self._catalogue_clients = []

        # Instantiate catalogue clients
        self.create_catalogue_clients()

    def create_catalogue_clients(self):
        """
        Instantiates catalogue clients for selected catalogue servers
        :return:
        """
        log.debug("Creating catalogue clients...")

        # If catalogue argument was specified -> ignore default publish catalogues
        if self._catalogue:
            # Get corresponding catalogue from workspace config
            cat_url = self._workspace.get_catalogue_server(self._catalogue)['url']
            assert cat_url, \
                "The specified catalogue ID '{}' does not exist in workspace configuration".format(self._catalogue)

            # Instantiate catalogue client with the obtained address
            self._catalogue_clients.append(CatalogueClient(cat_url))

        # If catalogue argument is absent -> get default publish catalogues
        else:
            # Get publish catalogues from workspace config

            for cat in self._workspace.catalogue_servers:
                if cat['publish'].lower() == 'yes':
                    self._catalogue_clients.append(cat['url'])

        # Ensure there are catalogues available
        assert len(self._catalogue_clients) > 0, "There are no catalogue servers available."

        log.debug("Added catalogue clients for servers: '{}'".format(self._catalogue_clients))


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Publish a project or component to the catalogue server")
    parser.add_argument("--workspace", help="Specify workspace. Default is located at '{}'"
                        .format(Workspace.DEFAULT_WORKSPACE_DIR), required=False)
    parser.add_argument("--project",
                        help="Specify project to be published", required=False)
    parser.add_argument("--component", help="Project component to be published.", required=False)
    parser.add_argument("--catalogue", help="Catalogue ID where to publish. Overrides defaults in workspace config.")

    args = parser.parse_args()

    # Ensure that either --component or --project argument is given, but not the two simultaneously (XOR)
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
        print("Could not find a SONATA SDK workspace at '{}'".format(ws_root), file=sys.stderr)
        exit(1)

    if args.project:
        prj_root = os.path.expanduser(args.project)
        proj = Project(prj_root, ws)
        if not proj:
            print("Could not find a SONATA SDK project at '{}'".format(prj_root), file=sys.stderr)
            exit(1)
        pub = Publisher(ws, project=proj, catalogue=args.catalogue)

    if args.component:
        comp_file = os.path.expanduser(args.component)
        if not os.path.isfile(comp_file):
            print("'{}' is not a valid file".format(comp_file), file=sys.stderr)
            exit(1)
        pub = Publisher(ws, component=comp_file, catalogue=args.catalogue)
