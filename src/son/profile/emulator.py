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

# define some constants for easy changing
# will likely be removed as default values dont make sense past testing
DEFAULT_KEY_LOC = "~/.ssh/id_rsa"
PATH_COMMAND = "cd ~/son-emu"
EXEC_COMMAND = "python src/emuvim/examples/profiling.py"
DEFAULT_SSH_USER_NAME = "root"

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
     Conduct multiple experiments which are described by a yaml file using the do_experiment method
     :config_loc: the location of the yaml config file
    """
    @staticmethod
    def do_experiment_series(config_loc):
        pass


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
     :address: address of the remote server
     :package_port: the port to which the service package is uploaded. Default: 5000
     :ssh_port: the port which is used for the ssh connection. Default: 22
     :username: the username which is used for the ssh connection
     :key_loc: location of the ssh RSA-key used for the ssh connection
    """
    @staticmethod
    def do_experiment(
            path_to_pkg="",
            runtime=10,
            address='127.0.0.1',
            package_port=5000,
            ssh_port=22,
            username=DEFAULT_SSH_USER_NAME,
            key_loc=DEFAULT_KEY_LOC):
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
        comm = threading.Thread(target=Emulator._exec_command, args=(ssh, "%s;%s"%(PATH_COMMAND,EXEC_COMMAND)))
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
        #stop the service
        LOG.info("Stopping service")
        service_instance_uuid = json.loads(r2.text).get("service_instance_uuid")
        r3 = requests.delete("http://%s:%s/instantiations"%(address,package_port), data={"service_uuid":service_uuid, "service_instance_uuid":service_instance_uuid})

        # stop the remote topology
        Emulator._exec_command(ssh, "pkill -f %r"%EXEC_COMMAND)

        #gather the logs etc. here
        sftp = ssh.open_sftp()
        #sftp.chdir(path)
        #sftp.get(remote_path, local_path)
        sftp.close()

        # close the ssh connection
        ssh.close()

    """
    Helper method to be called in a thread
    A single command is executed on a remote server via ssh
    """
    @staticmethod
    def _exec_command(ssh, command):
        comm_in, comm_out, comm_err = ssh.exec_command(command)
        comm_in.close()
        while not (comm_out.channel.exit_status_ready() and comm_err.channel.exit_status_ready()):
            for line in comm_out.read().splitlines():
                LOG.debug(line)
            for line in comm_err.read().splitlines():
                LOG.error(line)

if __name__=='__main__':
    Emulator.do_experiment(path_to_pkg='/home/levathos/son-emu/misc/sonata-demo-service.son')
