# son-access

This tool is responsible for authentication of users, submitting and requesting of resources
stored in the SONATA Service Platform Catalogues.

Dependencies:
* [pyaml](https://pypi.python.org/pypi/pyaml/) >= 15.8.2 (WTFPL)
* [validators](https://pypi.python.org/pypi/validators) >= 0.10.3 (BSD)
* [requests](https://pypi.python.org/pypi/requests) >= 2.10 (Apache 2.0)
* [PyJWT](https://pypi.python.org/pypi/PyJWT/1.4.0) >= 1.4.0 (MIT)
* [Flask](http://flask.pocoo.org/) >= 0.11.1 (BSD)

## Configuration

The required configuration for son-access is found in the son-workspace generated configuration file, under the section 'service_platforms'. It is possible to configure access parameters to multiple Service Platforms using different credentials. This configuration section keeps the following parameters:
```sh
service_platforms:
  sp1:
    url: http://sp.int3.sonata-nfv.eu:32001
    credentials: {password: '1234', token_file: token.txt, username: user01}
    signature: {cert: null, prv_key: prv_key.pem, pub_key: pub_key.pem}
```

```sh
url = 'URL address to the platform'
```
This setting must contain the protocol, address and port number of the platform, e.g.: 'http://sp.int3.sonata-nfv.eu:30021'

```sh
username = "user01" (optional)
password = "1234" (optional)
token_file = "token.txt"
```
This setting stores the user's credentials and the temporary file name of the access token.
User's credentials are optional allowing users to type them when signing in to the Platform, or let son-access to automatically read the them from the configuration file.
Token files are stored in the workspace folder 'platforms_dir'.

```sh
pub_key = "pub_key.pem" (optional)
prv_key = "prv_key.pem" (optional)
cert = "trust.crt" (optional)
```
This signature settings indicates the files names for the users public key, private key and certificate. These files are optional, as in case of signing needs, son-access will generate a private and public key for the user.
Generated public and private keys will be stored in the users workspace directory, and the public key will be sent to the Platform User Management module.

## Usage
```sh
usage: son-access [optional] command [<args>]
        The supported commands are:
           auth     Authenticate a user
           list     List available resources (service, functions, packages, ...)
           push     Submit a son-package or request a service instantiation
           pull     Request resources (services, functions, packages, ...)
           config   Configure access parameters


Authenticates users to submit and request resources from SONATA Service
Platform

positional arguments:
  command               Command to run

optional arguments:
  -h, --help            show this help message and exit
  -w WORKSPACE_PATH, --workspace WORKSPACE_PATH
                        Specify workspace to work on. If not specified will
                        assume '/root/.son-workspace'
  --platform PLATFORM_ID
                        Specify the ID of the Service Platform to use from
                        workspace configuration. If not specified will assume
                        the ID in 'default_service_platform'
  --debug               Set logging level to debug
```

The son-access tool supports five different subcommands to deal with authentication, listing of resources, uploading of resources, requesting of resources and configuration of access parameters.

### Authentication - `auth`
```sh
usage: son-access [..] auth [-h] -u USERNAME -p PASSWORD

Authenticate a user

optional arguments:
  -h, --help            show this help message and exit
  -u USERNAME, --username USERNAME
                        Specify username of the user
  -p PASSWORD, --password PASSWORD
                        Specify password of the user
  --logout              Ends access token lifespan
```

### List resources - `list`
```sh
usage: son-access [..] list [-h] resource_type

List available resources (services, functions, packages, ...)

positional arguments:
  resource_type  (services | functions | packages)

optional arguments:
  -h, --help     show this help message and exit
```

### Submit packages - `push`
```sh
usage: son-access [..] push [-h] (--upload PACKAGE_PATH [--sign] | --deploy SERVICE_ID)

Submit a son-package to the SP or deploy a service in the SP

positional arguments:
  --upload PACKAGE_PATH        Specify package path to submit
  --upload PACKAGE_PATH --sign Specify package path to sign and submit
  --deploy SERVICE_ID          Specify service identifier to instantiate

optional arguments:
  -h, --help  show this help message and exit
  --sign      Indicates if the package will be signed with user's private key
```

### Request resources - `pull`
```sh
usage: son-access [..] pull [-h] (--uuid UUID | --id VENDOR NAME VERSION)
                            resource_type

Request resources (services, functions, packages, ...)

positional arguments:
  resource_type         (services | functions | packages)

optional arguments:
  -h, --help            show this help message and exit
  --uuid UUID           Query value for SP identifiers (uuid-generated)
  --id VENDOR NAME VERSION
                        Query values for package identifiers (vendor name
                        version)
```

### Configure parameters - `config`
```sh
usage: son-access [..] config [-h] (--platform_id SP_ID | --list) [--new]
                              [--url URL] [-u USERNAME] [-p PASSWORD]
                              [--token TOKEN_FILE] [--default]

Configure access parameters

optional arguments:
  -h, --help            show this help message and exit
  --platform_id SP_ID   Specify the Service Platform ID to configure
  --list                List all Service Platform configuration entries
  --new                 Create a new access entry to a Service Platform
  --url URL             Configure URL of Service Platform
  -u USERNAME, --username USERNAME
                        Configure username
  -p PASSWORD, --password PASSWORD
                        Configure password
  --token TOKEN_FILE    Configure token filename (deprecated)
  --default             Set Service Platform as default
```

Example on how to configure a new platform, authenticate a user, submit a package file and retrieve resources:
```sh
    son-access config --platform_id sp1 --new --url http://127.0.0.1:5001 --default
    son-access auth -u tester -p 1234
    son-access list services
    son-access push --upload samples/sonata-demo.son
    son-access push --upload samples/sonata-demo.son --sign
    son-access --platform sp1 push --upload samples/sonata-demo.son
    son-access pull packages --uuid 65b416a6-46c0-4596-a9e9-0a9b04ed34ea
    son-access pull services --id sonata.eu firewall-vnf 1.0
    son-access --platform sp1 push --deploy 65b416a6-46c0-4596-a9e9-0a9b04ed34ea
```


