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
Prometheus API helper functions
(c) 2016 by Steven Van Rossem <steven.vanrossem@intec.ugent.be>
"""

import requests
import logging

# set this to localhost for now
# this is correct for son-emu started outside of a container or as a container with net=host
#TODO if prometheus sdk DB is started outside of emulator, place these globals in an external SDK config file?
prometheus_ip = 'localhost'
# When started in a docker container
#prometheus_ip = '172.17.0.1'
# when sdk is started with docker-compose, we could use
# prometheus_ip = 'prometheus'
prometheus_port = '9090'
prometheus_REST_api = 'http://{0}:{1}'.format(prometheus_ip, prometheus_port)

# translate metric names to the prometheus query
metric2total_query = {
    "rx_packet_count": "container_network_receive_packets_total{{name=\"mn.{0}\",interface=\"{1}\"}}",
    "tx_packet_count": "container_network_transmit_packets_total{{name=\"mn.{0}\",interface=\"{1}\"}}",
    "rx_bytes_count": "container_network_receive_bytes_total{{name=\"mn.{0}\",interface=\"{1}\"}}",
    "tx_bytes_count": "container_network_transmit_bytes_total{{name=\"mn.{0}\",interface=\"{1}\"}}"
}
metric2flowquery = {
    'tx_packet_count': 'sonemu_tx_count_packets{{flow_id=\"{0}\",vnf_name=\"{1}\",vnf_interface=\"{2}\"}}',
    'rx_packet_count': 'sonemu_rx_count_packets{{flow_id=\"{0}\",vnf_name=\"{1}\",vnf_interface=\"{2}\"}}',
    'tx_byte_count': 'sonemu_tx_count_bytes{{flow_id=\"{0}\",vnf_name=\"{1}\",vnf_interface=\"{2}\"}}',
    'rx_byte_count': 'sonemu_rx_count_bytes{{flow_id=\"{0}\",vnf_name=\"{1}\",vnf_interface=\"{2}\"}}'
}
metric2totalflowquery = {
    'tx_packet_count': 'sonemu_tx_count_packets{{flow_id=\"None\",vnf_name=\"{0}\",vnf_interface=\"{1}\"}}',
    'rx_packet_count': 'sonemu_rx_count_packets{{flow_id=\"None\",vnf_name=\"{0}\",vnf_interface=\"{1}\"}}',
    'tx_byte_count': 'sonemu_tx_count_bytes{{flow_id=\"None\",vnf_name=\"{0}\",vnf_interface=\"{1}\"}}',
    'rx_byte_count': 'sonemu_rx_count_bytes{{flow_id=\"None\",vnf_name=\"{0}\",vnf_interface=\"{1}\"}}'
}

metric2vnfquery = {
    "cpu" : "sum(rate(container_cpu_usage_seconds_total{{name=\"mn.{0}\"}}[3s]))*100",
    "mem" : "container_memory_usage_bytes{{name=\"mn.{0}\"}}",
    'tx_packet_rate': 'rate(sonemu_tx_count_packets{{flow_id=\"None\",vnf_name=\"{0}\",vnf_interface=\"{1}\"}}[3s])',
    'rx_packet_rate': 'rate(sonemu_rx_count_packets{{flow_id=\"None\",vnf_name=\"{0}\",vnf_interface=\"{1}\"}}[3s])',
    'tx_byte_rate': 'rate(sonemu_tx_count_bytes{{flow_id=\"None\",vnf_name=\"{0}\",vnf_interface=\"{1}\"}}[3s])',
    'rx_byte_rate': 'rate(sonemu_rx_count_bytes{{flow_id=\"None\",vnf_name=\"{0}\",vnf_interface=\"{1}\"}}[3s])',
}

profile2vnfquery = {
    "jitter" : "sonemu_jitter_ms{vnf_name=\"profile_sink\"}",
    "packet_loss": "sonemu_packet_loss_percent{vnf_name=\"profile_sink\"}"
}

def query_Prometheus(query):
    url = prometheus_REST_api + '/' + 'api/v1/query?query=' + query
    #logging.info('query:{0}'.format(url))
    req = requests.get(url)
    ret = req.json()
    if ret['status'] == 'success':
        try:
            ret = ret['data']['result'][0]['value']
        except:
            ret = None
    else:
        ret = None
    #logging.info('return:{0}'.format(ret))
    return ret