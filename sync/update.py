#! /usr/bin/env python3
# coding: utf-8
# flow@SEA
# Licensed under the MIT License.

import sys
import uvloop
import asyncio
import aiohttp
asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
from logzero import logger
from Crawler import Crawler
from Config import Config as C
from apscheduler.schedulers.asyncio import AsyncIOScheduler
asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
from pytz import utc


class UPT(Crawler):
    def __init__(self, mysql_args, neo_uri, loop, super_node_uri, tasks='100'):
        self.mysql_args = mysql_args
        self.max_tasks = int(tasks)
        self.neo_uri = neo_uri
        self.loop = loop
        self.processing = []
        self.cache = {}
        conn = aiohttp.TCPConnector(limit=10000)
        self.session = aiohttp.ClientSession(loop=loop, connector=conn, headers={"Connection": "close"},)
        self.super_node_uri = super_node_uri
        self.scheduler = AsyncIOScheduler(job_defaults = {
                        'coalesce': True,
                        'max_instances': 1,
                        'misfire_grace_time': 2
            })
        self.scheduler.add_job(self.update_neo_uri, 'interval', seconds=10, args=[], id='update_neo_uri', timezone=utc)
        self.scheduler.start()

        self.cache_decimals = {}
        self.cache_balances = {}


    async def get_address_info_to_update(self, height):
        sql = "SELECT address,asset FROM upt where update_height < %s limit %s;" % (height, self.max_tasks)
        return await self.mysql_query_one(sql)

    async def get_cache_decimals(self, contract):
        if contract not in self.cache_decimals.keys():
            self.cache_decimals[contract] = await self.get_decimals(contract)
        return self.cache_decimals[contract]
    
    async def get_cache_global_balance(self, address):
        if address not in self.cache_balances.keys():
            self.cache_balances[address] = await self.get_global_balance(address)
        return self.cache_balances[address]

    async def get_balance(self, address, asset):
        if 40 == len(asset):#nep5
            b = await self.get_nep5_balance(asset,address)
            if 0 == len(b['value']): return '0'
            if 'ByteArray' == b['type']:
                return self.hex_to_num_str(b['value'], decimals=await self.get_cache_decimals(asset))
            if 'Integer' == b['type']:
                return self.integer_to_num_str(b['value'], decimals=await self.get_cache_decimals(asset))
            sys.exit(1)
        if 64 == len(asset):#global
            asset = '0x' + asset
            b = await self.get_cache_global_balance(address)
            for i in b:
                if asset == i['asset']: return i['value']
            return '0'
        sys.exit(1)


    async def infinite_loop(self):
        while True:
            current_height = await self.get_block_count()
            upts = await self.get_address_info_to_update(current_height)
            if upts:
                result = await asyncio.gather(*[self.get_balance(*upt) for upt in upts]) 
                data = []
                for i in range(len(upts)):
                    upt = upts[i]
                    address = upt[0]
                    asset = upt[1]
                    r = result[i]
                    data.append((address,asset,r,current_height,r,current_height))
                await self.update_address_balances(data)
                await self.update_upts(upts, current_height)

                self.cache_balances = {}
            else:
               await asyncio.sleep(0.5)

    async def crawl(self):
        self.pool = await self.get_mysql_pool()
        if not self.pool:
            sys.exit(1)
        try:
            await self.infinite_loop()
        except Exception as e:
            logger.error('CRAWL EXCEPTION: {}'.format(e.args[0]))
        finally:
            self.pool.close()
            await self.pool.wait_closed()
            await self.session.close()


if __name__ == "__main__":
    mysql_args = {
                    'host':     C.get_mysql_host(),
                    'port':     C.get_mysql_port(),
                    'user':     C.get_mysql_user(),
                    'password': C.get_mysql_pass(),
                    'db':       C.get_mysql_db(),
                    'autocommit':True
                }
    neo_uri         = C.get_neo_uri()
    loop            = asyncio.get_event_loop()
    super_node_uri  = C.get_super_node()

    u = UPT(mysql_args, neo_uri, loop, super_node_uri)

    try:
        loop.run_until_complete(u.crawl())
    except Exception as e:
        logger.error('LOOP EXCEPTION: {}'.format(e.args[0]))
    finally:
        loop.close()
