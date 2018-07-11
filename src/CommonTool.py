#! /usr/bin/env python3
# coding: utf-8
# flow@蓝鲸淘
# Licensed under the MIT License.

import time


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
        s = '%.8f' % float(sciStr)
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
