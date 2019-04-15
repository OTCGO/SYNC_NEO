import os
import sys
import json
import asyncio
from coreweb import get, post, options
from aiohttp import web
from decimal import Decimal as D
from binascii import hexlify, unhexlify
from apis import APIValueError, APIResourceNotFoundError, APIError
from tools import Tool, check_decimal, sci_to_str, big_or_little
from assets import NEO, GAS, GLOBAL_TYPES, SEAS, SEAC, CSEAS, CSEAC
import logging
logging.basicConfig(level=logging.DEBUG)
from dotenv import load_dotenv, find_dotenv
load_dotenv(find_dotenv(), override=True)
from ont_handlers import height_ont, block_ont, transaction_ont, get_ont_balance, address_ont, claim_ont, transfer_ont, ong, get_ong, broadcast_ont, transfer_ont_options, ong_options, broadcast_ont_options
from ont_handlers import assets as ONT_ASSETS


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
    if index <= 0: return False, {'error':'wrong index'}
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
    try:
        return int(asset['decimals'])
    except:
        return 8

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
        method = 'sendrawtransaction'
        if 200 != resp.status:
            logging.error('Unable to visit %s %s' % (request.app['neo_uri'], method))
            return False,'404'
        j = await resp.json()
        if 'error' in j.keys():
            logging.error('result error when %s %s' % (request.app['neo_uri'], method))
            return False, j['error']['message']
        return j['result'],''

async def get_nep5_asset_balance(request, address, asset):
    sql = "SELECT value FROM balance WHERE address='%s',asset='%s';" % (address, asset)
    r = await mysql_query_one(request.app['pool'], sql)
    if r: return r[0][0]
    return '0'

async def get_resolve_address(resolve_invoke, request):
    result = await get_rpc(request, 'invokescript', [resolve_invoke])
    if result and "HALT, BREAK" == result["state"]:
        hex_str = result['stack'][0]['value']
        if '00' != hex_str: return Tool.hex_to_string(hex_str)
        return ''
    return ''

async def get_multi_nep5_balance(request, address, assets):
    #pass
    result = {}
    for asset in assets:
        try:
            asset['decimals'] = int(asset['decimals'])
        except:
            asset['decimals'] = 8
    nep5_result = await asyncio.gather(
            *[get_nep5_asset_balance(request, address, asset["id"]) for asset in assets])
    for i in range(len(assets)):
        result[assets[i]['id']] = nep5_result[i]
    return result

async def get_utxo(request, address, asset):
    #pass
    if not asset.startswith('0x'): asset = '0x' + asset
    result = []
    cursor = request.app['db'].utxos.find({'address':address, 'asset':asset, 'spent_height':None})
    for doc in await cursor.to_list(None):
        doc['asset'] = doc['asset'][2:]
        doc['txid']  = doc['txid'][2:]
        result.append({'prevIndex':doc['index'],'prevHash':doc['txid'],'value':doc['value']})
    return result

async def get_global_asset_balance(request, address, asset):
    #pass
    if not asset.startswith('0x'): asset = '0x' + asset
    utxo = await get_utxo(request, address, asset)
    return sci_to_str(str(sum([D(i['value']) for i in utxo])))

async def get_all_utxo(request, address):
    #pass
    result = {}
    cursor = request.app['db'].utxos.find({'address':address,'spent_height':None})
    for doc in await cursor.to_list(None):
        asset = doc['asset'] = doc['asset'][2:]
        doc['txid']  = doc['txid'][2:]
        if asset not in result.keys():
            result[asset] = []
        result[asset].append({'prevIndex':doc['index'],'prevHash':doc['txid'],'value':doc['value']})
    return result

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

def get_all_global(request):
    return request.app['cache'].get('assets')['GLOBAL']

def get_all_nep5(request):
    return request.app['cache'].get('assets')['NEP5']

def get_all_ontology(request):
    return request.app['cache'].get('assets')['OEP4']

def get_all_asset(request):
    return request.app['cache'].get('assets')

def get_an_asset(i, request):
    if i.startswith('0x'): i = i[2:]
    assets = request.app['cache'].get('assets')
    if i in assets['GLOBAL'].keys(): return assets['GLOBAL'][i]
    if i in assets['NEP5'].keys(): return assets['NEP5'][i]
    if i in assets['OEP4'].keys(): return assets['OEP4'][i]
    return None

@get('/')
def index(request):
    return {'hello':'%s' % request.app['net'],
            'GET':[
                '/',
                '/{net}/height',
                '/{net}/height/ont',
                '/{net}/block/{block}',
                '/{net}/block/ont/{block}',
                '/{net}/transaction/{txid}',
                '/{net}/transaction/ont/{txid}',
                '/{net}/claim/{address}',
                '/{net}/claim/ont/{address}',
                '/{net}/claim/seas/{address}',
                '/{net}/address/{address}',
                '/{net}/address/ont/{address}',
                '/{net}/asset?asset={assetid}',
                '/{net}/history/{address}?asset={assetid}&index={index}&length={length}',
                '/{net}/resolve/{domain}',
                ],
            'POST':[
                '/{net}/gas',
                '/{net}/ong',
                '/{net}/transfer',
                '/{net}/transfer/ont',
                '/{net}/broadcast',
                '/{net}/broadcast/ont',
                ],
            'ref':{
                'How to transfer?':'http://note.youdao.com/noteshare?id=b60cc93fa8e8804394ade199c52d6274',
                'How to claim GAS?':'http://note.youdao.com/noteshare?id=c2b09b4fa26d59898a0f968ccd1652a0',
                'How to claim ONG?':'http://note.youdao.com/noteshare?id=96992980cb8b5c6210a5b79478b3111d',
                'Source Code':'https://github.com/OTCGO/SYNC_NEO/',
                },
            }

@get('/{net}/height')
async def height(net, request):
    if not valid_net(net, request): return {'result':False, 'error':'wrong net'}
    return {'result':True, 'height':request.app['cache'].get('height')}

@get('/{net}/asset')
async def asset(net, request, *, asset=0):
    if not valid_net(net, request): return {'result':False, 'error':'wrong net'}
    if 0 == asset: return {'result':True, 'assets':get_all_asset(request)}
    if asset.startswith('0x'): asset = asset[2:]
    if not valid_asset(asset): return {'result':False, 'error':'asset not exist'}
    r = get_an_asset(asset, request)
    if r: return {'result':True, asset:r}
    return {'result':False, 'error':'asset not exist'}

@get('/{net}/block/{block}')
async def block(net, block, request):
    if not valid_net(net, request): return {'result':False, 'error':'wrong net'}
    try:
        b = int(block)
    except:
        return {'result':False, 'error':'wrong arg: {}'.format(block)}
    if b<0: return {'result':False, 'error':'block height must >= 0'}
    r = await mysql_get_block(request.app['pool'], b)
    if r: return {'result':True, block:r}
    return {'result':False, 'error':'not found'}

@get('/{net}/transaction/{txid}')
async def transaction(net, txid, request):
    if not valid_net(net, request): return {'error':'wrong net'}
    return await get_rpc(request, 'getrawtransaction', [txid,1])

@get('/{net}/address/{address}')
async def address(net, address, request):
    if not valid_net(net, request): return {'error':'wrong net'}
    if not Tool.validate_address(address): return {'error':'wrong address'}
    result = {'_id':address,'balances': await mysql_get_balance(request, address)}
    aresult = await get_ont_balance(request, address)
    result['balances'][ONT_ASSETS['ont']['scripthash']] = aresult['ont']
    result['balances'][ONT_ASSETS['ong']['scripthash']] = aresult['ong']
    return result

'''
@get('/{net}/claim/{address}')
async def claim(net, address, request):
    if not valid_net(net, request): return {'error':'wrong net'}
    if not Tool.validate_address(address): return {'error':'wrong address'}
    raw_utxo = []
    cursor = request.app['db'].utxos.find({'address':address,'asset':NEO, 'claim_height':None})
    for document in await cursor.to_list(None):
        raw_utxo.append(document)
    r = await request.app['db'].state.find_one({'_id':'height'})
    height = r['value'] + 1
    return await Tool.compute_gas(height, raw_utxo, request.app['db'])

@get('/{net}/claim/seas/{address}')
async def claim_seas(net, address, request):
    if not valid_net(net, request): return {'error':'wrong net'}
    if not Tool.validate_address(address): return {'error':'wrong address'}
    assetId = CSEAS[net][2:]
    asset = get_an_asset(assetId, request)
    ad = get_asset_decimal(asset)
    balance = D(await get_nep5_asset_balance(request, address, assetId))
    if balance > 0:
        r = await request.app['db'].state.find_one({'_id':'height'})
        bstorage = await get_rpc(request, 'getstorage', [CSEAS[net], Tool.address_to_scripthash(address)])
        bheight = bstorage[16:]
        bheight = D(Tool.hex_to_num_str(bheight,0))
        height = r['value']
        bonus = (height - bheight) * 6 * balance / 100000000
        return {'available':str(bonus),'unavailable':'0'}
    return {'available':'0', 'unavailable':'0'}

@get('/{net}/history/{address}')
async def history(net, address, request, *, asset=0, index=1, length=20):
    if not valid_net(net, request): return {'error':'wrong net'}
    if not Tool.validate_address(address): return {'error':'wrong address'}
    result,info = valid_page_arg(index, length)
    if not result: return info
    index, length = info['index'], info['length']
    skip_num = (index - 1) * length
    raw_utxo = []
    query = {'address':address}
    if 0 != asset:
        if asset.startswith('0x'): asset = asset[2:]
        if not valid_asset(asset): return {'error':'asset not exist'}
        if 64 == len(asset):
            query['asset'] = '0x' + asset
        else:
            query['asset'] = asset
    if 'asset' in query.keys() and 40 == len(query['asset']):
        cursor = request.app['db'].nep5history.find(query).sort('time', DESCENDING)
    else:
        cursor = request.app['db'].history.find(query).sort('time', DESCENDING)
    for document in await cursor.skip(skip_num).to_list(length=length):
        del document['_id']
        del document['address']
        raw_utxo.append(document)
    return {'result':raw_utxo}

@get('/{net}/version/{platform}')
async def version(net, platform, request):
    if not valid_net(net, request): return {'error':'wrong net'}
    platform = platform.lower()
    if not valid_platform(platform): return {'error':'wrong platform'}
    info = await request.app['db'].state.find_one({'_id':platform})
    if info:
        del info['_id']
        return {'result':True, 'version':info}
    return {'result':False, 'error':'not exist'}

@get('/{net}/resolve/{domain}')
async def resolve(net, domain, request):
    if not valid_domain(domain, request): return {'error':'wrong domain'}
    namehash = Tool.nns_namehash(domain)
    resolve_invoke = Tool.nns_resolve_invoke(namehash)
    address = await get_resolve_address(resolve_invoke, request)
    if not address: return {'error':'not resolve'}
    return {'result':True, 'address':address}

@get('/{net}/swap/{address}/{asset}')
async def swap(net, address, asset, request):
    if not valid_net(net, request): return {'result':False, 'error':'wrong net'}
    if not Tool.validate_address(address): return {'result':False, 'error':'wrong address'}
    if not asset.startswith('0x'): asset = '0x' + asset
    if not valid_swap_asset(asset, net): return {'result':False, 'error':'wrong asset'}
    sh_asset, name = get_swap_asset_info(asset, net)
    utxo = await get_utxo(request, address, asset)
    if not utxo: return {'result':False, 'error':'insufficient balance'}
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
        return {'result':True, 'transaction':transaction}
    return {'result':False, 'error':msg}

@post('/{net}/transfer')
async def transfer(net, request, *, source, dests, amounts, assetId, **kw):
    #params validation
    if not valid_net(net, request): return {'result':False, 'error':'wrong net'}
    if not Tool.validate_address(source): return {'result':False, 'error':'wrong source'}
    if assetId.startswith('0x'): assetId = assetId[2:]
    if not valid_asset(assetId): return {'result':False, 'error':'wrong assetId'}
    asset = get_an_asset(assetId, request)
    if not asset: return {'result':False, 'error':'wrong assetId'}
    nep5_asset = global_asset = False
    if 40 == len(assetId): nep5_asset = True
    if 64 == len(assetId): global_asset = True
    ad = get_asset_decimal(asset)
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
        transaction = Tool.transfer_nep5(assetId, source, dests[0], amounts[0], ad)
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
    if not valid_net(net, request): return {'result':False, 'error':'wrong net'}
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

@post('/{net}/new_contract')
async def new_contract(net, contract, address, request, **kw):
    if not valid_net(net, request): return {'result':False, 'error':'wrong net'}
    description =   kw.get('description','')
    email =         kw.get('email', '')
    author =        kw.get('author', '')
    version =       kw.get('version', '')
    name =          kw.get('name', '')
    storage =       kw.get('storage', '0')
    dynamic_invoke= kw.get('dynamic_invoke', '0')
    return_type =   kw.get('return_type', 'void')
    parameter =     kw.get('parameter', '')
    def str_to_hex_str(s):
        return hexlify(s.encode('utf8')).decode('utf8')
    tx = ''
    for k,v in {'description':description,
                'email':email,
                'author':author,
                'version':version,
                'name':name}.items():
        v = str_to_hex_str(v)
        if 0 == len(v):
            tx += '00'
            continue
        if len(v)/2>255: return {'result':False, 'error':'%s is too long' % k}
        tx += Tool.num_to_hex_str(len(v)//2) + v
    #use_storage && dynamic_invoke
    sys_fee = 0
    for k,v in {'storage':storage,
                'dynamic_invoke':dynamic_invoke,
                }.items():
        if v not in ['0','1']: return {'result':False, 'error':'wrong %s,must 0 or 1' % k}
    else:
        if '0' == storage and '0' == dynamic_invoke:
            tx += '00'
            sys_fee = 90
        if '1' == storage and '0' == dynamic_invoke:
            tx += '51'
            sys_fee = 490
        if '0' == storage and '1' == dynamic_invoke:
            tx += '52'
            sys_fee = 590
        if '1' == storage and '1' == dynamic_invoke:
            tx += '53'
            sys_fee = 990
    #return_type
    return_dict = {
            'signature':'00',
            'boolean':'51',
            'integer':'52',
            'hash160':'53',
            'hash256':'54',
            'bytearray':'55',
            'publickey':'56',
            'string':'57',
            'array':'60',
            'interopinterface':'F0',
            'void':'FF',
        }
    return_type = return_type.lower()
    if return_type not in return_dict.keys(): return {'result':False, 'error':'wrong return type, must 0 or 1'}
    tx += return_dict[return_type]
    #parameter
    parameter_dict = {
            'signature':'00',
            'boolean':'01',
            'integer':'02',
            'hash160':'03',
            'hash256':'04',
            'bytearray':'05',
            'publickey':'06',
            'string':'07',
            'array':'10',
            'interopinterface':'F0',
            'void':'FF',
            }
    parameter = parameter.split(',')
    parameter = list(filter(lambda i:i != '', parameter))
    if not parameter:
        tx += '00'
    else:
        if False in map(lambda x:x in parameter_dict.keys(), parameter):
            return {'result':False, 'error':'wrong parameter'}
        tx += Tool.num_to_hex_str(len(parameter))
        for p in parameter:
            tx += parameter_dict[p]
    #contract
    contract_len = len(contract)
    if 0 == contract_len or 1 == contract_len%2: return {'result':False, 'error':'wrong length of the contract'}
    contract_len = contract_len // 2
    if contract_len <= 0xFF:
        tx += '4c' + Tool.num_to_hex_str(contract_len) + contract
    elif contract_len <= 0xFFFF:
        tx += '4d' + Tool.num_to_hex_str(contract_len, 2) + contract
    else:
        tx += '4e' + Tool.num_to_hex_str(contract_len, 4) + contract
    tx += '68134e656f2e436f6e74726163742e437265617465'
    #check balance
    if not Tool.validate_address(address): return {'result':False, 'error':'wrong address'}
    #InvocationTransaction
    return {'result':True, 'transaction':tx}

@post('/{net}/broadcast')
async def broadcast(net, request, *, publicKey, signature, transaction):
    #params validation
    if not valid_net(net, request): return {'result':False, 'error':'wrong net'}
    if not Tool.validate_cpubkey(publicKey): return {'result':False, 'error':'wrong publicKey'}
    result,msg = Tool.verify(publicKey, signature, transaction)
    if not result: return {'result':False, 'error':msg}
    txid = Tool.compute_txid(transaction)
    sh_seas = big_or_little(CSEAS[net][2:])
    if transaction.startswith('d10121000a6d696e74546f6b656e7367'+sh_seas):
        tx1,tx2 = Tool.get_transaction_for_swap_seas(publicKey, signature, transaction)
        r = await asyncio.gather(*[send_raw_transaction(t, request) for t in [tx1, tx2]])
        for i in range(2):
            result,msg = r[i]
            if result: return {'result':True, 'txid':txid}
    else:
        tx = Tool.get_transaction(publicKey, signature, transaction)
        result,msg = await send_raw_transaction(tx, request)
        if result: return {'result':True, 'txid':txid}
    return {'result':False, 'error':msg}

@options('/{net}/transfer')
async def transfer_options(net, request):
    if not valid_net(net, request): return {'result':False, 'error':'wrong net'}
    return 'OK'
@options('/{net}/gas')
async def gas_options(net, request):
    if not valid_net(net, request): return {'result':False, 'error':'wrong net'}
    return 'OK'
@options('/{net}/broadcast')
async def broadcast_options(net, request):
    if not valid_net(net, request): return {'result':False, 'error':'wrong net'}
    return 'OK'
'''
