# son-validate

The son-validate tool can be used to validate the syntax, integrity and topology of SONATA SDK projects, services and functions. It receives the following arguments:

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
                        assume the directory: '/home/lconceicao/.son-
                        workspace'
  --project PROJECT_PATH
                        Validate the service of the specified SDK project. If
                        not specified will assume the current directory:
                        '/home/lconceicao/projects/sonata/son-cli'
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