import unittest
from unittest.mock import patch
from unittest.mock import Mock
from unittest import mock
from son.package.package import Packager
from son.workspace.workspace import Workspace


class UnitCreatePackageTests(unittest.TestCase):

    @patch('son.package.package.os.path.join')
    @patch('son.package.package.zipfile')
    def test_generate_package(self, m_zipfile, m_join):
        """
        Ensures that a package file is created with correct name and location
        """
        # First, create a workspace to give to Packager
        workspace = Workspace("ws/root", ws_name="ws_test", log_level='debug')

        # Instantiate a Packager instance
        packager = Packager("prj/path", workspace, generate_pd=False, dst_path="dst/path")
        packager._package_descriptor = True

        # Prepare mocks
        context_manager_mock = Mock()
        m_zipfile.ZipFile.return_value = context_manager_mock
        enter_mock = Mock()
        exit_mock = Mock()
        setattr(context_manager_mock, '__enter__', enter_mock)
        setattr(context_manager_mock, '__exit__', exit_mock)

        # execute
        packager.generate_package("package_name")

        # make assertions
        self.assertEqual(m_join.call_args_list[-1], mock.call('dst/path', 'package_name.son'))

    def test_package_gds(self):
        """
        Test the validation of the project general description section
        """
        # First, create a workspace to give to Packager
        workspace = Workspace("ws/root", ws_name="ws_test", log_level='debug')

        # Instantiate a Packager instance
        packager = Packager("prj/path", workspace, generate_pd=False, dst_path="dst/path")
        packager._package_descriptor = True

        # Create fake project configuration
        prj_config = {
            'catalogues': '[personal]',
            'description': 'Project description',
            'vendor': 'eu.sonata.project',
            'maintainer': 'Name, Company, Contact',
            'publish_to': '[personal]',
            'version': '0.0.1'
            }

        # Remove keys, one by one...
        for key in prj_config:
            value = prj_config.pop(key)
            self.assertFalse(packager.package_gds(prj_config))
            prj_config[key] = value

        # Make prj_config complete...
        prj_config['name'] = 'sonata - project - sample'

        self.assertTrue(packager.package_gds(prj_config))



