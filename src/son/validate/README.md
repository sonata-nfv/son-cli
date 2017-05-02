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

## son-validate micro-service

### Configuration
The Dockerfile for the son-validate service lives at the root of son-cli project at `tools/validator.Dockerfile` since it has dependencies with some modules of this project. Configuration is done using the following environment vars inside the Dockerfile:
* `HOST`: the binding IP address for the service, default is 0.0.0.0
* `PORT`: the listening port for the service, default is 5001

### API
The service API accepts the following requests:
* `/validate/package` [POST]: validates a  package
    The package file and validation options must be provided in the body of the POST request as follows:
    * `package`: package file
    * `syntax`: True | False
    * `integrity`: True | False
    * `topology`: True | False
* `/validate/service` [POST]: validates a service
    The service descriptor file and validation options must be provided in the body of the POST request as follows:
    * `service`: service descriptor file (NSD)
    * `syntax`: True | False
    * `integrity`: True | False
    * `topology`: True | False
* `/validate/function` [POST]: validates a function
    The function descriptor file and validation options must be provided in the body of the POST request as follows:
    * `service`: function descriptor file (VNFD)
    * `syntax`: True | False
    * `integrity`: True | False
    * `topology`: True | False

The provided result of the validation is a json dictionary with the following keys:
    `error_count`: provides the number of validation errors
    `warning_count`: provides the number of validation warnings
    `errors` (if error_count not zero): provides a list of error events as configured in `eventcfg.yml`
    `warnings` (if warning_count not zero): provides a list of warning events as configured in `eventcfg.yml`


## Event configuration
son-validate enables the customization of validation issues to be reported by a user-defined level of importance. Each possible validation event can be configured to be reported as `error`, `warning` or `none` (to not report).
Event configuration is defined in the file `eventcfg.yml`. For now, it can only be configured statically but in the future we aim to support a dynamic configuration through the CLI and service API.
The validation events are defined as follows:
* SDK Project related
    * invalid service descriptor in project: `evt_project_service_invalid`
    * multiple service descriptors in project: `evt_project_service_multiple`
* Package related
    * invalid package file format: `evt_package_format_invalid`
    * invalid package file structure: `evt_package_struct_invalid`
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