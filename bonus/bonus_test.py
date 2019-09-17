import unittest
import asyncio
import time
import random

from config import Config
from bonus import Bonus
from node import Node

def async_test(coro):
    def wrapper(*args, **kwargs):
        return loop.run_until_complete(coro(*args, **kwargs))
    return wrapper

async def init_bonus():
    mysql_args = {
        'host':     "127.0.0.1",
        'port':     3306,
        'user':     'root',
        'password': '123456',
        'db':       'sea_test',
        'autocommit':True,
        'maxsize':  1
    }
    global bonus
    bonus = Bonus(mysql_args, Config.get_bonus_conf())
    bonus.debug = True
    await bonus.db.init_pool()

async def insert_node(address, status, ref, layer, amount, days, next_bonus_time, level, team_level):
    '''插入节点'''
    sql = 'INSERT INTO node(address,status,referrer,layer,amount,days,nextbonustime,nodelevel,teamlevelinfo,txid,starttime,performance) ' \
          'VALUES ("{}",{},"{}",{},{},{},{},{},"{}","{}",{},{});'.format(address, status, ref, layer, amount, days,
                next_bonus_time, level, team_level, rand_string(64), time.time(), 0)
    await bonus.db.mysql_insert_one(sql)
async def get_node_by_address(address):
    sql = "SELECT id,status,referrer,address,amount,days,layer,nextbonustime,nodelevel,performance,teamlevelinfo,referrals FROM node WHERE address = '%s';" % address
    r = await bonus.db.mysql_query_one(sql)
    if r:
        node = Node()
        node.id = r[0]
        node.status = r[1]
        node.referrer = r[2]
        node.address = r[3]
        node.locked_amount = r[4]
        node.days = r[5]
        node.layer = r[6]
        node.next_bonus_time = r[7]
        node.level = r[8]
        node.performance = r[9]
        node.team_level_info = r[10]
        node.referrals = r[11]
        return node
    return None

def rand_string(n):
    '''生成随机字符串'''
    seed = "1234567890abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"
    sa = []
    for i in range(n):
        sa.append(random.choice(seed))
    salt = ''.join(sa)
    return salt

async def doBonus(times):
    '''分红，指定次数'''
    i = 0
    while i < times:
        f = await bonus.bonus()
        if not f:
            time.sleep(1)
        else:
            i += 1

async def del_all():
    conn, _ = await bonus.db.mysql_execute('delete from node')
    await bonus.db.pool.release(conn)
    conn,_ = await bonus.db.mysql_execute('delete from node_bonus')
    await bonus.db.pool.release(conn)
    conn, _ = await bonus.db.mysql_execute("delete from status;")
    await bonus.db.pool.release(conn)

class TestBonus(unittest.TestCase):
    @async_test
    async def setUp(self):
        await del_all()

    @async_test
    async def test_one_node(self):
        now = int(time.time())
        await bonus.prepare_status(now)
        address = rand_string(34)
        await insert_node(address, 0, rand_string(34), 1, 1000, 30, now+1, 1, '0'*96)
        await doBonus(31)

        b = await bonus.db.get_lastest_node_bonus(address)
        expect_bonus = round(30*Config.get_bonus_conf()['locked_bonus']['1000-30'], 3)
        self.assertEqual(expect_bonus, round(float(b['total']), 3))
        self.assertEqual(expect_bonus, round(float(b['remain']), 3))

    @async_test
    async def test_two_nodes(self):
        now = int(time.time())
        await bonus.prepare_status(now)
        address = rand_string(34)
        await insert_node(address, 0, rand_string(34), 1, 1000, 30, now+1, 1, '0'*96)
        address2 = rand_string(34)
        await insert_node(address2, 0, rand_string(34), 1, 1000, 30, now+1, 1, '0'*96)

        await doBonus(31)

        b = await bonus.db.get_lastest_node_bonus(address)
        expect_bonus = round(30*Config.get_bonus_conf()['locked_bonus']['1000-30'], 3)
        self.assertEqual(expect_bonus, round(float(b['total']), 3))
        self.assertEqual(expect_bonus, round(float(b['remain']), 3))

        b = await bonus.db.get_lastest_node_bonus(address2)
        expect_bonus = round(30*Config.get_bonus_conf()['locked_bonus']['1000-30'], 3)
        self.assertEqual(expect_bonus, round(float(b['total']), 3))
        self.assertEqual(expect_bonus, round(float(b['remain']), 3))

    @async_test
    async def test_two_layer(self):
        now = int(time.time())
        await bonus.prepare_status(now)
        address = rand_string(34)
        await insert_node(address, 0, rand_string(34), 1, 1000, 30, now+1, 1, '0'*96)
        address2 = rand_string(34)
        await insert_node(address2, 0, address, 2, 1000, 30, now+1, 1, '0'*96)
        await doBonus(2)

        node1 = await get_node_by_address(address)
        self.assertIsNotNone(node1)
        self.assertEqual(5, node1.level)


def run():
    loop.run_until_complete(init_bonus())
    loop.run_until_complete(unittest.main())
    loop.close()

if __name__ == '__main__':
    loop = asyncio.new_event_loop()
    run()