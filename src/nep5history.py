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
import binascii
import hashlib
from base58 import b58encode
import motor.motor_asyncio
from logzero import logger
from decimal import Decimal as D
from dotenv import load_dotenv, find_dotenv
load_dotenv(find_dotenv(), override=True)
asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())


now = lambda:time.time()

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

def get_neo_uri():
    neo_node = os.environ.get('NEONODE')
    neo_port = os.environ.get('NEOPORT')
    return 'http://%s:%s' % (neo_node, neo_port)

get_mongo_db = lambda:os.environ.get('MONGODB')

get_tasks = lambda:os.environ.get('TASKS')

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


class Crawler:
    def __init__(self, mongo_uri, mongo_db, neo_uri, loop, tasks='1000'):
        self.client = motor.motor_asyncio.AsyncIOMotorClient(mongo_uri)
        self.state  = self.client[mongo_db].state
        self.nep5history = self.client[mongo_db].nep5history
        self.max_tasks = int(tasks)
        self.neo_uri = neo_uri
        self.processing = []
        self.cache = {}
        self.cache_log = {}
        conn = aiohttp.TCPConnector(limit=10000)
        self.session = aiohttp.ClientSession(loop=loop,connector=conn)
        self.net = os.environ.get('NET')
        self.super_node_uri = 'http://127.0.0.1:9999'

    def hex_to_num_str(self, fixed8_str):
        hex_str = big_or_little(fixed8_str)
        if not hex_str: return '0'
        d = D(int('0x' + hex_str, 16))
        return sci_to_str(str(d/100000000))

    @staticmethod
    def hash256(b):
        return hashlib.sha256(hashlib.sha256(b).digest()).digest()

    @classmethod
    def scripthash_to_address(cls, sh):
        tmp = binascii.unhexlify('17' + sh)
        result = b58encode(tmp + cls.hash256(tmp)[:4])
        if isinstance(result, bytes): result = result.decode('utf8')
        return result

    async def get_block(self, height):
        async with self.session.post(self.neo_uri, json={'jsonrpc':'2.0','method':'getblock','params':[height,1],'id':1}) as resp:
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

    async def get_history_state(self):
        start = -1
        if 'mainnet' == self.net: start = 1444800
        if 'testnet' == self.net: start = 442400
        result = await self.state.find_one({'_id':'nep5history'})
        if not result:
            await self.state.insert_one({'_id':'nep5history','value':start})
            return start
        else:
            return result['value']

    async def update_history_state(self, height):
        await self.state.update_one({'_id':'nep5history'}, {'$set': {'value':height}}, upsert=True)

    async def cache_block(self, height):
        self.cache[height] = await self.get_block(height)

    async def cache_applicationlog(self, txid):
        url = self.super_node_uri + '/' + self.net + '/log/' + txid
        async with self.session.get(url, timeout=120) as resp:
            if 200 != resp.status:
                logger.error('Visit %s get status %s' % (url, resp.status))
                return None
            j = await resp.json()
            if 'error' in j.keys():
                logger.error('Visit %s return error %s' % (url, j['error']))
                return None
            self.cache_log[txid] = j

    async def update_a_vin(self, asset, txid, index, address, value, utc_time):
        _id = txid + str(index) + '_in_'
        try:
            await self.nep5history.update_one({'_id':_id},
                    {'$set':{
                        'txid':txid,
                        'time':utc_time,
                        'address':address,
                        'asset':asset,
                        'value':value,
                        'operation':'out'
                        }},upsert=True)
        except Exception as e:
            logger.error('Unable to update a vin %s:%s' % (_id,e))
            sys.exit(1)

    async def update_a_vout(self, asset, txid, index, address, value, utc_time):
        _id = txid + str(index) + '_out_'
        try:
            await self.nep5history.update_one({'_id':_id},
                    {'$set':{
                        'txid':txid,
                        'time':utc_time,
                        'address':address,
                        'asset':asset,
                        'value':value,
                        'operation':'in'
                        }},upsert=True)
        except Exception as e:
            logger.error('Unable to update a vout %s:%s' % (_id,e))
            sys.exit(1)

    def timestamp_to_utc(self, timestamp):
        return datetime.datetime.utcfromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M:%S")

    async def crawl(self):
        self.start = await self.get_history_state()
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
                txids = [] 
                for block in self.cache.values():
                    for tx in block['tx']:
                        if 'InvocationTransaction' == tx['type']:
                            txids.append(tx['txid'])
                if txids:
                    await asyncio.wait([self.cache_applicationlog(txid) for txid in txids])
                if sorted(txids) != sorted(self.cache_log.keys()):
                    msg = 'cache log error'
                    logger.error(msg)
                    sys.exit(1)

                #await asyncio.wait([self.add_nep5_history(log) for log in self.cache.values()])
                vins = [] #froms
                vouts = [] #tos
                for block in self.cache.values():
                    block_time = self.timestamp_to_utc(block['time'])
                    for tx in block['tx']:
                        txid = tx['txid']
                        if 'InvocationTransaction' == tx['type']:
                            log = self.cache_log[txid]
                            if 'HALT, BREAK' == log['vmstate']:
                                for i in range(len(log['notifications'])):
                                    n = log['notifications'][i]
                                    asset = n['contract'][2:]
                                    if isinstance(n['state']['value'],list) and 4 == len(n['state']['value']) and '7472616e73666572' == n['state']['value'][0]['value']:
                                        value = self.hex_to_num_str(n['state']['value'][3]['value'])
                                        from_sh = n['state']['value'][1]['value']
                                        if from_sh:
                                            from_address = self.scripthash_to_address(from_sh)
                                            vins.append([asset, txid, i, from_address, value, block_time])
                                        to_sh = n['state']['value'][2]['value']
                                        to_address = self.scripthash_to_address(to_sh)
                                        vouts.append([asset, txid, i, to_address, value, block_time])
                            
                if vins:
                    await asyncio.wait([self.update_a_vin(*vin) for vin in vins])
                if vouts:
                    await asyncio.wait([self.update_a_vout(*vout) for vout in vouts])

                time_b = now()
                logger.info('reached %s ,cost %.6fs to sync %s blocks ,total cost: %.6fs' % 
                        (max_height, time_b-time_a, stop-self.start, time_b-START_TIME))
                await self.update_history_state(max_height)
                self.start = max_height + 1
                del self.processing
                del self.cache
                del self.cache_log
                self.processing = []
                self.cache = {}
                self.cache_log = {}
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
    loop.run_until_complete(crawler.crawl())
    '''
    try:
        loop.run_until_complete(crawler.crawl())
    except Exception as e:
        logger.error('LOOP EXCEPTION: %s' % e)
    finally:
        loop.close()
    '''
