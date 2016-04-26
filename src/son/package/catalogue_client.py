import logging
import requests
import yaml
import sys
from requests import exceptions

log = logging.getLogger(__name__)

catalogues = []


class CatalogueClient(object):

    CAT_URI_BASE = "/"
    CAT_URI_NS = "/network-services"                    # List all NS
    CAT_URI_NS_ID = "/network-services/id/"             # Get a specific NS by ID
    CAT_URI_NS_NAME = "/network-services/name/"         # Get NS list by name
    CAT_URI_VNF = "/vnfs"                               # List all VNFs
    CAT_URI_VNF_ID = "/vnfs/id/"                        # Get a specific VNF by id
    CAT_URI_VNF_NAME = "/vnfs/name/"                    # GET VNF list by name

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
            response = requests.get(url, auth=self._auth, headers=self._headers)

        except requests.exceptions.InvalidURL:
            log.warning("Invalid URL: '{}'. Please specify a valid address to a catalogue server".format(url))
            return False
        except requests.exceptions.ConnectionError:
            log.warning("Connection Error while contacting '{}'. Error message: '{}'".format(url, sys.exc_info()))
            return False
        except:
            log.warning("Unexpected Error connecting to '{}'. Error message: '{}'".format(url, sys.exc_info()[0]))
            raise

        return response.status_code == requests.codes.ok

    def get_list_all_ns(self):
        return self.__get_cat_object__(CatalogueClient.CAT_URI_NS, "")

    def get_ns(self, ns_id):
        """
        Obtains a specific network service (NS)
        :param ns_id: ID of NS in the form 'vendor.ns_name.version'
        :return: yaml object containing NS
        """
        cat_obj = self.__get_cat_object__(CatalogueClient.CAT_URI_NS_ID, ns_id)
        if not isinstance(cat_obj, str) and len(cat_obj) > 1:
            log.error("Obtained multiple network services using the ID '{}'".format(ns_id))
            return
        log.debug("Obtained NS schema:\n{}".format(cat_obj))
        return yaml.load(cat_obj)

    def get_ns_by_name(self, ns_name):
        """
        Obtains a list of network services matching the ns_name
        :param ns_name: name of network service
        :return: (str) list of network services
        """
        return self.__get_cat_object__(CatalogueClient.CAT_URI_NS_NAME, ns_name)

    def get_list_all_vnf(self):
        return self.__get_cat_object__(CatalogueClient.CAT_URI_VNF, "")

    def get_vnf(self, vnf_id):
        """
        Obtains a specific VNF
        :param ns_id: ID of the VNF in the form 'vendor.vnf_name.version'
        :return: yaml object containing VNF
        :param vnf_id:
        :return:
        """
        cat_obj = self.__get_cat_object__(CatalogueClient.CAT_URI_VNF_ID, vnf_id)
        if not cat_obj:
            return
        if not isinstance(cat_obj, str) and len(cat_obj) > 1:
            log.error("Obtained multiple VNFs using the ID '{}'".format(vnf_id))
            return
        log.debug("Obtained VNF schema:\n{}".format(cat_obj))
        return yaml.load(cat_obj)

    def get_vnf_by_name(self, vnf_name):
        """
        Obtains a list of VNFs matching the vnf_name
        :param vnf_name: name of network service
        :return: (str) list of VNFs
        """
        return self.__get_cat_object__(CatalogueClient.CAT_URI_VNF_NAME, vnf_name)

    def __get_cat_object__(self, cat_uri, obj_id):
        url = self.base_url + cat_uri + obj_id
        response = requests.get(url, auth=self._auth, headers=self._headers)
        if not response.status_code == requests.codes.ok:
            return
        return response.text
