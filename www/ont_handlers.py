import os
import json
import asyncio
from coreweb import get, post, options
import logging
logging.basicConfig(level=logging.DEBUG)


def valid_net(net, request):
    return net == request.app['net']

async def get_rpc_ont(request,method,params):
    async with request.app['session'].post(request.app['ont_uri'],
            json={'jsonrpc':'2.0','method':method,'params':params,'id':1}) as resp:
        if 200 != resp.status:
            logging.error('Unable to visit %s %s' % (request.app['ont_uri'], method))
            return '404'
        j = await resp.json()
        if 'SUCCESS' != j['desc']:
            logging.error('result error when %s %s:%s' % (request.app['ont_uri'], method, j['error']))
            return '404'
        return j['result']

@get('/{net}/height/ont')
async def height_ont(net, request):
    if not valid_net(net, request): return {'error':'wrong net'}
    height = await get_rpc_ont(request,'getblockcount',[])
    if isinstance(height,int): return {'height':height}
    return {'error':'Unable to get Ontology height'}

@get('/{net}/block/ont/{block}')
async def block_ont(net, block, request):
    if not valid_net(net, request): return {'error':'wrong net'}
    try:
        b = int(block)
    except:
        return {'error':'wrong arg: {}'.format(block)}
    block = await get_rpc_ont(request,'getblock',[b,1])
    if isinstance(block, dict): return block
    return {'error':'Unable to get block %s of Ontology' % b}

@get('/{net}/transaction/ont/{txid}')
async def transaction_ont(net, txid, request):
    if not valid_net(net, request): return {'error':'wrong net'}
    tr = await get_rpc_ont(request, 'getrawtransaction', [txid,1])
    if isinstance(tr, dict): return tr
    return {'error':'Unable to get transaction %s of Ontology' % txid}
