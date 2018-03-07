import logging; logging.basicConfig(level=logging.INFO)
import asyncio
import aiohttp
import json
import os
import time
import uvloop; asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
import motor.motor_asyncio
from datetime import datetime
from aiohttp import web
from coreweb import add_routes
from dotenv import load_dotenv, find_dotenv
load_dotenv(find_dotenv(), override=True)


def get_mongo_uri():
    mongo_server = os.environ.get('MONGOSERVER')
    mongo_port   = os.environ.get('MONGOPORT')
    mongo_user   = os.environ.get('MONGOUSER')
    mongo_pass   = os.environ.get('MONGOPASS')
    if mongo_user and mongo_pass:
        return 'mongodb://%s:%s@%s:%s' % (mongo_user, mongo_pass, mongo_server, mongo_port)
    else:
        return 'mongodb://%s:%s' % (mongo_server, mongo_port)

def get_neo_uri():
    neo_node = os.environ.get('NEONODE')
    neo_port = os.environ.get('NEOPORT')
    return 'http://%s:%s' % (neo_node, neo_port)

get_mongo_db = lambda:os.environ.get('MONGODB')
get_listen_ip = lambda:os.environ.get('LISTENIP')
get_listen_port = lambda:os.environ.get('LISTENPORT')

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
    mongo_uri = get_mongo_uri()
    neo_uri = get_neo_uri()
    mongo_db = get_mongo_db()
    listen_ip = get_listen_ip()
    listen_port = get_listen_port()
    app['client'] = motor.motor_asyncio.AsyncIOMotorClient(mongo_uri)
    app['db'] = app['client'][mongo_db]
    app['session'] = aiohttp.ClientSession(loop=loop,connector_owner=False)
    app['neo_uri'] = neo_uri
    add_routes(app, 'handlers')
    srv = await loop.create_server(app.make_handler(), listen_ip, listen_port)
    logging.info('server started at http://%s:%s...' % (listen_ip, listen_port))
    return srv

loop = asyncio.get_event_loop()
loop.run_until_complete(init(loop))
loop.run_forever()
