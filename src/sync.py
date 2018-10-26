#! /usr/bin/env python3
# coding: utf-8
# flow@蓝鲸淘
# Licensed under the MIT License.

import sys
import uvloop
import asyncio
import aiohttp
from random import randint
import motor.motor_asyncio
from logzero import logger
from apscheduler.schedulers.asyncio import AsyncIOScheduler
asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
from Config import Config as C
from CommonTool import CommonTool as CT


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

    async def get_total_sys_fee(self, height):
        if -1 == height: return 0
        result = await self.blocks.find_one({'_id': height})
        if not result:
            msg = 'Unable to fetch block(height=%s)'.format(height)
            logger.error(msg)
            raise Exception(msg)
            sys.exit(1)
        return result['total_sys_fee']

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
        _id = block['index']
        ud = {'sys_fee':block['sys_fee'],
                'total_sys_fee':block['total_sys_fee'],
                'time':block['time'],
                'hash':block['hash'],
                'txs':[tx['txid'] for tx in block['tx']],
                }
        await self.blocks.update_one({'_id':_id}, {'$set':ud}, upsert=True)

    async def cache_block(self, height):
        self.cache[height] = await self.get_block(height)

    async def update_sys_fee(self, min_height):
        base_sys_fee = await self.get_total_sys_fee(min_height - 1)
        for h in self.processing:
            block = self.cache[h]
            block['sys_fee'] = 0
            block['total_sys_fee'] = base_sys_fee
            for tx in block['tx']:
                block['sys_fee'] += int(float(tx['sys_fee']))
            block['total_sys_fee'] += block['sys_fee']
            base_sys_fee = block['total_sys_fee']

    async def get_address_from_vin(self, vin):
        _id = vin['txid'] + '_' + str(vin['vout'])
        result = await self.utxos.find_one({'_id':_id})
        if not result:
            msg = 'Unable to fetch a spent utxo(_id=%s)'.format(_id)
            logger.error(msg)
            raise Exception(msg)
            sys.exit(1)
        return result['address']

    async def update_addresses(self, height, uas):
        await self.state.update_one({'_id':'update'}, {'$set': {'height':height,'value':uas}}, upsert=True)

    async def crawl(self):
        self.start = await self.get_state()
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
                    raise Exception(msg)
                    sys.exit(1)
                await self.update_sys_fee(min_height)
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

                #cache update addresses
                if stop == current_height and 1 == len(self.processing):
                    uas = []
                    vinas = await asyncio.gather(*[self.get_address_from_vin(vin[0]) for vin in vins])
                    voutas = [vout[0]['address'] for vout in vouts]
                    uas = list(set(vinas + voutas))
                    await self.update_addresses(max_height, uas)

                time_b = CT.now()
                logger.info('reached %s ,cost %.6fs to sync %s blocks ,total cost: %.6fs' % 
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
    START_TIME = CT.now()
    logger.info('STARTING...')
    mongo_uri = C.get_mongo_uri()
    neo_uri = C.get_neo_uri()
    mongo_db = C.get_mongo_db()
    tasks = C.get_tasks()
    loop = asyncio.get_event_loop()
    crawler = Crawler(mongo_uri, mongo_db, neo_uri, loop, tasks)
    try:
        loop.run_until_complete(crawler.crawl())
    except Exception as e:
        logger.error('LOOP EXCEPTION: %s' % e)
    finally:
        loop.close()
