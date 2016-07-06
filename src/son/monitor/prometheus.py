"""
Prometheus API helper functions
(c) 2016 by Steven Van Rossem <steven.vanrossem@intec.ugent.be>
"""

import requests

# set this to localhost for now
# this is correct for son-emu started outside of a container or as a container with net=host
PROMETHEUS_IP = '127.0.0.1'
PROMETHEUS_PORT = '9090'
PROMETHEUS_REST_API = 'http://{0}:{1}'.format(PROMETHEUS_IP, PROMETHEUS_PORT)


def query_Prometheus(query):
    url = PROMETHEUS_REST_API + '/' + 'api/v1/query?query=' + query
    req = requests.get(url)
    ret = req.json()
    if ret['status'] == 'success':
        try:
            ret = ret['data']['result'][0]['value']
        except:
            ret = None
    else:
        ret = None
    return ret