#! /usr/bin/env python3
# coding: utf-8
# flow@SEA
# Licensed under the MIT License.

import uvloop
import asyncio
asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
from logzero import logger
from Crawler import Crawler
from Config import Config as C
from binascii import unhexlify


class Asset(Crawler):
    def __init__(self, name, mysql_args, neo_uri, loop, super_node_uri, tasks='1000'):
        super(Asset,self).__init__(name, mysql_args, neo_uri, loop, super_node_uri, tasks)

    async def update_a_global_asset(self, key, asset):
        if key.startswith('0x'): key = key[2:]
        if 'c56f33fc6ecfcd0c225c4ab356fee59390af8560be0e930faebe74a6daff7c9b' == key: asset['name'][0]['name'] = 'NEO'
        if '602c79718b16e442de58778e148d0b1084e3b2dffd5de6b7b16cee7969282de7' == key: asset['name'][0]['name'] = 'GAS'
        sql="INSERT IGNORE INTO assets(asset,type,name,symbol,version,decimals,contract_name) VALUES ('%s','%s','%s','%s','%s',%s,'%s');" % (key,asset['type'],asset['name'][0]['name'],'','',asset['precision'],'')
        await self.mysql_insert_one(sql)

    async def update_a_nep5_asset(self, key, asset):
        funcs = ['decimals','totalSupply','name','symbol']
        results = await asyncio.gather(*[self.get_invokefunction(key, func) for func in funcs])
        for i in range(len(funcs)):
            func = funcs[i]
            r = results[i]
            if r['state'].startswith('FAULT'): return
            if 'decimals' == func:
                v = r['stack'][0]['value']
                if not v: v = "0"
                asset[func] = v
            if 'totalSupply' == func:
                try:
                    asset[func] = self.hex_to_num_str(r['stack'][0]['value'], asset['decimals'])
                except:
                    asset[func] = 'unknown'
            if func in ['name', 'symbol']:
                asset[func] = unhexlify(r['stack'][0]['value']).decode('utf8')
                if 'symbol' == func and 0 == len(asset[func]): return
        sql="INSERT IGNORE INTO assets(asset,type,name,symbol,version,decimals,contract_name) VALUES ('%s','NEP5','%s','%s','%s',%s,'%s');" % (key,asset['name'],asset['symbol'],asset['version'],asset['decimals'],asset['contract_name'])
        await self.mysql_insert_one(sql)

    async def deal_with(self):
        global_assets = {}
        nep5_assets = {}
        for block in self.cache.values():
            for tx in block['tx']:
                if 'RegisterTransaction' == tx['type']:
                    global_assets[tx['txid']] = tx['asset']
                if 'InvocationTransaction' == tx['type'] and 490 <= int(float(tx['sys_fee'])):
                    if tx['script'].endswith('68134e656f2e436f6e74726163742e437265617465'):
                        try:
                            asset = self.parse_script(tx['script'])
                        except Exception as e:
                            print('parse error:',e)
                            continue
                        nep5_assets[asset['contract']] = asset
        if global_assets:
            await asyncio.wait([self.update_a_global_asset(*i) for i in global_assets.items()])
        if nep5_assets:
            await asyncio.wait([self.update_a_nep5_asset(*i) for i in nep5_assets.items()])


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

    a = Asset('asset', mysql_args, neo_uri, loop, super_node_uri, tasks)

    try:
        loop.run_until_complete(a.crawl())
    except Exception as e:
        logger.error('LOOP EXCEPTION: {}'.format(e.args[0]))
    finally:
        loop.close()
