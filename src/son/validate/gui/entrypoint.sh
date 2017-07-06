#!/bin/bash

export VAPI_CACHE_TYPE="simple" 
son-workspace --init
son-validate-api --mode local &
http-server /usr/son-viewer/
