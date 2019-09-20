# /usr/bin/env python3
# coding: utf-8
# flow@SEA
# Licensed under the MIT License.

import time
import asyncio
import datetime
import binascii
from decimal import Decimal as D
from coreweb import get, post, options
import logging
logging.basicConfig(level=logging.DEBUG)
from .decorator import *
from .tools import Tool
from .assets import GAS
from message import MSG

SEAC = 'f735eb717f2f31dfc8d12d9df379da9b198b2045'
#RECEIVE = 'AU6WPAYiTFtay8QJqsYVGhZ6gbBwnKPxkf'
RECEIVE = 'Acs3FHua5pTUVrJjdYEZRR7j86YvDejc4h' #test
AMOUNTS = ['1000', '3000', '5000', '10000']
DAYS = ['30', '90', '180', '360']
OPERATION_REACTIVE_NODE = 5

def valid_net(net, request):
    return net == request.app['net']

def valid_amount(amount):
    try:
        amount = int(amount)
    except:
        return False
    if amount <= 0: return False
    return True

def valid_msg(msg):
    lm = len(msg)
    if lm % 2 != 0 or lm > 20: return False
    try:
        m = binascii.unhexlify(msg)
    except:
        return False
    return True

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

async def get_mysql_cursor(pool):
    conn = await pool.acquire()
    cur  = await conn.cursor()
    return conn, cur

async def mysql_insert_one(pool, sql):
    conn, cur = await get_mysql_cursor(pool)
    logging.info('SQL:%s' % sql)
    try:
        await cur.execute(sql)
        num = cur.rowcount
        return num
    except Exception as e:
        logging.error("mysql INSERT failure:{}".format(e))
        return 0
    finally:
        await pool.release(conn)

async def mysql_query_one(pool, sql):
    conn, cur = await get_mysql_cursor(pool)
    logging.info('SQL:%s' % sql)
    try:
        await cur.execute(sql)
        return await cur.fetchall()
    except Exception as e:
        logging.error("mysql QUERY failure:{}".format(e))
        return None
    finally:
        await pool.release(conn)

async def mysql_get_node_status(pool, address):
    sql = "SELECT status,referrer,amount,days,referrals,performance,nodelevel,penalty,teamlevelinfo,burned,smallareaburned,signin FROM node WHERE address = '%s';" % address
    r = await mysql_query_one(pool, sql)
    if r: return {
                'status':r[0][0],
                'referrer':r[0][1],
                'amount':r[0][2],
                'days':r[0][3],
                'referrals':r[0][4],
                'performance':r[0][5],
                'nodelevel':r[0][6],
                'penalty':r[0][7],
                'teamlevelinfo':r[0][8],
                'burned':r[0][9],
                'smallareaburned':r[0][10],
                'signin':r[0][11]
                }
    return None

async def mysql_query_node_exist(pool, address):
    sql = "SELECT address FROM node WHERE address='%s';" % address
    r = await mysql_query_one(pool, sql)
    if r: return True
    return None

async def mysql_query_node_status(pool, address):
    sql = "SELECT status FROM node WHERE address='%s';" % address
    r = await mysql_query_one(pool, sql)
    if r:
        status = r[0][0]
        if status == -7: return 'UNLOCK_ENSURED'
        if status in [-6,-5]: return 'UNLOCKING'
        if status == -4: return 'EXIT_ENSURED'
        if status in [-3, -2]: return 'EXITING'
        if status == -1: return 'CREATING'
        if status >= 0: return 'ACTIVE'
    return None

async def mysql_query_node_update_exist(pool, address):
    sql = "SELECT address FROM node_update WHERE address='%s';" % address
    r = await mysql_query_one(pool, sql)
    if r: return True
    return None

async def mysql_node_can_unlock(pool, address):
    sql = "SELECT status,days FROM node WHERE address='%s';" % address
    r = await mysql_query_one(pool, sql)
    if r:
        status,days = r[0][0],r[0][1]
        if status < 0: return False
        if status >= days: return False
        return True
    return False

async def mysql_node_can_signin(pool, address):
    sql = "SELECT signin FROM node WHERE address='%s';" % address
    r = await mysql_query_one(pool, sql)
    if r: return r[0][0] == 1
    return False

async def mysql_get_node_bonus_remain(pool, address):
    sql = "SELECT remain FROM node_bonus WHERE address='%s' ORDER BY bonustime DESC limit 1;" % address
    r = await mysql_query_one(pool, sql)
    if r: return r[0][0]
    return '0'

async def mysql_get_node_bonus_history(pool, address, offset, length):
    sql = "SELECT lockedbonus,teambonus,signinbonus,amount,total,remain,bonustime FROM node_bonus WHERE address='%s' ORDER BY bonustime DESC limit %s,%s;" % (address, offset, length)
    r = await mysql_query_one(pool, sql)
    if r: return [{'lockedbonus':i[0],'teambonus':i[1],'signinbonus':i[2],'amount':i[3],'total':i[4],'remain':i[5],'bonustime':i[6]} for i in r]
    return []

async def mysql_get_nep5_asset_balance(pool, address, asset):
    sql = "SELECT value FROM balance WHERE address='%s' AND asset='%s';" % (address, asset)
    r = await mysql_query_one(pool, sql)
    if r: return r[0][0]
    return '0'

async def mysql_get_utxo(pool, address, asset):
    if asset.startswith('0x'): asset = asset[2:]
    sql = "SELECT value,index_n,txid FROM utxos WHERE address='%s' AND asset='%s' AND status=1;" % (address,asset)
    r = await mysql_query_one(pool, sql)
    if r: return [{'value':i[0],'prevIndex':i[1],'prevHash':i[2][2:]} for i in r]
    return []

async def cache_utxo(request, txid, utxos):
    cache = request.app['cache']
    if len(utxos) ==0: return
    if cache.has(txid): cache.delete(txid)
    cache.set(txid, utxos, ttl=120)

async def cache_node_exist(request, address):
    return request.app['cache'].has(address)

async def cache_node_info(request, address, info):
    cache = request.app['cache']
    if cache.has(address): return False
    cache.set(address, info, ttl=120)
    return True

async def get_node_info_from_cache(request, address):
    cache = request.app['cache']
    if cache.has(address): return cache.get(address)
    return None

async def mysql_freeze_utxo(request, txid):
    cache = request.app['cache']
    utxos = cache.get(txid, [])
    if utxos:
        pool = request.app['pool']
        sql = "UPDATE utxos SET status=2 where txid='%s' and index_n=%s and status=1"
        data = [('0x'+u['prevHash'],u['prevIndex']) for u in utxos]
        await asyncio.gather(*[mysql_insert_one(pool, sql % d) for d in data])
        cache.delete(txid)

def compute_penalty(amount, days):
    if 1000 == amount:
        if 30 == days: return 0     # 0%
        if 90 == days: return 80    # 8%
        if 180 == days: return 130  # 13%
        if 360 == days: return 230  # 23%
    if 3000 == amount:
        if 30 == days: return 180   # 6%
        if 90 == days: return 270   # 9%
        if 180 == days: return 420  # 14%
        if 360 == days: return 780  # 26%
    if 5000 == amount:
        if 30 == days: return 350   # 7%
        if 90 == days: return 500   # 10%
        if 180 == days: return 750  # 15%
        if 360 == days: return 1500 # 30%
    if 10000 == amount:
        if 30 == days: return 800   # 8%
        if 90 == days: return 1100  # 11%
        if 180 == days: return 1800 # 18%
        if 360 == days: return 3600 # 36%
    raise ValueError("Wrong amount and days %s - %s".format(amount, days))

def get_now_timepoint():
    return str(time.mktime(datetime.datetime.now().timetuple())).split('.')[0]

async def mysql_node_update_new_node(pool, address, referrer, amount, days, txid, operation):
    penalty = compute_penalty(int(amount), int(days))
    timepoint = get_now_timepoint()
    sql = "INSERT INTO node_update(address,operation,referrer,amount,days,penalty,txid,timepoint) VALUES ('%s',%s,'%s','%s',%s,%s,'%s',%s)" % (address,operation,referrer,amount,days,penalty,txid,timepoint)
    n = await mysql_insert_one(pool, sql)
    if n: return True
    return False

async def mysql_node_update_unlock(pool, address):
    timepoint = get_now_timepoint()
    sql = "INSERT INTO node_update(address,operation,timepoint) VALUES ('%s',2,%s)" % (address,timepoint)
    n = await mysql_insert_one(pool, sql)
    if n: return True
    return False

async def mysql_node_update_withdraw(pool, address, amount):
    timepoint = get_now_timepoint()
    sql = "INSERT INTO node_update(address,operation,amount,timepoint) VALUES ('%s',3,'%s',%s);" % (address,amount,timepoint)
    n = await mysql_insert_one(pool, sql)
    if n: return True
    return False

async def mysql_node_update_signin(pool, address):
    timepoint = get_now_timepoint()
    sql = "INSERT INTO node_update(address,operation,timepoint) VALUES ('%s',4,%s);" % (address,timepoint)
    n = await mysql_insert_one(pool, sql)
    if n: return True
    return False

async def mysql_node_signature_add(pool, address, signature):
    sql = "INSERT INTO node_signature(address,signature) VALUES ('%s','%s');" % (address, signature)
    n = await mysql_insert_one(pool, sql)
    if n: return True
    return False


@format_result(['net','address'])
@get('/v2/{net}/node/status/{address}')
async def node_status(net, address, request):
    pool = request.app['pool']
    s = await mysql_get_node_status(pool, address)
    if s is None:
        request['result'].update(MSG['NODE_NOT_EXIST'])
    else:
        request['result']['data'] = s

@format_result(['net'])
@post('/v2/{net}/node/new')
async def node_new(net, request, *, referrer, amount, days, publicKey, signature, message):
    if not valid_msg(message): request['result'].update(MSG['WRONG_ARGUMENT_MESSAGE']);return
    result,_ = Tool.verify(publicKey, signature, message)
    if not result: request['result'].update(MSG['WRONG_ARGUMENT_SIGNATURE']);return
    if days not in DAYS: request['result'].update(MSG['WRONG_ARGUMENT']);return
    if amount not in AMOUNTS: request['result'].update(MSG['WRONG_ARGUMENT']);return
    if not Tool.validate_address(referrer): request['result'].update(MSG['WRONG_ARGUMENT']);return
    address = Tool.cpubkey_to_address(publicKey)
    pool = request.app['pool']
    result = await mysql_node_signature_add(pool, address, signature)
    if not result: request['result'].update(MSG['SIGNATURE_ALREADY_EXIST']);return
    if await cache_node_exist(request, address): request['result'].update(MSG['NODE_CREATING']);return
    operation = 1
    s = await mysql_query_node_status(pool, address)
    if address == referrer: #whole new top node or active old node
        if s in ['UNLOCK_ENSURED', 'EXIT_ENSURED']: operation = OPERATION_REACTIVE_NODE
        elif s is not None: request['result'].update(MSG['NODE_WAIT_PROCESS']);return
    else: #whole new but not the top
        if s is not None: request['result'].update(MSG['NODE_ALREADY_EXIST']);return
        rs = await mysql_query_node_status(pool, referrer)
        if rs is None: request['result'].update(MSG['REFERRER_NODE_NOT_EXIST']);return
    aeu = await mysql_query_node_update_exist(pool, address)
    if aeu: request['result'].update(MSG['WAIT_OTHER_OPERATION']);return
    fee = D('0.001')
    fee_utxos = []
    freeze_utxos = []
    balance = D(await mysql_get_nep5_asset_balance(pool, address, SEAC))
    if balance < D(amount): request['result'].update(MSG['INSUFFICIENT_BALANCE']);return
    transaction = Tool.transfer_nep5(SEAC, address, RECEIVE, D(amount))
    fee_utxos = await mysql_get_utxo(pool, address, GAS[2:])
    fee_balance = sum([D(i['value']) for i in fee_utxos])
    if fee_balance < fee: request['result'].update(MSG['INSUFFICIENT_FEE']);return
    fee_transaction,spent_utxos,msg = Tool.transfer_global_with_fee(address, [], [], '', fee, fee_utxos, GAS[2:])
    if spent_utxos: freeze_utxos.extend(spent_utxos)
    else:
        request['result'].update(MSG['UNKNOWN_ERROR'])
        request['result']['message'] += ':'+msg
        return 
    transaction = transaction[0:-4] + fee_transaction[6:]
    txid = Tool.compute_txid(transaction)
    info = {'referrer':referrer,'amount':amount,'days':days, 'txid':txid, 'operation':operation}
    result = await cache_node_info(request, address, info)
    if not result:
        request['result'].update(MSG['UNKNOWN_ERROR'])
        request['result']['message'] += ':'+'node is in creating,please wait'
        return 
    await cache_utxo(request, txid, freeze_utxos)
    request['result']['data'] = {'transaction':transaction}

@format_result(['net'])
@post('/v2/{net}/node/broadcast')
async def node_broadcast(net, request, *, publicKey, signature, transaction):
    result,_ = Tool.verify(publicKey, signature, transaction)
    if not result: request['result'].update(MSG['WRONG_ARGUMENT_SIGNATURE']);return
    address = Tool.cpubkey_to_address(publicKey)
    info = await get_node_info_from_cache(request, address)
    if info is None: request['result'].update(MSG['NODE_CREATE_TIMEOUT']);return
    txid = info['txid']
    if txid != Tool.compute_txid(transaction): request['result'].update(MSG['WRONG_ARGUMENT']);return
    pool = request.app['pool']
    #broadcast
    tx = Tool.get_transaction(publicKey, signature, transaction)
    #result,msg = await send_raw_transaction(tx, request)
    result,msg = True,'' #test
    if result:
        await mysql_freeze_utxo(request, txid)
        result  = await mysql_node_update_new_node(pool, address, info['referrer'], info['amount'], info['days'], info['txid'], info['operation'])
        if not result:
            request['result'].update(MSG['UNKNOWN_ERROR'])
            request['result']['message'] += ':'+'node create failure'
            return 
        request['result']['data'] = {'txid':txid};return

@format_result(['net'])
@post('/v2/{net}/node/unlock')
async def node_unlock(net, request, *, publicKey, signature, message):
    if not valid_msg(message): request['result'].update(MSG['WRONG_ARGUMENT_MESSAGE']);return
    result,_ = Tool.verify(publicKey, signature, message)
    if not result: request['result'].update(MSG['WRONG_ARGUMENT_SIGNATURE']);return
    address = Tool.cpubkey_to_address(publicKey)
    if await cache_node_exist(request, address): request['result'].update(MSG['NODE_CREATING']);return
    pool = request.app['pool']
    result = await mysql_node_signature_add(pool, address, signature)
    if not result: request['result'].update(MSG['SIGNATURE_ALREADY_EXIST']);return
    aeu = await mysql_query_node_update_exist(pool, address)
    if aeu: request['result'].update(MSG['WRONG_ARGUMENT']);return
    r = await mysql_node_can_unlock(pool, address)
    if not r: request['result'].update(MSG['WRONG_ARGUMENT']);return
    result  = await mysql_node_update_unlock(pool, address)
    if not result:
        request['result'].update(MSG['UNKNOWN_ERROR'])
        request['result']['message'] += ':'+'node unlock failure'
        return 

@format_result(['net','address'])
@get('/v2/{net}/node/details/{address}')
async def node_details(net, address, request, *, index=0, length=100):
    result,info = valid_page_arg(index, length)
    if not result: request['result'].update(MSG['WRONG_ARGUMENT']);return
    index, length = info['index'], info['length']
    pool = request.app['pool']
    h = await mysql_get_node_bonus_history(pool, address, index, length)
    request['result']['data'] = {'total':'0','history':[]}
    if h:
        request['result']['data']['total'] = h[0]['total']
        request['result']['data']['history'] = h

@format_result(['net'])
@post('/v2/{net}/node/withdraw')
async def node_withdraw(net, request, *, amount, publicKey, signature, message):
    if not valid_amount(amount): request['result'].update(MSG['WRONG_ARGUMENT']);return
    amount = int(amount)
    if not valid_msg(message): request['result'].update(MSG['WRONG_ARGUMENT_MESSAGE']);return
    result,_ = Tool.verify(publicKey, signature, message)
    if not result: request['result'].update(MSG['WRONG_ARGUMENT_SIGNATURE']);return
    address = Tool.cpubkey_to_address(publicKey)
    if await cache_node_exist(request, address): request['result'].update(MSG['NODE_CREATING']);return
    pool = request.app['pool']
    result = await mysql_node_signature_add(pool, address, signature)
    if not result: request['result'].update(MSG['SIGNATURE_ALREADY_EXIST']);return
    aeu = await mysql_query_node_update_exist(pool, address)
    if aeu: request['result'].update(MSG['WRONG_ARGUMENT']);return
    r = D(await mysql_get_node_bonus_remain(pool, address))
    if r < amount: request['result'].update(MSG['WRONG_ARGUMENT']);return
    result  = await mysql_node_update_withdraw(pool, address, amount)
    if not result:
        request['result'].update(MSG['UNKNOWN_ERROR'])
        request['result']['message'] += ':'+'node withdraw failure'
        return 

@format_result(['net'])
@post('/v2/{net}/node/signin')
async def node_signin(net, request, *, publicKey, signature, message):
    if not valid_msg(message): request['result'].update(MSG['WRONG_ARGUMENT_MESSAGE']);return
    result,_ = Tool.verify(publicKey, signature, message)
    if not result: request['result'].update(MSG['WRONG_ARGUMENT_SIGNATURE']);return
    address = Tool.cpubkey_to_address(publicKey)
    if await cache_node_exist(request, address): request['result'].update(MSG['NODE_CREATING']);return
    pool = request.app['pool']
    result = await mysql_node_signature_add(pool, address, signature)
    if not result: request['result'].update(MSG['SIGNATURE_ALREADY_EXIST']);return
    aeu = await mysql_query_node_update_exist(pool, address)
    if aeu: request['result'].update(MSG['WRONG_ARGUMENT']);return
    r = await mysql_node_can_signin(pool, address)
    if not r: request['result'].update(MSG['WRONG_ARGUMENT']);return
    result  = await mysql_node_update_signin(pool, address, amount)
    if not result:
        request['result'].update(MSG['UNKNOWN_ERROR'])
        request['result']['message'] += ':'+'node signin failure'
        return 


@options('/v2/{net}/node/new')
async def node_new_options(net, request):
    if not valid_net(net, request): return {'result':False, 'error':'wrong net'}
    return 'OK'
@options('/v2/{net}/node/broadcast')
async def node_broadcast_options(net, request):
    if not valid_net(net, request): return {'result':False, 'error':'wrong net'}
    return 'OK'
@options('/v2/{net}/node/unlock')
async def node_unlock_options(net, request):
    if not valid_net(net, request): return {'result':False, 'error':'wrong net'}
    return 'OK'
@options('/v2/{net}/node/withdraw')
async def node_withdraw_options(net, request):
    if not valid_net(net, request): return {'result':False, 'error':'wrong net'}
    return 'OK'
@options('/v2/{net}/node/signin')
async def node_signin_options(net, request):
    if not valid_net(net, request): return {'result':False, 'error':'wrong net'}
    return 'OK'
