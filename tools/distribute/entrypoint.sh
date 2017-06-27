#!/bin/bash

## first pass of py2deb as a temporary workaround for the error:
## "Exception: Expected requirement set to contain exactly one Python package whose name can be normalized to numpy but encountered 0 packages instead! (matching packages: [])"
py2deb -r deb-packages --name-prefix=python3 --no-name-prefix=sonata-cli --use-system-package=_numpy,python3-numpy --use-system-package=scipy,python3-scipy -- . || true

## actual build of debian packages
py2deb -r deb-packages --name-prefix=python3 --no-name-prefix=sonata-cli \
    --use-system-package=numpy,python3-numpy \
    --use-system-package=scipy,python3-scipy \
    --use-system-package=matplotlib,python3-matplotlib \
    --use-system-package=six,python3-six \
    -- .

## remove some original deb packages to avoid conflicts with official repos
rm deb-packages/python3-decorator_*.deb || true
rm deb-packages/python3-matplotlib_*.deb || true

#rm deb-packages/python3-six_*.deb
