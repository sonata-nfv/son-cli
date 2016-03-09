import unittest

import yaml

from son.package.package import Packager, load_schema


class PDTester(unittest.TestCase):

    __pfd__ = {
        'name': 'sonata-project-sample',
        'group': 'com.sonata.project',
        'version': '0.0.1',
        'maintainer': 'Name, Company, Contact',
        'description': 'Project description',
        'catalogues': ['personal'],
        'publish_to': ['personal']
    }

    def __init__(self, *args, **kwargs):
        super(PDTester, self).__init__(*args, **kwargs)
        self.pck = Packager()

    def test_correct_gds(self):
        """ Test the correct general description section """
        gsd = self.pck.package_gds(PDTester.__pfd__)
        self.assertNotEqual(gsd, False)

    def test_incomplete_gds(self):
        """ Test the returning message when the provided project has incomplete information."""
        pfd = PDTester.__pfd__
        pfd.pop('name')
        gsd = self.pck.package_gds(pfd)
        self.assertEqual(gsd, False)


class LoadSchemaTestes(unittest.TestCase):

    def test_load_invalid_template(self):
        """Test if the load schema is loading only available templates"""
        self.assertRaises(FileNotFoundError, load_schema, "test")

    def test_load_valid_schema(self):
        """ Test if the load schema is correctly loading the templates """
        schema = load_schema(Packager.schemas["PD"])
        self.assertIsInstance(schema, dict)

if __name__ == '__main__':
    unittest.main()
