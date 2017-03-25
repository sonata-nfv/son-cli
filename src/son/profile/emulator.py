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
import os
import stat

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
"""
class Emulator:

    """
     Initialize with a list of descriptors of workers to run experiments on
     :tpd_loc: target platforms descriptor. A YAML file describing the emulator nodes available.
    """
    def __init__(self, tpd):
        # if the whole config dictionary has been given, extract only the target platforms
        # a descriptor version should only be in the top level of the file
        if "descriptor_version" in tpd:
            tpd = tpd.get("target_platforms")
        # save the emulator nodes
        self.emulator_nodes = tpd
        # check for empty emulator node lists
        if not len(self.emulator_nodes):
            raise Exception("Need at least one emulator to be specified in the target platforms descriptor.")
        # all nodes are available at the start
        self.available_nodes = self.emulator_nodes.keys()
        LOG.info("%r nodes found."%len(self.emulator_nodes))
        LOG.debug("List of emulator nodes: %r"%self.emulator_nodes.keys())

    """
     Conduct multiple experiments using the do_experiment method
     All experiments are started in a separate thread
     The order in which the experiments are run is not fixed!
     :experiments: a dictionary mapping from run_id to package path
     :runtime: the time an experiment runs for
    """
    def do_experiment_series(self, experiments, runtime=10):
        # start the experiments in separate threads
        for i in experiments.keys():
            t = threading.Thread(target=self.do_experiment, kwargs={"run_id":i, "path_to_pkg":experiments[i], "runtime":runtime})
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
            path_to_pkg,
            run_id,
            runtime=10,
            node_name=None):
        # if the package path contains a tilde, expand it to full directory path
        path_to_pkg = os.path.expanduser(path_to_pkg)
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
        key_loc = os.path.expanduser(node["ssh_key_loc"])


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

        # gather the logs etc.
        sftp = ssh.open_sftp()
        # switch to directory containing relevant files
        sftp.chdir("/tmp/results/%s/"%service_uuid)
        # all files in the folder have to be copied, directories have to be handled differently
        files_to_copy = sftp.listdir()
        # as long as there are files to copy
        while files_to_copy:
            # get next "file"
            file_path = files_to_copy.pop()
            # if the "file" is a directory, put all files contained in the directory in the list of files to be copied
            if stat.S_ISDIR(sftp.stat(file_path).st_mode):
                more_files = sftp.listdir("file_path")
                for f in more_files:
                    # we need the full path
                    files_to_copy.append("file_path/%s"%f)
            else:
                # the "file" is an actual file
                # check whether the path already exists on the local system
                head, _ = os.path.split(file_path)
                if not os.path.exists(head):
                    # if not, create it
                    os.makedirs(head)
                # copy the file to the local system, preserving the folder hierarchy
                sftp.get(file_path, "result/%s/%s"(run_id,file_path))

        # close the sftp connection
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
    # open config file to extract target platforms
    with open("src/son/profile/config.yml", "r") as tpd:
        conf = yaml.load(tpd)
    tpd.close()
    # init emulator
    e = Emulator(tpd=conf)
    # define experiments, will be extracted from a file when used in code
    experiments = dict()
    for i in range(3):
        experiments[i] = '~/son-emu/misc/sonata-demo-service.son'
    # run the experiments
    e.do_experiment_series(experiments, runtime=10)
