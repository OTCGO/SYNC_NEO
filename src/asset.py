#! /usr/bin/env python3
# coding: utf-8
# flow@蓝鲸淘
# Licensed under the MIT License.

import sys
import uvloop
import asyncio
import aiohttp
import datetime
import hashlib
from random import randint
from binascii import hexlify, unhexlify
import motor.motor_asyncio
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
        self.assets = self.client[mongo_db].assets
        self.max_tasks = int(tasks)
        self.neo_uri = neo_uri
        self.processing = []
        self.cache = {}
        self.session = aiohttp.ClientSession(loop=loop)
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

    @staticmethod
    def bytes_to_num(bs):
        s = '0x'
        for i in range(len(bs)-1, -1, -1):
            tmp = hex(bs[i])[2:]
            if 1 == len(tmp): tmp = '0' + tmp
            s += tmp
        else:
            if '0x' == s: s += '00'
        return int(s, 16)

    @classmethod
    def hex_to_num_str(cls, hs):
        bs = unhexlify(hs)
        return CT.sci_to_str(str(D(cls.bytes_to_num(bs))/100000000))

    @staticmethod
    def script_to_hash(unhex):
        intermed = hashlib.sha256(unhex).digest()
        return CT.big_or_little(hexlify(hashlib.new('ripemd160', intermed).digest()).decode('ascii'))

    @staticmethod
    def parse_element(script):
        content = None
        content_length = 0
        uns = unhexlify(script)
        mark = uns[0]
        if 0x00 <= mark and mark <= 0x4B:
            content_length = mark
            content = script[2:2+content_length*2]
            script = script[2+content_length*2:]
        elif 0x4C <= mark and mark <= 0x4E:
            if 0x4C == mark:
                content_length = int(script[2:4], 16)
                content = script[4:4+content_length*2]
                script = script[4+content_length*2:]
            if 0x4D == mark:
                content_length = int(CT.big_or_little(script[2:6]), 16)
                content = script[6:6+content_length*2]
                script = script[6+content_length*2:]
            if 0x4E == mark:
                content_length = int(CT.big_or_little(script[2:10]), 16)
                content = script[10:10+content_length*2]
                script = script[10+content_length*2:]
        elif 0x4F == mark:
            content = -1
            script = script[2:]
        elif 0x51 <= mark and mark <= 0x60:
            content = mark - 0x50
            script = script[2:]
        else:
            pass
        return content, script

    @staticmethod
    def parse_storage_dynamic(mark):
        if not isinstance(mark, int): raise ValueError('wrong type for storage&dynamic {}'.format(mark))
        return 0x01 == mark & 0x01, 0x02 == mark & 0x02

    @staticmethod
    def get_arg_name(mark):
        return {
                0x00:'Signature',
                0x01:'Boolean',
                0x02:'Integer',
                0x03:'Hash160',
                0x04:'Hash256',
                0x05:'bytearray',
                0x06:'PublicKey',
                0x07:'String',
                0x10:'Array',
                0xf0:'InteropInterface',
                0xff:'Void',
                }[mark]

    @classmethod
    def parse_return_type(cls, mark):
        if isinstance(mark, str): mark = int(CT.big_or_little(mark), 16)
        if isinstance(mark, int): return cls.get_arg_name(mark)
        raise ValueError('wrong type for return {}'.format(mark))

    @classmethod
    def parse_parameter(cls, mark):
        if not isinstance(mark, str): raise ValueError('wrong type for paramater {}'.format(mark))
        result = []
        while mark:
            result.append(cls.get_arg_name(int(mark[:2],16)))
            mark = mark[2:]
        return result

    @classmethod
    def parse_script(cls, script):
        result = []
        for i in range(5):
            element, script = cls.parse_element(script)
            element = unhexlify(element).decode('utf8')
            result.append(element)
        description,email,author,version,name = result
        logger.info('description:{}\nemail:{}\nauthor:{}\nversion:{}\nname:{}'.format(description,email,author,version,name))

        sd, script = cls.parse_element(script)
        use_storage, dynamic_call = cls.parse_storage_dynamic(sd)
        logger.info('use_storage:{}\ndynamic_call:{}'.format(use_storage,dynamic_call))

        rmark, script = cls.parse_element(script)
        return_type = cls.parse_return_type(rmark)
        logger.info('return_type:{}'.format(return_type))

        pmark, script = cls.parse_element(script)
        parameter = cls.parse_parameter(pmark)
        logger.info('parameters:{}'.format(parameter))

        contract, script = cls.parse_element(script)
        contract = cls.script_to_hash(unhexlify(contract))
        logger.info('contract:{}'.format(contract))

        return {
                'contract':contract,
                'contract_name':name,
                'version':version,
                'parameter':parameter,
                'return_type':return_type,
                'use_storage':use_storage,
                'dynamic_call':dynamic_call,
                'author':author,
                'email':email,
                'description':description,
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

    async def get_invokefunction(self, contract, func):
        async with self.session.post(self.neo_uri,
                json={'jsonrpc':'2.0','method':'invokefunction','params':[contract, func],'id':1}) as resp:
            if 200 != resp.status:
                logger.error('Unable to get invokefunction')
                sys.exit(1)
            j = await resp.json()
            return j['result']

    async def update_asset_state(self, height):
        await self.state.update_one({'_id':'asset'}, {'$set': {'value':height}}, upsert=True)

    async def cache_block(self, height):
        self.cache[height] = await self.get_block(height)

    def timestamp_to_utc(self, timestamp):
        return datetime.datetime.utcfromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M:%S")

    async def update_a_global_asset(self, key, asset):
        if key.startswith('0x'):
            key = key[2:]
        _id = key
        try:
            await self.assets.update_one({'_id':_id},
                    {'$set':asset},upsert=True)
        except Exception as e:
            logger.error('Unable to update a global asset %s:%s' % (_id,e))
            sys.exit(1)

    async def update_a_nep5_asset(self, key, asset):
        _id = contract = key
        funcs = ['totalSupply','name','symbol','decimals']
        del asset['contract']
        results = await asyncio.gather(*[self.get_invokefunction(contract, func) for func in funcs])
        for i in range(len(funcs)):
            func = funcs[i]
            r = results[i]
            if r['state'].startswith('FAULT'):
                return
            if 'totalSupply' == func:
                try:
                    asset[func] = self.hex_to_num_str(r['stack'][0]['value'])
                except:
                    asset[func] = 'unknown'
            if func in ['name', 'symbol']:
                asset[func] = unhexlify(r['stack'][0]['value']).decode('utf8')
            if 'decimals' == func:
                asset[func] = r['stack'][0]['value']
        try:
            asset['type'] = 'NEP5'
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
                
                global_assets = {}
                nep5_assets = {}
                for block in self.cache.values():
                    block_time = block['time']
                    for tx in block['tx']:
                        if 'RegisterTransaction' == tx['type']:
                            global_assets[tx['txid']] = tx['asset']
                            global_assets[tx['txid']]['time'] = block_time
                        if 'InvocationTransaction' == tx['type'] and 490 <= int(float(tx['sys_fee'])):
                            if tx['script'].endswith('68134e656f2e436f6e74726163742e437265617465'):
                                try:
                                    asset = self.parse_script(tx['script'])
                                except Exception as e:
                                    print('parse error:',e)
                                    continue
                                asset['time'] = block_time
                                nep5_assets[asset['contract']] = asset
                if global_assets:
                    await asyncio.wait([self.update_a_global_asset(*i) for i in global_assets.items()])
                if nep5_assets:
                    await asyncio.wait([self.update_a_nep5_asset(*i) for i in nep5_assets.items()])

                time_b = CT.now()
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
    START_TIME = CT.now()
    logger.info('STARTING...')
    mongo_uri = C.get_mongo_uri()
    neo_uri = C.get_neo_uri()
    mongo_db = C.get_mongo_db()
    tasks = C.get_tasks()
    loop = asyncio.get_event_loop()
    crawler = Crawler(mongo_uri, mongo_db, neo_uri, loop, tasks)
    #try:
    loop.run_until_complete(crawler.crawl())
    #except Exception as e:
    #logger.error('LOOP EXCEPTION: %s' % e)
    #finally:
    #loop.close()
