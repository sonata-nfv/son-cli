import logging
import sys
import zipfile
from contextlib import closing
from pathlib import Path

import os
import pkg_resources
import yaml
from jsonschema import validate

from son.package.decorators import performance
from son.workspace.project import Project
from son.workspace.workspace import Workspace

log = logging.getLogger(__name__)


class Packager(object):

    schemas = {
        'PD': 'pd-schema.yaml'
    }

    def __init__(self, prj_path, version="0.1"):
        # Log variable
        logging.basicConfig(level=logging.DEBUG)
        self._log = logging.getLogger(__name__)

        self._version = version
        self._package_descriptor = None

        self._project_path = prj_path
        self.package_descriptor = self._project_path

    @property
    def package_descriptor(self):
        return self._package_descriptor

    @package_descriptor.setter
    def package_descriptor(self, prj_path):
        """
        Create and set the full package descriptor as a dictionary.
        It process the file by each individual section.
        :param prj_path: The project path to load the project yaml file
        """
        log.info('Loading Project file')
        prj_file = os.path.join(prj_path, Project.__descriptor_name__)
        with open(prj_file, 'r') as prj_file:
            prj = yaml.load(prj_file)

        log.info('Create General Description section')
        gds = self.package_gds(prj)
        self._package_descriptor = gds

        validate(self._package_descriptor, load_schema(Packager.schemas['PD']))

    @performance
    def package_gds(self, prj_descriptor):
        """
        Compile information for the general description section.
        This section is exclusively filled by the project descriptor
        file located on the root of every project.

        :param prj_descriptor: The file to gather all needed information.
        """
        gds_fields = ['group', 'name', 'version', 'maintainer', 'description']
        gds = dict()
        gds['descriptor_version'] = self._version

        errors = []
        for field in gds_fields:
            if field not in prj_descriptor.keys():
                errors.append(field)
            else:
                gds['package_'+field] = prj_descriptor[field]

        if errors:
            print('Please define {} on {}'.format(', '.join(errors), Project.__descriptor_name__),
                  file=sys.stderr)
            return False
        return gds

    @performance
    def generate_package(self, name, dst_path=None):
        """
        Generate the final package version.
        :param dst_path; The path were the package will be generated
        :param name: The name of the final version of the package, the project name will be used if no name provided
        """

        # Validate all needed information
        if not self._package_descriptor:
            self._log.error("Missing package descriptor")
            return

        # Create package specific folder
        dst_path = os.path.join(self._project_path, "target") if not dst_path else dst_path
        os.makedirs(dst_path, exist_ok=True)

        # Create the manifest folder and file
        meta_inf = os.path.join(dst_path, "META-INF")
        os.makedirs(meta_inf, exist_ok=True)
        with open(os.path.join(meta_inf, "MANIFEST.MF"), "w") as manifest:
            manifest.write(yaml.dump(self.package_descriptor, default_flow_style=False))

        # Generate package file
        zip_name = os.path.join(dst_path, name + '.zip')
        with closing(zipfile.ZipFile(zip_name, 'w')) as pck:
            for base, dirs, files in os.walk(dst_path):
                for file_name in files:
                    full_path = os.path.join(base, file_name)
                    relative_path = full_path[len(dst_path)+len(os.sep):]
                    if not full_path == zip_name:
                        pck.write(full_path, relative_path)


def load_schema(template):
    """
    Search for a given template on the schemas folder inside the current package.
    :param template: The name of the template to look for
    :return: The loaded schema as a dictionary
    """
    rp = __name__
    path = os.path.join('templates', template)
    tf = pkg_resources.resource_string(rp, path)
    schema = yaml.load(tf)
    assert isinstance(schema, dict)
    return schema


def __validate_directory__(paths):
    """
    Validates the given path, it first check if it's a directory,
    then validates if contains a specific identifier.

    :param paths: dictionary with path and path identifier
    """
    for path, file in paths.items():
        if not os.path.isdir(path) or file and not os.path.isfile(os.path.join(path, file)):
            print("{} must be a directory".format(path), file=sys.stderr)
            return False
    return True


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Generate new sonata package")
    parser.add_argument("--workspace", help="Specify workspace to generate the package", required=True)
    parser.add_argument("--project",
                        help="create a new package based on the project at the specified location", required=False)
    parser.add_argument("-d", "--destination", help="create the package on the specified location", required=False)
    parser.add_argument("-n", "--name", help="create the package with the specific name", required=False)

    log.debug("parsing arguments")
    args = parser.parse_args()
    ws = args.workspace
    prj = args.project if args.project else os.getcwd()

    # Validate given arguments
    path_ids = dict()
    path_ids[ws] = Workspace.__descriptor_name__
    path_ids[prj] = Project.__descriptor_name__
    if not __validate_directory__(paths=path_ids):
        return

    name = Path(prj).name if not args.name else args.name

    pck = Packager(prj)
    pck.generate_package(dst_path=args.destination, name=name)