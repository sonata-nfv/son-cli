import logging
import sys
import os
import yaml

from son.workspace.project import Project

log = logging.getLogger(__name__)


class Workspace:

    __descriptor_name__ = "workspace.yml"

    def __init__(self, ws_root):
        logging.basicConfig(level=logging.DEBUG)
        self._log = logging.getLogger(__name__)
        self.ws_root = ws_root

    def create_dirs(self):
        self._log.info('Creating workspace at %s', self.ws_root)
        directories = {'projects', 'catalogues', 'configuration', 'platforms'}

        os.makedirs(self.ws_root, exist_ok=False)
        for d in directories:
            path = os.path.join(self.ws_root, d)
            os.makedirs(path, exist_ok=True)

    def create_catalog_sample(self):
        d = {'name': 'My personal catalog',
             'credentials': 'personal'
             }

        ws_file_path = os.path.join(self.ws_root, 'catalogues', 'personal.yml')
        with open(ws_file_path, "w") as ws_file:
            ws_file.write(yaml.dump(d, default_flow_style=False))

    def create_ws_file(self):
        d = {'version': '0.01',  # should we version the workspace
             'name': 'SONATA workspace',
             'catalogues_dir': 'catalogues',
             'configuration_dir': 'configuration',
             'platforms_dir': 'platforms'
             }

        ws_file_path = os.path.join(self.ws_root, Workspace.__descriptor_name__)
        with open(ws_file_path, "w") as ws_file:
            ws_file.write(yaml.dump(d, default_flow_style=False))

    def create_files(self):
        self.create_ws_file()
        self.create_catalog_sample()

    def check_ws_exists(self):
        ws_file = os.path.join(self.ws_root, Workspace.__descriptor_name__)
        return os.path.exists(ws_file) or os.path.exists(self.ws_root)


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Generate new sonata workspaces and project layouts")
    parser.add_argument("--init", help="Create a new sonata workspace on the specified location", action="store_true")
    parser.add_argument("--workspace", help="location of existing (or new) workspace", required=True)
    parser.add_argument("--project",
                        help="create a new project at the specified location", required=False)

    log.debug("parsing arguments")
    args = parser.parse_args()
    ws_root = os.path.expanduser(args.workspace)
    ws = Workspace(ws_root)

    if args.init:
        if ws.check_ws_exists():
            print("A workspace already exists at the specified location, exiting", file=sys.stderr)
            return
        log.debug("Attempting to create a new workspace")
        cwd = os.getcwd()
        ws.create_dirs()
        ws.create_files()
        os.chdir(cwd)
        log.debug("Workspace created.")
    else:
        if not ws.check_ws_exists():
            print("Could not find a SONATA workspace at the specified location", file=sys.stderr)
            return

    if args.project is not None:
        log.debug("Attempting to create a new project")
        prj_root = os.path.expanduser(args.project)
        proj = Project(prj_root, ws_root)
        proj.create_prj()
        log.debug("Project created.")
