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


import requests
import json
from son.monitor.utils import *
import pkg_resources
import os
import copy
from itertools import groupby
import logging
logging.basicConfig(level=logging.INFO)

class Grafana():

    def __init__(self, host="127.0.0.1", port=3000):
        # Build up our session
        self.session = requests.Session()
        self.session.headers = {
            "Accept": "application/json; charset=UTF-8"
        }

        # authenticate with API key
        #self.session.auth = TokenAuth(authenticate_with)
        # authenticate with user, pw
        self.session.auth = requests.auth.HTTPBasicAuth("admin", "admin")

        self.url_protocol = "http"
        self.url_host = host
        if isinstance(port, int):
            port = str(port)
        self.url_port = port

    def construct_api_url(self, endpoint):
        params = {
            "host": self.url_host,
            "port": self.url_port,
            "endpoint": endpoint,
        }
        url_pattern = "http://{host}:{port}/api/{endpoint}"
        return url_pattern.format(**params)

    # post an empty json dashboard template file to grafana
    def init_dashboard(self, title=None):
        url = self.construct_api_url('dashboards/db')
        src_path = os.path.join('grafana', 'son-monitor-empty.json')
        srcfile = pkg_resources.resource_filename(__name__, src_path)
        dashboard = json.load(open(srcfile))
        if title is not None:
            dashboard["title"] = title
        ret = self.session.post(url, json={'dashboard': dashboard, 'overwrite': True})
        logging.info('init dahsboard: {0}'.format(ret))

    def del_dashboard(self, title=None):
        url = self.construct_api_url('dashboards/db') + "/" + title
        ret = self.session.delete(url)
        logging.info('delete dashboard: {0} return: {1}'.format(title, ret))

    def add_panel(self, metric_list, dashboard_name="son-monitor", title=None, graph_type="lines"):
        """
        add a graph panel to the son-monitor dashboard
        :param:metric_list: list of dictionaries from the nsd [{"desc":"", "metric":""}, ...]
        :return:
        """
        url = self.construct_api_url('dashboards/db/{0}'.format(dashboard_name))
        ret = self.session.get(url)
        dashboard = ret.json()
        dashboard = dashboard['dashboard']

        # add a new row
        src_path = os.path.join('grafana', 'grafana_row.json')
        srcfile = pkg_resources.resource_filename(__name__, src_path)
        dashboard['rows'].append(json.load(open(srcfile)))
        row_index = len(dashboard['rows']) - 1

        # add  a new panel to the row
        src_path = os.path.join('grafana', 'grafana_panel.json')
        srcfile = pkg_resources.resource_filename(__name__, src_path)
        new_panel = json.load(open(srcfile))
        new_panel['id'] = row_index + 1
        if graph_type == "lines":
            new_panel['bars'] = False
            new_panel['lines'] = True
        elif graph_type == "bars":
            new_panel['bars'] = True
            new_panel['lines'] = False
        dashboard['rows'][row_index]['panels'].append(new_panel)
        panel_index = len(dashboard['rows'][row_index]['panels']) - 1

        if title is None:
            # set panel title (first word of metric description)
            # need to make a copy of the list, because otherwise the original metric_list seems to get corrupted
            new_list = list(copy.deepcopy(metric_list))
            title = new_list[0]['desc'].split(' ')[0]

        dashboard['rows'][row_index]['panels'][panel_index]['title'] = title



        for metric in metric_list:
            # add a new target(graph) to the panel
            src_path = os.path.join('grafana', 'grafana_target.json')
            srcfile = pkg_resources.resource_filename(__name__, src_path)
            dashboard['rows'][row_index]['panels'][panel_index]['targets'].append(json.load(open(srcfile)))
            target_index = len(dashboard['rows'][row_index]['panels'][panel_index]['targets']) - 1

            query = metric['metric']
            dashboard['rows'][row_index]['panels'][panel_index]['targets'][target_index]['expr'] = query.replace('"',
                                                                                                                 '\"')
            legend = metric['desc']
            dashboard['rows'][row_index]['panels'][panel_index]['targets'][target_index]['legendFormat'] = legend
            logging.info('installed metric: {0} {1}'.format(legend, metric))

        url = self.construct_api_url('dashboards/db')
        ret = self.session.post(url, json={'dashboard': dashboard, 'overwrite': True})
        logging.info('post new dashboard: {0}'.format(ret))

    # find the monitor metrics in the nsd and add them to grafana
    def parse_nsd(self, nsd_path):
        logging.info('parsing nsd: {0}'.format(nsd_path))
        nsd = load_yaml(nsd_path)
        monitor_parameters = nsd['monitoring_parameters']
        # group metrics by type (the first word in the description is considered the type)
        for metric_type, metric_group in groupby(monitor_parameters, lambda x: x['desc'].split(' ')[0]):
            self.add_panel(metric_group)

class TokenAuth(requests.auth.AuthBase):
    """Authentication using a Grafana API token."""
    def __init__(self, token):
        self.token = token

    def __call__(self, request):
        request.headers.update({
            "Authorization": "Bearer {0}".format(self.token)
        })
        return request


if __name__ == '__main__':
    graf = Grafana()
    url = graf.construct_api_url('org')
    ret = graf.session.get(url)
    print(ret.json())

    url = graf.construct_api_url('dashboards/db/son-monitor')

    ret = graf.session.get(url)
    print(ret.json())

    url = graf.construct_api_url('dashboards/db')
    #dashboard = json.load(open('grafana/son-monitor-empty.json'))
    dashboard = ret.json()
    dashboard = dashboard['dashboard']
    dashboard['rows'].append(json.load(open('grafana/grafana_row.json')))
    row_index = len(dashboard['rows']) - 1
    dashboard['rows'][row_index]['panels'].append(json.load(open('grafana/grafana_panel.json')))
    panel_index = len(dashboard['rows'][row_index]['panels']) - 1
    dashboard['rows'][row_index]['panels'][panel_index]['targets'][0]['expr'] = \
        "sum(rate(container_cpu_usage_seconds_total{name=\"mn.ubuntu_vnf1\"}[10s]))"
    dashboard['rows'][row_index]['panels'][panel_index]['targets'][0]['legendFormat'] = "cpu (mn.ubuntu_vnf1)"
    ret = graf.session.post(url, json={'dashboard':dashboard, 'overwrite':True})
    print(ret.json())
