import unittest
from decimal import Decimal as D

from tools import *

class TestTools(unittest.TestCase):
    def test_sci_to_str(self):
        self.assertEqual('1', sci_to_str('1'))
        self.assertEqual("100",sci_to_str('1e2'))
        self.assertEqual('0.1', sci_to_str('1e-1'))
        self.assertEqual('0.00001', sci_to_str('1e-5'))
        self.assertEqual("200", sci_to_str('0.2e3'))
        self.assertEqual('10000', sci_to_str('10000'))

        '''test error'''
        self.assertRaises(AssertionError, sci_to_str, 1e2)

    def test_check_decimal(self):
        self.assertTrue(check_decimal('1', 0))
        self.assertTrue(check_decimal('2', 1))
        self.assertTrue(check_decimal('2.1', 1))
        self.assertFalse(check_decimal('2.22', 1))
        self.assertTrue(check_decimal('2.22', 2))

    def test_big_or_little(self):
        self.assertEqual('3412', big_or_little('1234'))
        self.assertEqual("cdab", big_or_little('abcd'))

    def test_validate_address(self):
        self.assertTrue(Tool.validate_address('AJnNUn6HynVcco1p8LER72s4zXtNFYDnys'))
        self.assertFalse(Tool.validate_address('AJnNUn6HynVcco1p8LER72s4zXtNFYDnyt'))
        self.assertFalse(Tool.validate_address('AJnNUn6HynVcco1p8LER72s4zXtNFY'))
        self.assertFalse(Tool.validate_address('BJnNUn6HynVcco1p8LER72s4zXtNFYDnyt'))

    def test_decimal_to_hex(self):
        pass

    def test_get_random_byte_str(self):
        self.assertEqual(2, len(Tool.get_random_byte_str(1)))
        self.assertEqual(0, len(Tool.get_random_byte_str(0)))
        self.assertEqual(4, len(Tool.get_random_byte_str(2)))
        self.assertEqual(0, len(Tool.get_random_byte_str(-1)))

    def test_hex_to_num_str(self):
        def check_num(num):
            d = D(str(num))
            x = Tool.decimal_to_hex(d)
            s = Tool.hex_to_num_str(x)
            return d == D(s)

        self.assertTrue(check_num(1))
        self.assertTrue(check_num(0))
        self.assertTrue(check_num(0.1))
        self.assertTrue(check_num(2.333333))
        self.assertFalse(check_num(1.222222222))
        self.assertTrue(check_num(100000000))
        self.assertTrue(check_num(1000000000000000000))

    def test_num_to_hex_str(self):
        self.assertEqual('10', Tool.num_to_hex_str(16))
        self.assertEqual('1000', Tool.num_to_hex_str(16, 2))
        self.assertEqual('10', Tool.num_to_hex_str(16, -1))




