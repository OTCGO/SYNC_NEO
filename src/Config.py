#! /usr/bin/env python3
# coding: utf-8
# flow@蓝鲸淘
# Licensed under the MIT License.

import os
from dotenv import load_dotenv, find_dotenv
load_dotenv(find_dotenv(), override=True)


class Config:
    @staticmethod
    def get_mongo_uri():
        mongo_uri    = os.environ.get('MONGOURI')
        if mongo_uri: return mongo_uri
        mongo_server = os.environ.get('MONGOSERVER')
        mongo_port   = os.environ.get('MONGOPORT')
        mongo_user   = os.environ.get('MONGOUSER')
        mongo_pass   = os.environ.get('MONGOPASS')
        if mongo_user and mongo_pass:
            return 'mongodb://%s:%s@%s:%s' % (mongo_user, mongo_pass, mongo_server, mongo_port)
        else:
            return 'mongodb://%s:%s' % (mongo_server, mongo_port)

    @staticmethod
    def get_neo_uri():
        neo_node = os.environ.get('NEONODE')
        neo_port = os.environ.get('NEOPORT')
        return 'http://%s:%s' % (neo_node, neo_port)

    @staticmethod
    def get_mongo_db():
        return os.environ.get('MONGODB')

    @staticmethod
    def get_tasks():
        return os.environ.get('TASKS')

    @staticmethod
    def get_net():
        return os.environ.get('NET')

    @staticmethod
    def get_super_node():
        return os.environ.get('SUPERNODE')
