from setuptools import setup, find_packages
import codecs
import os.path as path

# buildout build system 
# http://www.buildout.org/en/latest/docs/tutorial.html

# setup() documentation: 
# http://python-packaging-user-guide.readthedocs.org/en/latest/distributing/#setup-py

cwd = path.dirname(__file__)
longdesc = codecs.open(path.join(cwd, 'README.md'), 'r', 'utf-8').read()

name = 'son-monitor'
setup(
        name=name,
        license='To be determined',
        version='0.0.1',
        url='https://github.com/sonata-nfv/son-cli',
        author_email='sonata-dev@sonata-nfv.eu',
        long_description=longdesc,
        package_dir={'': 'src'},
        packages=find_packages('src'),  # dependency resolution
        namespace_packages=['son', ],
        #include_package_data=True,
        #package_data= {
        #    'son': []
        #},
        install_requires=['setuptools', 'requests', 'gevent', 'paramiko', 'zerorpc'],
        zip_safe=False,
        entry_points={
            'console_scripts': [
                'son-monitor=son.monitor.monitor:main'
            ],
        }
        #test_suite='son',
        #setup_requires=['pytest-runner'],
        #tests_require=['pytest']
#test_suite='son.workspace.tests.TestSample.main'
    )
