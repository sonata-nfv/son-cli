#!/bin/bash

# run son-validate service in background
export VAPI_CACHE_TYPE="simple" 
son-workspace --init
son-validate-api --mode local &

# serve web gui
http-server /usr/son-validate-gui/dist/
