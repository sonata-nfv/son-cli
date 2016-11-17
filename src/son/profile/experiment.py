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
import coloredlogs
import itertools as it
from son.profile.macro import rewrite_parameter_macros_to_lists
LOG = logging.getLogger(__name__)


class Experiment(object):

    def __init__(self, definition):
        # populate object from YAML definition
        self.__dict__.update(definition)
        # attributes
        self.run_configurations = list()

    def populate(self):
        """
        Search for parameter study macros and generate
        one run configuration for each parameter combination
        to be tested.
        """
        # convert parameter macros from PED file to plain lists
        for rl in self.resource_limitations:
            rewrite_parameter_macros_to_lists(rl)
        # aggregate all parameters to used in the experiment to a flat dict for further processing
        parameter_dict = self._get_configuration_space_as_dict()
        print(parameter_dict)
        # explore entire parameter space by calculating the Cartesian product over the given dict
        parameter_space_list = Experiment._compute_cartesian_product(parameter_dict)
        # create a run configuration object for each calculated configuration to test
        for i in range(0, len(parameter_space_list)):
            self.run_configurations.append(RunConfiguration(i, parameter_space_list[i]))
        LOG.info("Populated experiment: %r with %d configurations to test." % (self.name, len(self.run_configurations)))

    def _get_configuration_space_as_dict(self):
        """
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

    @staticmethod
    def _compute_cartesian_product(p_dict):
        """
        Compute Cartesian product on parameter dict:
        In:
            {"number": [1,2,3], "color": ["orange","blue"] }
        Out:
            [ {"number": 1, "color": "orange"},
              {"number": 1, "color": "blue"},
              {"number": 2, "color": "orange"},
              {"number": 2, "color": "blue"},
              {"number": 3, "color": "orange"},
              {"number": 3, "color": "blue"}
            ]
        """
        p_names = sorted(p_dict)
        return [dict(zip(p_names, prod)) for prod in it.product(*(p_dict[n] for n in p_names))]


class ServiceExperiment(Experiment):

    def __init__(self, definition):
        super().__init__(definition)
        LOG.debug("Created service experiment: %r" % self.name)


class FunctionExperiment(Experiment):

    def __init__(self, definition):
        super().__init__(definition)
        LOG.debug("Created function experiment: %r" % self.name)


class RunConfiguration(object):

    def __init__(self, run_id, configuration):
        self.run_id = run_id
        # TODO translate this to dict with simpler keys?
        self.configuration = configuration
