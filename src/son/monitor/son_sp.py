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

import logging
from requests import Session, post, get
import websocket
import threading
from subprocess import call, check_output
import json
from son.profile.helper import read_yaml, write_yaml
from prometheus_client import start_http_server, Gauge
import os
import docker
from time import gmtime, strftime
import datetime

"""
This class implements the son-sp commands.
These commands translate to the API's of the SONATA SP
"""

LOG = logging.getLogger('SP_monitor')
LOG.setLevel(level=logging.INFO)

prometheus_stream_port = 8082
prometheus_server_api = 'http://127.0.0.1:9090'
prometheus_config_path = '/tmp/son-monitor/prometheus/prometheus_sdk.yml'
GK_api = 'http://sp.int3.sonata-nfv.eu:32001/api/v2/'
monitor_api = 'http://sp.int3.sonata-nfv.eu:8000/api/v1/'
son_access_config_path = "/home/steven/.son-workspace"
platform_id = 'sp1'

class Service_Platform():
    def __init__(self, export_port=8082, GK_api=None, **kwargs):

        self.monitor_api = kwargs.get('monitor_api', monitor_api)
        self.GK_api = kwargs.get('GK_api', GK_api)
        self.son_access_config_path = kwargs.get('son_access_config_path', son_access_config_path)
        self.platform_id = kwargs.get('platform_id', platform_id)

        # Build up our session
        self.session = Session()
        self.session.headers = {
            "Accept": "application/json; charset=UTF-8"
        }

        # global parameters needed for the SP_websocket Class
        global prometheus_stream_port
        prometheus_stream_port = export_port
        global prometheus_server_api
        prometheus_server_api = kwargs.get('prometheus_server_api', prometheus_server_api)
        global prometheus_config_path
        prometheus_config_path = kwargs.get('prometheus_config_path', prometheus_config_path)

        self.ws_thread = None
        # websocket in the SP
        self.ws = None
        # access token to auth the SDK user
        self.access_token = None


    def list(self, **kwargs):
        # if metric is specified, show the list of VNFs that export ths metric
        metric = kwargs.get('metric')
        if metric :
            url = self.monitor_api + 'prometheus/metrics/name/' + metric
            ret = self.session.get(url).json().get("metrics").get("result")
        else:
            url = self.monitor_api + 'prometheus/metrics/list'
            resp = self.session.get(url)
            ret = resp.json().get('metrics')
        return ret

    def query(self, **kwargs):

        verbose = kwargs.get("verbose", False)
        LOG.setLevel(level=logging.INFO)
        if verbose:
            LOG.setLevel(level=logging.DEBUG)

        # periodically refresh token
        self._get_token()

        service_name = kwargs.get("service")
        vnf_name = kwargs.get("vnf_name")
        vdu_id = kwargs.get("vdu_id")
        vnfc_id = kwargs.get("vnfc_id")
        metric = kwargs.get("metric")
        since = kwargs.get("since")
        until = kwargs.get("until")

        metric_list = []

        service_desc_uuid = self._get_service_descriptor_uuid(service_name)
        vnf_instances = self._get_vnf_instances(service_desc_uuid)
        if len(vnf_instances) <= 0:
            LOG.warning("found no VNF instances for this service descriptor uuid: {0}".format(service_desc_uuid))
        else:
            vnf_descriptor_uuid = self._get_VNF_descriptor_uuid(vnf_name)
            for vnf_instance_uuid in vnf_instances:
                vdu_id, vc_id = self._check_VNF_instance(vnf_instance_uuid, vnf_descriptor_uuid, vdu_id, vnfc_id)
                if vc_id:
                    LOG.info("found VNF: {0} with instance uuid: {2}, vdu_id: {3} vnfc_id: {4} in service: {1} ".format(
                        vnf_name, service_name, vnf_instance_uuid, vdu_id, vc_id))
                    metric_list = self._get_async_metric(vnf_instance_uuid, vdu_id, vc_id, metric, since, until)
                    break

        return metric_list

    def stream_test(self, **kwargs):
        metric = kwargs.get('metric')
        vnf_name = kwargs.get('vnf_name')

        action = kwargs.get('action', 'start')
        if action == 'stop':
            SP_websocket._config_prometheus(remove=True)
            if self.ws:
                self.ws.close()
            #  kill all running websocket streams
            call(['pkill', '-f', 'son-monitor stream'])
            return 'websocket closed'

        # create the websocket with a filter eg: {"metric":"vm_cpu_perc","filters":["exported_instance":"vtc-vnf"]}
        url = self.monitor_api + 'ws/new'
        data = {'metric':str(metric), 'filters':str(list("exported_instance={}".format(vnf_name)))}
        response = self.session.post(url, json=data)
        code = response.status_code
        if code == 200:
            ws_url = response.json().get('ws_url')
            LOG.info('ws_url: {}'.format(ws_url))
            self.ws = SP_websocket(ws_url, vnf_name=vnf_name, metric=metric)
            self.ws_thread = threading.Thread(target=self.ws.run_forever)
            self.ws_thread.daemon = True
            self.ws_thread.start()
            self.ws_thread.join()
            return 'websocket thread started'

    def stream_auth(self, **kwargs):
        """
        call the SONATA Gatekeeper API to request monitoring metrics
        :param kwargs:
        :return:
        """

        verbose = kwargs.get("verbose", False)
        LOG.setLevel(level=logging.INFO)
        if verbose:
            LOG.setLevel(level=logging.DEBUG)

        action = kwargs.get('action', 'start')
        if action == 'stop':
            SP_websocket._config_prometheus(remove=True)
            if self.ws:
                self.ws.close()
            # kill all running websocket streams
            LOG.info('closing websocket')
            call(['pkill', '-f', 'son-monitor stream'])
            LOG.info('websocket closed')
            return 'websocket closed'

        # periodically refresh token
        self._get_token()


        service_name = kwargs.get("service","sonata-demo-12")
        vnf_name = kwargs.get("vnf_name","vtc-vnf2")
        vdu_id = kwargs.get("vdu_id")
        vnfc_id = kwargs.get("vnfc_id")
        metric = kwargs.get("metric")
        ws_url = None

        # first lookup if the service name is instantiated
        service_desc_uuid = self._get_service_descriptor_uuid(service_name)
        # then check if the service has an instance of this VNF
        vnf_instances = self._get_vnf_instances(service_desc_uuid)
        if len(vnf_instances) <= 0:
            LOG.warning("found no VNF instances for this service descriptor uuid: {0}".format(service_desc_uuid))
        else:
            # get the descriptor uuid of this vnf
            vnf_descriptor_uuid = self._get_VNF_descriptor_uuid(vnf_name)

            for vnf_instance_uuid in vnf_instances:
                # check if this VNF instance has the correct vdu and vnfc
                vdu_id, vnfc_id = self._check_VNF_instance(vnf_instance_uuid, vnf_descriptor_uuid, vdu_id, vnfc_id)
                if vnfc_id:
                    LOG.info("found VNF: {0} with instance uuid: {2}, vdu_id: {3} vnfc_id: {4} in service: {1} ".format(
                        vnf_name, service_name, vnf_instance_uuid, vdu_id, vnfc_id))
                    ws_url = self._get_ws_url(vnf_instance_uuid, vdu_id, vnfc_id, metric)
                    break

        if not vnfc_id:
            return 'No vnfc_id found in the record'
        if not ws_url:
            return 'No websocket url received'

        #ws_url = 'ws://10.30.0.112:8002/ws/98adab175fd64cc4bbe50ae9505fecf6'
        self.ws = SP_websocket(ws_url, vnf_name=vnf_name, metric=metric, vm_id=vnfc_id)
        self.ws_thread = threading.Thread(target=self.ws.run_forever)
        self.ws_thread.daemon = True
        self.ws_thread.start()
        self.ws_thread.join()
        return 'websocket thread started'

    # TODO: start background thread to refresh token
    def _get_token(self):
        # the credentials and token is fetched via son-access, the son-access config path must be given
        token_path = os.path.join(self.son_access_config_path, 'platforms', 'token.txt')
        output = check_output(['son-access', '-w', self.son_access_config_path, '-p', self.platform_id, 'auth'])

        #token_path = workspace_dir + '/' + token_file
        with open(token_path, 'r') as token:
            self.access_token = token.read()

    def _get_VNF_descriptor_uuid(self, vnf_name):
        headers = {'Authorization': "Bearer %s" % self.access_token}
        url = self.GK_api + "functions"
        resp = get(url, headers=headers)
        if resp.status_code >= 400:
            return 'error: {}'.format(resp.status_code)
        functions_list = resp.json()
        found_functions = [function.get("uuid") for function in functions_list if function["vnfd"]["name"] == vnf_name]
        if len(found_functions) > 1 or len(found_functions) == 0:
            LOG.warning("found {0} functions with name: {1}".format(len(found_functions), vnf_name))
            return None
        else:
            uuid = found_functions[0]
            LOG.info("found function descriptor of {0} with uuid: {1}".format(vnf_name, uuid))
            return uuid

    def _check_VNF_instance(self, vnf_instance_uuid, vnf_descriptor_uuid, vdu_id=None, vnfc_id=None):
        headers = {'Authorization': "Bearer %s" % self.access_token}
        url = self.GK_api + "records/functions"
        resp = get(url, headers=headers)
        if resp.status_code >= 400:
            return 'error: {}'.format(resp.status_code)
        LOG.debug('request VNF record, url:{0} json:{1}'.format(url, json.dumps(resp.json(), indent=2)))
        vnf_list = resp.json()
        vnf_list = [vnf for vnf in vnf_list if vnf.get("descriptor_reference") == vnf_descriptor_uuid and vnf.get("uuid") == vnf_instance_uuid]
        if len(vnf_list) > 1 :
            LOG.info("found multiple VNF instances with matching uuid: {0}".format(vnf_list))
            return False
        elif len(vnf_list) == 0 :
            LOG.info("found no VNF instance with matching uuid: {0}".format(vnf_instance_uuid))
            return False

        # we found 1 matching vnf instance, now check if it has a vdu
        LOG.info("found VNF instance with matching uuid: {0}".format(vnf_instance_uuid))
        vnf_record = vnf_list[0]
        vdu_list = vnf_record["virtual_deployment_units"]
        if vdu_id:
            vdu_list = [vdu for vdu in vdu_list if vdu.get("id") == vdu_id]
        else:
            #pick by default first vdu
            vdu_list = [vdu_list[0]]
            vdu = vdu_list[0]
            vdu_id = vdu["id"]
        if len(vdu_list) > 1 :
            LOG.info("found multiple vdu_ids with matching id: {0} list: {1}".format(vdu_id, vdu_list))
            return False
        elif len(vdu_list) == 0 :
            LOG.info("found no VDUs with matching id: {0}".format(vdu_id))
            return False

        # we found 1 matching vdu id, now check if it has a vdu instance(vnfc)
        LOG.info("found VDU with matching id: {0}".format(vdu_id))
        vdu = vdu_list[0]
        vnfc_list = vdu["vnfc_instance"]
        if vnfc_id:
            vnfc_list = [vnfc for vnfc in vnfc_list if vnfc.get("id") == vnfc_id]
        else:
            #pick by default first vnfc
            vnfc_list = [vnfc_list[0]]
            vnfc = vnfc_list[0]
            vnfc_id = vnfc["id"]
        if len(vnfc_list) > 1 :
            LOG.info("found multiple vnfc_ids with matching id: {0} list: {1}".format(vnfc_id, vnfc_list))
            return False
        elif len(vnfc_list) == 0 :
            LOG.info("found no VNFCs with matching id: {0}".format(vnfc_id))
            return False

        vnfc = vnfc_list[0]
        vc_id = vnfc["vc_id"]
        LOG.info("found VNFC with matching id: {0} and vc_id: {1}".format(vnfc_id, vc_id))

        return vdu_id, vc_id


    # Get the list of all the service instances registered
    def _get_service_instance_list(self):
        headers = {'Authorization': "Bearer %s" % self.access_token}
        url = self.GK_api + "records/services"
        resp = get(url, headers=headers)
        LOG.info('request service instance uuid list, url:{0} json:{1}'.format(url, json.dumps(resp.json(), indent=2)))
        return resp.text

    # Gets a registered service instance
    def _get_vnf_instances(self, service_descriptor_uuid):
        headers = {'Authorization': "Bearer %s" % self.access_token}
        url = self.GK_api + "records/services"
        resp = get(url, headers=headers)
        if resp.status_code >= 400:
            return 'error: {}'.format(resp.status_code)
        LOG.debug('request service instances, url:{0} json:{1}'.format(url, json.dumps(resp.json(), indent=2)))
        services_list = resp.json()
        found_services = [service for service in services_list if service["descriptor_reference"] == service_descriptor_uuid]
        if len(found_services) > 1 or len(found_services) == 0 :
            LOG.warning("found {0} service instances with descriptor uuid: {1}". format(len(found_services), service_descriptor_uuid))
            return []
        else:
            service = found_services[0]
            service_instance_uuid = service["uuid"]
            vnfr_list = [vnf.get("vnfr_id") for vnf in service["network_functions"]]
            LOG.info("found VNF descriptors: {}".format(json.dumps(vnfr_list,indent=2)))
            return vnfr_list

    # Obtain the list of services that can be instantiated
    def _get_service_descriptor_uuid(self, service_name):
        headers = {'Authorization': "Bearer %s" % self.access_token}
        url = self.GK_api + "services"
        resp = get(url, headers=headers)
        if resp.status_code >= 400:
            return 'error: {}'.format(resp.status_code)
        LOG.debug('request service descriptor uuid, url:{0} json:{1}'.format(url, json.dumps(resp.json(), indent=2)))
        services_list = resp.json()
        found_services = [service.get("uuid") for service  in services_list if service.get("nsd",{}).get("name") == service_name]
        if len(found_services) > 1 or len(found_services) == 0 :
            LOG.warning("found {0} services with name: {1}". format(len(found_services), service_name))
            return None
        else:
            uuid = found_services[0]
            LOG.info("found service descriptor of service: {0} with uuid: {1}".format(service_name, uuid))
            return uuid

    # get the websocket url where the metrocs will be streamed
    def _get_ws_url(self, vnf_instance_uuid, vdu_id, vc_id, metric):
        """
        call Gatekeeper API …/functions/metrics/:inst_id/:vdu_id/:vnfc_id/synch-mon-data
        A metric is uniquely identified by vnf_instance + vdu_id + vnfc_id.
        A VNF can consist out of multiple VDU's, a VNFC is an instance of a VDU.
        the vnfc_id is only unique in the scope of the VNFR/VDU
        :param vnf_instance_uuid: vnf instance uuid of the VNF
        :param vdu_id: vdu id in the VNFD of the metric we want to monitor
        :param vc_id: vc id in the VNFR of the metric we want to monitor
        :param metric:
        :return:
        """
        headers = {'Authorization': "Bearer %s" % self.access_token}
        #url = self.GK_api + "functions/" + function_uuid + "/instances/" + instance_uuid + "/synch-mon-data?metrics=" + \
        #      metric + "&for=10"
        url = self.GK_api + "functions/metrics/" + vnf_instance_uuid + "/" + vdu_id + "/" + vc_id +"/synch-mon-data"

        params = {"metrics": metric}
        response = get(url, headers=headers, params=params)
        code = response.status_code
        LOG.debug("url: {}".format(response.url))
        LOG.debug("websocket request response: {}".format(response.json()))
        if code == 200:
            ws_url = response.json().get('ws_url')
            LOG.info('ws_url: {}'.format(ws_url))
            return ws_url

    # Do a query to the SP Prometheus DB
    def _get_async_metric(self, vnf_instance_uuid, vdu_id, vc_id, metric, since=None, until=None, step='10s'):
        """
        call Gatekeeper API …/functions/metrics/:inst_id/:vdu_id/:vnfc_id/asynch-mon-data
        :param vnf_instance_uuid: vnf instance uuid of the VNF
        :param vdu_id: vdu id in the VNFD of the metric we want to monitor
        :param vnfc_id: vnfc id in the VNFR of the metric we want to monitor
        :param metric:
        :param since:
        :param until:
        :return:
        """

        # pick some default time values (since 1 min ago until now) (notation eg. 2017-05-05T17:10:22Z)
        # The SONATA integration env is UTC time
        if not until:
            #now = datetime.datetime.now()
            now = datetime.datetime.utcnow()
            until = now.strftime("%Y-%m-%dT%H:%M:%SZ")
            #until = '2017-06-19T10:06:00Z'

        if not since:
            #now = datetime.datetime.now()
            now = datetime.datetime.utcnow()
            now_minus_1 = now - datetime.timedelta(minutes=1)
            since = now_minus_1.strftime("%Y-%m-%dT%H:%M:%SZ")
            #since = '2017-06-19T10:05:00Z'

        LOG.info("since: {}".format(since))
        LOG.info("until: {}".format(until))
        LOG.info("step: {}".format(step))

        headers = {'Authorization': "Bearer %s" % self.access_token}
        url = self.GK_api + "functions/metrics/" + vnf_instance_uuid + "/" + vdu_id + "/" + vc_id + "/asynch-mon-data"
        params = {"metrics":metric,
                  "since":since,
                  "until":until,
                  "step":step}
        response = get(url, headers=headers, params=params)
        code = response.status_code
        LOG.debug("url: {}".format(response.url))
        LOG.debug("metric request response: {}".format(response.text))
        return response.json()

class SP_websocket(websocket.WebSocketApp):
    def __init__(self, url, vnf_name=None, metric=None, vm_id=None,
                 desc='exported metric from SP', print=True):

        self.vnf_name = vnf_name
        self.metric = metric
        self.vc_id = vm_id #the unique identifier of the vm, used by OpenStack
        self.desc = desc
        self.print = print

        self.metric_received = False
        self.prometheus_metric = None

        websocket.WebSocketApp.__init__(self, url,
                                        on_message=self._on_message,
                                        on_error=self._on_error,
                                        on_close=self._on_close,
                                        on_open=self._on_open
                                        )

    def _on_message(self, ws, message):

        LOG.info('ws message: {}'.format(message))

        metric_list = self.find_metric(message)

        # set the metric with the correct labels once, when first value is received
        if not self.metric_received:
            self.set_exported_metric(metric_list)

        if self.metric_received:
            for metric in metric_list:
                self.prometheus_metric.labels(**metric['labels']).set(metric["value"])

        # some info  printing
        if self.metric_received and self.print \
                and self.vnf_name is not None and self.metric is not None:
            message = self.filter_output(message)

    def _on_error(self, ws, error):
        self._config_prometheus(remove=True)
        pass

    def _on_close(self, ws):
        self._config_prometheus(remove=True)
        pass

    def _on_open(self, ws):
        global prometheus_stream_port
        # start local http export server
        start_http_server(prometheus_stream_port)
        # make Prometheus scrape this server
        self._config_prometheus()
        LOG.info('websocket opened: {}'.format(self.url))

    @staticmethod
    def _config_prometheus(remove=False):
        global prometheus_server_api
        global prometheus_config_path
        docker_cli = docker.from_env()
        # check if containers are already running
        c1 = docker_cli.containers.list(filters={'status': 'running', 'name': 'prometheus'})
        if len(c1) < 1:
            LOG.info('Prometheus is not running')
            return "Prometheus DB is not running"
        # make Prometheus scrape this server
        config_file = read_yaml(prometheus_config_path)
        targets = config_file.get('scrape_configs', [])
        SP_stream_config = next((target for target in targets if target.get('job_name') == 'SP_stream'), None)
        # the SP http server is not yet added to the config file
        config_dict = {'job_name': 'SP_stream', 'scrape_interval': '1s',
                       'static_configs': [{'targets': ['172.17.0.1:{}'.format(prometheus_stream_port)]}]}
        if not SP_stream_config and not remove:
            config_file['scrape_configs'].append(config_dict)
            LOG.info('added SP stream to Prometheus')
        elif remove and SP_stream_config:
            config_file['scrape_configs'].remove(config_dict)
            LOG.info('removed SP stream from Prometheus')

        write_yaml(prometheus_config_path, config_file)
        post(prometheus_server_api + '/-/reload')

    def set_exported_metric(self, metric_list):
        for metric in metric_list:
            # metric is found and labels are set
            metric_name = self.metric
            labels = list(metric['labels'])
            self.prometheus_metric = Gauge(metric_name, self.desc, labels)
            self.metric_received = True
            LOG.info('exporting metric with labels: {}'.format(labels))
            break

    def filter_output(self, message):
        data = json.loads(message)
        metric_list = data.get(self.metric, [])
        metric = {}
        for metric in metric_list:
            for label in metric.get('labels', []):
                if self.vc_id in label:
                    LOG.info('label: {}'.format(label))
                    LOG.info('value: {}'.format(metric.get('value')))
                    LOG.info('time: {}'.format(metric.get('time')))
                    break
        return metric

    def find_metric(self, message):
        data = json.loads(message)
        metric_list = data.get(self.metric, [])
        metric_list_out = []

        for metric in metric_list:
            metric_found = False
            labels = {}
            LOG.debug('metric found:{}'.format(metric))
            for label in metric.get('labels', []):
                key, value = label.split('=')
                labels[key] = str(value).replace('"','')
                if self.vc_id in value:
                    metric_found = True

            if metric_found:
                # metric is found and labels are set
                value = metric.get('value')
                metric = {'labels': labels, "value": value}
                metric_list_out.append(metric)

        return metric_list_out