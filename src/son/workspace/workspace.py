import logging
import coloredlogs
import sys
import os
from os.path import expanduser
import yaml

from son.workspace.project import Project

log = logging.getLogger(__name__)


class Workspace:

    WORKSPACE_VERSION = "0.01"

    DEFAULT_WORKSPACE_DIR = os.path.join(expanduser("~"), ".son-workspace")
    DEFAULT_SCHEMAS_DIR = os.path.join(expanduser("~"), ".son-schema")

    # Parameter strings for the configuration descriptor.
    CONFIG_STR_NAME = "name"
    CONFIG_STR_VERSION = "version"
    CONFIG_STR_CATALOGUES_DIR = "catalogues_dir"
    CONFIG_STR_CATALOGUE_NS_DIR = "ns_catalogue"
    CONFIG_STR_CATALOGUE_VNF_DIR = "vnf_catalogue"
    CONFIG_STR_CONFIG_DIR = "configuration_dir"
    CONFIG_STR_PLATFORMS_DIR = "platforms_dir"
    CONFIG_STR_PROJECTS_DIR = "projects_dir"
    CONFIG_STR_SCHEMAS_REMOTE_MASTER = "schemas_remote_master"
    CONFIG_STR_SCHEMAS_LOCAL_MASTER = "schemas_local_master"
    CONFIG_STR_DESCRIPTOR_EXTENSION = "descriptor_extension"
    CONFIG_STR_CATALOGUE_SERVERS = "catalogue_servers"
    CONFIG_STR_LOGGING_LEVEL = "log_level"

    __descriptor_name__ = "workspace.yml"

    def __init__(self, ws_root, ws_name='SONATA workspace', log_level='INFO'):
        self.log_level = log_level
        coloredlogs.install(level=log_level)
        self.ws_root = ws_root
        self.ws_name = ws_name
        self.dirs = dict()
        self.schemas = dict()
        self.descriptor_extension = ""
        self.load_default_config()
        # Catalogue servers
        self.catalogue_servers = []

    def load_default_config(self):
        self.dirs[self.CONFIG_STR_CATALOGUES_DIR] = 'catalogues'
        self.dirs[self.CONFIG_STR_CONFIG_DIR] = 'configuration'
        self.dirs[self.CONFIG_STR_PLATFORMS_DIR] = 'platforms'

        self.schemas[self.CONFIG_STR_SCHEMAS_LOCAL_MASTER] = Workspace.DEFAULT_SCHEMAS_DIR
        self.schemas[self.CONFIG_STR_SCHEMAS_REMOTE_MASTER] = \
            "https://raw.githubusercontent.com/sonata-nfv/son-schema/master/"


        # Sub-directories of catalogues
        self.dirs[self.CONFIG_STR_CATALOGUE_NS_DIR] = \
            os.path.join(self.dirs[self.CONFIG_STR_CATALOGUES_DIR], self.CONFIG_STR_CATALOGUE_NS_DIR)
        self.dirs[self.CONFIG_STR_CATALOGUE_VNF_DIR] = \
            os.path.join(self.dirs[self.CONFIG_STR_CATALOGUES_DIR], self.CONFIG_STR_CATALOGUE_VNF_DIR)

        # Projects dir (optional)
        self.dirs[self.CONFIG_STR_PROJECTS_DIR] = 'projects'

        # Extension for YAML - schema/descriptor files
        self.descriptor_extension = "yml"

    def create_dirs(self):
        """
        Create the base directory structure for the workspace
        Invoked upon workspace creation.
        :return:
        """

        log.info('Creating workspace at %s', self.ws_root)
        os.makedirs(self.ws_root, exist_ok=False)
        for d in self.dirs:
            path = os.path.join(self.ws_root, self.dirs[d])
            os.makedirs(path, exist_ok=True)

    def create_catalog_sample(self):
        d = {'name': 'My personal catalog',
             'credentials': 'personal'
             }

        ws_file_path = os.path.join(self.ws_root, self.dirs[self.CONFIG_STR_CATALOGUES_DIR], 'personal.yml')
        with open(ws_file_path, 'w') as ws_file:
            ws_file.write(yaml.dump(d, default_flow_style=False))

    def create_ws_descriptor(self):
        """
        Creates a workspace configuration file descriptor.
        This is triggered by workspace creation and configuration changes.
        :return:
        """
        cfg_d = {self.CONFIG_STR_VERSION: Workspace.WORKSPACE_VERSION,
                 self.CONFIG_STR_NAME: self.ws_name,
                 self.CONFIG_STR_CATALOGUES_DIR: self.dirs[self.CONFIG_STR_CATALOGUES_DIR],
                 self.CONFIG_STR_CONFIG_DIR: self.dirs[self.CONFIG_STR_CONFIG_DIR],
                 self.CONFIG_STR_PLATFORMS_DIR: self.dirs[self.CONFIG_STR_PLATFORMS_DIR],
                 self.CONFIG_STR_SCHEMAS_LOCAL_MASTER: self.schemas[self.CONFIG_STR_SCHEMAS_LOCAL_MASTER],
                 self.CONFIG_STR_SCHEMAS_REMOTE_MASTER: self.schemas[self.CONFIG_STR_SCHEMAS_REMOTE_MASTER],
                 self.CONFIG_STR_CATALOGUE_SERVERS: self.catalogue_servers,
                 self.CONFIG_STR_LOGGING_LEVEL: self.log_level,
                 self.CONFIG_STR_DESCRIPTOR_EXTENSION: self.descriptor_extension
                 }

        ws_file_path = os.path.join(self.ws_root, Workspace.__descriptor_name__)

        ws_file = open(ws_file_path, 'w')
        yaml.dump(cfg_d, ws_file, default_flow_style=False)

        return cfg_d

    def create_files(self):
        self.create_ws_descriptor()
        self.create_catalog_sample()

    def check_ws_exists(self):
        ws_file = os.path.join(self.ws_root, Workspace.__descriptor_name__)
        return os.path.exists(ws_file) or os.path.exists(self.ws_root)

    @staticmethod
    def __create_from_descriptor__(ws_root):
        """
        Creates a Workspace object based on a configuration descriptor
        :param ws_root: base path of the workspace
        :return: Workspace object
        """
        ws_filename = os.path.join(ws_root, Workspace.__descriptor_name__)
        if not os.path.isdir(ws_root) or not os.path.isfile(ws_filename):
            log.error("Unable to load workspace descriptor '{}'".format(ws_filename))
            return None

        ws_file = open(ws_filename)
        ws_config = yaml.load(ws_file)

        if not ws_config[Workspace.CONFIG_STR_VERSION] == Workspace.WORKSPACE_VERSION:
            log.warning("Reading a workspace configuration with a different version")

        ws = Workspace(ws_root, ws_name=ws_config[Workspace.CONFIG_STR_NAME],
                       log_level=ws_config[Workspace.CONFIG_STR_LOGGING_LEVEL])
        ws.dirs[Workspace.CONFIG_STR_CATALOGUES_DIR] = ws_config[Workspace.CONFIG_STR_CATALOGUES_DIR]
        ws.dirs[Workspace.CONFIG_STR_CATALOGUES_DIR] = ws_config[Workspace.CONFIG_STR_CONFIG_DIR]
        ws.dirs[Workspace.CONFIG_STR_CONFIG_DIR] = ws_config[Workspace.CONFIG_STR_CONFIG_DIR]
        ws.dirs[Workspace.CONFIG_STR_PLATFORMS_DIR] = ws_config[Workspace.CONFIG_STR_PLATFORMS_DIR]
        ws.schemas[Workspace.CONFIG_STR_SCHEMAS_LOCAL_MASTER] = \
            expanduser(ws_config[Workspace.CONFIG_STR_SCHEMAS_LOCAL_MASTER])
        ws.schemas[Workspace.CONFIG_STR_SCHEMAS_REMOTE_MASTER] = ws_config[Workspace.CONFIG_STR_SCHEMAS_REMOTE_MASTER]
        ws.catalogue_servers = ws_config[Workspace.CONFIG_STR_CATALOGUE_SERVERS]
        ws.descriptor_extension = ws_config[Workspace.CONFIG_STR_DESCRIPTOR_EXTENSION]

        return ws


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Generate new sonata workspaces and project layouts")
    parser.add_argument("--init", help="Create a new sonata workspace", action="store_true")
    parser.add_argument("--workspace", help="location of existing (or new) workspace. If not specified "
                                            "will assume '{}'".format(Workspace.DEFAULT_WORKSPACE_DIR),
                        required=False)
    parser.add_argument("--project",
                        help="create a new project at the specified location", required=False)
    parser.add_argument("--debug", help="increases logging level to debug", required=False, action="store_true")

    args = parser.parse_args()

    log_level = "INFO"
    if args.debug:
        log_level = "DEBUG"
        coloredlogs.install(level=log_level)

    # Ensure that one argument is given (--init, --workspace or --project)
    if not args.init and not args.workspace and not args.project:
        parser.print_help()
        return

    # Ensure that argument --workspace is not alone
    if not args.init and args.workspace and not args.project:
        parser.print_help()
        return

    # If workspace arg is not given, create a workspace in user home
    if args.workspace is None:
        ws_root = Workspace.DEFAULT_WORKSPACE_DIR

        # If a workspace already exists at user home, throw an error and quit
        if args.init and os.path.isdir(ws_root):
            print("A workspace already exists in {}. Please specify a different location.\n"
                  .format(ws_root), file=sys.stderr)
            exit(1)

    else:
        ws_root = expanduser(args.workspace)

    if args.init:
        ws = Workspace(ws_root, log_level=log_level)
        if ws.check_ws_exists():
            print("A workspace already exists at the specified location, exiting", file=sys.stderr)
            exit(1)

        log.debug("Attempting to create a new workspace")
        cwd = os.getcwd()
        ws.create_dirs()
        ws.create_files()
        os.chdir(cwd)
        log.debug("Workspace created.")
    else:
        ws = Workspace.__create_from_descriptor__(ws_root)
        if not ws:
            print("Could not find a SONATA workspace at the specified location", file=sys.stderr)
            exit(1)

    if args.project is not None:
        log.debug("Attempting to create a new project")

        prj_root = os.path.expanduser(args.project)
        proj = Project(prj_root, ws)
        proj.create_prj()

        log.debug("Project created.")
