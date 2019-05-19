#! /usr/bin/env python3
# coding: utf-8
# flow@SEA
# Licensed under the MIT License.

import math
import datetime
from decimal import Decimal as D
from coreweb import get, post, options
from .tools import Tool, check_decimal, sci_to_str, big_or_little
import logging
logging.basicConfig(level=logging.DEBUG)
from .decorator import *
from message import MSG


assets = {
        'ont':{
            'scripthash':'0000000000000000000000000000000000000001',
            'decimal':1
            },
        'ong':{
            'scripthash':'0000000000000000000000000000000000000002',
            'decimal':9
            },
        }
UNBOUND_TIME_INTERVAL = 31536000
UNBOUND_GENERATION_AMOUNT = [5, 4, 3, 3, 2, 2, 2, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1]
ONT_TOTAL_SUPPLY = 1000000000
ONG_TOTAL_SUPPLY = 1000000000

def unbound_deadline():
    count = sum(UNBOUND_GENERATION_AMOUNT)*UNBOUND_TIME_INTERVAL
    num_interval = len(UNBOUND_GENERATION_AMOUNT)
    return UNBOUND_TIME_INTERVAL*num_interval - (count - ONG_TOTAL_SUPPLY)

UNBOUND_DEADLINE = unbound_deadline()

def valid_net(net, request):
    return net == request.app['net']

def get_asset_name(aid):
    for a in assets:
        if aid == assets[a]['scripthash']:
            return a
    return ''

def get_asset_decimal(aname):
    return assets[aname]['decimal']

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
        if assets[i]['decimal'] > 1:
            result[i] = sci_to_str(str(D(result[i])/D(math.pow(10, assets[i]['decimal']))))
    if not asset_name: return result
    return result[asset_name]

async def get_unclaim_ong(request, address):
    result,err = await get_rpc_ont(request, 'getunboundong', [address])
    if err or not result: return "0"
    return sci_to_str(str(D(result)/D(math.pow(10, assets['ong']['decimal']))))

get_now_timestamp = lambda:int(datetime.datetime.now().timestamp())

async def get_unbound_offset(request, address):
    #756e626f756e6454696d654f6666736574 = unboundTimeOffset
    result,err = await get_rpc_ont(request, 'getstorage',
            ['0100000000000000000000000000000000000000',
                '756e626f756e6454696d654f6666736574'+Tool.address_to_scripthash(address)])
    if err or not result: return 0
    return int(big_or_little(result),16)

async def compute_ong(request,address):
    start_offset = await get_unbound_offset(request, address)
    if not start_offset: return "0"
    gbt = request.app['ont_genesis_block_timestamp']
    now = get_now_timestamp()
    end_offset = get_now_timestamp() - gbt
    if end_offset <= start_offset: return "0"
    b = await get_ont_balance(request, address)
    b_ont = b['ont']
    if D(b_ont) <= 0: return "0"
    amount = 0
    if start_offset < UNBOUND_DEADLINE:
        ustart = start_offset // UNBOUND_TIME_INTERVAL
        istart = start_offset % UNBOUND_TIME_INTERVAL
        if end_offset >= UNBOUND_DEADLINE:
            end_offset = UNBOUND_DEADLINE
        uend = end_offset // UNBOUND_TIME_INTERVAL
        iend = end_offset % UNBOUND_TIME_INTERVAL
        while ustart < uend:
            amount += (UNBOUND_TIME_INTERVAL - istart) * UNBOUND_GENERATION_AMOUNT[ustart]
            ustart += 1
            istart = 0
        amount += (iend - istart) * UNBOUND_GENERATION_AMOUNT[ustart]
    return sci_to_str(str(amount * D(b_ont) / D(ONT_TOTAL_SUPPLY)))

async def ont_send_raw_transaction(tx, request):
    return await get_rpc_ont(request, 'sendrawtransaction', [tx])

@format_result(['net'])
@get('/v2/{net}/height/ont')
async def height_ont_v2(net, request):
    height,err = await get_rpc_ont(request,'getblockcount',[])
    if err or not height:
        request['result'].update(MSG['UNKNOWN_ERROR'])
        request['result']['message'] += ':Unable to get Ontology height'
    else:
        request['result']['data'] = {'height':height}

@format_result(['net','address'])
@get('/v2/{net}/claim/ont/{address}')
async def claim_ont_v2(net, address, request):
    request['result']['data'] = {'available':await get_unclaim_ong(request, address), "unavailable":await compute_ong(request, address)}

@format_result(['net'])
@post('/v2/{net}/transfer/ont')
async def transfer_ont_v2(net, request, *, source, dests, amounts, assetId, **kw):
    #params validation
    if not Tool.validate_address(source): request['result'].update(MSG['WRONG_ARGUMENT']);return
    if assetId.startswith('0x'): assetId = assetId[2:]
    aname = get_asset_name(assetId)
    if not aname: request['result'].update(MSG['WRONG_ARGUMENT']);return
    ad = get_asset_decimal(aname)
    dests,amounts = dests.split(','), amounts.split(',')
    ld,la = len(dests), len(amounts)
    if ld != la: request['result'].update(MSG['WRONG_ARGUMENT']);return
    if 1 != ld: request['result'].update(MSG['WRONG_ARGUMENT']);return
    if False in map(Tool.validate_address, dests): request['result'].update(MSG['WRONG_ARGUMENT']);return
    try:
        amounts = [D(a) for a in amounts]
    except:
        request['result'].update(MSG['WRONG_ARGUMENT']);return
    if [a for a in amounts if a <= D(0)]: request['result'].update(MSG['WRONG_ARGUMENT']);return
    if False in [check_decimal(a,ad) for a in amounts]: request['result'].update(MSG['WRONG_ARGUMENT']);return
    #check balance && transaction
    tran_num = sum(amounts)
    balance = D(await get_ont_balance(request, source, aname))
    if 'ong' == aname:
        if balance < tran_num + D('0.01'): request['result'].update(MSG['INSUFFICIENT_BALANCE']);return
    else:
        ong_balance = D(await get_ont_balance(request, source, 'ong'))
        if ong_balance < D('0.01'): request['result'].update(MSG['INSUFFICIENT_BALANCE']);return
        if balance < tran_num: request['result'].update(MSG['INSUFFICIENT_BALANCE']);return
    transaction = Tool.transfer_ontology(net, assetId, source, dests[0], amounts[0], ad)
    result,msg = True,''
    if result:
        request['result']['data'] = {'sigdata':big_or_little(Tool.compute_txid(transaction)), 'transaction':transaction}
    else:
        request['result'].update(MSG['UNKNOWN_ERROR'])

@format_result(['net'])
@post('/v2/{net}/ong')
async def ong_v2(net, request, *, publicKey, **kw):
    #params validation
    if not Tool.validate_cpubkey(publicKey): request['result'].update(MSG['WRONG_ARGUMENT']);return
    #get gas
    address = Tool.cpubkey_to_address(publicKey)
    ong_balance = D(await get_ont_balance(request, address, 'ong'))
    if ong_balance < D('0.01'): request['result'].update(MSG['INSUFFICIENT_BALANCE']);return
    amount = await get_unclaim_ong(request, address)
    tx,result,msg = Tool.ong_claim_transaction(address, amount, net)
    if result:
        request['result']['data'] = {'transaction':tx, 'sigdata':big_or_little(Tool.compute_txid(tx))}
    else:
        request['result'].update(MSG['UNKNOWN_ERROR'])
        request['result']['message'] += ':' + msg

@format_result(['net','address'])
@get('/v2/{net}/ong/{address}')
async def get_ong_v2(net, address, request):
    ong_balance = D(await get_ont_balance(request, address, 'ong'))
    if ong_balance < D('0.01'): request['result'].update(MSG['INSUFFICIENT_BALANCE']);return
    amount = await get_unclaim_ong(request, address)
    tx,result,msg = Tool.ong_claim_transaction(address, amount, net)
    if result:
        request['result']['data'] = {'transaction':tx, 'sigdata':big_or_little(Tool.compute_txid(tx))}
    else:
        request['result'].update(MSG['UNKNOWN_ERROR'])
        request['result']['message'] += ':'+msg

@format_result(['net'])
@post('/v2/{net}/broadcast/ont')
async def broadcast_ont_v2(net, request, *, publicKey, signature, transaction):
    #params validation
    if not Tool.validate_cpubkey(publicKey): request['result'].update(MSG['WRONG_ARGUMENT']);return
    sigdata = big_or_little(Tool.compute_txid(transaction))
    result,msg = Tool.verify(publicKey, signature, sigdata)
    if not result:
        request['result'].update(MSG['UNKNOWN_ERROR'])
        request['result']['message'] += ':'+msg
    else:
        tx = Tool.get_transaction_ontology(publicKey, signature, transaction)
        txid = Tool.compute_txid(transaction)
        result,msg = await ont_send_raw_transaction(tx, request)
        if result:
            if txid != result:
                request['result'].update(MSG['UNKNOWN_ERROR'])
                request['result']['message'] += ':result:%s != txid:%s' % (result,txid)
                return
            request['result']['data'] = {'txid':result}
        else:
            request['result'].update(MSG['UNKNOWN_ERROR'])
            request['result']['message'] += ':' + msg

@options('/v2/{net}/transfer/ont')
async def transfer_ont_v2_options(net, request):
    if not valid_net(net, request): return {'result':False, 'error':'wrong net'}
    return 'OK'
@options('/v2/{net}/ong')
async def ong_v2_options(net, request):
    if not valid_net(net, request): return {'result':False, 'error':'wrong net'}
    return 'OK'
@options('/v2/{net}/broadcast/ont')
async def broadcast_ont_v2_options(net, request):
    if not valid_net(net, request): return {'result':False, 'error':'wrong net'}
    return 'OK'
