#! /usr/bin/env python3
# coding: utf-8
# flow@SEA
# Licensed under the MIT License.

import sys
import math
import uvloop
import asyncio
import aiohttp
import aiomysql
import binascii
import hashlib
from random import randint
from base58 import b58encode
from logzero import logger
from decimal import Decimal as D
from apscheduler.schedulers.asyncio import AsyncIOScheduler
asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
from Config import Config as C
from CommonTool import CommonTool as CT


class Crawler:
    def __init__(self, mongo_uri, mongo_db, neo_uri, loop, tasks='1000'):
        self.client = motor.motor_asyncio.AsyncIOMotorClient(mongo_uri,maxPoolSize=2)
        self.state  = self.client[mongo_db].state
        self.nep5history = self.client[mongo_db].nep5history
        self.max_tasks = int(tasks)
        self.neo_uri = neo_uri
        self.processing = []
        self.cache = {}
        self.cache_log = {}
        self.cache_decimals = {}
        conn = aiohttp.TCPConnector(limit=10000)
        self.session = aiohttp.ClientSession(loop=loop,connector=conn)
        self.net = C.get_net()
        self.super_node_uri = C.get_super_node()
        self.scheduler = AsyncIOScheduler(job_defaults = {
                        'coalesce': True,
                        'max_instances': 1,
                        'misfire_grace_time': 2
            })
        self.scheduler.add_job(self.update_neo_uri, 'interval', seconds=10, args=[], id='update_neo_uri')
        self.scheduler.start()

    async def get_super_node_info(self):
        async with self.session.get(self.super_node_uri) as resp:
            if 200 != resp.status:
                logger.error('Unable to fetch supernode info')
                sys.exit(1)
            j = await resp.json()
            return j

    async def update_neo_uri(self):
        heightA = await self.get_block_count()
        info = await self.get_super_node_info()
        heightB = info['height']
        if heightA < heightB:
            self.neo_uri = info['fast'][randint(0,len(info['fast'])-1)]
        logger.info('heightA:%s heightB:%s neo_uri:%s' % (heightA,heightB,self.neo_uri))

    def integer_to_num_str(self, int_str, decimals=8):
        d = D(int_str)
        return CT.sci_to_str(str(d/D(math.pow(10, decimals))))

    def hex_to_num_str(self, fixed8_str, decimals=8):
        hex_str = CT.big_or_little(fixed8_str)
        if not hex_str: return '0'
        d = D(int('0x' + hex_str, 16))
        return CT.sci_to_str(str(d/D(math.pow(10, decimals))))

    @staticmethod
    def hash256(b):
        return hashlib.sha256(hashlib.sha256(b).digest()).digest()

    @classmethod
    def scripthash_to_address(cls, sh):
        tmp = binascii.unhexlify('17' + sh)
        result = b58encode(tmp + cls.hash256(tmp)[:4])
        if isinstance(result, bytes): result = result.decode('utf8')
        return result

    async def get_invokefunction(self, contract, func):
        async with self.session.post(self.neo_uri,
                json={'jsonrpc':'2.0','method':'invokefunction','params':[contract, func],'id':1}) as resp:
            if 200 != resp.status:
                logger.error('Unable to get invokefunction')
                sys.exit(1)
            j = await resp.json()
            return j['result']

    async def get_decimals(self, contract):
        d = await self.get_invokefunction(contract, 'decimals')
        if 'state' in d.keys() and d['state'].startswith('HALT'):
            if d['stack'][0]['value']:
                return int(d['stack'][0]['value'])
            return 0
        return 8

    async def get_cache_decimals(self, contract):
        if contract not in self.cache_decimals.keys():
            self.cache_decimals[contract] = await self.get_decimals(contract)
        return self.cache_decimals[contract]

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

    async def crawl(self):
        self.start = await self.get_history_state()
        self.start += 1

        while True:
            current_height = await self.get_block_count()
            time_a = CT.now()
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
                    block_time = block['time']
                    for tx in block['tx']:
                        txid = tx['txid']
                        if 'InvocationTransaction' == tx['type']:
                            log = self.cache_log[txid]
                            if ('vmstate' in log.keys() and 'HALT, BREAK' == log['vmstate']) or ('executions' in log.keys() and 'vmstate' in log['executions'][0].keys() and 'HALT, BREAK' == log['executions'][0]['vmstate']):
                                if 'executions' in log.keys(): log['notifications'] = log['executions'][0]['notifications']
                                for i in range(len(log['notifications'])):
                                    n = log['notifications'][i]
                                    asset = n['contract'][2:]
                                    if 'value' in n['state'].keys() and \
                                            isinstance(n['state']['value'],list) and \
                                            4 == len(n['state']['value']) and \
                                            '7472616e73666572' == n['state']['value'][0]['value']:
                                        if 'Integer' == n['state']['value'][3]['type']:
                                            value = self.integer_to_num_str(n['state']['value'][3]['value'], decimals=await self.get_cache_decimals(asset))
                                        else:
                                            value = self.hex_to_num_str(n['state']['value'][3]['value'], decimals=await self.get_cache_decimals(asset))
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

                time_b = CT.now()
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
    START_TIME = CT.now()
    logger.info('STARTING...')
    mongo_uri = C.get_mongo_uri()
    neo_uri = C.get_neo_uri()
    mongo_db = C.get_mongo_db()
    tasks = C.get_tasks()
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
