#! /usr/bin/env python3
# coding: utf-8
# flow@SEA
# Licensed under the MIT License.

import sys
import math
import asyncio
from coreweb import get, post, options
from decimal import Decimal as D
from binascii import hexlify, unhexlify
from .tools import Tool, check_decimal, sci_to_str, big_or_little
from .assets import NEO, SEAS, SEAC, CSEAS, CSEAC, ONT_ASSETS
import logging
logging.basicConfig(level=logging.DEBUG)
from .decorator import *
from message import MSG


def valid_net(net, request):
    return net == request.app['net']

def valid_platform(platform):
    return platform in ['ios','android']

def valid_asset(asset):
    if asset.startswith('0x'): asset = asset[2:]
    if len(asset) in [40,64]: return True
    return False

def valid_swap_asset(asset, net):
    if asset not in [SEAS[net], SEAC[net]]:
        return False
    return True

def get_swap_asset_info(asset, net):
    if asset == SEAS[net]:
        return big_or_little(CSEAS[net][2:]), 'SEAS'
    return big_or_little(CSEAC[net][2:]), 'SEAC'

def valid_page_arg(index, length):
    try:
        index = int(index)
    except:
        return False, {'error':'wrong index'}
    try:
        length = int(length)
    except:
        return False, {'error':'wrong length'}
    if index < 0: return False, {'error':'wrong index'}
    if length <= 0 or length>100: return False, {'error':'wrong length'}
    return True, {'index':index, 'length':length}

def valid_domain(domain, request):
    domain = domain.split(".")
    if len(domain) < 2: return False
    if not domain[0]: return False
    if 'testnet' == request.app['net'] and domain[-1] not in ["test"]: return False
    if 'mainnet' == request.app['net'] and domain[-1] not in ["neo"]: return False
    return True

def get_asset_decimal(asset):
    return asset['decimals']

async def get_rpc(request,method,params):
    async with request.app['session'].post(request.app['neo_uri'],
            json={'jsonrpc':'2.0','method':method,'params':params,'id':1}) as resp:
        if 200 != resp.status:
            logging.error('Unable to visit %s %s' % (request.app['neo_uri'], method))
            return '404'
        j = await resp.json()
        if 'error' in j.keys():
            logging.error('result error when %s %s' % (request.app['neo_uri'], method))
            return '404'
        return j['result']

async def send_raw_transaction(tx, request):
    async with request.app['session'].post(request.app['neo_uri'],
            json={'jsonrpc':'2.0','method':'sendrawtransaction','params':[tx],'id':10}) as resp:
        method = 'sendrawtransaction'
        if 200 != resp.status:
            logging.error('Unable to visit %s %s' % (request.app['neo_uri'], method))
            return False,'404'
        j = await resp.json()
        if 'error' in j.keys():
            logging.error('result error when %s %s' % (request.app['neo_uri'], method))
            return False, j['error']['message']
        return j['result'],''

async def get_resolve_address(resolve_invoke, request):
    result = await get_rpc(request, 'invokescript', [resolve_invoke])
    if result and "HALT, BREAK" == result["state"]:
        hex_str = result['stack'][0]['value']
        if '00' != hex_str: return Tool.hex_to_string(hex_str)
        return ''
    return ''

async def get_rpc_ont(request,method,params):
    async with request.app['session'].post(request.app['ont_uri'],
            json={'jsonrpc':'2.0','method':method,'params':params,'id':1}) as resp:
        if 200 != resp.status:
            msg = 'Unable to visit %s %s' % (request.app['ont_uri'], method)
            logging.error(msg)
            return None,msg
        j = await resp.json()
        if 'SUCCESS' != j['desc']:
            msg = 'result error when %s %s:%s' % (request.app['ont_uri'], method, j['error'])
            logging.error(msg)
            return None,msg
        return j['result'],None

async def get_ont_balance(request, address, asset_name=None):
    result,err = await get_rpc_ont(request, 'getbalance', [address])
    if err or not result: return {'ont':"0",'ong':"0"}
    for i in result:
        if ONT_ASSETS[i]['decimal'] > 1:
            result[i] = sci_to_str(str(D(result[i])/D(math.pow(10, ONT_ASSETS[i]['decimal']))))
    if not asset_name: return result
    return result[asset_name]

async def get_mysql_cursor(pool):
    conn = await pool.acquire()
    cur  = await conn.cursor()
    return conn, cur

async def mysql_query_one(pool, sql):
    conn, cur = await get_mysql_cursor(pool)
    logging.info('SQL:%s' % sql)
    try:
        await cur.execute(sql)
        return await cur.fetchall()
    except Exception as e:
        logging.error("mysql QUERY failure:{}".format(e.args[0]))
        sys.exit(1)
    finally:
        await pool.release(conn)

async def mysql_get_block(pool, b):
    sql = "SELECT sys_fee,total_sys_fee FROM block WHERE height=%s;" % b
    r = await mysql_query_one(pool, sql)
    if r: return {'sys_fee':r[0][0], 'total_sys_fee':r[0][1]}
    return None

async def mysql_get_balance(request, address):
    assets = request.app['cache'].get('assets')
    sql = "SELECT asset,value FROM balance WHERE address='%s';" % address
    result = await mysql_query_one(request.app['pool'], sql)
    result = dict(result)
    balance = {}
    for g in assets['GLOBAL']:
        if g not in result.keys(): balance[g] = '0'
        else: balance[g] = result[g]
    for n in assets['NEP5']:
        if n not in result.keys(): balance[n] = '0'
        else: balance[n] = result[n]
    for o in assets['OEP4']:
        if o not in result.keys(): balance[n] = '0'
        else: balance[o] = result[o]
    return balance

async def mysql_get_all_unclaim_utxo(pool, address, height):
    sql = "SELECT txid,index_n,height,spent_txid,spent_height,value,status FROM utxos WHERE address='%s' AND asset='%s' AND claim_height IS NULL;" % (address, NEO[2:])
    result = {}
    r = await mysql_query_one(pool, sql)
    for i in r:
        if 0 == i[6]:#available
            result[i[0][2:]+'_'+str(i[1])] = {'startIndex':i[2],'stopHash':i[3],'stopIndex':i[4],'value':i[5],'status':True}
        else:#unavailable
            result[i[0][2:]+'_'+str(i[1])] = {'startIndex':i[2],'stopHash':'','stopIndex':height,'value':i[5],'status':False}
    return result

async def mysql_get_block_total_sys_fee(pool, heights):
    s = ''
    for i in range(len(heights)):
        if 0 == i: s += str(heights[i])
        else: s += ',' + str(heights[i])
    sql = "SELECT total_sys_fee FROM block WHERE height IN (%s);" % s
    result = {-1:0,0:0}
    r = await mysql_query_one(pool, sql)
    for i in range(len(heights)):
        result[heights[i]] = r[i][0]
    return result

async def mysql_get_nep5_asset_balance(pool, address, asset):
    sql = "SELECT value FROM balance WHERE address='%s' AND asset='%s';" % (address, asset)
    r = await mysql_query_one(pool, sql)
    if r: return r[0][0]
    return '0'

async def mysql_get_history(pool, address, asset, offset, length):
    if asset:
        if asset in ['0000000000000000000000000000000000000001','0000000000000000000000000000000000000002']:
            sql = "SELECT txid,timepoint,operation,value,asset FROM oep4_history WHERE address='%s' AND asset='%s' ORDER BY timepoint DESC limit %s,%s;" % (address, asset, offset, length)
        else:
            sql = "SELECT txid,timepoint,operation,value,asset FROM history WHERE address='%s' AND asset='%s' ORDER BY timepoint DESC limit %s,%s;" % (address, asset, offset, length)
    else:
        sql = "SELECT txid,timepoint,operation,value,asset FROM history WHERE address='%s' ORDER BY timepoint DESC limit %s,%s;" % (address, offset, length)
    result = []
    r = await mysql_query_one(pool, sql)
    for i in r:
        if 64==len(i[4]): result.append({'txid':i[0],'time':i[1],'asset':'0x'+i[4],'value':i[3],'operation':i[2]})
        else: result.append({'txid':i[0],'time':i[1],'asset':i[4],'value':i[3],'operation':i[2]})
    return result

async def mysql_get_ranks(pool, asset, offset, length):
    sql = "SELECT address,value FROM balance WHERE asset='%s' AND value<>'0' ORDER BY --value DESC limit %s,%s;" % (asset, offset, length)
    result = []
    r = await mysql_query_one(pool, sql)
    for i in r:result.append({'address':i[0],'balance':i[1]})
    return result

async def mysql_get_platform(pool, p):
    sql = "SELECT version,download_url,force_update,sha1,sha256,release_time,update_notes_zh,update_notes_en FROM platform WHERE name='%s' ORDER BY release_time DESC limit 1;" % p
    result = {'platform':p}
    r = await mysql_query_one(pool, sql)
    if r:
        result['version']           = r[0][0]
        result['download_url']      = r[0][1]
        result['force_update']      = False if r[0][2] == 0 else True
        result['sha1']              = r[0][3]
        result['sha256']            = r[0][4]
        result['release_time']      = str(r[0][5])
        result['update_notes_zh']   = r[0][6]
        result['update_notes_en']   = r[0][7]
    return result

async def mysql_get_utxo(pool, address, asset):
    if asset.startswith('0x'): asset = asset[2:]
    sql = "SELECT value,index_n,txid FROM utxos WHERE address='%s' AND asset='%s' AND status=1;" % (address,asset)
    result = []
    r = await mysql_query_one(pool, sql)
    for i in r:
        result.append({'value':i[0],'prevIndex':i[1],'prevHash':i[2][2:]})
    return result

async def mysql_insert_one(pool, sql):
    conn, cur = await get_mysql_cursor(pool)
    logging.info('SQL:%s' % sql)
    try:
        await cur.execute(sql)
        num = cur.rowcount
        return num
    except Exception as e:
        logger.error("mysql INSERT failure:{}".format(e.args[0]))
        sys.exit(1)
    finally:
        await pool.release(conn)

async def mysql_update_nep5(request, address):
    pool = request.app['pool']
    upt_height = request.app['cache'].get('height') - 1
    nep5 = get_all_nep5(request)
    sql = "INSERT IGNORE INTO upt(address,asset,update_height) VALUES ('%s','%s',%s)"
    data = [(address,n,upt_height) for n in nep5.keys()]
    await asyncio.gather(*[mysql_insert_one(pool, sql % d) for d in data])

def get_all_asset(request):
    return request.app['cache'].get('assets')

def get_old_all_asset(request):
    return request.app['cache'].get('old_assets')

def get_all_nep5(request):
    return request.app['cache'].get('assets')['NEP5']

def get_an_asset(i, request):
    if i.startswith('0x'): i = i[2:]
    assets = request.app['cache'].get('assets')
    if i in assets['GLOBAL'].keys(): return assets['GLOBAL'][i]
    if i in assets['NEP5'].keys(): return assets['NEP5'][i]
    if i in assets['OEP4'].keys(): return assets['OEP4'][i]
    return None



@format_result(['net'])
@get('/v2/{net}/height')
async def height_v2(net, request):
    request['result']['data'] = {'height':request.app['cache'].get('height')}

@format_result(['net'])
@get('/v2/{net}/asset')
async def asset_v2(net, request, *, asset=0):
    if 0 == asset: request['result']['data'] = get_all_asset(request)
    else:
        if asset.startswith('0x'): asset = asset[2:]
        if not valid_asset(asset): request['result'].update(MSG['WRONG_ASSET'])
        r = get_an_asset(asset, request)
        if r: request['result']['data'] = {asset:r}
        else: request['result']['data'].update(MSG['WRONG_ASSET'])

@format_result(['net','address'])
@get('/v2/{net}/address/{address}')
async def address_v2(net, address, request):
    data = []
    xresult = await asyncio.gather(
                mysql_get_balance(request, address),
                get_ont_balance(request, address),
                mysql_update_nep5(request, address)
            )
    assets = get_all_asset(request)
    for i in xresult[0]:
        if i in assets['GLOBAL'].keys():
            d = assets['GLOBAL'][i]
            d['chain'] = "NEO"
            d['id'] = i
            d['balance'] = xresult[0][i]
            data.append(d)
        if i in assets['NEP5'].keys():
            d = assets['NEP5'][i]
            d['chain'] = "NEO"
            d['id'] = i
            d['balance'] = xresult[0][i]
            data.append(d)
    data.append({'chain':"ONT",'type':"OEP4","name":"ONT","symbol":"ONT","decimals":0,'id':ONT_ASSETS['ont']['scripthash'],'balance':xresult[1]['ont']})
    data.append({'chain':"ONT",'type':"OEP4","name":"ONG","symbol":"ONG","decimals":9,'id':ONT_ASSETS['ong']['scripthash'],'balance':xresult[1]['ong']})
    request['result']['data'] = data

@format_result(['net','address'])
@get('/v2/{net}/claim/{address}')
async def claim_v2(net, address, request):
    data = {}
    height = request.app['cache'].get('height')
    claims = await mysql_get_all_unclaim_utxo(request.app['pool'], address, height)
    if claims:
        heights = list(set(
            [v['startIndex']-1 for v in claims.values() if v['startIndex'] != 0] + 
            [v['stopIndex']-1 for v in claims.values()]))
        heights.sort()
        fees = await mysql_get_block_total_sys_fee(request.app['pool'], heights)
        request['result']['data'] = await Tool.compute_gas(claims, fees)
    else:
        request['result']['data'] = {'available':'0', 'unavailable':'0', 'claims':[]}

@format_result(['net','address'])
@get('/v2/{net}/claim/seas/{address}')
async def claim_seas_v2(net, address, request):
    assetId = CSEAS[net][2:]
    asset = get_an_asset(assetId, request)
    ad = get_asset_decimal(asset)
    balance = D(await mysql_get_nep5_asset_balance(request.app['pool'], address, assetId))
    if balance > 0:
        bstorage = await get_rpc(request, 'getstorage', [CSEAS[net], Tool.address_to_scripthash(address)])
        bheight = bstorage[16:]
        bheight = D(Tool.hex_to_num_str(bheight,ad))
        height = request.app['cache'].get('height') - 1
        bonus = (height - bheight) * 6 * balance / 100000000
        request['result']['data'] = {'available':sci_to_str(str(bonus)),'unavailable':'0'}
    else:
        request['result']['data'] = {'available':'0', 'unavailable':'0'}

@format_result(['net','address'])
@get('/v2/{net}/history/{address}')
async def history_v2(net, address, request, *, asset=0, index=0, length=20):
    result,info = valid_page_arg(index, length)
    if not result: request['result'].update(MSG['WRONG_ARGUMENT']);return
    index, length = info['index'], info['length']
    raw_utxo = []
    if 0 != asset:
        if asset.startswith('0x'): asset = asset[2:]
        if not valid_asset(asset): request['result'].update(MSG['WRONG_ASSET']);return
    else: asset = None
    result = await mysql_get_history(request.app['pool'], address, asset, index, length)
    request['result']['data'] = result

@format_result(['net','platform'])
@get('/v2/{net}/version/{platform}')
async def version_v2(net, platform, request):
    info = await mysql_get_platform(request.app['pool'], platform)
    if info: request['result']['data'] = info
    else: request['result'].update(MSG['WRONG_PLATFORM'])

@format_result(['net','domain'])
@get('/v2/{net}/resolve/{domain}')
async def resolve_v2(net, domain, request):
    namehash = Tool.nns_namehash(domain)
    resolve_invoke = Tool.nns_resolve_invoke(namehash)
    address = await get_resolve_address(resolve_invoke, request)
    if not address: request['result'].update(MSG['NOT_RESOLVED'])
    else: request['result']['data'] = {'address':address}

@format_result(['net','address'])
@get('/v2/{net}/swap/{address}/{asset}')
async def swap_v2(net, address, asset, request):
    if not asset.startswith('0x'): asset = '0x' + asset
    if not valid_swap_asset(asset, net): return {'result':False, 'error':'wrong asset'}
    sh_asset, name = get_swap_asset_info(asset, net)
    utxo = await mysql_get_utxo(request.app['pool'], address, asset)
    if not utxo: request['result'].update(MSG['INSUFFICIENT_BALANCE'])
    balance = sum([D(i['value']) for i in utxo])
    items = [(Tool.scripthash_to_address(unhexlify(sh_asset)), balance)]
    transaction,result,msg = Tool.transfer_global(address, utxo, items, asset[2:])
    if result:
        itx = 'd10121000a6d696e74546f6b656e7367' + sh_asset + '0000000000000000'
        if 'SEAC' == name:
            itx += '0120' + Tool.address_to_scripthash(address)
        else:
            itx += '0220' + Tool.address_to_scripthash(address) + '20' + sh_asset
        transaction = itx + transaction[6:]
        request['result']['data'] = {'transaction':transaction}
    else:
        request['result'].update(MSG['UNKNOWN_ERROR'])
        request['result']['message'] += ':'+msg

@format_result(['net'])
@get('/v2/{net}/rankings/{asset}')
async def rankings_v2(net, asset, request, *, index=0, length=100):
    result,info = valid_page_arg(index, length)
    if not result: request['result'].update(MSG['WRONG_ARGUMENT']);return
    index, length = info['index'], info['length']
    if asset.startswith('0x'): asset = asset[2:]
    if not valid_asset(asset): request['result'].update(MSG['WRONG_ASSET']);return
    request['result']['data'] = await mysql_get_ranks(request.app['pool'], asset, index, length)

@format_result(['net'])
@post('/v2/{net}/transfer')
async def transfer_v2(net, request, *, source, dests, amounts, assetId, **kw):
    #params validation
    if not Tool.validate_address(source): request['result'].update(MSG['WRONG_ARGUMENT']);return
    if assetId.startswith('0x'): assetId = assetId[2:]
    if not valid_asset(assetId): request['result'].update(MSG['WRONG_ARGUMENT']);return
    asset = get_an_asset(assetId, request)
    if not asset: request['result'].update(MSG['WRONG_ARGUMENT']);return
    nep5_asset = global_asset = False
    if 40 == len(assetId): nep5_asset = True
    if 64 == len(assetId): global_asset = True
    ad = get_asset_decimal(asset)
    dests,amounts = dests.split(','), amounts.split(',')
    ld,la = len(dests), len(amounts)
    if ld != la: request['result'].update(MSG['WRONG_ARGUMENT']);return
    if nep5_asset and 1 != ld: request['result'].update(MSG['WRONG_ARGUMENT']);return
    if False in map(Tool.validate_address, dests): request['result'].update(MSG['WRONG_ARGUMENT']);return
    try:
        amounts = [D(a) for a in amounts]
    except:
        request['result'].update(MSG['WRONG_ARGUMENT']);return
    if [a for a in amounts if a <= D(0)]: request['result'].update(MSG['WRONG_ARGUMENT']);return
    if False in [check_decimal(a,ad) for a in amounts]: request['result'].update(MSG['WRONG_ARGUMENT']);return
    #check balance && transaction
    tran_num = sum(amounts)
    if nep5_asset:
        balance = D(await mysql_get_nep5_asset_balance(request.app['pool'], source, assetId))
        if balance < tran_num: request['result'].update(MSG['INSUFFICIENT_BALANCE']);return
        transaction = Tool.transfer_nep5(assetId, source, dests[0], amounts[0], ad)
        result,msg = True,''
    if global_asset:
        utxo = await mysql_get_utxo(request.app['pool'], source, assetId)
        balance = sum([D(i['value']) for i in utxo])
        if balance < tran_num: request['result'].update(MSG['INSUFFICIENT_BALANCE']);return
        items = [(dests[i],amounts[i]) for i in range(len(dests))]
        transaction,result,msg = Tool.transfer_global(source, utxo, items, assetId)
    if result:
        request['result']['data'] = {'transaction':transaction}
    else:
        request['result'].update(MSG['UNKNOWN_ERROR'])
        request['result']['message'] += ':'+msg

@format_result(['net'])
@post('/v2/{net}/gas')
async def gas_v2(net, request, *, publicKey, **kw):
    #params validation
    if not Tool.validate_cpubkey(publicKey): request['result'].update(MSG['WRONG_ARGUMENT']);return
    #get gas
    address = Tool.cpubkey_to_address(publicKey)
    raw_utxo = []
    height = request.app['cache'].get('height')
    claims = await mysql_get_all_unclaim_utxo(request.app['pool'], address, height)
    if claims:
        heights = list(set(
            [v['startIndex']-1 for v in claims.values() if v['startIndex'] != 0] + 
            [v['stopIndex']-1 for v in claims.values()]))
        heights.sort()
        fees = await mysql_get_block_total_sys_fee(request.app['pool'], heights)
        details = await Tool.compute_gas(claims, fees)
        tx,result,msg = Tool.claim_transaction(address, details)
    if result: request['result']['data'] = {'transaction':tx}
    else: request['result'].update(MSG['NO_CLAIM_GAS'])

@format_result(['net'])
@post('/v2/{net}/broadcast')
async def broadcast_v2(net, request, *, publicKey, signature, transaction):
    #params validation
    if not Tool.validate_cpubkey(publicKey): request['result'].update(MSG['WRONG_ARGUMENT']);return
    result,msg = Tool.verify(publicKey, signature, transaction)
    if not result: request['result'].update(MSG['WRONG_ARGUMENT']);return
    txid = Tool.compute_txid(transaction)
    sh_seas = big_or_little(CSEAS[net][2:])
    if transaction.startswith('d10121000a6d696e74546f6b656e7367'+sh_seas):
        tx1,tx2 = Tool.get_transaction_for_swap_seas(publicKey, signature, transaction)
        r = await asyncio.gather(*[send_raw_transaction(t, request) for t in [tx1, tx2]])
        for i in range(2):
            result,msg = r[i]
            if result: request['result']['data'] = {'txid':txid};return
    else:
        tx = Tool.get_transaction(publicKey, signature, transaction)
        result,msg = await send_raw_transaction(tx, request)
        if result: request['result']['data'] = {'txid':txid};return
    request['result'].update(MSG['UNKNOWN_ERROR'])
    request['result']['message'] += ':'+msg

@options('/v2/{net}/transfer')
async def transfer_v2_options(net, request):
    if not valid_net(net, request): return {'result':False, 'error':'wrong net'}
    return 'OK'
@options('/v2/{net}/gas')
async def gas_v2_options(net, request):
    if not valid_net(net, request): return {'result':False, 'error':'wrong net'}
    return 'OK'
@options('/v2/{net}/broadcast')
async def broadcast_v2_options(net, request):
    if not valid_net(net, request): return {'result':False, 'error':'wrong net'}
    return 'OK'
