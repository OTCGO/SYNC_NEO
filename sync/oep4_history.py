#! /usr/bin/env python3
# coding: utf-8
# flow@SEA
# Licensed under the MIT License.

import sys
import math
import uvloop
import asyncio
import aiohttp
asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
from logzero import logger
from Crawler import Crawler
from decimal import Decimal as D
from Config import Config as C
from CommonTool import CommonTool as CT


class OEP4History(Crawler):
    def __init__(self, name, mysql_args, ont_uri, loop, chain, tasks='1000'):
        self.name = name
        self.start_time = CT.now()
        self.mysql_args = mysql_args
        self.max_tasks = int(tasks)
        self.neo_uri = ont_uri 
        self.loop = loop
        self.chain = chain
        self.processing = []
        self.cache = {}
        self.sem = asyncio.Semaphore(value=self.max_tasks)
        self.session = aiohttp.ClientSession(loop=loop)
        self.cache_event = {}
        self.cache_decimals = {
                "0000000000000000000000000000000000000001":0,#ONT
                "0000000000000000000000000000000000000002":9,#ONG
                }

    async def get_smartcodeevent(self, height):
        async with self.session.post(self.neo_uri, timeout=60,
                json={'jsonrpc':'2.0','method':'getsmartcodeevent','params':[height],'id':3}) as resp:
            if 200 != resp.status:
                logger.error('Unable to fetch smartcodeevent {}, http status: {}'.format(height, resp.status))
                sys.exit(1)
            j = await resp.json()
            if not j['result']: return []
            return j['result']

    async def cache_smartcodeevent(self, height):
        self.cache_event[height] = await self.get_smartcodeevent(height)

    async def update_a_oep4history(self, txid, operation, index, address, value, dest, timepoint, asset):
        sql="""INSERT IGNORE INTO %s(txid,operation,index_n,address,value,dest,timepoint,asset) VALUES ('%s','%s',%s,'%s','%s','%s',%s,'%s');""" % (self.name,txid,operation,index,address,value,dest,timepoint,asset)
        await self.mysql_insert_one(sql)

    async def deal_with(self):
        #step 0: extract timestamp
        #step 1: get the smartcodeevent
        #step 2: convert transfer event to history
        #   A.collect asset
        #   B.sync asset
        #   C.sync history

        #step 0:
        for k in self.processing:
            self.cache[k]['timestamp'] = self.cache[k]['Header']['Timestamp']
        #step 1:
        await asyncio.wait([self.cache_smartcodeevent(h) for h in self.processing])
        if sorted(self.cache_event.keys()) != self.processing:
            msg = 'cache smartcodeevent error'
            logger.error(msg)
            sys.exit(1)
        #step 2:
        his = []
        for h in self.processing:
            for e in self.cache_event[h]:
                if 1 == e['State']:
                    txid = e['TxHash']
                    timepoint = self.cache[h]['timestamp']
                    index = 0
                    for n in e['Notify']:
                        asset = CT.big_or_little(n['ContractAddress'])
                        if asset in self.cache_decimals.keys():
                            address = n['States'][1]
                            dest = n['States'][2]
                            value = CT.sci_to_str(str(D(n['States'][3])/D(math.pow(10,self.cache_decimals[asset]))))
                            index = index + 1
                            index_n = index
                            his.append([txid, 'out', index_n, address, value, dest,    timepoint, asset])
                            his.append([txid, 'in',  index_n, dest,    value, address, timepoint, asset])
                
        if his: await asyncio.wait([self.update_a_oep4history(*h) for h in his])
        uas = list(set([(h[3],h[7]) for h in his]))
        if uas: await self.update_addresses(self.max_height, uas, self.chain)

        del self.cache_event
        self.cache_event = {}


if __name__ == "__main__":
    mysql_args = {
                    'host':     C.get_mysql_host(),
                    'port':     C.get_mysql_port(),
                    'user':     C.get_mysql_user(),
                    'password': C.get_mysql_pass(),
                    'db':       C.get_mysql_db(), 
                    'autocommit':True
                }
    ont_uri         = C.get_ont_uri()
    loop            = asyncio.get_event_loop()
    tasks           = C.get_tasks()

    h = OEP4History('oep4_history', mysql_args, ont_uri, loop, 'ONT', tasks)

    try:
        loop.run_until_complete(h.crawl())
    except Exception as e:
        logger.error('LOOP EXCEPTION: {}'.format(e.args[0]))
    finally:
        loop.close()
