#! /usr/bin/env python3
# coding: utf-8
# flow@SEA
# Licensed under the MIT License.

import os
from dotenv import load_dotenv, find_dotenv
load_dotenv(find_dotenv(), override=True)

class Config:

    @staticmethod
    def get_mysql_args():
        return {
            'host':    os.environ.get('MYSQLHOST'),
            'port':     int(os.environ.get('MYSQLPORT')),
            'user':     os.environ.get('MYSQLUSER'),
            'password': os.environ.get('MYSQLPASS'),
            'db':       os.environ.get('MYSQLDB'),
            'autocommit':True,
            'maxsize':256
        }

    @staticmethod
    def get_bonus_conf():
        return {
            "locked_bonus":{
                "1000-30": 1.64,
                "1000-90": 2.05,
                "1000-180": 2.73,
                "1000-360": 3.97,
                "3000-30": 5.75,
                "3000-90": 7.39,
                "3000-180": 10.27,
                "3000-360": 14.37,
                "5000-30": 11.23,
                "5000-90": 15.06,
                "5000-180": 20.54,
                "5000-360": 28.76,
                "10000-30": 26.29,
                "10000-90": 35.61,
                "10000-180": 49.31,
                "10000-360": 68.49,
            }
        }
