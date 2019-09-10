import asyncio
import time
from datetime import datetime
from logzero import logger

from db import DB
from config import Config as C

class Bonus:
    #节点分组，key为推荐人，value为节点数组
    node_group = {}

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
            bonus_time = now + C.get_bonus_interval()
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
            return 0
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
                team_bonus += info[k] * (1-self.bonus_conf['level_burned_bonus'][k]) * (1-self.bonus_conf['small_area_burned_bonus'])
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

    async def start(self):
        '''开始执行分红'''
        while True:
            f = await self.bonus()
            if not f:
                time.sleep(10)

async def run():
    b = Bonus(C.get_mysql_args(), C.get_bonus_conf())
    await b.prepare()
    await b.start()

if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    loop.run_until_complete(run())
    loop.run_forever()

