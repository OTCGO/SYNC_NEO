#! /usr/bin/env python3
# coding: utf-8
# flow@SEA
# Licensed under the MIT License.

import sys
import uvloop
import asyncio
import aiohttp
import aiomysql
from random import randint
from logzero import logger
from decimal import Decimal as D
from apscheduler.schedulers.asyncio import AsyncIOScheduler
asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
from Config import Config as C
from CommonTool import CommonTool as CT
from pytz import utc


class Crawler:
    def __init__(self, mysql_args, neo_uri, loop, super_node_uri, tasks='1000'):
        self.start_time = CT.now()
        self.mysql_args = mysql_args
        self.max_tasks = int(tasks)
        self.neo_uri = neo_uri
        self.loop = loop
        self.processing = []
        self.cache = {}
        self.cache_utxo = {}
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

    async def get_block(self, height):
        async with self.session.post(self.neo_uri,
                json={'jsonrpc':'2.0','method':'getblock','params':[height,1],'id':1}) as resp:
            if 200 != resp.status:
                logger.error('Unable to fetch block {}'.format(height))
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

    async def get_block_count(self):
        async with self.session.post(self.neo_uri,
                json={'jsonrpc':'2.0','method':'getblockcount','params':[],'id':1}) as resp:
            if 200 != resp.status:
                logger.error('Unable to fetch blockcount')
                sys.exit(1)
            j = await resp.json()
            return j['result']

    async def get_history_state(self):
        result = await self.state.find_one({'_id':'history'})
        if not result:
            await self.state.insert_one({'_id':'history','value':-1})
            return -1
        else:
            return result['value']

    async def update_history_state(self, height):
        await self.state.update_one({'_id':'history'}, {'$set': {'value':height}}, upsert=True)

    async def cache_block(self, height):
        self.cache[height] = await self.get_block(height)

    async def cache_utxo_vouts(self, txid):
        tx = await self.get_transaction(txid)
        self.cache_utxo[txid] = tx['vout']

    async def update_a_vin(self, vin, txid, index, utc_time):
        _id = txid + '_in_' + str(index)
        try:
            await self.history.update_one({'_id':_id},
                    {'$set':{
                        'txid':txid,
                        'time':utc_time,
                        'address':vin['address'],
                        'asset':vin['asset'],
                        'value':vin['value'],
                        'operation':'out'
                        }},upsert=True)
        except Exception as e:
            logger.error('Unable to update a vin %s:%s' % (_id,e))
            sys.exit(1)

    async def update_a_vout(self, vout, txid, index, utc_time):
        _id = txid + '_out_' + str(index)
        try:
            await self.history.update_one({'_id':_id},
                    {'$set':{
                        'txid':txid,
                        'time':utc_time,
                        'address':vout['address'],
                        'asset':vout['asset'],
                        'value':vout['value'],
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
                        for vin in tx['vin']:
                            txids.append(vin['txid'])
                txids = list(set(txids))
                if txids:
                    await asyncio.wait([self.cache_utxo_vouts(txid) for txid in txids])
                if sorted(txids) != sorted(self.cache_utxo.keys()):
                    msg = 'cache utxo error'
                    logger.error(msg)
                    sys.exit(1)
                vins= []
                vouts = []
                for block in self.cache.values():
                    block_time = block['time']
                    for tx in block['tx']:

                        utxo_dict = {}
                        for vin in tx['vin']:
                            utxo = self.cache_utxo[vin['txid']][vin['vout']]
                            key = utxo['asset'] + '_' + utxo['address']
                            if key in utxo_dict.keys():
                                utxo_dict[key]['value'] = CT.sci_to_str(str(D(utxo_dict[key]['value'])+D(utxo['value'])))
                            else:
                                utxo_dict[key] = utxo

                        vout_dict = {}
                        for vout in tx['vout']:
                            key = vout['asset'] + '_' + vout['address']
                            if key in vout_dict.keys():
                                vout_dict[key]['value'] = CT.sci_to_str(str(D(vout_dict[key]['value'])+D(vout['value'])))
                            else:
                                vout_dict[key] = vout

                        if 1 == len(utxo_dict) == len(vout_dict) and utxo_dict.keys() == vout_dict.keys():
                            key = list(utxo_dict.keys())[0]
                            if utxo_dict[key]['value'] == vout_dict[key]['value']:
                                continue

                        utxos = list(utxo_dict.values())
                        for i in range(len(utxos)):
                            utxo = utxos[i]
                            key = utxo['asset'] + '_' + utxo['address']
                            if key in vout_dict.keys():
                                if D(utxo['value']) > D(vout_dict[key]['value']):
                                    utxo['value'] = CT.sci_to_str(str(D(utxo['value'])-D(vout_dict[key]['value'])))
                                    del vout_dict[key]
                            vins.append([utxo, tx['txid'], i, block_time])

                        voutx = list(vout_dict.values())
                        for k in range(len(voutx)):
                            vout = voutx[k]
                            vouts.append([vout, tx['txid'], k, block_time])

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
                del self.cache_utxo
                self.processing = []
                self.cache = {}
                self.cache_utxo = {}
            else:
               await asyncio.sleep(0.5)


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
    tasks           = C.get_tasks()

    crawler = Crawler(mysql_args, neo_uri, loop, super_node_uri, tasks)

    try:
        loop.run_until_complete(crawler.crawl())
    except Exception as e:
        logger.error('LOOP EXCEPTION: {}'.format(e.args[0]))
    finally:
        loop.close()
