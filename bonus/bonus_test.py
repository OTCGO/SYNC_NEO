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
        await doBonus(3)

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
        await doBonus(3)

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

    @async_test
    async def test_level_one_to_four(self):
        '''测试等级 1—4'''
        now = int(time.time())
        await bonus.prepare_status(now)
        async def insert(amount, ref=''):
            address = rand_string(34)
            txid1 = rand_string(64)
            if ref == '':
                ref = address
            await insert_node_update(address, 1, ref=ref, amount=str(amount), days=30, txid=txid1)
            await insert_history(txid1, 'out', address, amount)
            await insert_history(txid1, 'in', Config.get_address_for_receive_seac(), amount)
            return address
        address1 = await insert(1000)
        address2 = await insert(3000)
        address3 = await insert(5000)
        address4 = await insert(10000)
        await bonus.handle_node_updates()
        await bonus.handle_unconfirmed_node_tx()
        await doBonus(1)

        async def check_level(address, level):
            node = await bonus.db.get_node_by_address(address)
            self.assertEqual(level, node.level)
        await check_level(address1, 1)
        await check_level(address2, 2)
        await check_level(address3, 3)
        await check_level(address4, 4)

    @async_test
    async def test_level_five(self):
        '''测试等级5'''
        '''
                5
             /    \
           4       4
        '''
        now = int(time.time())
        await bonus.prepare_status(now)
        async def insert(amount, ref=''):
            address = rand_string(34)
            txid1 = rand_string(64)
            if ref == '':
                ref = address
            await insert_node_update(address, 1, ref=ref, amount=str(amount), days=30, txid=txid1)
            await insert_history(txid1, 'out', address, amount)
            await insert_history(txid1, 'in', Config.get_address_for_receive_seac(), amount)
            return address
        addr1 = await insert(1000)
        addr2 = await insert(10000, ref=addr1)
        addr3 = await insert(10000, ref=addr1)
        await bonus.handle_node_updates()
        await bonus.handle_unconfirmed_node_tx()

        await doBonus(3)

        node = await bonus.db.get_node_by_address(addr1)
        self.assertEqual(5, node.level)
        self.assertEqual(2, node.referrals)
        self.assertEqual(20000, node.performance)
        self.assertEqual(1, node.status)
        self.assertEqual(1, node.burned)
        self.assertEqual(0, node.small_area_burned)

        b = await bonus.db.get_lastest_node_bonus(addr1)
        locked_bonus = 1*Config.get_bonus_conf()['locked_bonus']['1000-30']
        referrals_bonus = 2*0.2*Config.get_bonus_conf()['locked_bonus']['10000-30']
        team_bonus = 2*Config.get_bonus_conf()['locked_bonus']['10000-30']*(1-Config.get_bonus_conf()['level_burned_bonus']['low_one'])*Config.get_bonus_conf()['team_bonus_rate'][5]
        self.assertEqual(locked_bonus, float(b['locked_bonus']))
        self.assertEqual(referrals_bonus, float(b['referrals_bonus']))
        self.assertEqual(round(team_bonus, 3), float(b['team_bonus']))
        self.assertEqual(round(locked_bonus+referrals_bonus+team_bonus, 3), float(b['total']))

    @async_test
    async def test_small_area_burned(self):
        '''测试小区烧伤'''
        '''
                           5
                        /    \ 
                      6       3  
                   /  |  \      \
                 5    5    5     1
               /  \  / \  / \
              4   4 4  4 4   4  
        '''
        now = int(time.time())
        await bonus.prepare_status(now)
        async def insert(amount, ref=''):
            time.sleep(1)
            address = rand_string(34)
            txid1 = rand_string(64)
            if ref == '':
                ref = address
            await insert_node_update(address, 1, ref=ref, amount=str(amount), days=30, txid=txid1)
            await insert_history(txid1, 'out', address, amount)
            await insert_history(txid1, 'in', Config.get_address_for_receive_seac(), amount)
            return address
        a1 = await insert(10000)
        a2 = await insert(10000, ref=a1)
        a3 = await insert(5000, ref=a1)
        a4 = await insert(10000, ref=a2)
        a5 = await insert(10000, ref=a2)
        a6 = await insert(10000, ref=a2)
        a7 = await insert(1000, ref=a3)
        a8 = await insert(10000, ref=a4)
        a9 = await insert(10000, ref=a4)
        a10 = await insert(10000, ref=a5)
        a11 = await insert(10000, ref=a5)
        a12 = await insert(10000, ref=a6)
        a13 = await insert(10000, ref=a6)

        await bonus.handle_node_updates()
        await bonus.handle_unconfirmed_node_tx()

        await doBonus(3)
        async def check_node(addr, level, perf, status, burned, small_area_burned, referrals):
            node = await bonus.db.get_node_by_address(addr)
            self.assertEqual(level, node.level)
            self.assertEqual(perf, node.performance)
            self.assertEqual(status, node.status)
            self.assertEqual(burned, node.burned)
            self.assertEqual(small_area_burned, node.small_area_burned)
            self.assertEqual(referrals, node.referrals)
        await check_node(a1, 5, 106000, 1, 1, 1, 2)
        await check_node(a2, 6, 90000, 1, 1, 0, 3)
        await check_node(a3, 3, 1000, 1, 0, 0, 1)
        await check_node(a4, 5, 20000, 1, 1, 0, 2)
        await check_node(a5, 5, 20000, 1, 1, 0, 2)
        await check_node(a6, 5, 20000, 1, 1, 0, 2)
        await check_node(a7, 1, 0, 1, 0, 0, 0)
        await check_node(a8, 4, 0, 1, 0, 0, 0)
        await check_node(a9, 4, 0, 1, 0, 0, 0)
        await check_node(a10, 4, 0, 1, 0, 0, 0)
        await check_node(a11, 4, 0, 1, 0, 0, 0)
        await check_node(a12, 4, 0, 1, 0, 0, 0)
        await check_node(a13, 4, 0, 1, 0, 0, 0)

        async def check_bonus(addr, locked_bonus, referrals_bonus, team_bonus):
            b = await bonus.db.get_lastest_node_bonus(addr)
            self.assertEqual(locked_bonus, float(b['locked_bonus']))
            self.assertEqual(referrals_bonus, float(b['referrals_bonus']))
            self.assertEqual(round(team_bonus, 3), float(b['team_bonus']))
            self.assertEqual(round(locked_bonus+referrals_bonus+team_bonus, 3), float(b['total']))
        #a1
        conf = Config.get_bonus_conf()
        locked_bonus = conf['locked_bonus']['10000-30']
        referrals_bonus = 0.2*(conf['locked_bonus']['10000-30']+conf['locked_bonus']['5000-30'])
        team_bonus = 10*conf['locked_bonus']['10000-30']*(1-conf['level_burned_bonus']['high_level'])*conf['team_bonus_rate'][5] + (conf['locked_bonus']['5000-30']+conf['locked_bonus']['1000-30'])*(1-conf['small_area_burned_bonus']) *conf['team_bonus_rate'][5]
        await check_bonus(a1, locked_bonus, referrals_bonus, team_bonus)

        #a3
        locked_bonus = conf['locked_bonus']['5000-30']
        referrals_bonus = 0.2 * conf['locked_bonus']['1000-30']
        team_bonus = 0
        await check_bonus(a3, locked_bonus, referrals_bonus, team_bonus)


def run():
    loop.run_until_complete(init_bonus())
    loop.run_until_complete(unittest.main())
    loop.close()

if __name__ == '__main__':
    loop = asyncio.new_event_loop()
    run()