import logging
import requests
import yaml
import sys
from requests import exceptions

log = logging.getLogger(__name__)

catalogues = []


class CatalogueClient(object):

    CAT_URI_BASE = "/"
    CAT_URI_NS = "/network-services"                  # List all NS
    CAT_URI_NS_ID = "/network-services/id"            # Get a specific NS by ID
    CAT_URI_NS_NAME = "/network-services/name"         # Get NS list by name
    CAT_URI_VNF = "/vnfs"                             # List all VNFs
    CAT_URI_VNF_ID = "/vnfs/id"                       # Get a specific VNF by id
    CAT_URI_VNF_NAME = "/vnfs/name"                   # GET VNF list by name

    def __init__(self, base_url, auth=('', '')):
        self.base_url = base_url
        self._auth = auth   # Just basic auth for now
        self._headers = {'Content-Type': 'application/x-yaml'}

    def alive(self):
        """
        Checks if the catalogue API server is alive and responding to requests
        :return: True=server OK, False=server unavailable
        """
        url = self.base_url + CatalogueClient.CAT_URI_BASE
        try:
            r = requests.get(url, auth=self._auth, headers=self._headers)
        except requests.exceptions.ConnectionError:
            log.warning("Connection Error while contacting '{}'. Error message: '{}'".format(url, sys.exc_info()))
            return False
        except:
            log.warning("Unexpected Error connecting to '{}'. Error message: '{}'".format(url, sys.exc_info()[0]))
            raise

        return r.status_code == requests.codes.ok

    def get_list_all_ns(self):
        r = self.__get_cat_object__(CatalogueClient.CAT_URI_NS, "")
        return r

    def get_ns(self, ns_id):
        """
        Obtains a specific network service (NS)
        :param ns_id: ID of NS in the form 'vendor.ns_name.version'
        :return: yaml object containing NS
        """
        r = self.__get_cat_object__(CatalogueClient.CAT_URI_NS_ID, ns_id)
        if not isinstance(r, str) and len(r) > 1:
            log.error("Obtained multiple network services using the ID '{}'".format(ns_id))
            return
        return yaml.load(r)

    def get_ns_by_name(self, ns_name):
        """
        Obtains a list of network services matching the ns_name
        :param ns_name: name of network service
        :return: (str) list of network services
        """
        r = self.__get_cat_object__(CatalogueClient.CAT_URI_NS_NAME, ns_name)
        return r

    def get_vnf(self, vnf_id):
        """
        Obtains a specific VNF
        :param ns_id: ID of the VNF in the form 'vendor.vnf_name.version'
        :return: yaml object containing VNF
        :param vnf_id:
        :return:
        """

        r = self.__get_cat_object__(CatalogueClient.CAT_URI_VNF_ID, vnf_id)
        if not r:
            return
        if not isinstance(r, str) and len(r) > 1:
            log.error("Obtained multiple VNFs using the ID '{}'".format(vnf_id))
            return
        print(r)

        return yaml.load(r)

    def get_vnf_by_name(self, vnf_name):
        """
        Obtains a list of VNFs matching the vnf_name
        :param vnf_name: name of network service
        :return: (str) list of VNFs
        """
        r = self.__get_cat_object__(CatalogueClient.CAT_URI_VNF_NAME, vnf_name)
        return r

    def __get_cat_object__(self, cat_uri, obj_id):
        url = self.base_url + cat_uri + "/" + obj_id
        r = requests.get(url, auth=self._auth, headers=self._headers)
        assert r.status_code == requests.codes.ok, \
            "Failed to retrieve object '{}'. Error code={}".format(obj_id, r.status_code)
        return r.text







if __name__ == "__main__":  # Temporary! only for testing purposes
    client = CatalogueClient("http://10.10.201.24:4011")

    print(client.alive())
    #print(len(client.get_vnf_by_name("firewall-vnf")))

    # ns_list = client.get_vnf_by_name("firewall-vnf")
    # for ns in ns_list:
    #     print(ns)
    ns = client.get_vnf("eu.sonata-nfv.firewall-vnf.0.2")

    yaml.dump(ns, sys.stdout)

