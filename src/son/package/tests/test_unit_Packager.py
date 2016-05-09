import unittest
from unittest.mock import patch
from unittest.mock import Mock
from son.package.package import Packager
from son.workspace.workspace import Workspace


class UnitCreatePackageTests(unittest.TestCase):

    def test_generate_package(self):
        """
        Ensures that a package file is created with correct name and location
        """
        # First, create a workspace to give to Packager
        workspace = Workspace("ws/root", ws_name="ws_test", log_level='debug')

        # Instantiate a Packager instance
        packager = Packager("prj/path", workspace, generate_pd=False)



    @patch('son.package.package.yaml')
    @patch('builtins.open')
    def temp_test(self, m_open, m_yaml):
        # Mock required functions
        context_manager_mock = Mock()
        m_open.return_value = context_manager_mock
        file_mock = Mock()
        file_mock.read.return_value = None
        enter_mock = Mock()
        enter_mock.return_value = file_mock
        exit_mock = Mock()
        setattr(context_manager_mock, '__enter__', enter_mock)
        setattr(context_manager_mock, '__exit__', exit_mock)

        # Create fake project configuration
        prj_config = {
            'catalogues': '[personal]',
            'description': 'Project description',
            'group': 'eu.sonata.project',
            'maintainer': 'Name, Company, Contact',
            'name': 'sonata - project - sample',
            'publish_to': '[personal]',
            'version': '0.0.1'
            }
        # Assign prj_config to the loaded config
        m_yaml.load.return_value = prj_config


