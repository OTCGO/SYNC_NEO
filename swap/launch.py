#! /usr/bin/env python3
# coding: utf-8
# flow@SEA
# Licensed under the MIT License.

import os
import sys
import time
import asyncio
import aiohttp
import aiomysql
import uvloop; asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
from pytz import utc
from logzero import logger
from Config import Config as C
from tasks import tasks


async def get_mysql_pool(mysql_args):
    try:
        logger.info('start to connect db')
        pool = await aiomysql.create_pool(**mysql_args)
        logger.info('succeed to connet db!')
        return pool
    except asyncio.CancelledError:
        raise asyncio.CancelledError
    except Exception as e:
        logger.error("mysql connet failure:{}".format(e.args[0]))
        return False

async def get_mysql_cursor(pool):
    conn = await pool.acquire()
    cur  = await conn.cursor()
    return conn, cur

async def mysql_insert_one(pool, sql):
    conn, cur = await get_mysql_cursor(pool)
    logger.info('SQL:%s' % sql)
    try:
        await cur.execute(sql)
        num = cur.rowcount
        #logger.info('%s row affected' % num)
        return num
    except Exception as e:
        logger.error("mysql INSERT failure:{}".format(e.args[0]))
        sys.exit(1)
    finally:
        await pool.release(conn)

async def get_status(pool, name):
    conn, cur = await get_mysql_cursor(pool)
    try:
        await cur.execute("SELECT update_height FROM status WHERE name='%s';" % name)
        result = await cur.fetchone()
        if result:
            uh = result[0]
            logger.info('database %s height: %s' % (name, uh))
            return uh
        logger.info('database %s height: -1' % name)
        return -1 
    except Exception as e:
        logger.error("mysql SELECT failure:{}".format(e.args[0]))
        sys.exit(1)
    finally:
        await pool.release(conn)

async def update_status(name, pool, height):
    sql="INSERT INTO status(name,update_height) VALUES ('%s',%s) ON DUPLICATE KEY UPDATE update_height=%s;" % (name,height,height)
    await mysql_insert_one(pool, sql)

async def mysql_query(pool, sql):
    conn, cur = await get_mysql_cursor(pool)
    logger.info('SQL:%s' % sql)
    try:
        await cur.execute(sql)
        return await cur.fetchall()
    except Exception as e:
        logger.error("mysql QUERY failure:{}".format(e.args[0]))
        sys.exit(1)
    finally:
        await pool.release(conn)

async def get_block_timepoint(super_node, net, session, height):
    url = super_node + '/' + net + '/timepoint/' + str(height)
    async with session.get(url) as resp:
        if 200 != resp.status:
            logger.error('Unable to visit %s' % url)
            return None
        j = await resp.json()
        if 'error' in j.keys():
            logger.error('Visit %s occur error %s' % (url, j['error']))
            return None
        return j['timepoint']

async def mysql_get_swap_launch_history(pool, address, asset, ta, tb):
    if ta >= tb: return None
    sql = "SELECT txid,index_n,operation,address,asset,value,timepoint FROM history WHERE address='%s' AND timepoint > %s AND timepoint <= %s;" % (address,ta,tb)
    hd = {}
    his = await mysql_query(pool, sql)
    for h in his:
        if h[2] != 'in': continue
        key = h[0] + '_' + str(h[1])
        if h[4] == asset:
            if key not in hd.keys(): hd[key] = {}
            hd[key]['txid'] = h[0][-64:]
            hd[key]['to'] = address
            hd[key]['amount'] = h[5]
            hd[key]['asset'] = asset
            hd[key]['timepoint'] = h[6]
    for h in hd:
        sql = "SELECT address FROM history WHERE txid='{}' and operation='out' and index_n={};".format( *h.split('_'))
        r = await mysql_query(pool, sql)
        if r: hd[h]['from'] = r[0][0]
        else:
            logger.error('mysql query error')
            sys.exit(1)
    return hd

async def mysql_update_swap_launch(pool, swap_history):
    if not swap_history: return
    for h in swap_history.values():
        if 'from' not in h.keys():
            logger.error('txid:%s has no from' % h['txid'])
            sys.exit(1)
        sql = "INSERT IGNORE INTO swap_launch (txid,from_address,to_address,amount,asset,timepoint) VALUES ('%s','%s','%s','%s','%s',%s);" % (h['txid'],h['from'],h['to'],h['amount'],h['asset'],h['timepoint'])
        await mysql_insert_one(pool, sql)


async def launch(net, mysql_args, super_node, tasks, loop):
    logger.info(tasks)
    session = aiohttp.ClientSession(loop=loop)
    pool = await get_mysql_pool(mysql_args)
    if not pool: sys.exit(1)
    try:
        while True:
            ha, hb = await asyncio.gather(
                    get_status(pool, 'swap'),
                    get_status(pool, 'history')
                )
            if ha == -1: ha = 4115000
            hb = min([ha+100, hb])
            logger.info('height scope: %s - %s' % (ha, hb))
            if ha >= hb:
                logger.info('sleep 120 seconds')
                await asyncio.sleep(12)
                continue
            ta, tb = await asyncio.gather(
                    get_block_timepoint(super_node, net, session, ha),
                    get_block_timepoint(super_node, net, session, hb)
                )
            if None in [ta, tb]:
                logger.info('sleep 10 seconds')
                await asyncio.sleep(10)
                continue
            logger.info('time scope: %s - %s' % (ta, tb))
            for a in tasks:
                slh = await mysql_get_swap_launch_history(pool, a, tasks[a]['assetin'], ta, tb)
                logger.info('swap history\n%s' % slh)
                if slh: await mysql_update_swap_launch(pool, slh)
            await update_status('swap', pool, hb)
            logger.info('sleep 60 seconds')
            await asyncio.sleep(20)
    except Exception as e:
        logger.error('EXCEPTION: {}'.format(e.args[0]))
    finally:
        pool.close()
        await pool.wait_closed()
        await session.close()


if __name__ == "__main__":
    net = C.get_net()
    mysql_args = {
                    'host':     C.get_mysql_host(),
                    'port':     C.get_mysql_port(),
                    'user':     C.get_mysql_user(),
                    'password': C.get_mysql_pass(),
                    'db':       C.get_mysql_db(), 
                    'autocommit':True
                }
    super_node = C.get_super_node()
    loop = asyncio.get_event_loop()
    loop.run_until_complete(launch(net, mysql_args, super_node, tasks, loop))
    loop.run_forever()
