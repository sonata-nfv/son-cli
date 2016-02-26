#! /bin/bash -e
set -x

# Go to the 'root' directory
cd "$(dirname "$0")"

# Remove the dist directory
rm -rf dist

# Launch the Python unit tests
./bin/test

# Create the wheel package
python3 setup.py bdist_wheel --plat-name=linux_x86_64
