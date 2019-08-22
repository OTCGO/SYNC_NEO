#! /usr/bin/env python3
# coding: utf-8
# flow@SEA
# Licensed under the MIT License.

import os
from dotenv import load_dotenv, find_dotenv
load_dotenv(find_dotenv(), override=True)


class Config:
    @staticmethod
    def get_mysql_host():
        return os.environ.get('MYSQLHOST')

    @staticmethod
    def get_mysql_port():
        return int(os.environ.get('MYSQLPORT'))

    @staticmethod
    def get_mysql_user():
        return os.environ.get('MYSQLUSER')

    @staticmethod
    def get_mysql_pass():
        return os.environ.get('MYSQLPASS')

    @staticmethod
    def get_mysql_db():
        return os.environ.get('MYSQLDB')

    @staticmethod
    def get_net():
        return os.environ.get('NET')

    @staticmethod
    def get_super_node():
        return os.environ.get('SUPERNODE')

    @staticmethod
    def get_something(sth):
        return os.environ.get(sth)
