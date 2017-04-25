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

import os
import tempfile
import argparse
import logging
import coloredlogs
import time
from termcolor import colored
from tabulate import tabulate

from son.profile.experiment import ServiceExperiment, FunctionExperiment
from son.profile.generator.sonata import extract_son_package, SonataServicePackage
from son.profile.helper import read_yaml
from son.monitor.profiler import Emu_Profiler

LOG = logging.getLogger(__name__)

"""
Configurations:
"""
SON_PKG_INPUT_DIR = "input_service"  # location of input package contents in args.work_dir
SON_PKG_SERVICE_DIR = "output_services"  # location of generated services in args.work_dir
SON_PKG_OUTPUT_DIR = "output_packages"  # location of generated packages in args.work_dir


class ProfileManager(object):
    """
    Main component class.
    """

    def __init__(self, args):
        self.start_time = time.time()
        self.service_experiments = list()
        self.function_experiments = list()
        self.generated_services = list()
        # arguments
        self.args = args
        self.args.config = os.path.join(os.getcwd(), self.args.config)
        self.son_pkg_input_dir = os.path.join(self.args.work_dir, SON_PKG_INPUT_DIR)
        self.son_pkg_service_dir = os.path.join(self.args.work_dir, SON_PKG_SERVICE_DIR)
        self.son_pkg_output_dir = os.path.join(self.args.work_dir, SON_PKG_OUTPUT_DIR)
        # logging setup
        coloredlogs.install(level="DEBUG" if args.verbose else "INFO")
        LOG.info("SONATA profiling tool initialized")
        LOG.debug("Arguments: %r" % self.args)

    def run(self):
        """
        Run son-profile
        :return:
        """
        # try to load PED file
        self.ped = self._load_ped_file(self.args.config)
        self._validate_ped_file(self.ped)
        # load and populate experiment specifications
        self.service_experiments, self.function_experiments = self._generate_experiment_specifications(self.ped)

        # execute profiling run on pre-deployed service
        # only service experiments are executed
        if not self.args.no_execution :
            for experiment in self.service_experiments:
                input_msd_path = experiment.input_metrics
                output_msd_path = experiment.output_metrics
                input_commands = experiment.command_space_list
                configuration_commands = experiment.configuration_space_dict
                resource_list = experiment.resource_space_list
                timeout = experiment.time_limit
                profiler = Emu_Profiler(input_msd_path=input_msd_path,
                                        output_msd_path=output_msd_path,
                                        input_commands=input_commands,
                                        configuration_commands=configuration_commands,
                                        overload_vnf_list = experiment.overload_vnf_list,
                                        timeout=timeout,
                                        title=self.ped['name'],
                                        no_display=self.args.no_display,
                                        resource_configuration=resource_list,
                                        vnforder_list=experiment.vnforder_list)
                profiler.start_experiment()

        # generate service packages
        if not self.args.no_generation :
            # unzip *.son package to be profiled and load its contents
            extract_son_package(self.ped, self.son_pkg_input_dir)
            self.son_pkg_input = SonataServicePackage.load(self.son_pkg_input_dir)
            # generate experiment services (modified NSDs, VNFDs for each experiment run)
            self.generated_services = self.generate_experiment_services()
            # package experiment services
            self.package_experiment_services()
            # print generation statistics
            self.print_generation_and_packaging_statistics()

    @staticmethod
    def _load_ped_file(ped_path):
        """
        Loads the specified PED file.
        :param ped_path: path to file
        :return: dictionary
        """
        yml = None
        try:
            yml = read_yaml(ped_path)
            if yml is None:
                raise BaseException("PED file YMAL error.")
        except:
            LOG.error("Couldn't load PED file %r. Abort." % ped_path)
            exit(1)
        # add path annotation to ped file (simpler handling of referenced artifacts)
        yml["ped_path"] = ped_path
        LOG.info("Loaded PED file %r." % ped_path)
        return yml

    @staticmethod
    def _validate_ped_file(input_ped):
        """
        Semantic validation of PED file contents.
        Check for all things we need to have in PED file.
        :param input_ped: ped dictionary
        :return: None
        """
        try:
            if "service_package" not in input_ped:
                raise BaseException("No service_package field found.")
            if "service_experiments" not in input_ped:
                raise BaseException("No service_experiments field found.")
            if "function_experiments" not in input_ped:
                raise BaseException("No function_experiments field found.")
            # TODO extend this when PED format is finally fixed
        except:
            LOG.exception("PED file verification error:")

    @staticmethod
    def _generate_experiment_specifications(input_ped):
        """
        Create experiment objects based on the contents of the PED file.
        :param input_ped: ped dictionary
        :return: service experiments list, function experiments list
        """
        service_experiments = list()
        function_experiments = list()

        # service experiments
        for e in input_ped.get("service_experiments"):
            e_obj = ServiceExperiment(e)
            e_obj.populate()
            service_experiments.append(e_obj)

        # function experiments
        for e in input_ped.get("function_experiments"):
            e_obj = FunctionExperiment(e)
            e_obj.populate()
            function_experiments.append(e_obj)

        return service_experiments, function_experiments

    def generate_experiment_services(self):
        """
        Generate SONATA service projects for each experiment and its configurations. The project is based
        on the contents of the service package referenced in the PED file and loaded to self.son_pkg_input.
        The generated project files are stored in self.args.work_dir.
        :return: list of service objects
        """
        services = list()
        # generate service objects
        for e in self.service_experiments:
            services += e.generate_sonata_services(self.son_pkg_input)
        for e in self.function_experiments:
            services += e.generate_sonata_services(self.son_pkg_input)
        LOG.info("Generated %d services." % len(services))
        # write services to disk
        for s in services:
            s.write(self.son_pkg_service_dir)
        LOG.info("Wrote %d services to disk." % len(services))
        return services

    def package_experiment_services(self):
        """
        Use son-package to package all previously generated service projects.
        :param services: list of service objects.
        :return:
        """
        for s in self.generated_services:
            son_pkg_path = s.pack(self.son_pkg_output_dir)
            # reset loglevel (ugly, but workspace and packaging tool overwrite it)
            coloredlogs.install(level="DEBUG" if self.args.verbose else "INFO")
            LOG.debug(
                "Packaged service %r to %r" % (s, son_pkg_path))
        LOG.info("Packaged %d services." % len(self.generated_services))

    def print_generation_and_packaging_statistics(self):

        def b(txt):
            return colored(txt, attrs=['bold'])

        def get_pkg_time(e):
            return sum([s.pack_time for s in e.generated_services])

        def get_pkg_size(e):
            return sum([float(s.pkg_file_size) / 1024 for s in e.generated_services])

        def generate_table():
            rows = list()
            # header
            rows.append([b("Experiment"), b("Num. Pkg."), b("Pkg. Time (s)"), b("Pkg. Sizes (kB)")])
            # body
            sum_pack_time = 0.0
            sum_file_size = 0.0
            for e in self.service_experiments:
                rows.append([e.name, len(e.run_configurations), get_pkg_time(e), get_pkg_size(e)])
                sum_pack_time += get_pkg_time(e)
                sum_file_size += get_pkg_size(e)
            for e in self.function_experiments:
                rows.append([e.name, len(e.run_configurations), get_pkg_time(e), get_pkg_size(e)])
                sum_pack_time += get_pkg_time(e)
                sum_file_size += get_pkg_size(e)
            # footer
            rows.append([b("Total"), b(len(self.generated_services)), b(sum_pack_time), b(sum_file_size)])
            return rows

        print(b("-" * 80))
        print(b("SONATA Profiler: Experiment Package Generation Report"))
        print(b("-" * 80))
        print("")
        print(tabulate(generate_table(), headers="firstrow", tablefmt="orgtbl"))
        print("")
        print("Temporary service projects path: %s" % b(self.son_pkg_service_dir))
        print("Generated service packages path: %s" % b(self.son_pkg_output_dir))
        print("Total time: %s" % b("%.4f" % (time.time() - self.start_time)))
        print("")



def parse_args(manual_args=None):
    """
    CLI interface definition.
    :return:
    """
    parser = argparse.ArgumentParser(
        description="Manage and control VNF and service profiling experiments.")

    parser.add_argument(
        "-v",
        "--verbose",
        help="Increases logging level to debug.",
        required=False,
        default=False,
        dest="verbose",
        action="store_true")

    parser.add_argument(
        "-c",
        "--config",
        help="PED file to be used for profiling run",
        required=True,
        dest="config")

    parser.add_argument(
        "--work-dir",
        help="Dictionary for generated artifacts, e.g., profiling packages. Will use a temporary folder as default.",
        required=False,
        default=tempfile.mkdtemp(),
        dest="work_dir")

    parser.add_argument(
        "--output-dir",
        help="Folder to collect measurements. Default: Current directory.",
        required=False,
        default=os.getcwd(),
        dest="output_dir")

    parser.add_argument(
        "--no-generation",
        help="Skip profiling package generation step.",
        required=False,
        default=False,
        dest="no_generation",
        action="store_true")

    parser.add_argument(
        "--no-execution",
        help="Skip profiling execution step.",
        required=False,
        default=False,
        dest="no_execution",
        action="store_true")

    parser.add_argument(
        "--no-display",
        help="Disable realtime output of profiling results",
        required=False,
        default=False,
        dest="no_display",
        action="store_true")

    if manual_args is not None:
        return parser.parse_args(manual_args)
    return parser.parse_args()


def main():
    """
    Program entry point
    :return: None
    """
    args = parse_args()
    p = ProfileManager(args)
    p.run()
