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
from son.profile.macro import rewrite_parameter_macros_to_lists
from son.profile.helper import compute_cartesian_product
from son.profile.sonpkg import SonataServicePackage
LOG = logging.getLogger(__name__)


class Experiment(object):

    def __init__(self, definition):
        # populate object from YAML definition
        self.__dict__.update(definition)
        # attributes
        self.run_configurations = list()
        self.generated_services = list()
        self.command_space_list = list()
        self.resource_space_list = list()

    def populate(self):
        """
        Search for parameter study macros and generate
        one run configuration for each parameter combination
        to be tested.
        """
        # convert parameter macros from PED file to plain lists
        for rl in self.resource_limitations:
            rewrite_parameter_macros_to_lists(rl)
        # convert measurment points from PED file to plain lists
        for mp in self.measurement_points:
            rewrite_parameter_macros_to_lists(mp)

        # aggregate all commands to be used in the experiment to a flat dict for further processing
        command_dict = self._get_command_space_as_dict()
        # explore entire command space by calculating the Cartesian product over the given dict
        self.command_space_list = compute_cartesian_product(command_dict)
        #LOG.info("command space:{0}".format(self.command_space_list))

        # aggregate all parameters to used in the experiment to a flat dict for further processing
        resource_dict = self._get_resource_space_as_dict()
        # print(parameter_dict)
        # explore entire parameter space by calculating the Cartesian product over the given dict
        self.resource_space_list = compute_cartesian_product(resource_dict)


        # create a run configuration object for each calculated configuration to test
        for i in range(0, len(self.resource_space_list)):
            self.run_configurations.append(RunConfiguration(i, self.resource_space_list[i]))
        LOG.info("Populated experiment specifications: %r with %d configurations to test." % (self.name, len(self.run_configurations)))

    def _get_command_space_as_dict(self):
        m = dict()
        for mp in self.measurement_points:
            vnf_name = mp.get("name")
            vnf_cmds = mp.get("cmd")
            # make sure the cmds are in a list
            if not isinstance(vnf_cmds, list):
                vnf_cmds = [vnf_cmds]
            m[vnf_name] = vnf_cmds
        return m

    def _get_resource_space_as_dict(self):
        """
        Create a flat dictionary with configuration lists to be tested for each configuration parameter.
        Output: dict
        {"function1:parameter1" : [0.1, 0.2, ...],
         "functionN:parameterN" : [0.1, ...],
         "function1:parameter1" : [0.1],
         "functionN:parameterN" : [0.1, 0.2, ...],
         "repetition" : [1, 2, 3]}
        """
        r = dict()
        for rl in self.resource_limitations:
            name = rl.get("function")
            for k, v in rl.items():
                if k == "function":
                    continue
                if not isinstance(v, list):
                    v = [v]
                r["%s:%s" % (name, k)] = v
        # add additional parameters (unrolled as lists!)
        r["repetition"] = list(range(0, self.repetitions))
        return r

    def generate_sonata_services(self, son_pkg_input):
        """
        Create a SONATA service for each configuration to be tested.
        :param son_pkg_input: base service to be used
        :return: list of services
        """
        services = list()
        for r in self.run_configurations:
            s = son_pkg_input.copy()
            s.annotate(self.name, r)
            self.modify_nsd(s, r)
            self.modify_vnfds(s, r)
            services.append(s)
        self.generated_services += services
        return services

    def modify_nsd(self, service, run_cfg):
        """
        Abstract: Needs to be overwritten.
        :param service: service to be modified
        :param run_cfg: run configuration to be applied
        :return:
        """
        pass

    def modify_vnfds(self, service, run_cfg):
        """
        TODO
        :param service: the service with the VNFDs to be modified
        :param run_cfg: the specific configuration to be applied
        :return:
        """
        def get_cfg_by_fun(fun_id):
            """
            Hepler to get config for a specific function.
            """
            r = dict()
            for k, v in run_cfg.configuration.items():
                kk = k.split(":")
                if kk[0] == fun_id:
                    r[kk[1]] = v
            return r

        for vnfd in service.vnfd_list:
            cfg = get_cfg_by_fun(service.get_id(vnfd))
            if len(cfg) > 0:
                # apply the resource limitations to the VNFD
                self.apply_resourcelimits_to_vnfd(vnfd, cfg)

    def apply_resourcelimits_to_vnfd(self, vnfd, cfg):
        pass


class ServiceExperiment(Experiment):

    def __init__(self, definition):
        super().__init__(definition)
        LOG.debug("Created service experiment: %r" % self.name)

    def modify_nsd(self, service, run_cfg):
        """
        Add measurement point (MP) VNFs to service graph of original NSD.
        :param service: service to be modified
        :param run_cfg: run configuration to be applied
        :return:
        """
        # TODO: implement
        pass


class FunctionExperiment(Experiment):

    def __init__(self, definition):
        super().__init__(definition)
        LOG.debug("Created function experiment: %r" % self.name)

    def modify_nsd(self, service, run_cfg):
        """
        Create a new NSD which is dedicated to test a single VNF and add measurement point (MP) VNFs to service graph.
        :param service: service to be modified
        :param run_cfg: run configuration to be applied
        :return:
        """
        # TODO: implement
        pass


class RunConfiguration(object):

    def __init__(self, run_id, configuration):
        self.run_id = run_id
        # TODO translate this to dict with simpler keys?
        self.configuration = configuration
