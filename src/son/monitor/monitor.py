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


"""

#from emuvim.cli import compute
#from emuvim.cli import network
#from emuvim.cli import datacenter
#from emuvim.cli import monitor
import prometheus

import argparse
import zerorpc

import pprint
pp = pprint.PrettyPrinter(indent=4)

import logging
log = logging.getLogger(__name__)

## parameters for the emulator VIM
COMPUTE_API = zerorpc.Client()  # heartbeat=None, timeout=120
COMPUTE_API.connect("tcp://127.0.0.1:4242")  # TODO hard coded for now. we'll change this later
NET_API = zerorpc.Client()
NET_API.connect("tcp://127.0.0.1:5151")  # TODO hard coded for now. we'll change this later

def prometheus_query_emu(args):
    vnf_name = _parse_vnf_name(args.get("vnf_name"))
    vnf_interface = _parse_vnf_interface(args.get("vnf_name"))
    dc_label = args.get("datacenter")
    query = args.get("query")
    vnf_status = COMPUTE_API.compute_status(dc_label, vnf_name)
    uuid = vnf_status['id']
    query = query.replace('<uuid>', uuid)

    r = prometheus.query_Prometheus(query)
    pp.pprint(r)

def _parse_vnf_name( vnf_name_str):
    vnf_name = vnf_name_str.split(':')[0]
    return vnf_name


def _parse_vnf_interface( vnf_name_str):
    try:
        vnf_interface = vnf_name_str.split(':')[1]
    except:
        vnf_interface = None

    return vnf_interface


def _execute_command(args):
    if args["command"] is not None:
        if args.get('vim') == 'emu':
            # call the local method with the same name as the command arg
            function = function_mapper_emu[args["command"]]
            function(args)
    else:
        print("Command not implemented")


description = """
    Install monitor features of the SONATA service platform/emulator or get monitor data
    from the SONATA platform/emulator.
    """
examples = """Example usage:

    son-monitor prometheus_query --vim emu -d datacenter1 -vnf vnf1 -q 'sum(rate(container_cpu_usage_seconds_total{id="/docker/<uuid>"}[10s]))'
    son-monitor profile --vim emu -d datacenter1 -n vnf1 -i vnf1_image --net '(id=input),(id=output)' -in input -out output
    """

parser = argparse.ArgumentParser(description=description,
                        formatter_class=argparse.RawDescriptionHelpFormatter,
                        epilog=examples)
parser.add_argument(
    "command",
    choices=['profile', 'prometheus_query'],
    help="Monitoring feature to be executed")

# map user input arguments to ffunction names
function_mapper_emu = {'prometheus_query':prometheus_query_emu }

parser.add_argument(
    "--vim", "-v", dest="vim",
    help="VIM where the command shold be executed (emu/sp)")
parser.add_argument(
    "--vnf_name", "-vnf", dest="vnf_name",
    help="vnf name:interface to be monitored")
parser.add_argument(
    "--query", "-q", dest="query",
    help="prometheus query")
parser.add_argument(
    "--datacenter", "-d", dest="datacenter",
    help="Data center where the vnf is deployed")
parser.add_argument(
    "--image","-i", dest="image",
    help="Name of container image to be used e.g. 'ubuntu:trusty'")
parser.add_argument(
    "--dcmd", "-c", dest="docker_command",
    help="Startup command of the container e.g. './start.sh'")
parser.add_argument(
    "--net", dest="network",
    help="Network properties of a compute instance e.g. \
          '(id=input,ip=10.0.10.3/24),(id=output,ip=10.0.10.4/24)' for multiple interfaces.")
parser.add_argument(
    "--input", "-in", dest="input",
    help="input interface of the vnf to profile")
parser.add_argument(
    "--output", "-out", dest="output",
    help="output interface of the vnf to profile")


def main():
    args = vars(parser.parse_args())
    #args = vars(parser.parse_args(argv))

    if args is None:
        parser.print_help()
        return

    _execute_command(args)

