#! /usr/bin/env python3
# coding: utf-8
# flow@SEA
# Licensed under the MIT License.

import time
import hashlib
import datetime
from binascii import unhexlify
from base58 import b58encode, b58decode


class CommonTool:

    @staticmethod
    def now():
        return time.time()

    @staticmethod
    def sci_to_str(sciStr):
        '''科学计数法转换成字符串'''
        assert type('str')==type(sciStr),'invalid format'
        if 'E' not in sciStr:
            return sciStr
        s = '%.10f' % float(sciStr)
        while '0' == s[-1] and '.' in s:
            s = s[:-1]
        if '.' == s[-1]:
            s = s[:-1]
        return s

    @staticmethod
    def big_or_little(arr):
        '''大小端互转'''
        arr = bytearray(str(arr),'ascii')
        length = len(arr)
        for idx in range(length//2):
            if idx%2 == 0:
                arr[idx], arr[length-2-idx] = arr[length-2-idx], arr[idx]
            else:
                arr[idx], arr[length - idx] = arr[length - idx], arr[idx]
        return arr.decode('ascii')

    @staticmethod
    def timestamp_to_utc(timestamp):
        return datetime.datetime.utcfromtimestamp(timestamp)

    @staticmethod
    def hash256(b):
        return hashlib.sha256(hashlib.sha256(b).digest()).digest()

    @classmethod
    def validate_address(cls, address):
        if len(address) not in [33,34]: return False
        if 'A' != address[0]: return False
        tmp = b58decode(address)
        x,check = tmp[:-4],tmp[-4:]
        return cls.hash256(x)[:4] == check

    @classmethod
    def scripthash_to_address(cls, sh):
        tmp = unhexlify('17' + sh)
        tmp = b58encode(tmp + cls.hash256(tmp)[:4])
        if isinstance(tmp, bytes):
            return tmp.decode('utf8')
        return tmp

    @classmethod
    def hex_to_biginteger(cls, fixed8_str):
        if not fixed8_str: return 0
        hex_str = cls.big_or_little(fixed8_str)
        return int('0x' + hex_str, 16)
