# son-profile

This component supports network service developers to automatically profile their network services and network functions.

* **Active mode**:
Automatically create Service Packages with varying resource allocations and test runs with a defined set of metrics to monitor.
The created set of service packages can be automatically deployed on the SONATA Platform. The service performance can be monitored ad analyzed while the service packages are deployed.

* **Passive mode**:
Dynamically update a service which is deployed in the emulator. Resource allocation can be dynamically adjusted. Functional tests can be generated and the set of monitored metrics can be specified. During the tests, the monitored metrics will be statistically analyzed and a summary of the measured results will be generated, giving an indication of the VNF's performance and used resources.
Further info on this mode can be found on the [Wiki](https://github.com/sonata-nfv/son-cli/wiki/son-profile:-passive-mode).

## Examples

* Simple example run: `son-profile --mode active -v -p src/son/profile/tests/misc/example_ped1.yml`

* Passive mode run: `son-profile --mode passive -p ped_file.yml` 
  
  The exact structure of the ped file and other options for the passive mode are documented on the [Wiki](https://github.com/sonata-nfv/son-cli/wiki/son-profile:-passive-mode).
