#  Copyright (c) 2015 SONATA-NFV, Paderborn University
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

import logging
import zipfile
import os
import copy
import time
from termcolor import colored
from tabulate import tabulate
from son.profile.helper import read_yaml, write_yaml, relative_path, ensure_dir
from son.profile.generator import ServiceConfigurationGenerator
from son.workspace.project import Project
from son.workspace.workspace import Workspace
from son.package.package import Packager


LOG = logging.getLogger(__name__)

# working directories created in "output_path"
SON_BASE_DIR = ".tmp_base_service"  # temp folder with input package contents
SON_GEN_SERVICES = ".tmp_gen_services"  # temp folder holding the unpacked generated services

class SonataServiceConfigurationGenerator(ServiceConfigurationGenerator):
    """
    SONATA Service Configuration Generator.
    Input: SONATA service package.
    Output: SONATA service packages.
    """

    def __init__(self, args):
        self.args = args
        self.RUN_ID = 0
        self.generated_services = dict()
        LOG.info("SONATA service configuration generator initialized")

    def generate(self, input_reference, function_experiments, service_experiments, working_path):
        """
        Generates service configurations according to the inputs.
        Returns a list of identifiers / paths to the generated service configurations.
        """
        self.start_time = time.time()
        self.output_path = working_path
        # load base service using PED reference (to a *.son file)
        base_service_obj = self._load(input_reference, working_path)
        # generate one SonataService for each experiment
        generated_service_objs = dict()
        generated_service_objs.update(self._generate_function_experiments(
            base_service_obj, function_experiments))
        generated_service_objs.update(self._generate_service_experiments(
            base_service_obj, service_experiments))
        # pack all generated services and write them to disk
        return self._pack(working_path, generated_service_objs)

    def _extract(self, input_reference, working_path):
        """
        Unzips a SONATA service package and stores all its contents
        to working_path + SON_BASE_DIR
        """
        # prepare working directory
        base_service_path = os.path.join(working_path, SON_BASE_DIR)
        ensure_dir(base_service_path)
        # locate referenced *.son file
        if not os.path.exists(input_reference):
            raise BaseException("Couldn't find referenced SONATA package: %r" % input_reference)
        # extract *.son file and put it into base_service_path
        LOG.debug("Unzipping: {} to {}".format(input_reference, base_service_path))
        with zipfile.ZipFile(input_reference, "r") as z:
            z.extractall(base_service_path)
        LOG.info("Extracted SONATA service package: {}".format(input_reference))
        return base_service_path

    def _load(self, input_reference, working_path):
        """
        Load a SONATA from the specified package (*.son).
        Creates temporary files in working_path.
        Returns SonataService objecct.
        """
        # extract service project from SONATA package
        base_service_path = self._extract(input_reference, working_path)
        return SonataService.load(base_service_path)

    def _generate_function_experiments(self, base_service_obj, experiments):
        LOG.warning("SONATA function experiment generation not implemented.")
        # TODO some dummy generation for testing
        r = dict()
        for i in range(0, 2):
            n = base_service_obj.copy()
            n.manifest["name"] += "-f-{}".format(self.RUN_ID)
            n.metadata["run_id"] = self.RUN_ID
            n.metadata["exname"] = "function-experiment"
            r[self.RUN_ID] = n
            self.RUN_ID += 1
        return r

    def _generate_service_experiments(self, base_service_obj, experiments):
        LOG.warning("SONATA service experiment generation not implemented.")
        # TODO some dummy generation for testing
        r = dict()
        for i in range(0, 1):
            n = base_service_obj.copy()
            n.manifest["name"] += "-s-{}".format(self.RUN_ID)
            n.metadata["run_id"] = self.RUN_ID
            n.metadata["exname"] = "service-experiment"
            r[self.RUN_ID] = n
            self.RUN_ID += 1
        return r

    def _pack(self, output_path, service_objs):
        """
        return: dict<run_id: package_path>
        """
        r = dict()
        for i, s in service_objs.items():
            r[i] = s.pack(output_path, self.args.verbose)
            self.generated_services[i] = s  # keep a pointer for statistics output
        LOG.info("Generated {} service packages in '{}'".format(len(r), output_path))
        return r

    def print_generation_and_packaging_statistics(self):

        def b(txt):
            return colored(txt, attrs=['bold'])

        def get_exname_list(slist):
            return set(s.metadata.get("exname") for s in slist)

        def get_services_by_exname(exname):
            return [s for s in self.generated_services.values() if s.metadata.get("exname") == exname]

        def get_pkg_time(l):
            return sum([s.metadata.get("package_generation_time") for s in l])

        def get_pkg_size(l):
            return sum([float(s.metadata.get("package_disk_size")) / 1024 for s in l])

        def generate_table():
            rows = list()
            # header
            rows.append([b("Experiment"), b("Num. Pkg."), b("Pkg. Time (s)"), b("Pkg. Sizes (kB)")])
            # body
            sum_pack_time = 0.0
            sum_file_size = 0.0
            for en in get_exname_list(self.generated_services.values()):
                filtered_s = get_services_by_exname(en)
                rows.append([en, len(filtered_s), get_pkg_time(filtered_s), get_pkg_size(filtered_s)])
                sum_pack_time += get_pkg_time(filtered_s)
                sum_file_size += get_pkg_size(filtered_s)
            # footer
            rows.append([b("Total"), b(len(self.generated_services)), b(sum_pack_time), b(sum_file_size)])
            return rows

        print(b("-" * 80))
        print(b("SONATA Profiler: Experiment Package Generation Report (sonata-pkg-gen)"))
        print(b("-" * 80))
        print("")
        print(tabulate(generate_table(), headers="firstrow", tablefmt="orgtbl"))
        print("")
        print("Generated service packages path: %s" % b(self.output_path))
        print("Total time: %s" % b("%.4f" % (time.time() - self.start_time)))
        print("")


class SonataService(object):

    def __init__(self, manifest, nsd, vnfd_list, metadata):
        self.manifest = manifest
        self.nsd = nsd
        self.vnfd_list = vnfd_list
        self.metadata = self._init_metadata()
        self.metadata.update(metadata)
        LOG.debug("Initialized: {}".format(self))


    def __repr__(self):
        return "SonataService({}.{}.{})".format(
            self.manifest.get("vendor"),
            self.manifest.get("name"),
            self.manifest.get("version"))

    @staticmethod
    def _init_metadata():
        m = dict()
        m["run_id"] = -1
        m["exname"] = None
        m["project_disk_path"] = None
        m["package_disk_path"] = None
        return m

    @staticmethod
    def load(path):
        """
        Loads the service package contents from the given path.
        :param path: path to a folder with service package contents.
        :return: SonataService object.
        """
        # load manifest
        manifest = read_yaml(
            os.path.join(path, "META-INF/MANIFEST.MF"))
        # load nsd
        nsd = read_yaml(
            os.path.join(
                path,
                relative_path(manifest.get("entry_service_template"))))
        # load vnfds
        vnfd_list = list()
        for ctx in manifest.get("package_content"):
            if "function_descriptor" in ctx.get("content-type"):
                vnfd_list.append(
                    read_yaml(
                        os.path.join(path,
                                     relative_path(ctx.get("name")))))
        # add some meta information
        metadata = dict()
        metadata["project_disk_path"] = path
        # create SonataServicePackage object
        s = SonataService(manifest, nsd, vnfd_list, metadata)
        LOG.info(
            "Loaded SONATA service package contents: {} ({} VNFDs).".format(
                s,
                len(vnfd_list)))
        # create SonataServicePackage object
        return s

    @property
    def pd(self):
        """
        Generate project descriptor based on information form
        the manifest file of the base package.
        """
        d = dict()
        d["descriptor_extension"] = "yml"
        d["version"] = "0.5"
        p = dict()
        p["description"] = self.manifest.get("description")
        p["maintainer"] = self.manifest.get("maintainer")
        p["name"] = self.manifest.get("name")
        p["vendor"] = self.manifest.get("vendor")
        p["version"] = self.manifest.get("version")
        d["package"] = p
        return d

    @property
    def pkg_name(self):
        """
        Generate name used for generated service project folder and package.
        :return: string
        """
        return "%s_%05d" % (self.metadata.get("exname"), self.metadata.get("run_id"))

    def copy(self):
        """
        Create a real copy of this service object.
        :return: object
        """
        LOG.debug("Copy: {}".format(self))
        return copy.deepcopy(self)

    def _write(self, output_path):
        path = os.path.join(output_path, SON_GEN_SERVICES, self.pkg_name)
        # update package path to reflect new location
        self.metadata["project_disk_path"] = path
        # create output folder
        ensure_dir(path)
        # write project yml
        write_yaml(os.path.join(path, "project.yml"), self.pd)
        # write nsd
        nsd_dir = os.path.join(path, "sources/nsd")
        ensure_dir(nsd_dir)
        write_yaml(os.path.join(nsd_dir,  "%s.yml" % self.nsd.get("name")), self.nsd)
        # write all vnfds
        vnf_dir = os.path.join(path, "sources/vnf")
        for vnfd in self.vnfd_list:
            d = os.path.join(vnf_dir, vnfd.get("name"))
            ensure_dir(d)
            write_yaml(os.path.join(d, "%s.yml" % vnfd.get("name")), vnfd)
        LOG.debug("Wrote: {} to {}".format(self, path))
        return path
    
    def pack(self, output_path, verbose=False):
        """
        Creates a *.son file of this service object.
        First writes the normal project structure to disk (to be used with packaging tool)
        """
        start_time = time.time()
        tmp_path = self._write(output_path)
        pkg_path = os.path.join(output_path, self.pkg_name) + ".son"
        LOG.warning(pkg_path)
        self.metadata["package_disk_path"] = pkg_path
        # be sure the target directory exists
        ensure_dir(output_path)
        # obtain workspace
        # TODO have workspace dir as command line argument
        workspace = Workspace.__create_from_descriptor__(Workspace.DEFAULT_WORKSPACE_DIR)
        if workspace is None:
            LOG.error("Couldn't initialize workspace: %r. Abort." % Workspace.DEFAULT_WORKSPACE_DIR)
            exit(1)
        # force verbosity of external tools if required
        workspace.log_level = "DEBUG" if verbose else "INFO"
        # obtain project
        project = Project.__create_from_descriptor__(workspace, tmp_path)
        if project is None:
            LOG.error("Packager couldn't load service project: %r. Abort." % tmp_path)
            exit(1)
        # initialize and run packager
        pck = Packager(workspace, project, dst_path=output_path)
        pck.generate_package(self.pkg_name)
        self.metadata["package_disk_size"] = os.path.getsize(pkg_path)
        self.metadata["package_generation_time"] = time.time() - start_time
        LOG.debug("Packed: {} to {}".format(self, pkg_path))
        return pkg_path

