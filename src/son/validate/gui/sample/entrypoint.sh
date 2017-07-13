#!/bin/bash

# run son-validate service in background
export VAPI_CACHE_TYPE="simple" 
son-workspace --init
cp /usr/son-validate-gui/sample/sample-workspace.yml /root/.son-workspace/workspace.yml
mv /usr/son-validate-gui/sample/projects /root/
son-validate-api --mode local &

# serve web gui
http-server /usr/son-validate-gui/dist/
