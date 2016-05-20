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


from son.monitor import prometheus
from son.monitor import profiler

import argparse
import zerorpc

import pprint
pp = pprint.PrettyPrinter(indent=4)

import logging
log = logging.getLogger(__name__)

## parameters for the emulator VIM
# TODO: these settings come from the deployed topology in the emulator, read from centralized config file?
COMPUTE_API = zerorpc.Client()  # heartbeat=None, timeout=120
COMPUTE_API.connect("tcp://127.0.0.1:4242")  # TODO hard coded for now. we'll change this later
NET_API = zerorpc.Client()
NET_API.connect("tcp://127.0.0.1:5151")  # TODO hard coded for now. we'll change this later


## commands to export specific counter metrics from the emulator to prometheus
def start_metric_emu(args):
    vnf_name = _parse_vnf_name(args.get("vnf_name"))
    vnf_interface = _parse_vnf_interface(args.get("vnf_name"))
    r = NET_API.setup_metric(
        vnf_name,
        vnf_interface,
        args.get("metric"))
    pp.pprint(r)

def stop_metric_emu(args):
    vnf_name = _parse_vnf_name(args.get("vnf_name"))
    vnf_interface = _parse_vnf_interface(args.get("vnf_name"))
    r = NET_API.stop_metric(
        vnf_name,
        vnf_interface,
        args.get("metric"))
    pp.pprint(r)


def setup_flow(args):
    vnf_name = _parse_vnf_name(args.get("vnf_name"))
    vnf_interface = _parse_vnf_interface(args.get("vnf_name"))
    r = NET_API.setup_flow(
        vnf_name,
        vnf_interface,
        args.get("metric"),
        args.get("cookie"))
    pp.pprint(r)


def stop_flow(args):
    vnf_name = _parse_vnf_name(args.get("vnf_name"))
    vnf_interface = _parse_vnf_interface(args.get("vnf_name"))
    r = NET_API.stop_flow(
        vnf_name,
        vnf_interface,
        args.get("metric"),
        args.get("cookie"))
    pp.pprint(r)

## command to start a profiling action
def profile_emu(args):
    nw_list = list()
    if args.get("network") is not None:
        nw_list = _parse_network(args.get("network"))

    params = _create_dict(
        network=nw_list,
        command=args.get("docker_command"),
        image=args.get("image"),
        input=args.get("input"),
        output=args.get("output"))

    profiler_emu = profiler.Emu_Profiler(NET_API, COMPUTE_API)

    #deploy the test service chain
    vnf_name = _parse_vnf_name(args.get("vnf_name"))
    dc_label = args.get("datacenter")
    profiler_emu.deploy_chain(dc_label, vnf_name, params)

    #generate output table
    for output in profiler_emu.generate():
        print(output + '\n')

## command to query some metrics in prometheus
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


## helper functions
def _parse_vnf_name( vnf_name_str):
    vnf_name = vnf_name_str.split(':')[0]
    return vnf_name


def _parse_vnf_interface( vnf_name_str):
    try:
        vnf_interface = vnf_name_str.split(':')[1]
    except:
        vnf_interface = None

    return vnf_interface


def _create_dict(**kwargs):
    return kwargs


def _parse_network(network_str):
    '''
    parse the options for all network interfaces of the vnf
    :param network_str: (id=x,ip=x.x.x.x/x), ...
    :return: list of dicts [{"id":x,"ip":"x.x.x.x/x"}, ...]
    '''
    nw_list = list()
    networks = network_str[1:-1].split('),(')
    for nw in networks:
        nw_dict = dict(tuple(e.split('=')) for e in nw.split(','))
        nw_list.append(nw_dict)

    return nw_list


# map the command and vim selections to the correct function
def _execute_command(args):
    if args["command"] is not None and args.get('vim') == 'sp':
        # call the local method with the same name as the command arg
        function = function_mapper_sp[args["command"]]
        function(args)
    elif args["command"] is not None and (args.get('vim') == 'emu' or args.get('vim') is None):
        # call the local method with the same name as the command arg
        function = function_mapper_emu[args["command"]]
        function(args)
    else:
        print("Command not implemented")



## cli parser

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

# map user input arguments to function names
function_mapper_emu = {'prometheus_query':prometheus_query_emu, 'profile':profile_emu }
function_mapper_sp = {}

## select the vim to execute the monitoring action on (default=emulator)
parser.add_argument(
    "--vim", "-v", dest="vim",
    help="VIM where the command shold be executed (emu/sp)")

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

## arguments specific for metric/flow monitoring
parser.add_argument(
    "--metric", "-m", dest="metric",
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

