"""
Early implementation of the son-push tool

This tool connects to a REST api of the SONATA Service Platform Gatekeeper. As 
these API's are still under construction, functionality as well as implementation
of this module probably change continuously. 

This version currently interoperates with the dummy gatekeeper provided 
by the son-emu tool.
"""
import validators
import requests
import logging
from json import loads

log = logging.getLogger(__name__)

def upload_package(platform_url, package_file_name):
    """
    Upload package to platform
    
    :param platform_url: url of the SONATA service platform/gatekeeper or 
                         emulator to upload package to
    :param package_file_name: filename including full path of the package to be 
                              uploaded
    
    :returns: text response message of the server or error message
    
    """
    import os

    if not os.path.isfile(package_file_name):
        return(package_file_name, "is not a file.")

    # TODO: fix potential simple typo issues like double slashes in url
    url = platform_url+"/api/packages" 

    if not validators.url(url):
        return(url, "is not a valid url.")

    try:
        with open(package_file_name, 'rb') as pkg_file:
            r = requests.post(url, files={'file': pkg_file})
            return(r.text)
    except Exception as e:
        return("Service package upload failed. "+e)

def instantiate_package(platform_url, service_uuid=""):
    """
    Instantiate servide on SONATA service platform or 
    
    :param platform_url: url of the SONATA service platform/gatekeeper or 
                         emulator to upload package to
    :param service_uuid: uuid of the service package (requires it to be available
                         on the platform)
    
    :returns: text response message of the server
    """
    # TODO: to be removed (default choice) after testing 
    try:
        if len(service_uuid)==0:
            service_uuid = package_list(platform_url)[0]

        if not service_uuid in package_list(platform_url):
            return("Given service uuid does not exist on the platform.")

        url = platform_url+"/api/instantiations" 

        r = requests.post(url, json = {"service_uuid":service_uuid})
        return(r.text)
    except Exception as e:
        return("Service could not be instantiated. "+e)

def _get_from_url(url):
    """
    Generic/internal function to fetch content of a given URL 
    
    :param url: url of the website to be queried
    
    :returns: text response of the server
    """
    if not validators.url(url):
        raise Exception(url+" is not a valid url.")

    try:
        r = requests.get(url)
        return(r.text)
    except:
        raise Exception("Content cannot be downloaded from "+url)


get_packages = lambda url:_get_from_url(url+"/api/packages")
get_instances = lambda url:_get_from_url(url+"/api/instantiations")
package_list = lambda url:loads(get_packages(url))["service_uuid_list"]
instance_list = lambda url:loads(get_instances(url))["service_instantiations_list"]

def main():
    from argparse import ArgumentParser, RawDescriptionHelpFormatter

    description = """
    Push packages to the SONATA service platform/emulator or list packages/instances 
    available on the SONATA platform/emulator.
    """
    examples = """Example usage:

    son-push http://127.0.0.1:8000 -U sonata-demo.son
    son-push http://127.0.0.1:8000 --list-packages
    son-push http://127.0.0.1:8000 --deploy-package <uuid>
    son-push http://127.0.0.1:8000 -I
    """
    parser = ArgumentParser(description=description, 
                            formatter_class=RawDescriptionHelpFormatter,
                            epilog=examples)
    parser.add_argument("platform_url", 
                        help="url of the gatekeeper/platform/emulator")
    parser.add_argument("-P", "--list_packages", 
                        help="List packages uploaded to the platform", 
                        action="store_true")
    parser.add_argument("-I", "--list_instances",
                        help="List deployed packages on the platform",
                        action="store_true")
    parser.add_argument("-U", "--upload_package",
                        help="Filename incl. path of package to be uploaded")
    parser.add_argument("-D", "--deploy_package_uuid",
                        help="UUID of package to be deployed (must be available at platform)")
    args = parser.parse_args()

    if not args.platform_url:
        print("Platform url is required.")

    if args.list_packages:
        print(get_packages(args.platform_url))

    if args.list_instances:
        print(get_instances(args.platform_url))

    if args.upload_package:
        print(upload_package(args.platform_url, args.upload_package))

    if args.deploy_package_uuid:
        print(instantiate_package(args.platform_url, args.deploy_package_uuid))
