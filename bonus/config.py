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

    def get_bonus_conf():
        return {}