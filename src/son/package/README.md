
#son-package
Generate a SONATA SDK package

This tool delivers a ZIP file compiling all the required descriptors of specified the project and workspace.

The generated file struture follows the format defined in the package-descritor of the son-schema repository (https://github.com/sonata-nfv/son-schema/tree/master/package-descriptor). Please check folder examples for a demo package.

```sh
Usage: son-package [-h] --workspace WORKSPACE [--project PROJECT]
                   [-d DESTINATION] [-n NAME]


optional arguments:
  -h, --help            show this help message and exit
  --workspace WORKSPACE
                        Specify workspace to generate the package
  --project PROJECT     create a new package based on the project at the
                        specified location
  -d DESTINATION, --destination DESTINATION
                        create the package on the specified location
  -n NAME, --name NAME  create the package with the specific name
```

son-package will create a package inside the DESTINATION directory. If DESTINATION is not specified, the package will be deployed at <project root/target>.

