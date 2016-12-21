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

from son.monitor.utils import *
from son.monitor.prometheus import query_Prometheus, compute2vnfquery, network2vnfquery, test2vnfquery, metric2flowquery
from son.monitor.grafana_lib import Grafana

import logging
logging.basicConfig(level=logging.INFO)
LOG = logging.getLogger(__name__)

COOKIE_START = 100
MONITOR_FLOW_PRIORITY = 100

metric2flow_metric = {
    "rx_packet_count": "rx_packets",
    "tx_packet_count": "tx_packets",
    "rx_byte_count": "tx_bytes",
    "tx_byte_count": "tx_bytes",
    "rx_packet_rate": "rx_packets",
    "tx_packet_rate": "tx_packets",
    "rx_byte_rate": "tx_bytes",
    "tx_byte_rate": "tx_bytes"
}

class msd():

    def __init__(self, msd_file, vim):

        # Parse the msd file
        LOG.info('parsing msd: {0}'.format(msd_file))
        self.msd_dict = load_yaml(msd_file)

        # the VIM class where the monitoring is installed (son-emu manager)
        self.vim = vim

        # initialize a new Grafana dashboard
        self.grafana = Grafana()

        # get msd file parameters
        self.dashboard = self.msd_dict.get('dashboard')
        self.version = self.msd_dict.get('version')

        # get msd VNF metrics to monitor
        self.vnf_metrics = self.msd_dict.get('vnf_metrics')
        # get msd NSD links to monitor
        self.nsd_links = self.msd_dict.get('nsd_links')

        # cookie integer, unique per monitred flow
        self.cookie_counter = COOKIE_START

    def start(self):
        # init the dashboard
        self.grafana.init_dashboard(title=self.dashboard)

        # install and export metrics from the MSD file
        self.set_vnf_metrics('start')
        self.set_nsdlink_metrics('start')

    def stop(self):
        # clear the dashboard
        self.grafana.del_dashboard(title=self.dashboard)

        # remove metrics from the MSD file
        self.set_vnf_metrics('stop')
        self.set_nsdlink_metrics('stop')


    def set_vnf_metrics(self, action):
        for metric_group in self.vnf_metrics:
            graph_list = []
            title = metric_group['description']
            graph_list = self.vnfmetric_classifier(metric_group, action)
            if action == 'start':
                if 'count' in metric_group['metric_type']:
                    self.grafana.add_panel(metric_list=graph_list, title=title, dashboard_name=self.dashboard,
                                           graph_type='bars')
                else:
                    self.grafana.add_panel(metric_list=graph_list, title=title, dashboard_name=self.dashboard)


    # execute the correct function tto start/stop the metric_type
    def vnfmetric_classifier(self, metric_group, action):
        compute_metric_dict = {'start': self.start_compute_metric}
        compute_metrics = ['cpu', 'mem']

        testvnf_metric_dict = {'start': self.start_testvnf_metric}
        testvnf_metrics = ['packet_loss', 'jitter']

        network_metric_dict = {'start': self.start_network_metric, 'stop': self.stop_network_metric}
        network_metrics = ['packet_rate', 'byte_rate', 'packet_count', 'byte_count',
                           'packet_rate_cadv', 'byte_rate_cadv', 'packet_count_cadv', 'byte_count_cadv']

        metric_type = metric_group['metric_type']
        LOG.info('metric_type:{0}'.format(metric_type))

        graph_list = []
        for vnf_id in metric_group.get('vnf_ids', []):
            graph_dict = {}

            # Monitor metrics exported by Test-VNFs
            if metric_type in testvnf_metrics:
                function = testvnf_metric_dict.get(action)
                if function:
                    graph_dict = function(metric_group, vnf_id)

            # monitor compute stats (exported by cAdvisor in son-emu)
            elif metric_type in compute_metrics:
                function = compute_metric_dict.get(action)
                if function:
                    graph_dict = function(metric_group, vnf_id)

            # monitor network stats (exported by Ryu/cAdvisor in son-emu)
            elif metric_type in network_metrics:
                function = network_metric_dict.get(action)
                if function:
                    graph_dict = function(metric_group, vnf_id)

            else:
                logging.info("No query found for metric type: {0}".format(metric_type))
                continue

            graph_list.append(graph_dict)

        return graph_list


    def start_testvnf_metric(self, metric_group, vnf_id):
        # make default description
        desc = vnf_id.get("description")
        if not desc:
            desc = vnf_id['vnf']

        metric_type = metric_group['metric_type']
        # set correct Prometheus query
        query =test2vnfquery[metric_type].format(vnf_id['vnf'])
        graph_dict = dict(desc=desc, metric=query)
        return graph_dict

    def start_compute_metric(self, metric_group, vnf_id):
        # make default description
        desc = vnf_id.get("description")
        if not desc:
            desc = vnf_id['vnf']

        metric_type = metric_group['metric_type']
        # set correct Prometheus query
        query = compute2vnfquery[metric_type].format(vnf_id['vnf'])
        graph_dict = dict(desc=desc, metric=query)
        return graph_dict

    # network metrics gathered by the network interface counters
    def start_network_metric(self, metric_group, vnf_id):
        metric_type = metric_group['metric_type']
        metric_type2 = vnf_id['direction'] + "_" + metric_type
        vnf_name = parse_vnf_name(vnf_id['vnf'])
        vnf_interface = parse_vnf_interface(vnf_id['vnf'])
        flow_metric = metric2flow_metric[metric_type2]

        # metrics of cadvisor al already exported by default
        if not '_cadv' in metric_type:
            self.vim.monitor_interface('start', vnf_name + ':' + vnf_interface, flow_metric)

        query = network2vnfquery[metric_type2].format(vnf_name, vnf_interface)
        # make default description
        desc = vnf_id.get("description")
        if not desc:
            desc = vnf_id['vnf'] + ':' + vnf_id['direction']
        graph_dict = dict(desc=desc, metric=query)
        return graph_dict

    def stop_network_metric(self, metric_group, vnf_id):
        metric_type = metric_group['metric_type']
        metric_type2 = vnf_id['direction'] + "_" + metric_type
        vnf_name = parse_vnf_name(vnf_id['vnf'])
        vnf_interface = parse_vnf_interface(vnf_id['vnf'])
        flow_metric = metric2flow_metric[metric_type2]
        # metrics of cadvisor al already exported by default
        if not '_cadv' in metric_type:
            self.vim.monitor_interface('stop', vnf_name + ':' + vnf_interface, flow_metric)
        return

    def set_nsdlink_metrics(self, action):
        for metric_group in self.nsd_links:
            title = metric_group['description']
            graph_list = self.nsdlink_classifier(metric_group, action)
            if action == 'start':
                if 'count' in metric_group['metric_type']:
                    self.grafana.add_panel(metric_list=graph_list, title=title, dashboard_name=self.dashboard,
                                           graph_type='bars')
                else:
                    self.grafana.add_panel(metric_list=graph_list, title=title, dashboard_name=self.dashboard)

    # execute the correct function tto start/stop the metric_type
    def nsdlink_classifier(self, metric_group, action):
        nsdlink_metric_dict = {'start': self.start_nsdlink_metric, 'stop': self.stop_nsdlink_metric}
        nsdlink_metrics = ['packet_rate', 'byte_rate', 'packet_count', 'byte_count',
                           'packet_rate_cadv', 'byte_rate_cadv', 'packet_count_cadv', 'byte_count_cadv']

        graph_list = []

        metric_type = metric_group['metric_type']
        LOG.info('metric_type:{0}'.format(metric_type))

        #cookie = self.cookie_counter
        for nsdlink_id in metric_group.get('link_ids', []):
            graph_dict = {}

            # monitor network stats (exported by Ryu/cAdvisor in son-emu)
            if metric_type in nsdlink_metrics:
                function = nsdlink_metric_dict.get(action)
                if function:
                    graph_dict = function(metric_group, nsdlink_id)
                    # increment cookie when a match flow is installed
                    #if nsdlink_id.get('match'): cookie += 1

                else:
                    logging.info("No query found for metric type: {0}".format(metric_type))
                    continue

            graph_list.append(graph_dict)

        return graph_list

    # install flow_metrics for a specified chain
    def start_nsdlink_metric(self, metric_group, nsdlink_id):
        # install the link metric
        title = metric_group['description']
        metric_type = metric_group['metric_type']
        metric_type2 = nsdlink_id['direction'] + "_" + metric_type
        source = nsdlink_id['source']
        destination = nsdlink_id['destination']
        direction = nsdlink_id['direction']

        if 'rx' in direction:
            vnf_name = parse_vnf_name(destination)
            vnf_interface = parse_vnf_interface(destination)
        elif 'tx' in direction:
            vnf_name = parse_vnf_name(source)
            vnf_interface = parse_vnf_interface(source)

        # make default description
        desc = nsdlink_id.get("description")
        if not desc:
            desc = nsdlink_id['link_id'] + ':' + nsdlink_id['direction']

        # if match is empty then it is a total interface counter
        if not nsdlink_id.get('match'):
            flow_metric = metric2flow_metric[metric_type2]
            # metrics of cadvisor al already exported by default
            if not '_cadv' in metric_type:
                self.vim.monitor_interface('start', vnf_name + ':' + vnf_interface, flow_metric)
            query = network2vnfquery[metric_type2].format(vnf_name, vnf_interface)
            graph_dict = dict(desc=desc, metric=query)

        # if a match is given, install a flow specific counter
        else:
            flow_metric = metric2flow_metric[metric_type2]
            source = nsdlink_id['source']
            destination = nsdlink_id['destination']
            match = nsdlink_id['match']
            # install the flow and export the metric
            self.vim.flow_total('start', source, destination, flow_metric, self.cookie_counter, match=match,
                            bidirectional=False, priority=MONITOR_FLOW_PRIORITY)
            query = metric2flowquery[metric_type2].format(self.cookie_counter, vnf_name, vnf_interface)
            graph_dict = dict(desc=desc, metric=query)
            self.cookie_counter += 1

        return graph_dict

    # delete flow_metrics for a specified chain
    def stop_nsdlink_metric(self, metric_group, nsdlink_id):
        # install the link metrics
        title = metric_group['description']
        metric_type = metric_group['metric_type']
        metric_type2 = nsdlink_id['direction'] + "_" + metric_type
        source = nsdlink_id['source']
        destination = nsdlink_id['destination']
        direction = nsdlink_id['direction']

        if 'rx' in direction:
            vnf_name = parse_vnf_name(destination)
            vnf_interface = parse_vnf_interface(destination)
        elif 'tx' in direction:
            vnf_name = parse_vnf_name(source)
            vnf_interface = parse_vnf_interface(source)

        # if match is empty then it is a total interface counter
        if not nsdlink_id.get('match'):
            flow_metric = metric2flow_metric[metric_type2]
            # metrics of cadvisor al already exported by default
            if not '_cadv' in metric_type:
                self.vim.monitor_interface('stop', vnf_name + ':' + vnf_interface, flow_metric)

        # if a match is given, uninstall a flow specific counter
        else:
            flow_metric = metric2flow_metric[metric_type2]
            source = nsdlink_id['source']
            destination = nsdlink_id['destination']
            match = nsdlink_id['match']
            # install the flow and export the metric
            self.vim.flow_total('stop', source, destination, flow_metric, self.cookie_counter, match=match,
                                bidirectional=False, priority=MONITOR_FLOW_PRIORITY)
            self.cookie_counter += 1
