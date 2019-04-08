#! /usr/bin/env python3
# coding: utf-8
# flow@SEA
# Licensed under the MIT License.

import sys
import uvloop
import asyncio
asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
from logzero import logger
from Crawler import Crawler
from Config import Config as C


class UTXO(Crawler):
    def __init__(self, name, mysql_args, neo_uri, loop, super_node_uri, tasks='1000'):
        super(Asset,self).__init__(name, mysql_args, neo_uri, loop, super_node_uri, tasks)

    async def get_total_sys_fee(self, height):
        if -1 == height: return 0
        result = await self.blocks.find_one({'_id': height})
        if not result:
            msg = 'Unable to fetch block(height={})'.format(height)
            logger.error(msg)
            raise Exception(msg)
            sys.exit(1)
        return result['total_sys_fee']

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
            msg = 'Unable to fetch a spent utxo(_id={})'.format(_id)
            logger.error(msg)
            raise Exception(msg)
            sys.exit(1)
        return result['address']

    async def update_addresses(self, height, uas):
        await self.state.update_one({'_id':'update'}, {'$set': {'height':height,'value':uas}}, upsert=True)

    async def deal_with(self):
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

        await asyncio.wait([self.update_block(block) for block in self.cache.values()])


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

    u = UTXO('utxo', mysql_args, neo_uri, loop, super_node_uri, tasks)

    try:
        loop.run_until_complete(u.crawl())
    except Exception as e:
        logger.error('LOOP EXCEPTION: {}'.format(e.args[0]))
    finally:
        loop.close()
