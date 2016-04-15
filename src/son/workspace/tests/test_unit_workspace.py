import unittest
from unittest import mock
from son.workspace.workspace import Workspace
from unittest.mock import patch


class CreateWorkspaceTests(unittest.TestCase):

    @patch('son.workspace.workspace.log')
    @patch('son.workspace.workspace.yaml')
    @patch('builtins.open')
    @patch('son.workspace.workspace.os.path')
    def test__create_from_descriptor__(self, m_path, m_open, m_yaml, m_log):
        """
        Perform several tests to the static function "__create_from_descriptor__"
        to ensure that workspaces are correctly created from a configuration descriptor"
        :param m_path:
        :param m_open:
        :param m_yaml:
        :return:
        """
        # Make sure the workspace root dir and config file do not exist by patching os.path
        m_path.join.return_value = None
        m_path.isdir.return_value = False
        m_path.isfile.return_value = False

        # Assure that None is returned using non-existent root dir and config file
        self.assertEqual(Workspace.__create_from_descriptor__("/some/root/dir"), None)

        # Assure that an error message was logged
        self.assertTrue(m_log.error.called)

        # Make the root dir and config file exist
        m_path.isdir.return_value = True
        m_path.isfile.return_value = True

        # Create an invalid config descriptor for workspace
        conf_d = {
            'version': '0.01',
            'catalogue_servers': "['http://10.10.1.101:4011','http://10.10.1.102:4011']",
            'descriptor_extension': 'yml',
            'schemas_local_master': '~/.son-schema',
            'schemas_remote_master': 'https://raw.githubusercontent.com/sonata-nfv/son-schema/master/',
            'platforms_dir': 'platforms',
            'catalogues_dir': 'catalogues',
            'configuration_dir': 'configuration'
        }

        # Feed this descriptor as a config file by patching os.open and yaml.load methods
        m_open.return_value = None
        m_yaml.load.return_value = conf_d

        # Ensure it raises error when loading incomplete config descriptor
        self.assertRaises(KeyError, Workspace.__create_from_descriptor__, None)

        # Complete config descriptor
        conf_d['name'] = 'test workspace config'
        conf_d['log_level'] = 'info'

        # Ensure that a valid Workspace object is returned
        self.assertIsInstance(Workspace.__create_from_descriptor__(None), Workspace)
