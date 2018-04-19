import os
import asyncio
from coreweb import get, post, options
from aiohttp import web
from decimal import Decimal as D
from pymongo import DESCENDING
from apis import APIValueError, APIResourceNotFoundError, APIError
from tools import Tool, check_decimal, sci_to_str, big_or_little
from assets import NEO,NEP5, validate_asset, get_asset_decimal
import logging
logging.basicConfig(level=logging.DEBUG)
from dotenv import load_dotenv, find_dotenv
load_dotenv(find_dotenv(), override=True)

NET = os.environ.get('NET')

def valid_net(net):
    return NET == net

def valid_asset(asset):
    if len(asset) in [40,64]: return True
    return False

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
            json={'jsonrpc':'2.0','method':'sendrawtransaction','params':[tx],'id':1}) as resp:
        if 200 != resp.status:
            logging.error('Unable to visit %s %s' % (request.app['neo_uri'], method))
            return False,'404'
        j = await resp.json()
        if 'error' in j.keys():
            logging.error('result error when %s %s' % (request.app['neo_uri'], method))
            return False, j['error']['message']
        return j['result'],''

async def get_nep5_asset_balance(request, address, asset):
    result = await get_rpc(request, 'invokefunction',
            [asset, "balanceOf", [{"type":"Hash160","value":big_or_little(Tool.address_to_scripthash(address))}]])
    if result and "HALT, BREAK" == result["state"]:
        hex_str = result['stack'][0]['value']
        if hex_str: return Tool.hex_to_num_str(hex_str)
        return '0'
    return '0'

async def get_multi_nep5_balance(request, address, asset_list):
    result = {}
    nep5_result = await asyncio.gather(
            *[get_nep5_asset_balance(request, address, asset) for asset in asset_list])
    for i in range(len(asset_list)):
        result[asset_list[i]] = nep5_result[i]
    return result

async def get_utxo(request, address, asset):
    if not asset.startswith('0x'): asset = '0x' + asset
    result = []
    cursor = request.app['db'].utxos.find({'address':address, 'asset':asset, 'spent_height':None})
    for doc in await cursor.to_list(None):
        doc['asset'] = doc['asset'][2:]
        doc['txid']  = doc['txid'][2:]
        result.append({'prevIndex':doc['index'],'prevHash':doc['txid'],'value':doc['value']})
    return result

async def get_global_asset_balance(request, address, asset):
    if not asset.startswith('0x'): asset = '0x' + asset
    utxo = await get_utxo(request, address, asset)
    return sci_to_str(str(sum([D(i['value']) for i in utxo])))

async def get_all_utxo(request, address):
    result = {}
    cursor = request.app['db'].utxos.find({'address':address,'spent_height':None})
    for doc in await cursor.to_list(None):
        asset = doc['asset'] = doc['asset'][2:]
        doc['txid']  = doc['txid'][2:]
        if asset not in result.keys():
            result[asset] = []
        result[asset].append({'prevIndex':doc['index'],'prevHash':doc['txid'],'value':doc['value']})
    return result

async def get_all_asset(request):
    result = {'GLOBAL':[],'NEP5':[]}
    cursor = request.app['db'].assets.find()
    for doc in await cursor.to_list(None):
        doc['id'] = doc['_id']
        del doc['_id']
        if 'NEP5' == doc['type']:
            result['NEP5'].append(doc)
        else:
            result['GLOBAL'].append(doc)
    return result

async def get_an_asset(id, request):
    return await request.app['db'].assets.find_one({'_id':id}) 

@get('/')
def index(request):
    return {'hello':'neo',
            'GET':[
                '/',
                '/{net}/height',
                '/{net}/block/{block}',
                '/{net}/transaction/{txid}',
                '/{net}/claim/{address}',
                '/{net}/address/{address}',
                '/{net}/asset?id={assetid}',
                '/{net}/history/{address}?asset={assetid}',
                ],
            'POST':[
                '/{net}/gas',
                '/{net}/transfer',
                '/{net}/broadcast',
                ],
            'ref':{
                'How to transfer?':'http://note.youdao.com/noteshare?id=b60cc93fa8e8804394ade199c52d6274',
                'How to claim GAS?':'http://note.youdao.com/noteshare?id=c2b09b4fa26d59898a0f968ccd1652a0',
                'Source Code':'https://github.com/OTCGO/SYNC_NEO/',
                },
            }

@get('/{net}/height')
async def height(net, request):
    if not valid_net(net): return {'error':'wrong net'}
    r = await request.app['db'].state.find_one({'_id':'height'}) 
    return {'height':r['value']+1}

@get('/{net}/asset')
async def asset(net, request, *, id=0):
    if not valid_net(net): return {'error':'wrong net'}
    if 0 == id:
        return await get_all_asset(request)
    if id.startswith('0x'): id = id[2:]
    if not valid_asset(id): return {'error':'asset not exist'}
    r = await get_an_asset(id, request)
    if r: 
        r['id'] = r['_id']
        del r['_id']
        return r
    return {'error':'asset not exist'}

@get('/{net}/block/{block}')
async def block(net, block, request):
    if not valid_net(net): return {'error':'wrong net'}
    try:
        b = int(block)
    except:
        return {'error':'wrong arg: {}'.format(block)}
    r = await request.app['db'].state.find_one({'_id':'height'})
    h = r['value']
    if b < 0 or b > h: return {'error':'not found'}
    r = await request.app['db'].blocks.find_one({'_id':b})
    r['index'] = r['_id']
    del r['_id']
    return r

@get('/{net}/transaction/{txid}')
async def transaction(net, txid, request):
    if not valid_net(net): return {'error':'wrong net'}
    return await get_rpc(request, 'getrawtransaction', [txid,1])

@get('/{net}/address/{address}')
async def address(net, address, request):
    if not valid_net(net): return {'error':'wrong net'}
    if not Tool.validate_address(address): return {'error':'wrong address'}
    result = {'_id':address,'balances':{}}
    nep5_keys = list(NEP5.keys())
    aresult = await asyncio.gather(
            get_all_utxo(request,address),
            get_multi_nep5_balance(request, address, nep5_keys))
    result['utxo'],result['balances'] = aresult[0], aresult[1]
    for k,v in result['utxo'].items():
        result['balances'][k] = sci_to_str(str(sum([D(i['value']) for i in v])))
    return result

@get('/{net}/claim/{address}')
async def claim(net, address, request):
    if not valid_net(net): return {'error':'wrong net'}
    if not Tool.validate_address(address): return {'error':'wrong address'}
    raw_utxo = []
    cursor = request.app['db'].utxos.find({'address':address,'asset':NEO, 'claim_height':None})
    for document in await cursor.to_list(None):
        raw_utxo.append(document)
    r = await request.app['db'].state.find_one({'_id':'height'})
    height = r['value'] + 1
    return await Tool.compute_gas(height, raw_utxo, request.app['db'])

@get('/{net}/history/{address}')
async def history(net, address, request, *, asset=0):
    if not valid_net(net): return {'error':'wrong net'}
    if not Tool.validate_address(address): return {'error':'wrong address'}
    raw_utxo = []
    query = {'address':address}
    if 0 != asset:
        if asset.startswith('0x'): asset = asset[2:]
        if not valid_asset(asset): return {'error':'asset not exist'}
        query['asset'] = '0x' + asset
    cursor = request.app['db'].history.find(query).sort('time', DESCENDING)
    for document in await cursor.to_list(length=100):
        del document['_id']
        del document['address']
        raw_utxo.append(document)
    return {'result':raw_utxo}

@post('/{net}/transfer')
async def transfer(net, request, *, source, dests, amounts, assetId, **kw):
    #params validation
    if not valid_net(net): return {'result':False, 'error':'wrong net'}
    if not Tool.validate_address(source): return {'result':False, 'error':'wrong source'}
    if assetId.startswith('0x'): assetId = assetId[2:]
    if not validate_asset(assetId): return {'result':False, 'error':'wrong assetId'}
    nep5_asset = global_asset = False
    if 40 == len(assetId): nep5_asset = True
    if 64 == len(assetId): global_asset = True
    ad = get_asset_decimal(assetId)
    dests,amounts = dests.split(','), amounts.split(',')
    ld,la = len(dests), len(amounts)
    if ld != la: return {'result':False, 'error':'length of dests != length of amounts'}
    if nep5_asset and 1 != ld:
        return {'result':False, 'error':"NEP5 token transfer only support One to One"}
    if False in map(Tool.validate_address, dests): return {'error':'wrong dests'}
    try:
        amounts = [D(a) for a in amounts]
    except:
        return {'result':False, 'error':'wrong amounts'}
    if [a for a in amounts if a <= D(0)]: return {'error':'wrong amounts'}
    if False in [check_decimal(a,ad) for a in amounts]:
        return {'result':False, 'error':'wrong amounts'}
    #check balance && transaction
    tran_num = sum(amounts)
    if nep5_asset:
        balance = D(await get_nep5_asset_balance(request, source, assetId))
        if balance < tran_num: return {'result':False, 'error':'insufficient balance'}
        transaction = Tool.transfer_nep5(assetId, source, dests[0], amounts[0])
        result,msg = True,''
    if global_asset:
        utxo = await get_utxo(request, source, assetId)
        balance = sum([D(i['value']) for i in utxo])
        if balance < tran_num: return {'result':False, 'error':'insufficient balance'}
        items = [(dests[i],amounts[i]) for i in range(len(dests))]
        transaction,result,msg = Tool.transfer_global(source, utxo, items, assetId)
    if result:
        return {'result':True, 'transaction':transaction}
    return {'result':False, 'error':msg}

@post('/{net}/gas')
async def gas(net, request, *, publicKey, **kw):
    #params validation
    if not valid_net(net): return {'result':False, 'error':'wrong net'}
    if not Tool.validate_cpubkey(publicKey): return {'result':False, 'error':'wrong publicKey'}
    #get gas
    address = Tool.cpubkey_to_address(publicKey)
    raw_utxo = []
    cursor = request.app['db'].utxos.find({'address':address,'asset':NEO, 'claim_height':None})
    for document in await cursor.to_list(None):
        raw_utxo.append(document)
    r = await request.app['db'].state.find_one({'_id':'height'})
    height = r['value'] + 1
    details = await Tool.compute_gas(height, raw_utxo, request.app['db'])
    tx,result,msg = Tool.claim_transaction(address, details)
    if result:
        return {'result':True, 'transaction':tx}
    return {'result':False, 'error':msg}

@post('/{net}/broadcast')
async def broadcast(net, request, *, publicKey, signature, transaction):
    #params validation
    if not valid_net(net): return {'result':False, 'error':'wrong net'}
    if not Tool.validate_cpubkey(publicKey): return {'result':False, 'error':'wrong publicKey'}
    result,msg = Tool.verify(publicKey, signature, transaction)
    if not result: return {'result':False, 'error':msg}
    tx = Tool.get_transaction(publicKey, signature, transaction)
    txid = Tool.compute_txid(transaction)
    result,msg = await send_raw_transaction(tx, request)
    if result:
        return {'result':True, 'txid':txid}
    return {'result':False, 'error':msg}

@options('/{net}/transfer')
async def transfer_options(net):
    if not valid_net(net): return {'result':False, 'error':'wrong net'}
    return 'OK'
@options('/{net}/gas')
async def gas_options(net):
    if not valid_net(net): return {'result':False, 'error':'wrong net'}
    return 'OK'
@options('/{net}/broadcast')
async def broadcast_options(net):
    if not valid_net(net): return {'result':False, 'error':'wrong net'}
    return 'OK'
