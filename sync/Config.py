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
    def get_neo_uri():
        protocol = os.environ.get('NODEPROTOCOL')
        neo_node = os.environ.get('NEONODE')
        neo_port = os.environ.get('NEOPORT')
        return '%s://%s:%s' % (protocol,neo_node, neo_port)

    @staticmethod
    def get_ont_uri():
        ont_node = os.environ.get('ONTNODE')
        ont_port = os.environ.get('ONTPORT')
        return 'http://%s:%s' % (ont_node, ont_port)

    @staticmethod
    def get_tasks():
        return os.environ.get('TASKS')

    @staticmethod
    def get_net():
        return os.environ.get('NET')

    @staticmethod
    def get_super_node():
        return os.environ.get('SUPERNODE')
