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

import yaml
import logging

## helper functions
def parse_vnf_name( vnf_name_str):
    vnf_name = vnf_name_str.split(':')[0]
    return vnf_name


def parse_vnf_interface( vnf_name_str):
    try:
        vnf_interface = vnf_name_str.split(':')[1]
    except:
        vnf_interface = None

    return vnf_interface


def create_dict(**kwargs):
    return kwargs


def parse_network(network_str):
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


def valid_arguments(*args):
    ret = True
    for arg in args:
        if arg is None or arg == "":
            #log.error("Argument not valid: {0}".format(arg))
            ret = False
    return ret


def construct_url(base, prefix, *args):
    url = '/'.join([base, prefix])
    for arg in args:
        if valid_arguments(arg):
            url += "/" + arg
    return url


def load_nsd(nsd_path):
    """
    Load the entry NSD YAML and keep it as dict.
    :return:
    """
    nsd = load_yaml(nsd_path)
    return nsd


def load_yaml(path):
    with open(path, "r") as f:
        try:
            r = yaml.load(f)
        except yaml.YAMLError as exc:
            logging.exception("YAML parse error")
            r = dict()
    return r