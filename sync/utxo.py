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
        super(UTXO,self).__init__(name, mysql_args, neo_uri, loop, super_node_uri, tasks)

    async def update_a_vin(self, vin, txid, height):
        sql="""UPDATE utxos SET spent_txid='%s',spent_height=%s,status=0 WHERE txid='%s' AND index_n=%s;""" % (txid,height,vin['txid'],vin['vout'])
        await self.mysql_insert_one(sql)

    async def update_a_vout(self, vout, txid, height):
        sql="""INSERT IGNORE INTO utxos(txid,index_n,address,value,asset,height) VALUES ('%s',%s,'%s','%s','%s',%s);""" % (txid,vout['n'],vout['address'],vout['value'],vout['asset'][2:],height)
        await self.mysql_insert_one(sql)

    async def update_a_claim(self, claim, txid, height):
        sql="""UPDATE utxos SET claim_txid='%s',claim_height=%s WHERE txid='%s' AND index_n=%s;""" % (txid,height,claim['txid'],claim['vout'])
        await self.mysql_insert_one(sql)

    async def update_block(self, block):
        sql="INSERT IGNORE INTO block(height,sys_fee,total_sys_fee) VALUES (%s,%s,%s) ;" % (block['index'],block['sys_fee'],block['total_sys_fee'])
        await self.mysql_insert_one(sql)

    async def update_sys_fee(self):
        base_sys_fee = await self.get_total_sys_fee(self.min_height - 1)
        for h in self.processing:
            block = self.cache[h]
            block['sys_fee'] = 0
            block['total_sys_fee'] = base_sys_fee
            for tx in block['tx']:
                block['sys_fee'] += int(float(tx['sys_fee']))
            block['total_sys_fee'] += block['sys_fee']
            base_sys_fee = block['total_sys_fee']

    async def get_address_info_from_vin(self, vin):
        conn, cur = await self.get_mysql_cursor()
        try:
            await cur.execute("select address,asset from utxos where txid='%s' and index_n=%s;" % (vin['txid'],vin['vout']))
            result = await cur.fetchone()
            if result:
                addr = result[0]
                asset = result[1]
                logger.info('from utxos get address:%s, asset:%s' % (addr,asset))
                return addr,asset
            logger.error('Unable to get utxos {}'.format(vin['txid']))
            sys.exit(1)
        except Exception as e:
            logger.error("mysql SELECT failure:{}".format(e.args[0]))
            sys.exit(1)
        finally:
            await self.pool.release(conn)

    async def deal_with(self):
        await self.update_sys_fee()
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
        if vouts:
            await asyncio.wait([self.update_a_vout(*vout) for vout in vouts])
        if vins:
            await asyncio.wait([self.update_a_vin(*vin) for vin in vins])
        if claims:
            await asyncio.wait([self.update_a_claim(*claim) for claim in claims])

        uas = []
        vinas = await asyncio.gather(*[self.get_address_info_from_vin(vin[0]) for vin in vins])
        voutas = [(vout[0]['address'],vout[0]['asset'][2:]) for vout in vouts]
        uas = list(set(vinas + voutas))
        if uas: await self.update_addresses(self.max_height, uas)

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
