#! /bin/bash -e
set -x

# Go to the 'root' directory
BASE_DIR=$(readlink -f "$(dirname $(readlink -f $0))/..")
cd ${BASE_DIR}

# Cleaning 'dist' directory
rm -rf dist/*

# Launch the Python unit tests
./bin/py.test -s -v --junit-xml junit/testreport.xml

# Create the wheel package
python3 setup.py bdist_wheel --plat-name=linux_x86_64
# Create the wheel package for son-monitor (python2)
python setup_son-monitor.py bdist_wheel --plat-name=linux_x86_64

# Fixing the 'dist' directory's permissions
chmod -R a+rw dist
