"""
Copyright (c) 2015 SONATA-NFV
ALL RIGHTS RESERVED.
Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at
    http://www.apache.org/licenses/LICENSE-2.0
Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
Neither the name of the SONATA-NFV [, ANY ADDITIONAL AFFILIATION]
nor the names of its contributors may be used to endorse or promote
products derived from this software without specific prior written
permission.
This work has been performed in the framework of the SONATA project,
funded by the European Commission under Grant number 671517 through
the Horizon 2020 and 5G-PPP programmes. The authors would like to
acknowledge the contributions of their colleagues of the SONATA
partner consortium (www.sonata-nfv.eu).
"""

"""
son-monitor features available by cli

In current implementation, the son-monitor commands connects either to:
1) the SDK emulator (son-emu)
    supported functions:
        - query monitored data via Prometheus API
        - add a (temporarily) monitor metric to the son-emu monitor framework:
            - ryu metrics
            - custom metrics exported by a dedicated agent
        - perform a profiling action and return a profiling table

or

2) the SP Monitor Manager:
    supported functions:
        - query monitored data via Prometheus API
        - generate a profiling table for a vnf

(c) 2016 by Steven Van Rossem <steven.vanrossem@intec.ugent.be>
"""

import argparse

from son.monitor.son_emu import emu
from son.monitor.son_sp import sp

import pprint
pp = pprint.PrettyPrinter(indent=4)

import logging
logging.basicConfig(level=logging.INFO)

## parameters for the emulator VIM
# TODO: these settings come from the deployed topology in the emulator, read from centralized config file?
# API from docker container
SON_EMU_API = "http://172.17.0.1:5001"
# API when docker network=host in son-cli, or when not started as container
#SON_EMU_API = "http://localhost:5001"
# API when started with docker-compose
#SON_EMU_API = "http://son-emu:5001"

# initalize the vims accessible from the SDK
emu = emu(SON_EMU_API)


# map the command and vim selections to the correct function
def _execute_command(args):
    if args["command"] is not None:
        VIM_class = eval(args.get('vim'))
        # call the VIM class method with the same name as the command arg
        ret = getattr(VIM_class, args["command"][0])(**args)
        logging.info("cmd: {0} \nreturn: {1}".format(args["command"][0], ret))
        #pp.pprint(ret)
    else:
        logging.error("Command not implemented: {0}".format(args.get("command")))


## cli parser

description = """
    Install monitor features on or get monitor data from the SONATA platform/emulator.
    """
examples = """Example usage:

    son-monitor query --vim emu -d datacenter1 -vnf vnf1 -q 'sum(rate(container_cpu_usage_seconds_total{id="/docker/<uuid>"}[10s]))'
    son-monitor profile --vim emu -d datacenter1 -n vnf1 -i vnf1_image --net '(id=input),(id=output)' -in input -out output
    """

parser = argparse.ArgumentParser(description=description,
                        formatter_class=argparse.RawTextHelpFormatter,
                        epilog=examples)
parser.add_argument(
    "command",
    choices=['init', 'profile', 'query', 'interface', 'flow_mon', 'flow_entry', 'flow_total'],
    nargs=1,
    help="""Monitoring feature to be executed:
         interface: export interface metric (tx/rx bytes/packets)
         flow_entry : (un)set the flow entry
         flow_mon : export flow_entry metric (tx/rx bytes/packets)
         flow_total : flow_entry + flow_mon
         init : start/stop the monitoring framework
         profile : performance profiling (tba)
         """)

parser.add_argument(
    "action",
    choices=['start', 'stop'],
    default='start',
    nargs='?',
    help="""Action for interface, flow_mon, flow_entry, flow_total:
          start: install the flowentry and/or export the metric
          stop: delete the flowentry and/or stop exporting the metric
          Action for init:
          start: start the monitoring framework (cAdvisor, Prometheus DB + Pushgateway)
          stop: stop the monitoring framework
          """)

## select the vim to execute the monitoring action on (default=emulator)
parser.add_argument(
    "--vim", "-v", dest="vim",
    default="emu",
    help="VIM where the command should be executed (emu/sp)")

## arguments to specify a vnf
parser.add_argument(
    "--vnf_name", "-vnf", dest="vnf_name",
    help="vnf name:interface to be monitored")
parser.add_argument(
    "--datacenter", "-d", dest="datacenter",
    help="Data center where the vnf is deployed")

## arguments to deploy a vnf
parser.add_argument(
    "--image","-i", dest="image",
    help="Name of container image to be used e.g. 'ubuntu:trusty'")
parser.add_argument(
    "--dcmd", "-cmd", dest="docker_command",
    help="Startup command of the container e.g. './start.sh'")
parser.add_argument(
    "--net", dest="network",
    help="Network properties of a compute instance e.g. \
          '(id=input,ip=10.0.10.3/24),(id=output,ip=10.0.10.4/24)' for multiple interfaces.")

## arguments to query prometheus
parser.add_argument(
    "--query", "-q", dest="query",
    help="prometheus query")

## arguments specific for vnf profling
parser.add_argument(
    "--input", "-in", dest="input",
    help="input interface of the vnf to profile")
parser.add_argument(
    "--output", "-out", dest="output",
    help="output interface of the vnf to profile")

## arguments specific for metric/flow installing
parser.add_argument(
    "--source", "-src", dest="source",
    help="vnf name:interface of the source of the chain")
parser.add_argument(
    "--destination", "-dst", dest="destination",
    help="vnf name:interface of the destination of the chain")
parser.add_argument(
    "--weight", "-w", dest="weight",
    help="weight edge attribute to calculate the path")
parser.add_argument(
    "--match", "-ma", dest="match",
    help="string holding extra matches for the flow entries")
parser.add_argument(
    "--bidirectional", "-b", dest="bidirectional",
    action='store_true',
    help="add/remove the flow entries from src to dst and back")
parser.add_argument(
    "--priority", "-p", dest="priority",
    help="priority of the installed flowrule")

## arguments specific for metric/flow monitoring
parser.add_argument(
    "--metric", "-me", dest="metric",
    default='tx_packets',
    help="tx_bytes, rx_bytes, tx_packets, rx_packets")
parser.add_argument(
    "--cookie", "-c", dest="cookie",
    help="flow cookie to monitor")

def main():

    args = vars(parser.parse_args())

    if args is None:
        parser.print_help()
        return

    _execute_command(args)

if __name__ == "__main__":
    main()

