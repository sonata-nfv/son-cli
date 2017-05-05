
#son-package
Generate a SONATA SDK package

This tool delivers a ZIP file compiling all the required descriptors of specified the project and workspace.

The generated file structure follows the format defined in the package-descriptor of the son-schema repository (https://github.com/sonata-nfv/son-schema/tree/master/package-descriptor). Please check folder examples for a demo package.

```sh
usage: son-package [-h] [--workspace WORKSPACE] [--project PROJECT]
                   [-d DESTINATION] [-n NAME]

Generate new sonata package

optional arguments:
  -h, --help            show this help message and exit
  --workspace WORKSPACE
                        Specify workspace to generate the package. If not
                        specified will assume '$HOME/.son-workspace'

  --project PROJECT     create a new package based on the project at the
                        specified location. If not specified will assume the
                        current directory.

  -d DESTINATION, --destination DESTINATION
                        create the package on the specified location

  -n NAME, --name NAME  create the package with the specific name
```

son-package will create a package inside the DESTINATION directory. If DESTINATION is not specified, the package will be deployed at <project root/target>.

