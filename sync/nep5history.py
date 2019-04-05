#! /usr/bin/env python3
# coding: utf-8
# flow@SEA
# Licensed under the MIT License.

import sys
import math
import uvloop
import asyncio
asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
from logzero import logger
from Crawler import Crawler
from decimal import Decimal as D
from Config import Config as C
from CommonTool import CommonTool as CT


class History:
    def __init__(self, name, mysql_args, neo_uri, loop, super_node_uri, net, tasks='1000'):
        super(History,self).__init__(name, mysql_args, neo_uri, loop, super_node_uri, tasks)
        self.net = net
        self.cache_log = {}
        self.cache_decimals = {}

    def integer_to_num_str(self, int_str, decimals=8):
        d = D(int_str)
        return CT.sci_to_str(str(d/D(math.pow(10, decimals))))

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

    async def deal_with(self):
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

        del self.cache_log
        self.cache_log = {}


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
    net             = C.get_net()
    tasks           = C.get_tasks()

    h = History('history', mysql_args, neo_uri, loop, super_node_uri, net, tasks)

    try:
        loop.run_until_complete(h.crawl())
    except Exception as e:
        logger.error('LOOP EXCEPTION: {}'.format(e.args[0]))
    finally:
        loop.close()
