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
        node_bonus = await self.db.get_status('node_bonus')
        if node_bonus == -1:
            await self.db.update_status('node_bonus', 0)
        node_bonus_timepoint = await self.db.get_status('node_bonus_timepoint')
        if node_bonus_timepoint == -1:
            bonus_time = int(time.time()) + C.get_bonus_interval()
            if C.get_bonus_start_time() != 'now':
                bonus_time = time.mktime(datetime.fromtimestamp(bonus_time).date().timetuple())+10

            await self.db.update_status('node_bonus_timepoint', bonus_time)

    def handle_by_layer(self, nodes, bonus_time, layer):
        '''处理同一层级的所有节点'''
        group_by_ref = {}
        for i in range(len(nodes)):
            # 计算锁仓分红
            if nodes[i].can_bonus(bonus_time):
                nodes[i].locked_bonus = self.compute_locked_bonus(nodes[i].locked_amount, nodes[i].days)
                nodes[i].status += 1
            # 找子节点
            if nodes[i].address in self.node_group.keys():
                nodes[i].set_children(self.node_group[nodes[i].address])
            # 计算团队业绩
            nodes[i].compute_performance()
            # 计算直推人
            nodes[i].compute_referrals()
            # 计算团队各等级数量
            nodes[i].compute_team_level()
            # 计算节点等级
            nodes[i].compute_level()
            # 团队业绩分红
            if nodes[i].can_bonus(bonus_time):
                nodes[i].team_bonus = self.compute_team_bonus(nodes[i])

            # 增加分红记录、更新节点状态，更新数据到数据库
            self.db.add_node_bonus(nodes[i], bonus_time)

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

    def compute_team_bonus(self, node):
        '''计算团队分红, 保留三位小数'''
        if node.level < 5:
            return 0
        team_bonus = 0
        for child in node.children:
            performance = child.performance
            if child.can_compute_in_team():
                performance += child.locked_amount
            burn_rate = 1
            if node.level < child.level: # 烧伤 收益
                burn_rate = self.bonus_conf['burn_bonus'][node.level-child.level]
            team_bonus += performance*burn_rate*node.level*0.02/365
        return round(team_bonus, 3)

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

    async def start(self):
        '''开始执行分红'''
        while True:
            now = time.time()
            bonus_time = await self.db.get_status('node_bonus_timepoint')
            if now < bonus_time:
                time.sleep(10)
                continue

            node_bonus = await self.db.get_status('node_bonus')
            is_max_layer = False
            if node_bonus == 0:
                node_bonus = await self.db.get_max_node_layer()
                is_max_layer = True
                logger.info("[BONUS] get max node layer: {}".format(node_bonus))

            for layer in range(node_bonus, 0, -1):
                if not self.check_next_layer(is_max_layer):
                    await self.recover_layer(layer+1)

                nodes = await self.db.get_node_for_bonus(layer)
                self.handle_by_layer(nodes, bonus_time, layer)

                await self.db.update_status('node_bonus', layer)
                logger.info("[BONUS] handle {} layer success".format(layer))

            await self.db.update_node_status_exit()

            await self.db.update_status('node_bonus', 0)
            await self.db.update_status('node_bonus_timepoint', bonus_time + C.get_bonus_interval())
            logger.info("[BONUS] handle all layers success")
            self.node_group = {}

async def run():
    b = Bonus(C.get_mysql_args(), C.get_bonus_conf())
    await b.prepare()
    await b.start()

if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    loop.run_until_complete(run())
    loop.run_forever()

