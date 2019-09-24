import unittest
import asyncio
import time
import random

from config import Config
from bonus import Bonus
from node import Node, encode_advance_area_table, encode_advance_bonus_table

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
    await bonus.db.init_pool()

async def insert_node(address, status, ref, layer, amount, days, next_bonus_time, level, team_level, txid='', bonus_table=Node.zero_advance_bonus_table(), area_table=Node.zero_advance_area_table()):
    '''插入节点'''
    n = {
        'address': address,
        'status': status,
        'txid': rand_string(64) if txid == '' else txid,
        'referrer': ref,
        'layer': layer,
        'amount': amount,
        'days': days,
        'nextbonustime': next_bonus_time,
        'nodelevel': level,
        'teamlevelinfo': team_level,
        'starttime': int(time.time()),
        'bonusadvancetable': encode_advance_bonus_table(bonus_table),
        'areaadvancetable': encode_advance_area_table(area_table),
    }
    await bonus.db.insert_node(n)

async def insert_node_update(addr, op, ref='', amount='0', days=0, penalty=0, txid=''):
    sql = "INSERT INTO node_update(address,operation,referrer,amount,days,penalty,txid,timepoint) " \
          "VALUES ('{}',{},'{}','{}',{},{},'{}',{})".format(addr, op, ref, amount, days, penalty, txid, int(time.time()))
    await bonus.db.mysql_insert_one(sql)

async def insert_history(txid, op, address, amount):
    sql = "INSERT INTO history(txid,operation,index_n,address,value,timepoint,asset) " \
          "VALUES ('{}','{}',0,'{}','{}',{},'{}');".format(txid, op, address, amount, int(time.time()), Config.get_check_seac_asset())
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
    conn, _ = await bonus.db.mysql_execute("delete from node_withdraw;")
    await bonus.db.pool.release(conn)
    conn, _ = await bonus.db.mysql_execute("delete from node_update;")
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

        await bonus.db.update_node_by_address({'address': address, 'signin': 1})
        await doBonus(31)

        b = await bonus.db.get_lastest_node_bonus(address)
        expect_bonus = round(30*Config.get_bonus_conf()['locked_bonus']['1000-30']+Config.get_bonus_conf()['locked_bonus']['1000-30']*0.1, 3)
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
        self.assertEqual(1, node1.level)

        b = await bonus.db.get_lastest_node_bonus(address)
        expect_bonus = round(2*Config.get_bonus_conf()['locked_bonus']['1000-30']+Config.get_bonus_conf()['locked_bonus']['1000-30']*0.2*2, 3)
        self.assertEqual(expect_bonus, round(float(b['total']), 3))
        self.assertEqual(expect_bonus, round(float(b['remain']), 3))

    @async_test
    async def test_handle_unconfirmed_node_tx(self):
        address = rand_string(34)
        txid1 = rand_string(64)
        await insert_node(address, -1, rand_string(34), 1, 1000, 30, 1, 1, '0'*96, txid=txid1)
        await insert_history(txid1, 'out', address, 1000)
        await insert_history(txid1, 'in', Config.get_address_for_receive_seac(), 1000)

        address2 = rand_string(34)
        txid2 = rand_string(64)
        await insert_node(address2, 1, address, 2, 1000, 30, 1, 1, '0' * 96, txid=txid2)
        await insert_history(txid2, 'out', address2, 1000)
        await insert_history(txid2, 'in', Config.get_address_for_receive_seac(), 1000)

        #amount不匹配
        address3 = rand_string(34)
        txid3 = rand_string(64)
        await insert_node(address3, -1, address, 2, 1000, 30, 1, 1, '0' * 96, txid=txid3)
        await insert_history(txid3, 'out', address3, 900)
        await insert_history(txid3, 'in', Config.get_address_for_receive_seac(), 900)

        #使用过的txid
        address4 = rand_string(34)
        txid4 = rand_string(64)
        await insert_node(address4, -1, address, 2, 1000, 30, 1, 1, '0' * 96, txid=txid4)
        await insert_history(txid4, 'out', address3, 1000)
        await insert_history(txid4, 'in', Config.get_address_for_receive_seac(), 1000)
        await bonus.db.record_used_txid(txid4, time.time())

        await bonus.handle_unconfirmed_node_tx()
        await bonus.handle_unconfirmed_node_tx()

        node = await bonus.db.get_node_by_address(address)
        self.assertEqual(0, node.status)
        node = await bonus.db.get_node_by_address(address2)
        self.assertEqual(1, node.status)
        node = await bonus.db.get_node_by_address(address3)
        self.assertEqual(-8, node.status)
        node = await bonus.db.get_node_by_address(address4)
        self.assertEqual(-10, node.status)

    @async_test
    async def test_handle_node_updates_new(self):
        address = rand_string(34)
        await insert_node_update(address, 1, ref=address, amount='1000', days=30, txid=rand_string(64))
        await bonus.handle_node_updates()

        node = await bonus.db.get_node_by_address(address)
        self.assertEqual(1, node.layer)
        updates = await bonus.db.get_node_updates()
        self.assertEqual(0, len(updates))

        address2 = rand_string(34)
        await insert_node_update(address2, 1, ref=address, amount='1000', days=30, txid=rand_string(64))
        await bonus.handle_node_updates()

        node = await bonus.db.get_node_by_address(address2)
        self.assertEqual(2, node.layer)
        updates = await bonus.db.get_node_updates()
        self.assertEqual(0, len(updates))

    @async_test
    async def test_handle_node_updates_unlock(self):
        address = rand_string(34)
        await insert_node(address, 0, rand_string(34), 1, 1000, 30, 1, 1, '0'*96)

        await insert_node_update(address, 2)
        await bonus.handle_node_updates()

        node = await bonus.db.get_node_by_address(address)
        self.assertEqual(-5, node.status)

    @async_test
    async def test_handle_node_updates_withdraw(self):
        now = int(time.time())
        await bonus.prepare_status(now)
        address = rand_string(34)
        await insert_node(address, 0, rand_string(34), 1, 1000, 30, now+1, 1, '0'*96)
        await doBonus(2)

        await insert_node_update(address, 3, amount='1')
        await bonus.handle_node_updates()

        b = await bonus.db.get_lastest_node_bonus(address)
        expect_bonus = round(2*Config.get_bonus_conf()['locked_bonus']['1000-30'], 3)
        self.assertEqual(expect_bonus, round(float(b['total']), 3))
        self.assertEqual(expect_bonus-1, round(float(b['remain']), 3))

    @async_test
    async def test_handle_node_updates_signin(self):
        address = rand_string(34)
        await insert_node(address, 0, rand_string(34), 1, 1000, 30, 1, 1, '0' * 96)

        await insert_node_update(address, 4)
        await bonus.handle_node_updates()
        node = await bonus.db.get_node_by_address(address)
        self.assertEqual(1, node.signin)

    @async_test
    async def test_handle_node_updates_active(self):
        address = rand_string(34)
        await insert_node_update(address, 1, ref=address, amount='1000', days=30, txid=rand_string(64))
        await bonus.handle_node_updates()

        node = await bonus.db.get_node_by_address(address)
        self.assertEqual(1, node.layer)
        self.assertEqual(-1, node.status)
        updates = await bonus.db.get_node_updates()
        self.assertEqual(0, len(updates))

        txid = rand_string(64)
        await insert_node_update(address, 5, amount='1000', days=30, txid=txid)
        await bonus.handle_node_updates()

        nodes = await bonus.db.get_nodes_by_status(-1)
        node = nodes[0]
        self.assertEqual(txid, node['txid'])
        updates = await bonus.db.get_node_updates()
        self.assertEqual(0, len(updates))

def run():
    loop.run_until_complete(init_bonus())
    loop.run_until_complete(unittest.main())
    loop.close()

if __name__ == '__main__':
    loop = asyncio.new_event_loop()
    run()