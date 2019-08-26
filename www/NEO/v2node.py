#! /usr/bin/env python3
# coding: utf-8
# flow@SEA
# Licensed under the MIT License.

from coreweb import get, post, options
import logging
logging.basicConfig(level=logging.DEBUG)
from .decorator import *
from message import MSG


def valid_net(net, request):
    return net == request.app['net']

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

async def mysql_get_node_status(pool, address):
    sql = "SELECT status,referrer,amount,days,referrals,performance,nodelevel,penalty,teamLevelInfo FROM node WHERE address = '%s';" % address
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
                'teamLevelInfo':r[0][8]
                }
    return None


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
