"""
Copyright (c) 2015 SONATA-NFV and Paderborn University
ALL RIGHTS RESERVED.

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.

Neither the name of the SONATA-NFV [, ANY ADDITIONAL AFFILIATION]
nor the names of its contributors may be used to endorse or promote
products derived from this software without specific prior written
permission.

This work has been performed in the framework of the SONATA project,
funded by the European Commission under Grant number 671517 through
the Horizon 2020 and 5G-PPP programmes. The authors would like to
acknowledge the contributions of their colleagues of the SONATA
partner consortium (www.sonata-nfv.eu).
"""
"""

"""
import paramiko
import json
import logging
import mininet.clean
import requests
import time
import threading
import yaml

# define some constants for easy changing
# will likely be removed as default values dont make sense past testing
DEFAULT_KEY_LOC = "~/.ssh/id_rsa"
PATH_COMMAND = "cd ~/son-emu"
EXEC_COMMAND = "sudo python src/emuvim/examples/profiling.py"
DEFAULT_SSH_USER_NAME = "ssh_user"

# create a Logger
logging.basicConfig()
LOG = logging.getLogger("SON-Profile Emulator")
LOG.setLevel(logging.DEBUG)
logging.getLogger("werkzeug").setLevel(logging.WARNING)

"""
 A class which provides methods to do experiments with service packages
 All methods are static
"""
class Emulator:

    """
     Initialize with a list of descriptors of workers to run experiments on
     :tpd_loc: target platforms descriptor. A YAML file describing the emulator nodes available.
    """
    def __init__(self, tpd_loc):
        # extract the emulator nodes from the target platforms descriptor file
        self.emulator_nodes = list()
        with open(tpd_loc, "r") as tpd:
            self.emulator_nodes = yaml.load(tpd)["target_platforms"]
        tpd.close()
        # check for empty emulator node lists
        if not len(self.emulator_nodes):
            raise Exception("Need at least one emulator to be specified in the target platforms descriptor.")
        # all nodes are available at the start
        self.available_nodes = self.emulator_nodes.keys()
        LOG.info("%r nodes found."%len(self.emulator_nodes))
        LOG.debug("List of emulator nodes: %r"%self.emulator_nodes.keys())

    """
     Load another config file to use other target platforms
     Does not need to be called to use an emulator object.
     Will overwrite the existing emulator nodes list.
     Will wait for currently running experiments to prevent unintended behaviour.
     :tpd_loc: target platforms descriptor. A YAML file describing the emulator nodes available
    """
    def load_config_file(self, tpd_loc):
        # wait for currently running experiments
        # failing to do so will result in old emulator nodes being reused even after using a new list
        while not self.emulator_nodes.keys() == self.available_nodes:
            time.sleep(1)
        # empty the available nodes to prevent further experiments
        self.available_nodes = list()
        # extract the emulator nodes from the target platforms descriptor file
        emulator_nodes = list()
        with open(tpd_loc, "r") as tpd:
            emulator_nodes = yaml.load(tpd)["target_platforms"]
        tpd.close()
        # check for empty emulator node lists
        if not len(emulator_nodes):
            raise Exception("Need at least one emulator to be specified in the target platforms descriptor.")
        # after checking for empty lists, apply the new node list
        self.emulator_nodes = emulator_nodes
        # all nodes are available at the start
        self.available_nodes = self.emulator_nodes.keys()
        LOG.info("%r nodes found."%len(self.emulator_nodes))
        LOG.debug("List of emulator nodes: %r"%self.emulator_nodes.keys())

    """
     Conduct multiple experiments which are described by a yaml file using the do_experiment method
     :package_paths: a list of paths to packages that will be tested
     :runtimes: a list of runtimes for the packages, needs to be same length as package_paths
     :runtime: if the runtimes list is empty, use this time for all packages
    """
    def do_experiment_series(self, package_paths, runtimes=[], runtime=10):
        # if the runtimes are not specified for each package, choose the same runtime for all of them
        if not len(runtimes):
            for p in package_paths:
                runtimes.append(runtime)
        # check whether package paths and runtimes are the same size
        if not len(package_paths) == len(runtimes):
            raise Exception("Need a runtime for each package and a package for each runtime.")
        # start the experiments
        for i in range(len(package_paths)):
            t = threading.Thread(target=self.do_experiment, kwargs={"path_to_pkg":package_paths[i], "runtime":runtimes[i]})
            t.start()

    """
     Conduct a single experiment with given values
     One experiment consists of:
     1) starting the topology remotely on a server
     2) uploading the service package
     3) starting the service
     4) wait a specified amount of time
     5) stop the service
     6) gather log files
     :path_to_pkg: the path to the service package which is to be tested
     :runtime: the service will run for the specified amoutn of seconds
     :node_name: the name of the emulator node to be used for the experiment. If not specified, the first available node will be used.
    """
    def do_experiment(self,
            path_to_pkg="",
            runtime=10,
            node_name=None):
        # get neccessary information from (un-)specified worker
        if not node_name:
            # choose an emulator node
            # the first idle node would be best
            while not self.available_nodes:
                time.sleep(1)
            node_name = self.available_nodes.pop()
        node=self.emulator_nodes[node_name]
        LOG.info("Running package for %r seconds on emulator node %r"%(runtime, node_name))
        address = node["address"]
        # get the port to upload the packages to, if not specified, default to 5000
        package_port = node.get("package_port", 5000)
        # get the ssh port, if not specified, default to 22
        ssh_port = node.get("ssh_port", 22)
        username = node["ssh_user"]
        key_loc = node["ssh_key_loc"]


        # ensure a clean mininet instance
        #mininet.clean.cleanUp().cleanup()

        # connect to the client per ssh
        ssh = paramiko.client.SSHClient()

        # set policy for unknown hosts or import the keys
        # for now, we just add all new keys instead of adding certain ones
        ssh.set_missing_host_key_policy(paramiko.client.AutoAddPolicy())

        # import the RSA key
        pkey = paramiko.RSAKey.from_private_key_file(key_loc)

        # connect to the remote host via ssh
        ssh.connect(address, port=ssh_port, username=username, pkey=pkey)

        # start the profiling topology on the client
        # use a seperate thread to prevent blocking by the topology
        comm = threading.Thread(target=self._exec_command, args=(ssh, "%s;%s -p %s"%(PATH_COMMAND,EXEC_COMMAND,package_port)))
        comm.start()

        # wait a short while to let the topology start
        time.sleep(5)

        # upload the service package
        LOG.info("Path to package is %r" % path_to_pkg)
        f = open(path_to_pkg, "rb")
        LOG.info("Uploading package to http://%r." % address)
        r1 = requests.post("http://%s:%s/packages"%(address,package_port), files={"package":f})
        service_uuid = json.loads(r1.text).get("service_uuid")
        # start the service
        r2 = requests.post("http://%s:%s/instantiations"%(address,package_port), data={"service_uuid":service_uuid})
        # let the service run for a specified time
        LOG.info("Sleep for %r seconds." % runtime)
        time.sleep(runtime)
        # stop the service
        LOG.info("Stopping service")
        service_instance_uuid = json.loads(r2.text).get("service_instance_uuid")
        r3 = requests.delete("http://%s:%s/instantiations"%(address,package_port), data={"service_uuid":service_uuid, "service_instance_uuid":service_instance_uuid})

        # stop the remote topology
        self._exec_command(ssh, 'sudo pkill -f "%s -p %s"'%(EXEC_COMMAND, package_port))

        # gather the logs etc. here
        sftp = ssh.open_sftp()
        #sftp.chdir(path)
        #sftp.get(remote_path, local_path)
        sftp.close()

        # close the ssh connection
        ssh.close()

        # make the current worker available again
        self.available_nodes.append(node_name)

    """
    Helper method to be called in a thread
    A single command is executed on a remote server via ssh
    """
    def _exec_command(self, ssh, command):
        comm_in, comm_out, comm_err = ssh.exec_command(command)
        comm_in.close()
        while not (comm_out.channel.exit_status_ready() and comm_err.channel.exit_status_ready()):
            for line in comm_out.read().splitlines():
                LOG.debug(line)
            for line in comm_err.read().splitlines():
                LOG.error(line)

if __name__=='__main__':
    e = Emulator(wld_loc="src/son/profile/emulator_test.yml")
    paths=['/home/levathos/son-emu/misc/sonata-demo-service.son' for i in range(3)]
    runtimes = [10, 30, 10]
    e.do_experiment_series(package_paths=paths, runtimes=runtimes)
#    e.do_experiment(path_to_pkg='/home/levathos/son-emu/misc/sonata-demo-service.son')#, worker_name="worker01")
