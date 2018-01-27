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
import motor.motor_asyncio
from logzero import logger
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

class Crawler:
    def __init__(self, mongo_uri, mongo_db, neo_uri, loop, tasks='1000'):
        self.client = motor.motor_asyncio.AsyncIOMotorClient(mongo_uri)
        self.state  = self.client[mongo_db].state
        self.utxos  = self.client[mongo_db].utxos
        self.blocks = self.client[mongo_db].blocks
        self.max_tasks = int(tasks)
        self.neo_uri = neo_uri
        self.processing = []
        self.cache = {}
        self.session = aiohttp.ClientSession(loop=loop)

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

    async def get_state(self):
        result = await self.state.find_one({'_id':'height'})
        if not result:
            await self.state.insert_one({'_id':'height','value':-1})
            return -1
        else:
            return result['value']

    async def update_state(self, height):
        await self.state.update_one({'_id':'height'}, {'$set': {'value':height}}, upsert=True)

    async def update_a_vin(self, vin, txid, height):
        _id = vin['txid'] + '_' + str(vin['vout'])
        try:
            await self.utxos.update_one({'_id':_id},
                    {'$set':{'spent_txid':txid,'spent_height':height}},upsert=True)
        except Exception as e:
            logger.error('Unable to update a vin %s:%s' % (_id,e))
            sys.exit(1)

    async def update_a_vout(self, vout, txid, height):
        index = vout['n']
        _id = txid + '_' + str(index)
        address = vout['address']
        value = vout['value']
        asset = vout['asset']
        ud = {
            'txid':txid,
            'index':index,
            'address':address,
            'value':value,
            'asset':asset,
            'height':height,
            }
        try:
            await self.utxos.update_one({'_id':_id}, {'$set':ud}, upsert=True)
        except Exception as e:
            logger.error('Unable to update a vout %s:%s' % (_id,e))
            sys.exit(1)

    async def update_a_claim(self, claim, txid, height):
        _id = claim['txid'] + '_' + str(claim['vout'])
        try:
            await self.utxos.update_one({'_id':_id},
                    {'$set':{'claim_height':height,'claim_txid':txid}}, upsert=True)
        except Exception as e:
            logger.error('Unable to update a claim %s:%s' % (_id,e))
            sys.exit(1)

    async def update_block(self, block):
        block['sys_fee'] = 0
        for tx in block['tx']:
            block['sys_fee'] += int(tx['sys_fee'])
        _id = block['index']
        ud = {'sys_fee':block['sys_fee'],
                'time':block['time'],
                'hash':block['hash'],
                'txs':[tx['txid'] for tx in block['tx']],
                }
        await self.blocks.update_one({'_id':_id}, {'$set':ud}, upsert=True)

    async def cache_block(self, height):
        self.cache[height] = await self.get_block(height)

    async def crawl(self):
        self.start = await self.get_state()
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
                await asyncio.wait([self.cache_block(h) for h in self.processing])
                if self.processing != sorted(self.cache.keys()):
                    raise Exception('cache != processing')
                vins = []
                vouts = []
                claims = []
                for block in self.cache.values():
                    for tx in block['tx']:
                        txid = tx['txid']
                        height = block['index']
                        for vin in tx['vin']:
                            vins.append([vin, txid, height])
                        for vout in tx['vout']:
                            vouts.append([vout, txid, height])
                        if 'claims' in tx.keys():
                            for claim in tx['claims']:
                                claims.append([claim, txid, height])
                if vins:
                    await asyncio.wait([self.update_a_vin(*vin) for vin in vins])
                if vouts:
                    await asyncio.wait([self.update_a_vout(*vout) for vout in vouts])
                if claims:
                    await asyncio.wait([self.update_a_claim(*claim) for claim in claims])

                time_b = now()
                logger.info('Synced %s ,cost %.6f s to sync %s blocks ,total cost: %.6f s' % 
                        (max_height, time_b-time_a, stop-self.start, time_b-START_TIME))
                await asyncio.wait([self.update_block(block) for block in self.cache.values()])
                await self.update_state(max_height)
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
    try:
        loop.run_until_complete(crawler.crawl())
    except Exception as e:
        logger.error('LOOP EXCEPTION: %s' % e)
    finally:
        loop.close()
