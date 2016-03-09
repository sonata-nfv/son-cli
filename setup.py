from setuptools import setup, find_packages
# buildout build system 
# http://www.buildout.org/en/latest/docs/tutorial.html

# setup() documentation: 
# http://python-packaging-user-guide.readthedocs.org/en/latest/distributing/#setup-py

name = 'son'
setup(
        name=name,
        license='To be determined',
        version='0.0.1',
        url='http://github.com/sonata-nfv',
        author_email='sonata-dev@sonata-nfv.eu',
        package_dir={'': 'src'},
        packages=find_packages('src'),  # dependency resolution
        namespace_packages=['son',],
        include_package_data=True,
        install_requires=['setuptools', 'pyaml', 'jsonschema'],
        zip_safe=False,
        entry_points={
            'console_scripts': [
                'son-workspace=son.workspace.workspace:main',
                'son-package=son.package.package:main',
            ],
        },
        test_suite='son'
#test_suite='son.workspace.tests.TestSample.main'
    )
