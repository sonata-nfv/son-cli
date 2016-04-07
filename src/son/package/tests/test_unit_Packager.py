import unittest
from unittest import mock
from son.package.package import Packager, load_local_schema, load_remote_schema
from unittest.mock import patch


class UnitLoadSchemaTests(unittest.TestCase):

    @patch("son.package.package.yaml")
    @patch("builtins.open")
    @patch("son.package.package.os.path")
    def test_load_local_schema(self, m_os_path, m_open, m_yaml):
        # Ensure that a FileNotFoundError is raised when the file does not exist
        m_os_path.isfile.return_value = False
        self.assertRaises(FileNotFoundError, load_local_schema, "/some/file/path")

        # Ensure a correct schema format and a correct opening of the schema file
        m_os_path.isfile.return_value = True
        m_open.return_value = None
        m_yaml.load.return_value = "not a dict"
        self.assertRaises(AssertionError, load_local_schema, "/some/file/path")
        self.assertEqual(m_open.call_args, mock.call('/some/file/path', 'r'))

        # Ensure that a dictionary is allowed to be returned
        sample_dict = {'dict_key': 'this is a dict'}
        m_os_path.isfile.return_value = True
        m_open.return_value = None
        m_yaml.load.return_value = sample_dict
        return_dict = load_local_schema("/some/file/path")
        self.assertEqual(sample_dict, return_dict)

    @patch("son.package.package.yaml")
    @patch("son.package.package.urllib.request.urlopen.headers.get_content_charset")
    @patch("son.package.package.urllib.request.urlopen.read.decode")
    @patch("son.package.package.urllib.request.urlopen")
    def test_load_remote_schema(self, m_urlopen, m_decode, m_cs, m_yaml):

        sample_dict = {"key": "content"}
        m_decode.return_value = ""
        m_cs.return_value = ""
        m_yaml.load.return_value = sample_dict

        # Ensure that urlopen is accessing the same address of the argument
        load_remote_schema("url")
        self.assertEqual(m_urlopen.call_args, mock.call("url"))

        # Ensure it raises error on loading an invalid schema
        m_yaml.load.return_value = "not a dict"
        self.assertRaises(AssertionError, load_remote_schema, "url")

        # Ensure that a dictionary is allowed to be returned
        m_yaml.load.return_value = sample_dict
        return_dict = load_remote_schema("url")
        self.assertEqual(sample_dict, return_dict)
