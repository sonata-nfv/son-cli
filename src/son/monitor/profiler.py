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
Performance profiling function available in the SONATA SDK
(c) 2016 by Steven Van Rossem <steven.vanrossem@intec.ugent.be>

1) via the selected vim, start a VNF and chain it to a traffic generator and sink

2) steer the traffic generation to reach the max performance in an optimal way

3) gather metrics while traffic is flowing

4) return a table with the test results
"""

import paramiko
import time

from son.monitor.msd import msd
from son.monitor.son_emu import emu

from son.monitor.prometheus_lib import query_Prometheus


import logging
LOG = logging.getLogger('Profiler')
LOG.setLevel(level=logging.DEBUG)
LOG.addHandler(logging.StreamHandler())


# TODO read from ped file
SON_EMU_IP = '172.17.0.1'
SON_EMU_REST_API_PORT = 5001
SON_EMU_API = "http://{0}:{1}".format(SON_EMU_IP, SON_EMU_REST_API_PORT)


# TODO call from son-profile
class Emu_Profiler():

    def __init__(self, input_msd_path, output_msd_path, input_commands, timeout=20):

        #class to control son-emu (export/query metrics)
        self.emu = emu(SON_EMU_API)
        # list of class Metric
        input_msd = msd(input_msd_path, emu)
        self.input_metric_queries = input_msd.get_metrics_list()
        output_msd = msd(output_msd_path, emu)
        self.output_metric_queries = output_msd.get_metrics_list()
        # each list item is a dict with {vnf_name:"cmd_to_execute", ..}
        self.input_commands = input_commands

        self.timeout = timeout

    def start_experiment(self):

        # query metrics

        start_time = time.time()
        # start commands
        for vnf_name, cmd in [cmd_dict for cmd_dict in self.input_commands]:
            self.emu.docker_exec(vnf_name, cmd)

            # let the load stabilize
            time.sleep(2)

            while(time.time()-start_time < self.timeout):
                self.query_metrics(self.input_metric_queries)

                self.query_metrics(self.output_metric_queries)

                time.sleep(1)

            # stop the load
            self.emu.docker_exec(vnf_name, cmd, action='stop')


    def query_metrics(self, metrics):
        for metric in metrics:
            query = metric.query
            value = query_Prometheus(query)
            metric_name = metric.metric_name
            metric_unit = metric.unit
            LOG.info("metric query: {1} {0} {2}".format(value, metric_name, metric_unit))


    # TODO: deploy this as a Service/VNF Descriptor
    # Service Chain: traffic source -> vnf -> traffic sink
    def deploy_chain(self, dc_label, compute_name, kwargs):

        # start vnf
        vnf_status = self.compute_api.compute_action_start(dc_label, compute_name,
                                               kwargs.get('image'),
                                               kwargs.get('network'),
                                               kwargs.get('command'))
        logging.info('vnf status:{0}'.format(vnf_status))
        # start traffic source (with fixed ip addres, no use for now...)
        psrc_status = self.compute_api.compute_action_start(dc_label, 'psrc', 'profile_source', [{'id': 'output'}], None)
        # start traffic sink (with fixed ip addres)
        psink_status = self.compute_api.compute_action_start(dc_label, 'psink', 'profile_sink', [{'id': 'input'}], None)


        # link traffic source to vnf
        vnf_src_name = 'psrc'
        vnf_dst_name = compute_name

        params = dict(
            vnf_src_interface='output',
            vnf_dst_interface=kwargs.get('input'),
            bidirectional=True)
        # note zerorpc does not support named arguments
        r = self.net_api.network_action_start( vnf_src_name, vnf_dst_name, params)

        params = dict(
            vnf_src_interface='output',
            vnf_dst_interface=kwargs.get('input'),
            bidirectional=True,
            match='dl_type=0x0800,nw_proto=17,udp_dst=5001',
            cookie=10)
        r = self.net_api.network_action_start(vnf_src_name, vnf_dst_name, params)

        # link vnf to traffic sink
        vnf_src_name = compute_name
        vnf_dst_name = 'psink'

        params = dict(
            vnf_src_interface='output',
            vnf_dst_interface=kwargs.get('input'),
            bidirectional=True)
        r = self.net_api.network_action_start(vnf_src_name, vnf_dst_name, params)

        params = dict(
            vnf_src_interface=kwargs.get('output'),
            vnf_dst_interface='input',
            bidirectional=True,
            match='dl_type=0x0800,nw_proto=17,udp_dst=5001',
            cookie=11)
        r = self.net_api.network_action_start(vnf_src_name, vnf_dst_name, params)

        ## get the data we need from the deployed vnfs
        for nw in psink_status.get('network'):
            if nw.get('intf_name') == 'input':
                self.psink_input_ip = nw['ip']
                break

        self.vnf_uuid = vnf_status['id']
        self.psrc_mgmt_ip = psrc_status['docker_network']

        # need to wait a bit before containers are fully up?
        time.sleep(3)

    def generate(self):
        for rate in [0, 1, 2, 3]:
            # logging.info('query:{0}'.format(query_cpu))

            output_line = self.profile(self.psrc_mgmt_ip, rate, self.psink_input_ip, self.vnf_uuid)
            yield output_line

    def profile(self, mgmt_ip, rate, input_ip, vnf_uuid):

        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        # ssh.connect(mgmt_ip, username='steven', password='test')
        ssh.connect(mgmt_ip, username='root', password='root')
        #ssh.connect(mgmt_ip)

        iperf_cmd = 'iperf -c {0} -u -l18 -b{1}M -t1000 &'.format(input_ip, rate)
        if rate > 0:
            stdin, stdout, stderr = ssh.exec_command(iperf_cmd)

        start_time = time.time()
        query_cpu = '(sum(rate(container_cpu_usage_seconds_total{{id="/docker/{0}"}}[{1}s])))'.format(vnf_uuid, 1)
        while (time.time() - start_time) < 10:
            data = query_Prometheus(query_cpu)
            # logging.info('rate: {1} data:{0}'.format(data, rate))
            time.sleep(1)

        query_cpu2 = '(sum(rate(container_cpu_usage_seconds_total{{id="/docker/{0}"}}[{1}s])))'.format(vnf_uuid, 8)
        cpu_load = float(query_Prometheus(query_cpu2)[1])
        output = 'rate: {1}Mbps; cpu_load: {0}%'.format(round(cpu_load * 100, 2), rate)
        output_line = output
        logging.info(output_line)

        stop_iperf = 'pkill -9 iperf'
        stdin, stdout, stderr = ssh.exec_command(stop_iperf)

        return output_line


