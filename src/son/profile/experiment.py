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
import operator
from collections import OrderedDict

LOG = logging.getLogger(__name__)


class Experiment(object):

    def __init__(self, definition):
        # populate object from YAML definition
        self.__dict__.update(definition)
        # attributes
        self.run_configurations = list()
        self.generated_services = list()
        self.command_space_list = list()
        self.vnforder_list = list()
        self.resource_space_list = list()
        self.configuration_space_dict = dict()
        self.overload_vnf_list = list()

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

        # check for vnfs that need overload detection
        if hasattr(self, 'overload_detection') :
            for vnf_name in self.overload_detection:
                self.overload_vnf_list.append(vnf_name)

        # get the configuration that needs to be executed in the vnf before the test run.
        self.configuration_space_dict = self._get_configuration_space_as_dict()
        #LOG.info("configuration space:{0}".format(self.command_space_list))

        # aggregate all commands to be used in the experiment to a flat dict for further processing
        command_dict, self.vnforder_list = self._get_command_space_as_dict()
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

    def _get_configuration_space_as_dict(self):
        """
        Create a dict that lists all commands that need to be executed per VNF
        :return: dict
        {"vnf_name1": [cmd1, cmd2, ...],
         "vnf_nameN": [cmd, ...],
        }
        """
        m = dict()
        for mp in self.measurement_points:
            vnf_name = mp.get("name")
            vnf_cmds = mp.get("configuration")
            # check if not empty
            if not vnf_cmds:
                return m
            # make sure the cmds are in a list
            if not isinstance(vnf_cmds, list):
                vnf_cmds = [vnf_cmds]
            m[vnf_name] = vnf_cmds
        return m

    def _get_command_space_as_dict(self):
        """
        Create a dict that lists all commands that need to be executed per VNF
        :return: dict
        {"vnf_name1": [cmd1, cmd2, ...],
         "vnf_nameN": [cmd, ...],
        }
        """
        cmds = dict()
        vnf_name2order = dict()
        vnforder_list = []
        for mp in self.measurement_points:
            vnf_name = mp.get("name")
            vnf_cmds = mp.get("cmd")
            cmd_order = mp.get("cmd_order")
            # check if not empty
            if not vnf_cmds:
                return (cmds, vnforder_list)
            # make sure the cmds are in a list
            if not isinstance(vnf_cmds, list):
                vnf_cmds = [vnf_cmds]
            cmds[vnf_name] = vnf_cmds

            if cmd_order:
                vnf_name2order[vnf_name] = int(cmd_order)
            else:
                vnf_name2order[vnf_name] = 0
            # create ordered list of vnf_names, so the commands are always executed in a defined order
            vnforder_dict = OrderedDict(sorted(vnf_name2order.items(), key=operator.itemgetter(1)))
            vnforder_list = [vnf_name for vnf_name, order in vnforder_dict.items()]

        return (cmds, vnforder_list)

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
