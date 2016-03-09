import os
import logging
import yaml


class Project:

    __descriptor_name__ = 'project.yaml'

    def __init__(self, prj_root, workspace):
        self.prj_root = prj_root
        self.log = logging.getLogger(__name__)

    def create_prj(self):
        self._create_dirs()
        self._create_prj_stub()

    def _create_dirs(self):
        directories = {'sources', 'dependencies', 'deployment'}
        src_subdirs = {'fsm', 'ssm', 'pattern', 'vnf'}

        os.makedirs(self.prj_root, exist_ok=False)
        for d in directories:
            path = os.path.join(self.prj_root, d)
            os.makedirs(path, exist_ok=True)

        src_path = os.path.join(self.prj_root, 'sources')
        for d in src_subdirs:
            path = os.path.join(src_path, d, 'sample')
            os.makedirs(path, exist_ok=True)
            self._create_sample(d, path)

    def _create_prj_stub(self):
        d = {
            'name': 'sonata-project-sample',
            'group': 'com.sonata.project',
            'version': '0.0.1',
            'maintainer': 'Name, Company, Contact',
            'description': 'Project description',
            'catalogues': ['personal'],
            'publish_to': ['personal']
        }

        prj_path = os.path.join(self.prj_root, Project.__descriptor_name__)
        with open(prj_path, 'w') as prj_file:
            prj_file.write(yaml.dump(d))

    def _create_sample(self, prj_type, path):
        switcher = {
            'fsm': self._create_sample_fsm,
            'ssm': self._create_sample_ssm,
            'pattern': self._create_sample_pattern,
            'vnf': self._create_sample_vnf
        }
        func = switcher.get(prj_type)
        if func is None:
            self.log.error("Could not create sample for " + prj_type + ", unknown project type");
            return
        func(path)

    def _create_sample_fsm(self, path):
        d = {
            'name': 'sample fsm',
            'id': 'com.sonata.fsm.sample',
            'version': '0.1'
        }
        prj_path = os.path.join(path, 'fsm.yaml')
        with open(prj_path, 'w') as prj_file:
            prj_file.write(yaml.dump(d))

    def _create_sample_ssm(self, path):
        d = {
            'name': 'sample ssm',
            'id': 'com.sonata.ssm.sample',
            'version': '0.1'
        }
        prj_path = os.path.join(path, 'ssm.yaml')
        with open(prj_path, 'w') as prj_file:
            prj_file.write(yaml.dump(d))

    def _create_sample_pattern(self, path):
        d = {
            'name': 'sample pattern',
            'id': 'com.sonata.pattern.sample',
            'version': '0.1'
        }
        prj_path = os.path.join(path, 'patterm.yaml')
        with open(prj_path, 'w') as prj_file:
            prj_file.write(yaml.dump(d))

    def _create_sample_vnf(self, path):
        d = {
            'name': 'sample vnf',
            'id': 'com.sonata.vnf.sample',
            'version': '0.1'
        }
        prj_path = os.path.join(path, 'vnf.yaml')
        with open(prj_path, 'w') as prj_file:
            prj_file.write(yaml.dump(d))
