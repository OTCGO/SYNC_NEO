import unittest
import asyncio
import time
import random
import sys

from db import DB
from config import Config as C

def async_test(coro):
    def wrapper(*args, **kwargs):
        return loop.run_until_complete(coro(*args, **kwargs))
    return wrapper

def _run(coro):
    def wrapper(*args, **kwargs):
        return loop.run_until_complete(coro(*args, **kwargs))
    return wrapper

async def init_db():
    mysql_args = {
        'host':     "127.0.0.1",
        'port':     3306,
        'user':     'root',
        'password': '123456',
        'db':       'sea_test',
        'autocommit':True,
        'maxsize':1
    }
    global db
    db = DB(mysql_args)
    await db.init_pool()
    return db

def rand_string(n):
    '''生成随机字符串'''
    seed = "1234567890abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"
    sa = []
    for i in range(n):
        sa.append(random.choice(seed))
    salt = ''.join(sa)
    return salt

async def del_all():
    conn, _ = await db.mysql_execute('delete from status')
    await db.pool.release(conn)
    conn, _ = await db.mysql_execute('delete from node')
    await db.pool.release(conn)
    conn, _ = await db.mysql_execute('delete from node_bonus')
    await db.pool.release(conn)

async def insert_node(address, status, ref, layer, amount, days, next_bonus_time, level, team_level):
    '''插入节点'''
    sql = 'INSERT INTO node(address,status,referrer,layer,amount,days,nextbonustime,nodelevel,teamlevelinfo,txid,starttime,performance) ' \
          'VALUES ("{}",{},"{}",{},{},{},{},{},"{}","{}",{},{});'.format(address, status, ref, layer, amount, days,
                next_bonus_time, level, team_level, rand_string(64), time.time(), 0)
    await db.mysql_insert_one(sql)

class TestDB(unittest.TestCase):

    @async_test
    async def setUp(self):
        await del_all()

    @async_test
    async def test_update_status(self):
        status = await db.get_status('node_bonus')
        assert status == -1
        await db.update_status('node_bonus', 0)
        status = await db.get_status('node_bonus')
        assert status == 0
        await db.update_status('node_bonus', 1)
        self.assertEqual(1, await db.get_status('node_bonus'))

    @async_test
    async def test_get_max_node_layer(self):
        m = await db.get_max_node_layer()
        assert m == 0
        #插入节点
        await insert_node(rand_string(34), 0, rand_string(34), 1, 1000, 30, time.time(), 1, '0'*96)
        await insert_node(rand_string(34), 0, rand_string(34), 2, 1000, 30, time.time(), 1, '0'*96)

        m = await db.get_max_node_layer()
        assert m == 2

    @async_test
    async def test_get_node_for_bonus(self):
        nodes = await db.get_node_for_bonus(1)
        self.assertEqual(0, len(nodes))
        address = rand_string(34)
        ref = rand_string(34)
        await insert_node(address, 0, ref, 1, 1000, 30, time.time(), 1, '0'*96)

        nodes = await db.get_node_for_bonus(1)
        self.assertEqual(1, len(nodes))
        node = nodes[0]
        self.assertEqual(address, node.address)
        self.assertEqual(0, node.status)
        self.assertEqual(ref, node.referrer)
        self.assertTrue(node.id > 0)
        self.assertEqual(1, node.layer)
        self.assertEqual(1000, node.locked_amount)
        self.assertEqual(30, node.days)
        self.assertEqual('0'*96, node.team_level_info)

    @async_test
    async def test_update_node_status_exit(self):
        await insert_node(rand_string(34), 30, rand_string(34), 1, 1000, 30, time.time(), 1, '0'*96)
        await insert_node(rand_string(34), 90, rand_string(34), 1, 1000, 90, time.time(), 1, '0'*96)
        await insert_node(rand_string(34), 89, rand_string(34), 1, 1000, 180, time.time(), 1, '0'*96)

        await db.update_node_status_exit()

        nodes = await db.get_node_for_bonus(1)
        self.assertEqual(3, len(nodes))
        for i in range(len(nodes)):
            if nodes[i].days == 180:
                self.assertEqual(89, nodes[i].status)
            else:
                self.assertEqual(-2, nodes[i].status)

    @async_test
    async def test_add_node_bonus(self):
        now = int(time.time())
        addr = rand_string(34)
        await insert_node(addr, 0, rand_string(34), 1, 1000, 30, now, 1, '0'*96)
        nodes = await db.get_node_for_bonus(1)
        self.assertEqual(1, len(nodes))
        node = nodes[0]
        node.locked_bonus = 1.64
        await db.add_node_bonus(node, now)

        ns = await db.get_node_for_bonus(1)
        self.assertEqual(1, len(ns))
        self.assertEqual(1, ns[0].status)
        ns[0].locked_bonus = 1.64
        bt = now + C.get_bonus_interval()
        await db.add_node_bonus(ns[0], bt)

        b = await db.get_lastest_node_bonus(addr)
        self.assertEqual(3.28, float(b['total']))

def run():
    loop.run_until_complete(init_db())
    loop.run_until_complete(unittest.main())
    loop.run_until_complete(db.pool.close())
    loop.close()

if __name__ == '__main__':
    loop = asyncio.new_event_loop()
    run()