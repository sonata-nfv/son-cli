# son-validate
The son-validate tool can be used to validate the syntax, integrity and topology of SONATA SDK packages, projects, services and functions.
son-validate can be used through the CLI or as a micro-service running inside a docker container.

## son-validate CLI
The CLI interface is designed for developer usage, allowing to validate SDK projects, package descriptors, service descriptors and function descriptors. It receives the following arguments:

```sh
usage: son-validate [-h] [-w WORKSPACE_PATH]
                    (--project PROJECT_PATH | --package PD | --service NSD | --function VNFD)
                    [--dpath DPATH] [--dext DEXT] [--syntax] [--integrity]
                    [--topology] [--debug]

Validate a SONATA Service. By default it performs a validation to the syntax, integrity and network topology.

optional arguments:
  -h, --help            show this help message and exit
  -w WORKSPACE_PATH, --workspace WORKSPACE_PATH
                        Specify the directory of the SDK workspace for
                        validating the SDK project. If not specified will
                        assume the directory: '$HOME/.son-workspace'
  --project PROJECT_PATH
                        Validate the service of the specified SDK project. If
                        not specified will assume the current directory.
  --package PD          Validate the specified package descriptor.
  --service NSD         Validate the specified service descriptor. The
                        directory of descriptors referenced in the service
                        descriptor should be specified using the argument '--
                        path'.
  --function VNFD       Validate the specified function descriptor. If a
                        directory is specified, it will search for descriptor
                        files with extension defined in '--dext'
  --dpath DPATH         Specify a directory to search for descriptors.
                        Particularly useful when using the '--service'
                        argument.
  --dext DEXT           Specify the extension of descriptor files.
                        Particularly useful when using the '--function'
                        argument
  --syntax, -s          Perform a syntax validation.
  --integrity, -i       Perform an integrity validation.
  --topology, -t        Perform a network topology validation.
  --debug               sets verbosity level to debug
```

The different levels of validation, namely syntax, integrity and topology can only be used in the following combinations:
* syntax `-s`
* syntax and integrity `-si`
* syntax, integrity and topology `-sit`

The son-validate tool can be used to validate one of the following components:
* **project** - to validate an SDK project, the `--workspace` parameter must be specified, otherwise the default location `$HOME/.son-workspace` is assumed.
* **service** - in service validation, if the chosen level of validation comprises more than syntax (integrity or topology), the `--dpath` argument must be specified in order to indicate the location of the VNF descriptor files, referenced in the service. Has a standalone validation of a service, son-validate is not aware of a directory structure, unlike the project validation. Moreover, the `--dext` parameter should also be specified to indicate the extension of descriptor files.
* **function** - this specifies the validation of an individual VNF. It is also possible to validate multiple functions in bulk contained inside a directory. To if the `--function` is a directory, it will search for descriptor files with the extension specified by parameter `--dext`.

Some usage examples are as follows:
* validate a project: `son-validate --project /home/sonata/projects/project_X --workspace /home/sonata/.son-workspace`
* validate a service: `son-validate --service ./nsd_file.yml --path ./vnfds/ --dext yml`
* validate a function: `son-validate --function ./vnfd_file.yml --dext yml`
* validate multiple functions: `son-validate --function ./vnfds/ --dext yml`





## son-validate Service
son-validate can be executed as a service, providing a RESTful interface to validate objects and retrieve validation reports. son-validate API service can be executed in two distinct modes: `stateless` or `local`. Stateless mode will run as a stateless service only and can be instantiated at any remote location. Local mode is designed to run in the developer OS, providing additional functionalities. It aims to provide automatic monitoring and validation of local SDK projects, packages, services and functions. Automatic monitoring and validation can be enabled in workspace configuration, specifying the type of validation and which objects to validate. This functionallity watches for changes in the specified objects automatically triggering the validation process as required.

### Configuration
The Dockerfile for the son-validate service lives at the root of son-cli project at `tools/validator.Dockerfile` since it has dependencies with some modules of this project. Configuration is done using the following environment vars inside the Dockerfile:
* `VAPI_HOST`: the binding IP address for the service, default is 0.0.0.0
* `VAPI_PORT`: the listening port for the service, default is 5001
* `VAPI_CACHE_TYPE`: type of caching to be used, default is 'redis'
* `VAPI_ARTIFACTS_DIR`: working directory, where temporary artifacts will be stored (auto removed on program exit). Default is `./artifacts`
* `VAPI_DEBUG`: set verbose level to debug, default is 'False'

### Run son-validate API service
son-validate-api has the following usage:
```sh
usage: son-validate-api [-h] [--mode {stateless,local}] [--host HOST]
                        [--port PORT] [-w WORKSPACE] [--debug]

SONATA Validator API. By default service runs on 127.0.0.1:5001

optional arguments:
  -h, --help            show this help message and exit
  --mode {stateless,local}
                        Specify the mode of operation. 'stateless' mode will
                        run as a stateless service only. 'local' mode will run
                        as a service and will also provide automatic
                        monitoring and validation of local SDK projects,
                        services, etc. that are configured in the developer
                        workspace
  --host HOST           Bind address for this service
  --port PORT           Bind port number
  -w WORKSPACE, --workspace WORKSPACE
                        Only valid in 'local' mode. Specify the directory of
                        the SDK workspace. Validation objects defined in the
                        workspace configuration will be monitored and
                        automatically validated. If not specified will assume
                        '/home/lconceicao/.son-workspace'
  --debug               Sets verbosity level to debug
```
Please notice that specified arguments will override environement variables, if defined.

#### Run in stateless mode
To execute son-validate as a local service simply run:
`son-validate-api --mode stateless`

#### Run in local mode
To execute son-validate as a local service simply run:
`son-validate-api --mode local`

### Workspace configuration
When running in local mode, automatic monitoring and validation of objects may be set up in the workspace configuration, under the 'validate_watchers' key. Example for validating a project and a service:
```yaml
validate_watchers:
    ~/sonata/sdk-projects/sample-project:
        type: project
        syntax: true
        integrity: true
        topology: true
    ~/sonata/sdk-projects/objects/nsds/sample-nsd.yml
        type: service
        syntax: true
```
### API
The service API accepts the following requests:
* `/validate/<object_type>` [POST]: validate an SDK project, a package, a service or a function specified by <object_type>
    * Mandatory request parameters:
        * `source`: local | url | embedded
        Specifies the origin of the object to validate. Local to retrieve object from local filesystem, url to download from remote location and embedded means that the object is included in the request.
        * `path` (local and url sources)
        Specifies the local path or the url of the object.
        * `file` (embedded source)
        File type parameter which includes the object file.
    * Optional request parameters:
        * `syntax`: True | False (default: True)
        Requires syntax validation.
        * `integrity`: True | False (default: False)
        Requires integrity validation.
        * `topology`: True | False (default: False)
        Requires topology validation.
    * Returns dictionary of validation results as described further in `/report/result/` including the `resource_id` associated with the validation
* `/report` [GET]: provides a dictionary of available validated objects
    * Returns dictionary in the format:
        ```yaml
        "resource_id":
            flags: "S" | "SI" | "SIT"
            path: "/some/local/path"
            type: "project" | "package" | "service" | "function"
        ```
* `/report/result/<resource_id>` [GET]: provides validation results of <resource_id>
    * Returns dictionary in the format:
        ```yaml
        resource_id: <validation resource_id>
        error_count: <number of errors>
        warning_count: <number of warnings>
        errors:  # only present if error_count not zero
            "object_id":  # object to whom the error is associated
                <event_code>:  # event code as configured in eventcfg.yaml (see further for details)
                    [msg1, msg2]  # list of messages associated with event
        warnings:  # only present if warning_count not zero
            "object_id":  # object to whom the warning is associated
                <event_code>:  # event code as configured in eventcfg.yaml (see further for details)
                    [msg1, msg2]  # list of messages associated with event
        ```
* `/report/topology/<resource_id>`[GET]: provides the validated network topology graph of <resource_id>
    * Returns a list of network topologies in the graphml format:
        ```yaml
        [<graphml_network_topology_1, ..., graphml_network_topology_N]
        ```
        The number of contained services (in a project or package) is equal to the list size N.

* `/resources` [GET]: retrieves the cached validation resources
    * Returns a dictionary of cached resources, in the format:
        ```yaml
         "resource_id":
            flags: "S" | "SI" | "SIT"
            path: "/some/local/path"
            type: "project" | "package" | "service" | "function"
        ```
* `/watches` [GET]: retrieves watched resources
    * Returns the dictionary of resources configured to be watched, in the format:
        ```yaml
        "resource_path":
            flags: "S" | "SI" | "SIT"
            type: "project" | "package" | "service" | "function"
        ```

### Event configuration
son-validate enables the customization of validation issues to be reported by a user-defined level of importance. Each possible validation event can be configured to be reported as `error`, `warning` or `none` (to not report).
Event configuration is defined in the file `eventcfg.yml`. For now, it can only be configured statically but in the future we aim to support a dynamic configuration through the CLI and service API.
The validation events are defined as follows:
* SDK Project related
    * invalid service descriptor in project: `evt_project_service_invalid`
    * multiple service descriptors in project: `evt_project_service_multiple`
* Package related
    * invalid package file format: `evt_package_format_invalid`
    * invalid package file structure: `evt_package_struct_invalid`
    * invalid package signature: `evt_package_signature_invalid`
    * invalid package descriptor (PD) syntax: `evt_pd_stx_invalid`
    * invalid references in PD: `evt_pd_itg_invalid_reference`
    * invalid file MD5 checksums: `evt_pd_itg_invalid_md5`
* Service related
    * invalid descriptor file: `evt_service_invalid_descriptor`
    * invalid service descriptor (NSD) syntax: `evt_nsd_stx_invalid`
    * referenced function unavailable: `evt_nsd_itg_function_unavailable`
    * invalid function: `evt_nsd_itg_function_invalid`
    * section 'connection_points' contains invalid references: `evt_nsd_itg_badsection_cpoints`
    * section 'virtual_links' contains invalid references: `evt_nsd_itg_badsection_vlinks`
    * use of undeclared connection point: `evt_nsd_itg_undeclared_cpoint`
    * unused connection point: `evt_nsd_itg_unused_cpoint`
    * failure on building topology graph: `evt_nsd_top_topgraph_failed`
    * topology graph is disconnected: `evt_nsd_top_topgraph_disconnected`
    * section 'forwarding_graphs' contains invalid references: `evt_nsd_top_badsection_fwgraph`
    * section 'forwarding_graphs' not defined: `evt_nsd_top_fwgraph_unavailable`
    * undefined connection point in forwarding graph: `evt_nsd_top_fwgraph_cpoint_undefined`
    * duplicate position index in forwarding graph: `evt_nsd_top_fwgraph_position_duplicate`
    * number of connection points in forwarding graph is odd: `evt_nsd_top_fwgraph_cpoints_odd`
    * forwarding path incompatible with defined topology: `evt_nsd_top_fwpath_invalid`
    * cycles found in forwarding path: `evt_nsd_top_fwpath_cycles`
    * direct path linking interfaces of the same VNF: `evt_nsd_top_fwpath_inside_vnf`
    * disrupted forwarding path: `evt_nsd_top_fwpath_disrupted`
* Function related:
    * invalid function descriptor file: `evt_function_invalid_descriptor`
    * invalid function descriptor (VNFD) syntax: `evt_vnfd_stx_invalid`
    * section 'connection_points' contains invalid references: `evt_vnfd_itg_badsection_cpoints`
    * section 'virtual_deployment_units' contains invalid references: `evt_vnfd_itg_badsection_vdus`
    * section 'connection_points' in VDU contains invalid references: `evt_vnfd_itg_vdu_badsection_cpoints`
    * section 'virtual_links' contains invalid references: `evt_vnfd_itg_badsection_vlinks`
    * use of undeclared connection point: `evt_vnfd_itg_undeclared_cpoint`
    * unused connection point: `evt_vnfd_itg_unused_cpoint`
    * undefined connection point: `evt_vnfd_itg_undefined_cpoint`
    * failure on building topology graph: `evt_vnfd_top_topgraph_failed`
* Generic:
    * duplicate connection point: `evt_duplicate_cpoint`
    * invalid SONATA descriptor: `evt_invalid_descriptor`
    