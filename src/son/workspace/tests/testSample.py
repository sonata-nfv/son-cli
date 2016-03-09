import unittest


class MyTestCase(unittest.TestCase):
    def test_something(self):
        self.assertEqual(True, False)


class MyTestCase2(unittest.TestCase):
    def test_something2(self):
        self.assertEqual(True, False)


if __name__ == '__main__':
    unittest.main()
