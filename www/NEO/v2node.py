#! /usr/bin/env python3
# coding: utf-8
# flow@SEA
# Licensed under the MIT License.

from coreweb import get, post, options
import logging
logging.basicConfig(level=logging.DEBUG)
from .decorator import *
from message import MSG


@format_result(['net','address'])
@get('/v2/{net}/node/status/{address}')
async def node_status(net, address, request):
    pass

@format_result(['net'])
@post('/v2/{net}/node/new')
async def node_new(net, request, *, referrer, amount, days, publicKey, signature):
    pass

@format_result(['net'])
@post('/v2/{net}/node/unlock')
async def node_unlock(net, request, *, publicKey, signature):
    pass

@format_result(['net','address'])
@get('/v2/{net}/node/details/{address}')
async def node_details(net, address, request):
    pass

@format_result(['net'])
@post('/v2/{net}/node/withdraw')
async def node_withdraw(net, request, *, amount, publicKey, signature):
    pass


@options('/v2/{net}/node/new')
async def node_new_options(net, request):
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
