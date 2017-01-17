from son.access.pull import Pull
from son.access.push import Push
from son.access.config.config import GK_ADDRESS, GK_PORT


def pull_tests():
    platform_url = 'http://' + str(GK_ADDRESS) + ':' + str(GK_PORT)
    pull_client = Pull(base_url="http://sp.int.sonata-nfv.eu:32001")

    # resource = pull_client.get_vnf("eu.sonata-nfv.firewall-vnf.0.2")
    # resource = pull_client.get_vnf("name=firewall-vnf&vendor=eu.sonata-nfv&version=0.2")
    # resource = pull_client.get_package("97b2e5e9-048a-44f5-b91e-69a90f525f2a")

    resource = pull_client.get_all_nss()
    print("NSS RESPONSE", resource)

    resource = pull_client.get_all_vnfs()
    print("VFNS RESPONSE", resource)

    resource = pull_client.get_all_packages()
    print("PACKAGES RESPONSE", resource)

    resource = pull_client.get_ns("a6707125-bf8d-4c6f-999d-2a5990311762")
    print("NS RESPONSE", resource)

    resource = pull_client.get_vnf("dce3cffd-4957-40fe-adcc-cdc41c97a805")
    print("VNF RESPONSE", resource)

    #resource = pull_client.get_package("e84cf007-3e68-45a2-8f05-d1718c767220")
    #print "Package RESPONSE", resource


def push_tests():
    platform_url = 'http://' + str(GK_ADDRESS) + ':' + str(GK_PORT)
    push_client = Push(base_url="http://sp.int.sonata-nfv.eu:32001")
    print(push_client.upload_package(None, "../samples/sonata-demo.son"))

if __name__ == '__main__':
    push_tests()
    pull_tests()