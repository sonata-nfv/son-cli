# son-validate local service
son-validate can be run as a local service in the developer system, aiming to provide automatic monitoring and validation of local SDK projects, packages, services and functions. Automatic monitoring and validation can be enabled in workspace configuration, specifying the type of validation and which objects to validate. This functionallity watches for changes in the specified objects automatically triggering the validation process as required.
The son-validate service implements an API to access the validation reports, but also to trigger arbitrary validation of objects.

## Run as a local service
To execute son-validate as a local service simply run:
`son-validate-api --mode local`

## Workspace configuration
Automatic monitoring and validation of objects may be set up in the workspace configuration, under the 'validate_watchers' key. Example for validating a project and a service:
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
        error_count: <number of errors>
        warning_count: <number of warnings>
        errors:  # only if error_count not zero
            "object_id":  # object to whom the error is associated
                <event_code>:  # event code as configured in eventcfg.yaml (see further for details)
                    [msg1, msg2]  # list of messages associated with event
        warnings:  # only if warning_count not zero
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