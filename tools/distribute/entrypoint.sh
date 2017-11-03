#!/bin/bash

## first pass of py2deb as a temporary workaround for the error:
## "Exception: Expected requirement set to contain exactly one Python package whose name can be normalized to numpy but encountered 0 packages instead! (matching packages: [])"
py2deb -r deb-packages --name-prefix=python3 --no-name-prefix=sonata-cli --use-system-package=_numpy,python3-numpy --use-system-package=scipy,python3-scipy -- . || true

## actual build of debian packages
py2deb -r deb-packages --name-prefix=python3 --no-name-prefix=sonata-cli \
    --use-system-package=numpy,python3-numpy \
    --use-system-package=scipy,python3-scipy \
    -- .

## remove some original deb packages to avoid conflicts with official repos
rm deb-packages/python3-setuptools_*.deb || true
rm deb-packages/python3-requests_*.deb || true
rm deb-packages/python3-chardet_*.deb || true
rm deb-packages/python3-urllib3_*.deb || true
#rm deb-packages/python3-cffi_*.deb || true
rm deb-packages/python3-pyasn1_*.deb || true
rm deb-packages/python3-dateutil_*.deb || true
#rm deb-packages/python3-idna_*.deb || true
rm deb-packages/python3-jinja2_*.deb || true
rm deb-packages/python3-jsonschema_*.deb || true
rm deb-packages/python3-markupsafe_*.deb || true
rm deb-packages/python3-pycparser_*.deb || true
rm deb-packages/python3-decorator_*.deb || true
rm deb-packages/python3-matplotlib_*.deb || true
rm deb-packages/python3-six_*.deb || true
ls deb-packages/
