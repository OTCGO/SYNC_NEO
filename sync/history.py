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
from decimal import Decimal as D
from Config import Config as C
from CommonTool import CommonTool as CT


class History(Crawler):
    def __init__(self, name, mysql_args, neo_uri, loop, super_node_uri, net, tasks='1000'):
        super(History,self).__init__(name, mysql_args, neo_uri, loop, super_node_uri, tasks)
        self.net = net
        self.cache_utxo = {}
        self.cache_log = {}
        self.cache_decimals = {}

    async def cache_utxo_vouts(self, txid):
        tx = await self.get_transaction(txid)
        self.cache_utxo[txid] = tx['vout']

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

    async def update_a_gvin(self, vin, txid, index, utc_time):
        sql="""INSERT IGNORE INTO history(txid,operation,index_n,address,value,timepoint,asset) VALUES ('%s','%s',%s,'%s','%s',%s,'%s');""" % (txid,'out',index,vin['address'],vin['value'],utc_time,vin['asset'][2:])
        await self.mysql_insert_one(sql)

    async def update_a_gvout(self, vout, txid, index, utc_time):
        sql="""INSERT IGNORE INTO history(txid,operation,index_n,address,value,timepoint,asset) VALUES ('%s','%s',%s,'%s','%s',%s,'%s');""" % (txid,'in',index,vout['address'],vout['value'],utc_time,vout['asset'][2:])
        await self.mysql_insert_one(sql)

    async def update_a_svin(self, asset, txid, index, address, value, utc_time):
        sql="""INSERT IGNORE INTO history(txid,operation,index_n,address,value,timepoint,asset) VALUES ('%s','%s',%s,'%s','%s',%s,'%s');""" % (txid,'out',index,address,value,utc_time,asset)
        await self.mysql_insert_one(sql)

    async def update_a_svout(self, asset, txid, index, address, value, utc_time):
        sql="""INSERT IGNORE INTO history(txid,operation,index_n,address,value,timepoint,asset) VALUES ('%s','%s',%s,'%s','%s',%s,'%s');""" % (txid,'in',index,address,value,utc_time,asset)
        await self.mysql_insert_one(sql)

    async def deal_with(self):
        gtxids = [] #global
        stxids = [] #smart contract
        for block in self.cache.values():
            for tx in block['tx']:
                for vin in tx['vin']:
                    gtxids.append(vin['txid'])
                if 'InvocationTransaction' == tx['type']:
                    stxids.append(tx['txid'])
        gtxids = list(set(gtxids))
        if gtxids:
            await asyncio.wait([self.cache_utxo_vouts(txid) for txid in gtxids])
        if sorted(gtxids) != sorted(self.cache_utxo.keys()):
            msg = 'cache utxo error'
            logger.error(msg)
            sys.exit(1)
        if stxids:
            await asyncio.wait([self.cache_applicationlog(txid) for txid in stxids])
        if sorted(stxids) != sorted(self.cache_log.keys()):
            msg = 'cache log error'
            logger.error(msg)
            sys.exit(1)

        gvins= []
        gvouts = []
        svins = [] #froms
        svouts = [] #tos
        for block in self.cache.values():
            block_time = block['time']
            for tx in block['tx']:
                #global
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
                    gvins.append([utxo, tx['txid'], i, block_time])

                voutx = list(vout_dict.values())
                for k in range(len(voutx)):
                    vout = voutx[k]
                    gvouts.append([vout, tx['txid'], k, block_time])

                #smart contract
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
                                    if self.validate_address(from_address): svins.append([asset, txid, i, from_address, value, block_time])
                                to_sh = n['state']['value'][2]['value']
                                to_address = self.scripthash_to_address(to_sh)
                                if self.validate_address(to_address): svouts.append([asset, txid, i, to_address, value, block_time])
                    
        if gvins:
            await asyncio.wait([self.update_a_gvin(*vin) for vin in gvins])
        if gvouts:
            await asyncio.wait([self.update_a_gvout(*vout) for vout in gvouts])
        uas = []
        if svins:
            await asyncio.wait([self.update_a_svin(*vin) for vin in svins])
            uas = [(vin[3],vin[0]) for vin in svins]
        if svouts:
            await asyncio.wait([self.update_a_svout(*vout) for vout in svouts])
            uas.extend([(vout[3],vout[0]) for vout in svouts])
        uas = list(set(uas))
        if uas:
            await self.update_addresses(self.max_height, uas)

        del self.cache_utxo
        self.cache_utxo = {}
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
