#! /usr/bin/env python3
# coding: utf-8
# flow@蓝鲸淘
# Licensed under the MIT License.

import os
import sys
import time
import uvloop
import asyncio
import aiohttp
import datetime
import hashlib
from binascii import hexlify, unhexlify
import motor.motor_asyncio
from logzero import logger
from decimal import Decimal as D
from dotenv import load_dotenv, find_dotenv
load_dotenv(find_dotenv(), override=True)
asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())


now = lambda:time.time()

def get_mongo_uri():
    mongo_server = os.environ.get('MONGOSERVER')
    mongo_port   = os.environ.get('MONGOPORT')
    mongo_user   = os.environ.get('MONGOUSER')
    mongo_pass   = os.environ.get('MONGOPASS')
    if mongo_user and mongo_pass:
        return 'mongodb://%s:%s@%s:%s' % (mongo_user, mongo_pass, mongo_server, mongo_port)
    else:
        return 'mongodb://%s:%s' % (mongo_server, mongo_port)

def get_neo_uri():
    neo_node = os.environ.get('NEONODE')
    neo_port = os.environ.get('NEOPORT')
    return 'http://%s:%s' % (neo_node, neo_port)

get_mongo_db = lambda:os.environ.get('MONGODB')

get_tasks = lambda:os.environ.get('TASKS')

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

class Crawler:
    def __init__(self, mongo_uri, mongo_db, neo_uri, loop, tasks='1000'):
        self.client = motor.motor_asyncio.AsyncIOMotorClient(mongo_uri)
        self.state  = self.client[mongo_db].state
        self.assets = self.client[mongo_db].assets
        self.max_tasks = int(tasks)
        self.neo_uri = neo_uri
        self.processing = []
        self.cache = {}
        self.session = aiohttp.ClientSession(loop=loop)

    @staticmethod
    def bytes_to_num(bs):
        s = '0x'
        for i in range(len(bs)-1, -1, -1):
            tmp = hex(bs[i])[2:]
            if 1 == len(tmp): tmp = '0' + tmp
            s += tmp
        return int(s, 16)

    @staticmethod
    def script_to_hash(unhex):
        intermed = hashlib.sha256(unhex).digest()
        return big_or_little(hexlify(hashlib.new('ripemd160', intermed).digest()).decode('ascii'))

    @classmethod
    def parse_script(cls, script):
        unhex = unhexlify(script)
        description, description_length, unhex = '', unhex[0], unhex[1:]
        if description_length: description, unhex = unhex[:description_length].decode('utf8'), unhex[description_length:]
        print('description:',description)
        email, email_length, unhex = '', unhex[0], unhex[1:]
        if email_length: email, unhex = unhex[:email_length].decode('utf8'), unhex[email_length:]
        print('email:',email)
        author, author_length, unhex = '', unhex[0], unhex[1:]
        if author_length: author, unhex = unhex[:author_length].decode('utf8'), unhex[author_length:]
        print('author:',author)
        version, version_length, unhex = '', unhex[0], unhex[1:]
        if version_length: version, unhex = unhex[:version_length].decode('utf8'), unhex[version_length:]
        print('version:',version)
        name, name_length, unhex = '', unhex[0], unhex[1:]
        if name_length: name, unhex = unhex[:name_length].decode('utf8'), unhex[name_length:]
        print('name:',name)
        use_storage = True if 81 == unhex[0] else False
        print('use_storage:',use_storage)
        unhex = unhex[1:]
        return_dict = {
                0:'Signature',
                81:'Boolean',
                82:'Integer',
                83:'Hash160',
                84:'Hash256',
                85:'ByteArray',
                86:'PublicKey',
                87:'String',
                96:'Array',
                240:'InteropInterface',
                255:'Void',
            }
        return_type = return_dict[unhex[0]]
        print('return_type:',return_type)
        unhex = unhex[1:]
        parameter_dict = {
                0:'Signature',
                1:'Boolean',
                2:'Integer',
                3:'Hash160',
                4:'Hash256',
                5:'bytearray',
                6:'PublicKey',
                7:'String',
                16:'Array',
                240:'InteropInterface',
                255:'Void',
                }
        parameter, parameter_length, unhex = [], unhex[0], unhex[1:]
        for i in range(parameter_length):
            parameter.append(parameter_dict[unhex[0]])
            unhex = unhex[1:]
        print('parameters:',parameter)
        contract_dict = {
                76:1,
                77:2,
                78:4,
                }
        contract_length_length,unhex = contract_dict[unhex[0]], unhex[1:]
        contract_length, unhex = cls.bytes_to_num(unhex[:contract_length_length]), unhex[contract_length_length:]
        contract = cls.script_to_hash(unhex[:contract_length])
        return {
                'contract':contract,
                'name':name,
                'version':version,
                'parameter':parameter,
                'return_type':return_type,
                'use_storage':use_storage,
                'author':author,
                'email':email,
                'description':description
                }

    async def get_block(self, height):
        async with self.session.post(self.neo_uri,
                json={'jsonrpc':'2.0','method':'getblock','params':[height,1],'id':1}) as resp:
            if 200 != resp.status:
                logger.error('Unable to fetch block {}'.format(height))
                sys.exit(1)
            j = await resp.json()
            return j['result']

    async def get_block_count(self):
        async with self.session.post(self.neo_uri,
                json={'jsonrpc':'2.0','method':'getblockcount','params':[],'id':1}) as resp:
            if 200 != resp.status:
                logger.error('Unable to fetch blockcount')
                sys.exit(1)
            j = await resp.json()
            return j['result']

    async def get_asset_state(self):
        result = await self.state.find_one({'_id':'asset'})
        if not result:
            await self.state.insert_one({'_id':'asset','value':-1})
            return -1
        else:
            return result['value']

    async def update_asset_state(self, height):
        await self.state.update_one({'_id':'asset'}, {'$set': {'value':height}}, upsert=True)

    async def cache_block(self, height):
        self.cache[height] = await self.get_block(height)

    def timestamp_to_utc(self, timestamp):
        return datetime.datetime.utcfromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M:%S")

    async def update_a_global_asset(self, key, asset):
        _id = key
        try:
            await self.assets.update_one({'_id':_id},
                    {'$set':asset},upsert=True)
        except Exception as e:
            logger.error('Unable to update a global asset %s:%s' % (_id,e))
            sys.exit(1)

    async def update_a_nep5_asset(self, key, asset):
        _id = key
        del asset['contract']
        try:
            await self.assets.update_one({'_id':_id},
                    {'$set':asset},upsert=True)
        except Exception as e:
            logger.error('Unable to update a nep5 asset %s:%s' % (_id,e))
            sys.exit(1)

    async def crawl(self):
        self.start = await self.get_asset_state()
        self.start += 1
        
        while True:
            current_height = await self.get_block_count()
            time_a = now()
            if self.start < current_height:
                stop = self.start + self.max_tasks
                if stop >= current_height:
                    stop = current_height
                self.processing.extend([i for i in range(self.start,stop)])
                max_height = max(self.processing)
                min_height = self.processing[0]
                await asyncio.wait([self.cache_block(h) for h in self.processing])
                if self.processing != sorted(self.cache.keys()):
                    msg = 'cache != processing'
                    logger.error(msg)
                    sys.exit(1)
                
                global_assets = {}
                nep5_assets = {}
                for block in self.cache.values():
                    block_time = self.timestamp_to_utc(block['time'])
                    for tx in block['tx']:
                        if 'RegisterTransaction' == tx['type']:
                            global_assets[tx['txid']] = tx['asset']
                            global_assets[tx['txid']]['time'] = block_time
                        if 'InvocationTransaction' == tx['type'] and 490 <= int(float(tx['sys_fee'])):
                            if tx['script'].endswith('68134e656f2e436f6e74726163742e437265617465'):
                                try:
                                    asset = self.parse_script(tx['script'])
                                except EXCEPTION as e:
                                    print('parse error:',e)
                                    continue
                                asset['time'] = block_time
                                nep5_assets[asset['contract']] = asset
                if global_assets:
                    await asyncio.wait([self.update_a_global_asset(*i) for i in global_assets.items()])
                if nep5_assets:
                    await asyncio.wait([self.update_a_nep5_asset(*i) for i in nep5_assets.items()])

                time_b = now()
                logger.info('reached %s ,cost %.6fs to sync %s blocks ,total cost: %.6fs' % 
                        (max_height, time_b-time_a, stop-self.start, time_b-START_TIME))
                await self.update_asset_state(max_height)
                self.start = max_height + 1
                del self.processing
                del self.cache
                self.processing = []
                self.cache = {}
            else:
               await asyncio.sleep(0.5)


if __name__ == "__main__":
    START_TIME = now()
    logger.info('STARTING...')
    mongo_uri = get_mongo_uri()
    neo_uri = get_neo_uri()
    mongo_db = get_mongo_db()
    tasks = get_tasks()
    loop = asyncio.get_event_loop()
    crawler = Crawler(mongo_uri, mongo_db, neo_uri, loop, tasks)
    #try:
    loop.run_until_complete(crawler.crawl())
    #except Exception as e:
    #logger.error('LOOP EXCEPTION: %s' % e)
    #finally:
    #loop.close()
