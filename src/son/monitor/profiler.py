"""
Performance profiling function available in the SONATA SDK

1) via the selected vim, start a VNF and chain it to a traffic generator and sink

2) steer the traffic generation to reach the max performance in an optimal way

3) gather metrics while traffic is flowing

4) return a table with the test results
"""

import paramiko
import time
import gevent

from son.monitor import prometheus
import logging

log = logging.getLogger(__name__)


def _create_dict(**kwargs):
    return kwargs

class Emu_Profiler():

    def __init__(self, net_api, compute_api):
        self.net_api = net_api
        self.compute_api = compute_api

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

        params = _create_dict(
            vnf_src_interface='output',
            vnf_dst_interface=kwargs.get('input'),
            bidirectional=True)
        # note zerorpc does not support named arguments
        r = self.net_api.network_action_start( vnf_src_name, vnf_dst_name, params)

        params = _create_dict(
            vnf_src_interface='output',
            vnf_dst_interface=kwargs.get('input'),
            bidirectional=True,
            match='dl_type=0x0800,nw_proto=17,udp_dst=5001',
            cookie=10)
        r = self.net_api.network_action_start(vnf_src_name, vnf_dst_name, params)

        # link vnf to traffic sink
        vnf_src_name = compute_name
        vnf_dst_name = 'psink'

        params = _create_dict(
            vnf_src_interface='output',
            vnf_dst_interface=kwargs.get('input'),
            bidirectional=True)
        r = self.net_api.network_action_start(vnf_src_name, vnf_dst_name, params)

        params = _create_dict(
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
            gevent.sleep(0)
            yield output_line

    def profile(self, mgmt_ip, rate, input_ip, vnf_uuid):

        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        # ssh.connect(mgmt_ip, username='steven', password='test')
        #ssh.connect(mgmt_ip, username='root', password='root')
        ssh.connect(mgmt_ip)

        iperf_cmd = 'iperf -c {0} -u -l18 -b{1}M -t1000 &'.format(input_ip, rate)
        if rate > 0:
            stdin, stdout, stderr = ssh.exec_command(iperf_cmd)

        start_time = time.time()
        query_cpu = '(sum(rate(container_cpu_usage_seconds_total{{id="/docker/{0}"}}[{1}s])))'.format(vnf_uuid, 1)
        while (time.time() - start_time) < 15:
            data = prometheus.query_Prometheus(query_cpu)
            # logging.info('rate: {1} data:{0}'.format(data, rate))
            gevent.sleep(0)
            time.sleep(1)

        query_cpu2 = '(sum(rate(container_cpu_usage_seconds_total{{id="/docker/{0}"}}[{1}s])))'.format(vnf_uuid, 8)
        cpu_load = float(prometheus.query_Prometheus(query_cpu2)[1])
        output = 'rate: {1}Mbps; cpu_load: {0}%'.format(round(cpu_load * 100, 2), rate)
        output_line = output
        logging.info(output_line)

        stop_iperf = 'pkill -9 iperf'
        stdin, stdout, stderr = ssh.exec_command(stop_iperf)

        return output_line


