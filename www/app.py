#! /usr/bin/env python3
# coding: utf-8
# flow@SEA
# Licensed under the MIT License.

import logging; logging.basicConfig(level=logging.INFO)
import asyncio
import uvloop; asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
import aiohttp
import aiomysql
from cacheout import Cache
import os
import sys
import json
import time
from pytz import utc
from aiohttp import web
from random import randint
from datetime import datetime
from coreweb import add_routes
from dotenv import load_dotenv, find_dotenv
load_dotenv(find_dotenv(), override=True)
from apscheduler.schedulers.asyncio import AsyncIOScheduler


GLOBAL_TYPES = ["GoverningToken","UtilityToken","Share","Token"]

def get_mysql_host():
    return os.environ.get('MYSQLHOST')

def get_mysql_port():
    return int(os.environ.get('MYSQLPORT'))

def get_mysql_user():
    return os.environ.get('MYSQLUSER')

def get_mysql_pass():
    return os.environ.get('MYSQLPASS')

def get_mysql_db():
    return os.environ.get('MYSQLDB')

def get_neo_uri():
    neo_node = os.environ.get('NEONODE')
    neo_port = os.environ.get('NEOPORT')
    return 'http://%s:%s' % (neo_node, neo_port)

def get_ont_uri():
    ont_node = os.environ.get('ONTNODE')
    ont_port = os.environ.get('ONTPORT')
    return 'http://%s:%s' % (ont_node, ont_port)

def get_super_node_uri():
    return os.environ.get('SUPERNODE')

def get_gas_address():
    return os.environ.get('GASADDRESS')

def get_gas_prikey():
    return os.environ.get('GASPRIKEY')

def get_gas_pubkey():
    return os.environ.get('GASPUBKEY')

get_listen_ip = lambda:os.environ.get('LISTENIP')
get_listen_port = lambda:os.environ.get('LISTENPORT')
get_net = lambda:os.environ.get('NET')
get_ont_genesis_block_timestamp = lambda:int(os.environ.get('ONTGENESISBLOCKTIMESTAMP'))


async def get_mysql_cursor(pool):
    conn = await pool.acquire()
    cur  = await conn.cursor()
    return conn, cur

async def get_mysql_pool(mysql_args):
    try:
        logging.info('start to connect db')
        pool = await aiomysql.create_pool(**mysql_args)
        logging.info('succeed to connet db!')
        return pool
    except asyncio.CancelledError:
        raise asyncio.CancelledError
    except Exception as e:
        logging.error("mysql connet failure:{}".format(e.args[0]))
        return False

async def get_block_count(app):
    async with app['session'].post(app['neo_uri'],
            json={'jsonrpc':'2.0','method':'getblockcount','params':[],'id':1}) as resp:
        if 200 != resp.status:
            logging.error('Unable to fetch blockcount')
            sys.exit(1)
        j = await resp.json()
        return j['result']

async def get_super_node_info(app):
    async with app['session'].get(app['super_node_uri']) as resp:
        if 200 != resp.status:
            logging.error('Unable to fetch supernode info')
            sys.exit(1)
        j = await resp.json()
        return j

async def update_neo_uri(app):
    heightA = await get_block_count(app)
    info = await get_super_node_info(app)
    heightB = info['height']
    if heightA < heightB:
        app['neo_uri'] = info['fast'][randint(0,len(info['fast'])-1)]
    logging.info('heightA:%s heightB:%s neo_uri:%s' % (heightA,heightB,app['neo_uri']))

async def get_height(pool, name):
    conn, cur = await get_mysql_cursor(pool)
    try:
        await cur.execute("select update_height from status where name='%s';" % name)
        result = await cur.fetchone()
        if result:
            uh = result[0]
            logging.info('database %s height: %s' % (name,uh))
            return uh
        logging.info('database %s height: -1' % name)
        return -1
    except Exception as e:
        logging.error("mysql SELECT failure:{}".format(e.args[0]))
        sys.exit(1)
    finally:
        await pool.release(conn)

async def get_sync_height(pool):
    return await get_height(pool, 'utxo')

async def update_height(pool, cache):
    cache.evict()
    r = await get_sync_height(pool)
    old = cache.get('height')
    height = r + 1
    if old is None or int(old) < height:
        cache.set('height',height)

async def get_asset_state(pool):
    conn, cur = await get_mysql_cursor(pool)
    try:
        await cur.execute("select update_height from status where name='asset';")
        result = await cur.fetchone()
        if result:
            uh = result[0]
            logging.info('database asset height: %s' % uh)
            return uh
        logging.info('database asset height: -1')
        return -1
    except exception as e:
        logging.error("mysql select failure:{}".format(e.args[0]))
        sys.exit(1)
    finally:
        await pool.release(conn)

async def update_assets(pool, cache):
    state = await get_asset_state(pool)
    old_assets = {'state':state, 'GLOBAL':[], 'NEP5':[], 'ONTOLOGY':[
        {"name":"Ontology Token","symbol":"ontology-ONT","decimals":"0","type":"ONTOLOGY","id":'0000000000000000000000000000000000000001'},
        {"name":"Ontology Gas",  "symbol":"ontology-ONG","decimals":"9","type":"ONTOLOGY","id":'0000000000000000000000000000000000000002'}
        ]}
    assets = {'state':state, 'GLOBAL':{}, 'NEP5':{}, 'ONTNATIVE':{}, 'OEP4':{}}
    conn, cur = await get_mysql_cursor(pool)
    try:
        await cur.execute("select asset,type,name,symbol,decimals from assets;")
        result = await cur.fetchall()
        if result:
            for r in result:
                if r[1] in GLOBAL_TYPES:
                    old_assets['GLOBAL'].append({'type':r[1],'name':[{"lang":"zh-CN","name":r[2]},{"lang":"en","name":r[2]}],'precision':r[4],'id':r[0]})
                    assets['GLOBAL'][r[0]]  = {'type':r[1],'name':r[2],'symbol':r[3],'decimals':r[4]}
                elif 'NEP5' == r[1]:
                    old_assets['NEP5'].append({'name':r[2],'symbol':r[3],'decimals':str(r[4]),'type':r[1],'id':r[0]})
                    assets['NEP5'][r[0]]    = {'type':r[1],'name':r[2],'symbol':r[3],'decimals':r[4]}
                elif 'ONTNATIVE' == r[1]:
                    assets['ONTNATIVE'][r[0]]   = {'type':r[1],'name':r[2],'symbol':'ontology-'+r[3],'decimals':r[4]}
                elif 'OEP4' == r[1]:
                    assets['OEP4'][r[0]]  = {'type':r[1],'name':r[2],'symbol':'ontology-'+r[3],'decimals':r[4]}
                    old_assets['ONTOLOGY'].append({'type':'ONTOLOGY','name':r[2],'symbol':'ontology-'+r[3],'decimals':r[4],'id':r[0]})
    except Exception as e:
        logging.error("mysql SELECT failure:{}".format(e.args[0]))
        sys.exit(1)
    finally:
        cache.set('old_assets', old_assets)
        cache.set('assets', assets)
        await pool.release(conn)

async def update_seas_price(pool, cache):
    price_pre = 'PRICE_'
    seas = 'de7be47c4c93f1483a0a3fff556a885a68413d97'
    conn, cur = await get_mysql_cursor(pool)
    try:
        sql = "SELECT price FROM node_price WHERE asset='%s';" % (seas)
        await cur.execute(sql)
        result = await cur.fetchone()
        if result: price = result[0]
        else: price = '0'
    except Exception as e:
        logging.error("mysql SELECT failure:{}".format(e.args[0]))
        sys.exit(1)
    finally:
        cache.set(price_pre + seas, price, ttl=60)
        await pool.release(conn)

async def init_cache(app):
    await update_height(app['pool'], app['cache'])
    await update_assets(app['pool'], app['cache'])
    #await update_seas_price(app['pool'], app['cache'])

async def logger_factory(app, handler):
    async def logger(request):
        logging.info('request:%s %s' % (request.method, request.path))
        return (await handler(request))
    return logger

async def data_factory(app, handler):
    async def parse_data(request):
        if request.method == 'POST':
            if request.content_type.startswith('application/json'):
                request.__data__ = await request.json()
                logging.info('request json: %s' % str(request.__data__))
            elif request.content_type.startswith('application/x-www-form-urlencoded'):
                request.__data__ = await request.post()
                logging.info('request form:%s' % str(request.__data__))
        return (await handler(request))
    return parse_data

async def response_factory(app, handler):
    async def response(request):
        logging.info('Response handler..')
        r = await handler(request)
        if isinstance(r, web.StreamResponse):
            return r
        if isinstance(r, bytes):
            resp = web.Response(body=r)
            resp = content_type = 'Application/octet-stream'
            return resp
        if isinstance(r, str):
            if r.startswith('redirect:'):
                return web.HTTPFound(r[9:])
            resp = web.Response(body=r.encode('utf-8'))
            resp.content_type = 'text/html;charset=utf-8'
            resp.headers["access-control-allow-origin"] = "*"
            resp.headers["Access-Control-Allow-Headers"] = "content-type, x-requested-with"
            resp.headers['Access-Control-Allow-Methods'] = 'POST, GET'
            return resp
        if isinstance(r, dict):
            template = r.get('__template__')
            if template is None:
                resp = web.Response(body=json.dumps(r, ensure_ascii=False, default=lambda o:o.__dict__).encode('utf-8'))
                resp.content_type = 'Application/json;charset=utf-8'
                resp.headers["access-control-allow-origin"] = "*"
                resp.headers["Access-Control-Allow-Headers"] = "x-requested-with"
                resp.headers['Access-Control-Allow-Methods'] = 'POST, GET'
                return resp
            else:
                resp = web.Response(body=app['__templating__'].get_template(template).render(**r).encode('utf-8'))
                resp.content_type = 'text/html;charset=utf-8'
                return resp
        if isinstance(r, int) and r >= 100 and r < 600:
            return web.Response(r)
        if isinstance(r, tuple) and len(r) == 2:
            t, m = r
            if isinstance(t, int) and t>= 100 and t < 600:
                return web.Response(t, str(m))
        #default
        resp = web.Response(body=str(r).encode('utf-8'))
        resp.content_type = 'text/plain;charset=utf-8'
        return resp
    return response


async def init(loop):
    app = web.Application(loop=loop, middlewares=[
        logger_factory, response_factory
    ])
    mysql_args = {
                    'host':     get_mysql_host(),
                    'port':     get_mysql_port(),
                    'user':     get_mysql_user(),
                    'password': get_mysql_pass(),
                    'db':       get_mysql_db(),
                    'autocommit':True,
                    'maxsize':256
                }
    neo_uri = get_neo_uri()
    ont_uri = get_ont_uri()
    listen_ip = get_listen_ip()
    listen_port = get_listen_port()
    super_node_uri = get_super_node_uri()
    app['pool'] = await get_mysql_pool(mysql_args)
    app['session'] = aiohttp.ClientSession(loop=loop,connector_owner=False)
    app['neo_uri'] = neo_uri
    app['ont_uri'] = ont_uri
    app['net'] = get_net()
    app['super_node_uri'] = super_node_uri
    app['cache'] = Cache(maxsize=0)
    await init_cache(app)
    app['ont_genesis_block_timestamp'] = get_ont_genesis_block_timestamp()
    app['gasaddress'] = get_gas_address()
    app['gasprikey'] = get_gas_prikey()
    app['gaspubkey'] = get_gas_pubkey()
    scheduler = AsyncIOScheduler(job_defaults = {
                    'coalesce': True,
                    'max_instances': 1,
        })
    scheduler.add_job(update_height, 'interval', seconds=2, args=[app['pool'], app['cache']], id='update_height', timezone=utc)
    scheduler.add_job(update_neo_uri, 'interval', seconds=20, args=[app], id='update_neo_uri', timezone=utc)
    scheduler.add_job(update_assets, 'interval', seconds=120, args=[app['pool'], app['cache']], id='update_assets', timezone=utc)
    #scheduler.add_job(update_seas_price, 'interval', seconds=20, args=[app['pool'], app['cache']], id='update_seas_price', timezone=utc)
    scheduler._logger = logging
    scheduler.start()
    add_routes(app, 'handlers')
    srv = await loop.create_server(app.make_handler(), listen_ip, listen_port)
    logging.info('server started at http://%s:%s...' % (listen_ip, listen_port))
    return srv

loop = asyncio.get_event_loop()
loop.run_until_complete(init(loop))
loop.run_forever()
