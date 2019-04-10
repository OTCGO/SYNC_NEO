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
import hashlib
from random import randint
from binascii import hexlify, unhexlify
from logzero import logger
from base58 import b58encode
from decimal import Decimal as D
from apscheduler.schedulers.asyncio import AsyncIOScheduler
asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
from Config import Config as C
from CommonTool import CommonTool as CT
from pytz import utc


class Crawler:
    def __init__(self, name, mysql_args, neo_uri, loop, super_node_uri, tasks='1000'):
        self.name = name
        self.start_time = CT.now()
        self.mysql_args = mysql_args
        self.max_tasks = int(tasks)
        self.neo_uri = neo_uri
        self.loop = loop
        self.processing = []
        self.cache = {}
        self.session = aiohttp.ClientSession(loop=loop)
        self.super_node_uri = super_node_uri
        self.scheduler = AsyncIOScheduler(job_defaults = {
                        'coalesce': True,
                        'max_instances': 1,
                        'misfire_grace_time': 2
            })
        self.scheduler.add_job(self.update_neo_uri, 'interval', seconds=10, args=[], id='update_neo_uri', timezone=utc)
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
    def integer_to_num_str(int_str, decimals=8):
        '''eg: "100000000" --(decimals=8)--> "1" '''
        d = D(int_str)
        return CT.sci_to_str(str(d/D(math.pow(10, decimals))))

    @staticmethod
    def hash256(b):
        return hashlib.sha256(hashlib.sha256(b).digest()).digest()

    @classmethod
    def scripthash_to_address(cls, sh):
        tmp = unhexlify('17' + sh)
        result = b58encode(tmp + cls.hash256(tmp)[:4])
        if isinstance(result, bytes): result = result.decode('utf8')
        return result

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
    def hex_to_num_str(cls, hs, decimals=8):
        if isinstance(decimals, str): decimals = int(decimals)
        if not isinstance(decimals, int): sys.exit(1)
        bs = unhexlify(hs)
        return CT.sci_to_str(str(D(cls.bytes_to_num(bs))/D(math.pow(10, decimals))))

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
                logger.error('Unable to fetch block {}, http status: {}'.format(height, resp.status))
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

    async def get_transaction(self, txid):
        async with self.session.post(self.neo_uri,
                json={'jsonrpc':'2.0','method':'getrawtransaction','params':[txid,1],'id':1}) as resp:
            if 200 != resp.status:
                logger.error('Unable to fetch transaction {}'.format(txid))
                sys.exit(1)
            j = await resp.json()
            return j['result']

    async def get_mysql_pool(self):
        try:
            logger.info('start to connect db')
            pool = await aiomysql.create_pool(**self.mysql_args)
            logger.info('succeed to connet db!')
            return pool
        except asyncio.CancelledError:
            raise asyncio.CancelledError
        except Exception as e:
            logger.error("mysql connet failure:{}".format(e.args[0]))
            return False

    async def get_mysql_cursor(self):
        conn = await self.pool.acquire()
        cur  = await conn.cursor()
        return conn, cur

    async def get_status(self):
        conn, cur = await self.get_mysql_cursor()
        try:
            await cur.execute("select update_height from status where name='%s';" % self.name)
            result = await cur.fetchone()
            if result:
                uh = result[0]
                logger.info('database asset height: %s' % uh)
                return uh
            logger.info('database asset height: -1')
            return -1
        except Exception as e:
            logger.error("mysql SELECT failure:{}".format(e.args[0]))
            sys.exit(1)
        finally:
            await self.pool.release(conn)

    async def get_total_sys_fee(self, height):
        if -1 == height: return 0
        conn, cur = await self.get_mysql_cursor()
        try:
            await cur.execute("select total_sys_fee from block where height=%s;" % height)
            result = await cur.fetchone()
            if result:
                h = result[0]
                logger.info('database block height: %s' % h)
                return h
            logger.error('Unable to get block {}'.format(height))
            sys.exit(1)
        except Exception as e:
            logger.error("mysql SELECT failure:{}".format(e.args[0]))
            sys.exit(1)
        finally:
            await self.pool.release(conn)

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
        logger.error('Can not get the decimals of {}'.format(contract))
        sys.exit(1)

    async def update_status(self, height):
        sql="INSERT INTO status(name,update_height) VALUES ('%s',%s) ON DUPLICATE KEY UPDATE update_height=%s;" % (self.name,height,height)
        await self.mysql_insert_one(sql)

    async def cache_block(self, height):
        self.cache[height] = await self.get_block(height)

    async def mysql_insert_one(self, sql):
        conn, cur = await self.get_mysql_cursor()
        logger.info('SQL:%s' % sql)
        try:
            await cur.execute(sql)
            num = cur.rowcount
            #logger.info('%s row affected' % num)
            return num
        except Exception as e:
            logger.error("mysql INSERT failure:{}".format(e.args[0]))
            sys.exit(1)
        finally:
            await self.pool.release(conn)

    async def deal_with(self):
        pass

    async def infinite_loop(self):
        while True:
            current_height = await self.get_block_count()
            time_a = CT.now()
            if self.start < current_height:
                stop = self.start + self.max_tasks
                if stop >= current_height:
                    stop = current_height
                self.processing.extend([i for i in range(self.start,stop)])
                self.max_height = max(self.processing)
                self.min_height = self.processing[0]
                await asyncio.wait([self.cache_block(h) for h in self.processing])
                if self.processing != sorted(self.cache.keys()):
                    msg = 'can not cache so much blocks one time(cache != processing)'
                    logger.error(msg)
                    self.max_tasks -= 10
                    if self.max_tasks > 0:
                        continue
                    else:
                        sys.exit(1)
                
                await self.deal_with()

                time_b = CT.now()
                logger.info('reached %s ,cost %.6fs to sync %s blocks ,total cost: %.6fs' % 
                        (self.max_height, time_b-time_a, stop-self.start, time_b-self.start_time))
                await self.update_status(self.max_height)
                self.start = self.max_height + 1
                del self.processing
                del self.cache
                self.processing = []
                self.cache = {}
            else:
               await asyncio.sleep(0.5)

    async def crawl(self):
        self.pool = await self.get_mysql_pool()
        if not self.pool:
            sys.exit(1)
        try:
            self.start = await self.get_status()
            self.start += 1
            logger.info('start infinite loop from height: %s' % self.start)
            await self.infinite_loop()
        except Exception as e:
            logger.error('CRAWL EXCEPTION: {}'.format(e.args[0]))
        finally:
            self.pool.close()
            await self.pool.wait_closed()
            await self.session.close()
