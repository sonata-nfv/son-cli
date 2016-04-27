import unittest
import pkg_resources
import os
from urllib.error import HTTPError
from son.schema.validator import load_local_schema, load_remote_schema


class IntLoadSchemaTests(unittest.TestCase):

    def test_load_invalid_local_template(self):
        """Test if the load schema is loading only available templates"""
        self.assertRaises(FileNotFoundError, load_local_schema, "test")

    def test_load_valid_local_schema(self):
        """ Test if the load schema is correctly loading the templates """
        # Access to local stored schemas for this test
        schema_f = pkg_resources.resource_filename(__name__, os.path.join("son-schema", 'pd-schema.yml'))
        schema = load_local_schema(schema_f)
        self.assertIsInstance(schema, dict)

        schema_f = pkg_resources.resource_filename(__name__, os.path.join("son-schema", 'nsd-schema.yml'))
        schema = load_local_schema(schema_f)
        self.assertIsInstance(schema, dict)

        schema_f = pkg_resources.resource_filename(__name__, os.path.join("son-schema", 'vnfd-schema.yml'))
        schema = load_local_schema(schema_f)
        self.assertIsInstance(schema, dict)

    def test_load_invalid_remote_template_unavailable(self):
        """ Test if it raises a HTTP error with a valid but unavailable schema URL """
        self.assertRaises(HTTPError, load_remote_schema, "http://somerandomurl.com/artifact.yml")

    def test_load_invalid_remote_template_invalid(self):
        """ Test if it raises an error with an invalid schema URL """
        self.assertRaises(ValueError, load_remote_schema, "some.incorrect/..url")

    def test_load_valid_remote_schema(self):
        """ Test if the load_remote_schema is retrieving and loading the templates correctly """
        schema = load_remote_schema(
            "https://raw.githubusercontent.com/sonata-nfv/son-schema/master/package-descriptor/pd-schema.yml")
        self.assertIsInstance(schema, dict)
