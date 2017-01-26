#son-access

This tool is responsible for authentication of users, submitting and requesting of resources
stored in the SONATA Service Platform Catalogues.

Dependencies:
* [pyaml](https://pypi.python.org/pypi/pyaml/) >= 15.8.2 (WTFPL)
* [validators](https://pypi.python.org/pypi/validators) >= 0.10.3 (BSD)
* [requests](https://pypi.python.org/pypi/requests) >= 2.10 (Apache 2.0)
* [PyJWT](https://pypi.python.org/pypi/PyJWT/1.4.0) >= 1.4.0 (MIT)
* [Flask](http://flask.pocoo.org/) >= 0.11.1 (BSD)

Configuration:
A configuration file 'config.py' in 'access/config/' folder contains the required settings:

```sh
GK_ADDRESS = 'URL address to the platform'
```
This setting must be a string pointing to the URL address of the resource owner platform, e.g: 'sp.int3.sonata-nfv.eu'.

```sh
GK_PORT = 'Port number address'
```
This setting must be a string pointing to the port number address of the resource owner platform, e.g: '32001'.

```sh
TOKEN_PATH = "/config/token.txt"
```
This setting is a string pointing to the folder where access token are temporary saved.

```sh
usage: access.py [-h]
                 [--auth] [-u USERNAME] [-p PASSWORD]
                 [--push PACKAGE_PATH] 
                 [--list RESOURCE_TYPE]
                 [--pull RESOURCE_TYPE] [--uuid UUID]
                                        [--id VENDOR NAME VERSION] 
                 [--debug]


Authenticates users to submit and request resources from SONATA Service Platform

optional arguments:
  -h, --help                show this help message and exit
  --auth                    authenticates a user, requires -u username -p password
  -u USERNAME               specifies username of a user
  -p PASSWORD               specifies password of a user
  --push PACKAGE_PATH       submits a son-package to the SP
  --list RESOURCE_TYPE      lists resources based on its type (services,
                            functions, packages, file)
  --pull RESOURCE_TYPE      requests a resource based on its type (services,
                            functions, packages, file), requires a query parameter
                            --uuid or --id
  --uuid UUID               Query value for SP identifiers (uuid-generated)
  --id VENDOR NAME VERSION  Query values for package identifiers (vendor name
                            version)
  --debug                   increases logging level to debug

```

Example on how to authenticate a user, submit a package file and retrieve resources:
```sh
    access --auth -u tester -p 1234
    access --push samples/sonata-demo.son
    access --list services
    access --pull packages --uuid 65b416a6-46c0-4596-a9e9-0a9b04ed34ea
    access --pull services --id sonata.eu firewall-vnf 1.0

```

