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
from Config import Config as C
from decimal import Decimal as D
asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
from CommonTool import CommonTool as CT


class OEP4UPT(Crawler):
    def __init__(self, name, mysql_args, ont_uri, loop, chain, tasks='100'):
        self.name = name
        self.start_time = CT.now()
        self.mysql_args = mysql_args
        self.max_tasks = int(tasks)
        self.neo_uri = ont_uri 
        self.ont_uri = ont_uri
        self.loop = loop
        self.chain = chain
        self.processing = []
        self.cache = {}
        self.sem = asyncio.Semaphore(value=self.max_tasks)
        self.session = aiohttp.ClientSession(loop=loop)

    async def get_address_info_to_update(self, height):
        sql = "SELECT address,asset FROM upt where chain='%s' AND update_height < %s limit %s;" % (self.chain, height, self.max_tasks)
        return await self.mysql_query_one(sql)

    async def get_rpc_ont(self, method, params):
        async with self.session.post(self.ont_uri,
                json={'jsonrpc':'2.0','method':method,'params':params,'id':1}) as resp:
            if 200 != resp.status:
                msg = 'Unable to visit %s %s' % (self.ont_uri, method)
                logging.error(msg)
                return None,msg
            j = await resp.json()
            if 'SUCCESS' != j['desc']:
                msg = 'result error when %s %s:%s' % (self.ont_uri, method, j['error'])
                logging.error(msg)
                return None,msg
            return j['result'],None

    async def get_ont_balance(self, address, asset_name=None):
        result,err = await self.get_rpc_ont('getbalance', [address])
        if err or not result: return {'ont':"0",'ong':"0"}
        result['ong'] = CT.sci_to_str(str(D(result['ong'])/D(math.pow(10, 9))))
        if not asset_name: return result
        return result[asset_name]
    
    async def get_balance(self, address, asset):
        if 40 == len(asset):#nep5
            if '0000000000000000000000000000000000000001' == asset:
                return await self.get_ont_balance(address,'ont')
            elif '0000000000000000000000000000000000000002' == asset:
                return await self.get_ont_balance(address,'ong')
            else:
                pass
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
    ont_uri         = C.get_ont_uri()
    loop            = asyncio.get_event_loop()
    tasks           = C.get_tasks()

    u = OEP4UPT('upt', mysql_args, ont_uri, loop, "ONT", tasks)

    try:
        loop.run_until_complete(u.crawl())
    except Exception as e:
        logger.error('LOOP EXCEPTION: {}'.format(e.args[0]))
    finally:
        loop.close()
