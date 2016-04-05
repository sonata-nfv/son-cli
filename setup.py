from setuptools import setup, find_packages
import codecs
import os.path as path

# buildout build system 
# http://www.buildout.org/en/latest/docs/tutorial.html

# setup() documentation: 
# http://python-packaging-user-guide.readthedocs.org/en/latest/distributing/#setup-py

cwd = path.dirname(__file__)
longdesc = codecs.open(path.join(cwd, 'README.md'), 'r', 'ascii').read()

name = 'son'
setup(
        name=name,
        license='To be determined',
        version='0.0.1',
        url='https://github.com/sonata-nfv/son-cli',
        author_email='sonata-dev@sonata-nfv.eu',
        long_description=longdesc,
        package_dir={'': 'src'},
        packages=find_packages('src'),  # dependency resolution
        namespace_packages=['son',],
        include_package_data=True,
        package_data= {
            'son': ['package/templates/*', 'workspace/samples/*']
        },
        install_requires=['setuptools', 'pyaml', 'jsonschema', 'validators', 'requests'],
        zip_safe=False,
        entry_points={
            'console_scripts': [
                'son-workspace=son.workspace.workspace:main',
                'son-package=son.package.package:main',
                'son-push=son.push.push:main'
            ],
        },
        test_suite='son',
        setup_requires=['pytest-runner'],
        tests_require=['pytest']
#test_suite='son.workspace.tests.TestSample.main'
    )
