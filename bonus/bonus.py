import asyncio
import time
from datetime import datetime

from db import DB
from config import Config as C

class Bonus:
    #节点分组，key为推荐人，value为节点数组
    node_group = {}

    def __init__(self, mysql_args, bonus_conf):
        self.db = DB(mysql_args)
        pass

    async def prepare(self):
        await self.db.init_pool()
        node_bonus = await self.db.get_status('node_bonus')
        if node_bonus == -1:
            await self.db.update_status('node_bonus', 0)
        node_bonus_timepoint = await self.db.get_status('node_bonus_timepoint')
        if node_bonus_timepoint == -1:
            next_day = time.mktime(datetime.fromtimestamp(time.time()+60*60*24).date().timetuple())
            await self.db.update_status('node_bonus_timepoint', next_day)

    def handle_by_layer(self, nodes, bonus_time, layer):
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
            team_amount = nodes[i].compute_team_amount()
            # 团队业绩分红
            if nodes[i].can_bonus(bonus_time):
                nodes[i].team_bonus = self.compute_team_bonus(nodes[i].level, team_amount)

            # TODO: 增加分红记录，更新数据到数据库

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

    def compute_team_bonus(self, node_level, team_amount):
        '''计算团队分红'''

    async def start(self):
        '''开始执行分红'''
        while True:
            now = time.time()
            next_bonus_time = self.db.get_status('node_bonus_timepoint')
            if now < next_bonus_time:
                time.sleep(10)
                continue

            node_bonus = self.db.get_status('node_bonus')
            if node_bonus == 0:
                node_bonus = self.db.get_max_node_layer()

            for layer in range(node_bonus, 0, -1):
                self.handle_by_layer(next_bonus_time, layer)


async def run():
    b = Bonus(C.get_mysql_args(), C.get_bonus_conf())
    await b.prepare()
    await b.start()

if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    loop.run_until_complete(run())
    loop.run_forever()