import os
import json
import math
import asyncio
from decimal import Decimal as D
from coreweb import get, post, options
from tools import Tool, check_decimal, sci_to_str, big_or_little
import logging
logging.basicConfig(level=logging.DEBUG)


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
decimal_ont = 1
decimal_ong = 9

def valid_net(net, request):
    return net == request.app['net']

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

async def get_balance(request, address):
    result,err = await get_rpc_ont(request, 'getbalance', [address])
    if err or not result: return {}
    for i in result:
        if assets[i]['decimal'] > 1:
            result[i] = sci_to_str(str(D(result[i])/D(math.pow(10, assets[i]['decimal']))))
    return result

async def get_unclaim_ong(request, address):
    result,err = await get_rpc_ont(request, 'getunclaimong', [address])
    if err or not result: return "0"
    return sci_to_str(str(D(result)/D(math.pow(10, assets['ong']['decimal']))))

async def compute_ong(request,addrss):
    pass

@get('/{net}/height/ont')
async def height_ont(net, request):
    if not valid_net(net, request): return {'error':'wrong net'}
    height,err = await get_rpc_ont(request,'getblockcount',[])
    if err or not height: return {'error':'Unable to get Ontology height'}
    return {'height':height}

@get('/{net}/block/ont/{block}')
async def block_ont(net, block, request):
    if not valid_net(net, request): return {'error':'wrong net'}
    try:
        b = int(block)
    except:
        return {'error':'wrong arg: {}'.format(block)}
    block,err = await get_rpc_ont(request,'getblock',[b,1])
    if err or not block: return {'error':'Unable to get block %s of Ontology' % b}
    return block

@get('/{net}/transaction/ont/{txid}')
async def transaction_ont(net, txid, request):
    if not valid_net(net, request): return {'error':'wrong net'}
    tr,err = await get_rpc_ont(request, 'getrawtransaction', [txid,1])
    if err or not tr: return {'error':'Unable to get transaction %s of Ontology' % txid}
    return tr

@get('/{net}/address/ont/{address}')
async def address_ont(net, address, request):
    if not valid_net(net, request): return {'error':'wrong net'}
    if not Tool.validate_address(address): return {'error':'wrong address'}
    result = {'address':address,'balances':await get_balance(request, address)}
    return result

@get('/{net}/claim/ont/{address}')
async def claim_ont(net, address, request):
    if not valid_net(net, request): return {'error':'wrong net'}
    if not Tool.validate_address(address): return {'error':'wrong address'}
    return {'available':await get_unclaim_ong(request, address),
            "unavailable":await compute_ong(request, address)}

@post('/{net}/transfer/ont')
async def transfer_ont(net, request, *, source, dests, amounts, assetId, **kw):
    pass
