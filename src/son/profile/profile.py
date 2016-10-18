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
import yaml

from son.profile.experiment import ServiceExperiment, FunctionExperiment

LOG = logging.getLogger(__name__)


class ProfileManager(object):

    def __init__(self, args):
        self.service_experiments = list()
        self.function_experiments = list()
        # arguments
        self.args = args
        self.args.config = os.path.join(os.getcwd(), self.args.config)
        # logging setup
        coloredlogs.install(level="DEBUG" if args.verbose else "INFO")
        LOG.info("SONATA profiling tool initialized")
        LOG.debug("Arguments: %r" % self.args)
        # try to load PED file
        self.ped = self._load_ped_file(self.args.config)
        self._validate_ped_file(self.ped)
        # load and populate experiments
        self.service_experiments, self.function_experiments = self._generate_experiments(self.ped)

    @staticmethod
    def _load_ped_file(ped_path):
        yml = None
        try:
            with open(ped_path, "r") as f:
                try:
                    yml = yaml.load(f)
                except yaml.YAMLError as ex:
                    LOG.exception("YAML error in PED file. Abort.")
                    exit(1)
        except:
            LOG.error("Couldn't load PED file %r. Abort." % ped_path)
            exit(1)
        LOG.info("Loaded PED file %r." % ped_path)
        return yml

    @staticmethod
    def _validate_ped_file(ped_data):
        try:
            if "service_package" not in ped_data:
                raise BaseException("No service_package field found.")
            if "service_experiments" not in ped_data:
                raise BaseException("No service_experiments field found.")
            if "function_experiments" not in ped_data:
                raise BaseException("No function_experiments field found.")
            # TODO extend this when PED format is finally fixed
        except:
            LOG.exception("PED file verification error:")

    @staticmethod
    def _generate_experiments(input_ped):
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

    def _load_son_package(self, son_path):
        pass

    def generate_profiling_services(self):
        pass

    def package_profiling_services(self):
        pass


def parse_args():

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

    return parser.parse_args()


def main():
    args = parse_args()
    p = ProfileManager(args)
