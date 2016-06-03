import unittest
from son.package.package import Packager
from son.workspace.workspace import Workspace


class IntPDTester(unittest.TestCase):

    __pfd__ = {
        'name': 'sonata-project-sample',
        'vendor': 'com.sonata.project',
        'version': '0.0.1',
        'maintainer': 'Name, Company, Contact',
        'description': 'Project description',
        'catalogues': ['personal'],
        'publish_to': ['personal']
    }

    def __init__(self, *args, **kwargs):
        super(IntPDTester, self).__init__(*args, **kwargs)
        ws = Workspace("")
        self.pck = Packager(workspace=ws, prj_path='/', generate_pd=False)

    def test_correct_gds(self):
        """ Test the correct general description section """
        gsd = self.pck.package_gds(IntPDTester.__pfd__)
        self.assertNotEqual(gsd, False)

    def test_incomplete_gds(self):
        """ Test the returning message when the provided project has incomplete information."""
        pfd = IntPDTester.__pfd__
        pfd.pop('name')
        gsd = self.pck.package_gds(pfd)
        self.assertEqual(gsd, False)
