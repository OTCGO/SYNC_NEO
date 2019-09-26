import asyncio
import time
from datetime import datetime
from logzero import logger
import requests

from db import DB
from config import Config as C
from node import Node, encode_advance_area_table, encode_advance_bonus_table

class Bonus:
    #节点分组，key为推荐人，value为节点数组
    node_group = {}
    err_txid_dict = {}

    def __init__(self, mysql_args, bonus_conf):
        self.db = DB(mysql_args)
        self.bonus_conf = bonus_conf
        pass

    async def prepare(self):
        await self.db.init_pool()
        await self.prepare_status(int(time.time()))

    async def prepare_status(self, now):
        node_bonus = await self.db.get_status('node_bonus')
        if node_bonus == -1:
            await self.db.update_status('node_bonus', 0)
        node_bonus_timepoint = await self.db.get_status('node_bonus_timepoint')
        if node_bonus_timepoint == -1:
            bonus_time = now
            if C.get_bonus_start_time() != 'now':
                bonus_time = time.mktime(datetime.fromtimestamp(bonus_time).date().timetuple())+10

            await self.db.update_status('node_bonus_timepoint', bonus_time)

    async def handle_by_layer(self, nodes, bonus_time, layer):
        '''处理同一层级的所有节点'''
        group_by_ref = {}
        for i in range(len(nodes)):
            # 计算锁仓分红
            if nodes[i].can_bonus(bonus_time):
                nodes[i].locked_bonus = self.compute_locked_bonus(nodes[i].locked_amount, nodes[i].days)
                #签到收益
                if nodes[i].signin == 1:
                    nodes[i].signin_bonus = round(0.1*nodes[i].locked_bonus, 3)
                    nodes[i].signin = 0
            # 找子节点
            if nodes[i].address in self.node_group.keys():
                nodes[i].set_children(self.node_group[nodes[i].address])
            # 计算团队业绩
            nodes[i].compute_performance()
            # 计算直推人
            nodes[i].compute_referrals()
            # 计算直推分红
            nodes[i].referrals_bonus = self.compute_referrals_bonus(nodes[i])
            # 计算团队各等级数量
            nodes[i].compute_team_level()
            # 计算节点等级
            nodes[i].compute_level()
            # 团队业绩分红
            if nodes[i].can_bonus(bonus_time):
                burned, small_area_burned, nodes[i].team_bonus = self.compute_team_bonus(nodes[i])
                nodes[i].burned = 1 if burned else 0
                nodes[i].small_area_burned = 1 if small_area_burned else 0

            nodes[i].compute_advance_bonus_table()
            nodes[i].compute_area_advance_tabel()

            # 增加分红记录、更新节点状态，更新数据到数据库
            await self.db.add_node_bonus(nodes[i], bonus_time)

            if nodes[i].can_bonus(bonus_time):
                nodes[i].status += 1

            # 根据推荐人进行分组
            ref = nodes[i].referrer
            if ref in group_by_ref.keys():
                group_by_ref[ref].append(nodes[i])
            else:
                group_by_ref[ref] = [nodes[i]]

        # 清除孙子以下节点，减少内存占用
        for addr in self.node_group.keys():
            ns = self.node_group[addr]
            for i in range(len(ns)):
                ns[i].clear_children()

        self.node_group = group_by_ref
        # 所有分红结束，清空数据
        if layer == 1:
            self.node_group = {}


    def compute_locked_bonus(self, locked_amount, days):
        '''计算锁仓分红'''
        return self.bonus_conf['locked_bonus']["%s-%s" % (locked_amount, days)]

    def compute_referrals_bonus(self, node):
        '''计算直推分红'''
        bonus = 0
        for child in node.children:
            if not child.can_compute_in_team():
                continue
            bonus += 0.2*self.compute_locked_bonus(child.locked_amount, child.days)
        return round(bonus, 3)

    def compute_team_bonus(self, node):
        '''计算团队分红, 保留三位小数'''
        if node.level < 5:
            return False, False, 0
        team_bonus = 0
        small_area_burned = False #小区烧伤
        big_small_area = node.compute_big_small_area()
        if len(big_small_area['big']) > 0 and big_small_area['small'] > min(big_small_area['big'])*0.5:
            small_area_burned = True

        burned = False
        info = node.compute_dynamic_bonus_cate()
        for k in info:
            if k in ['high_level', 'equal_level', 'low_one'] and info[k] > 0:
                burned = True
            if small_area_burned and k == 'normal':
                b = info[k] * (1-self.bonus_conf['level_burned_bonus'][k])
                if small_area_burned:
                    b = b*(1-self.bonus_conf['small_area_burned_bonus'])
                team_bonus += b
            else:
                team_bonus += info[k] * (1-self.bonus_conf['level_burned_bonus'][k])
        return burned, small_area_burned, round(team_bonus*self.bonus_conf['team_bonus_rate'][node.level], 3)

    def check_next_layer(self, is_max_layer):
        '''检测是否需要先找出下一层级节点，防止程序异常退出再次运行，下一层级节点数据丢失'''
        if is_max_layer or self.node_group:
            return True
        return False

    async def recover_layer(self, layer):
        '''恢复指定的层级节点数据'''
        logger.info("[BONUS] recover {} layer node data...".format(layer))
        # 恢复数据
        nodes = await self.db.get_node_for_bonus(layer)
        group_by_ref = {}
        for i in range(len(nodes)):
            # 根据推荐人进行分组
            ref = nodes[i].referrer
            if ref in group_by_ref.keys():
                group_by_ref[ref].append(nodes[i])
            else:
                group_by_ref[ref] = [nodes[i]]
        self.node_group = group_by_ref

    async def bonus(self):
        '''执行分红'''
        now = time.time()
        bonus_time = await self.db.get_status('node_bonus_timepoint')
        if now < bonus_time:
            return False

        node_bonus = await self.db.get_status('node_bonus')
        is_max_layer = False
        if node_bonus == 0:
            node_bonus = await self.db.get_max_node_layer()
            is_max_layer = True
            logger.info("[BONUS] get max node layer: {}".format(node_bonus))

        for layer in range(node_bonus, 0, -1):
            if not self.check_next_layer(is_max_layer):
                await self.recover_layer(layer + 1)

            nodes = await self.db.get_node_for_bonus(layer)
            await self.handle_by_layer(nodes, bonus_time, layer)

            await self.db.update_status('node_bonus', layer)
            logger.info("[BONUS] handle {} layer success".format(layer))

        await self.db.update_node_status_exit()

        await self.db.update_status('node_bonus', 0)
        await self.db.update_status('node_bonus_timepoint', bonus_time + C.get_bonus_interval())
        logger.info("[BONUS] handle all layers success")
        self.node_group = {}
        return True

    async def handle_unconfirmed_node_tx(self):
        '''处理未确认的节点交易'''
        nodes = await self.db.get_nodes_by_status(-1)
        logger.info('[NODE] handle {} unconfirmed nodes.'.format(len(nodes)))
        for node in nodes:
            status = await self.check_tx_confirmed(node['txid'], node['address'], node['amount'])
            if status == 0:
                await self.db.update_node_by_id({'id': node['id'], 'status': status})
            elif status == -1:
                continue
            else:
                if node['txid'] in self.err_txid_dict.keys():
                    await self.db.update_node_by_id({'id': node['id'], 'status': status})
                    del self.err_txid_dict[node['txid']]
                else:#记录一次
                    self.err_txid_dict[node['txid']] = status
                    continue

            logger.info('[NODE] confirm tx status({}) for node address({})'.format(status, node['address']))

    async def check_tx_confirmed(self, txid, address, amount):
        '''交易tx是否已确认'''
        used = await self.db.is_txid_used(txid)
        if used:
            logger.warning('[NODE] check tx but txid({}) was be used'.format(txid))
            return -10
        def find(histories, op, address):
            amounts = []
            for h in histories:
                if h['operation'] == op and h['asset'] == C.get_check_seac_asset() and h['address'] == address:
                    amounts.append(int(h['value']))
            return amounts

        try:
            hs = await self.db.get_tx_history_by_txid(txid)
            if len(hs) == 0:
                return -1
            amounts = find(hs, 'in', C.get_address_for_receive_seac())
            if len(amounts) == 0:
                return -10
            if not amount in amounts:
                return -8
            amounts = find(hs, 'out', address)
            if len(amounts) == 0:
                return -10
            if not amount in amounts:
                return -8
            return 0
        except Exception as e:
            logger.error('[NODE] check tx confirmed tx err: {}'.format(e.args))
        return -1

    async def handle_node_updates(self):
        '''处理用户的节点更新'''
        updates = await self.db.get_node_updates()
        logger.info('[NODE] handle {} node updates.'.format(len(updates)))
        for up in updates:
            op = up['operation']
            if op == 1: #新节点
                layer = 1
                f = True
                if up['address'] != up['referrer']:
                    #找出推荐人
                    referrer_node = await self.db.get_node_by_address(up['referrer'])
                    if not referrer_node:
                        logger.warning("[NODE] add node for address({}), but referrer({}) not found.".format(up['address'], up['referrer']))
                        f = False
                    else:
                        layer = referrer_node.layer + 1
                if f:
                    node_bonus_timepoint = await self.db.get_status('node_bonus_timepoint')
                    node = {
                        'address': up['address'],
                        'referrer': up['referrer'],
                        'amount': int(up['amount']),
                        'days': up['days'],
                        'txid': up['txid'],
                        'status': -1,
                        'signin': 0,
                        'nextbonustime': node_bonus_timepoint+2*C.get_bonus_interval(),
                        'layer':layer,
                        'starttime': int(time.time()),
                        'bonusadvancetable': encode_advance_bonus_table(Node.zero_advance_bonus_table()),
                        'areaadvancetable': encode_advance_area_table(Node.zero_advance_area_table())
                    }
                    await self.db.insert_node(node)
                    up['status'] = 1
            elif op == 2: #解锁
                await self.db.update_node_by_address({'address': up['address'], 'status': -5})
                up['status'] = 1
            elif op == 3: #提取
                await self.withdraw_bonus(up['address'], up['amount'])
                up['status'] = 1
            elif op == 4: #签到
                await self.db.update_node_by_address({'address': up['address'], 'signin': 1})
                up['status'] = 1
            elif op == 5: #激活节点
                origin = await self.db.get_node_by_address(up['address'])
                if origin:
                    node_bonus_timepoint = await self.db.get_status('node_bonus_timepoint')
                    await self.db.update_node_by_address({
                        'address': up['address'],
                        'amount': int(up['amount']),
                        'days': up['days'],
                        'txid': up['txid'],
                        'status': -1,
                        'signin': 0,
                        'nextbonustime': node_bonus_timepoint + 2 * C.get_bonus_interval(),
                    })
                    up['status'] = 1
                else:
                    logger.warning('[NODE] active node({}) but not found'.format(up['address']))
            else:
                logger.error('[NODE] wrong operation: {}'.format(op))
            await self.db.del_node_update(up['id'])
            up['timepoint'] = int(time.time())
            await self.db.insert_node_update_history(up)

    async def withdraw_bonus(self, address, amount):
        '''提取分红'''
        last = await self.db.get_lastest_node_bonus(address)
        if not last:
            logger.warning("[WITHDRAW] no any node_bonus for address: {}".format(address))
            return
        remain = float(last['remain'])
        remain = (remain-float(amount)) if remain > float(amount) else 0
        node_bonus  = {
            "id": last['id'],
            "remain": str(remain)
        }
        #更新分红表
        await self.db.update_node_bonus_by_id(node_bonus)
        node_withdraw = {
            'address': address,
            'txid': '',
            'amount': amount,
            'timepoint': int(time.time()),
            'status': 0
        }
        #增加收益记录
        await self.db.insert_node_withdraw(node_withdraw)

    async def start(self):
        '''开始执行'''
        while True:
            f = await self.bonus()
            if not f:
                await self.handle_unconfirmed_node_tx()
                await self.handle_node_updates()
                time.sleep(10)

async def run():
    b = Bonus(C.get_mysql_args(), C.get_bonus_conf())
    await b.prepare()
    await b.start()

if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    loop.run_until_complete(run())
    loop.run_forever()

