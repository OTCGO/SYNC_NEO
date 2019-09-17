import asyncio
import aiomysql
from logzero import logger
import sys

from node import Node, decode_advance_area_table, decode_advance_bonus_table
from config import Config as C

class DB:
    def __init__(self, mysql_args):  
        self.mysql_args = mysql_args

    async def init_pool(self):
        self.pool = await self.get_mysql_pool()

    async def get_mysql_pool(self):
        try:
            logger.info('start to connect db')
            pool = await aiomysql.create_pool(**self.mysql_args)
            logger.info('succeed to connet db!')
            return pool
        except asyncio.CancelledError:
            raise asyncio.CancelledError
        except Exception as e:
            logger.error("mysql connet failure:{}".format(e.args[0]))
            raise e

    async def get_mysql_cursor(self):
        conn = await self.pool.acquire()
        cur  = await conn.cursor()
        return conn, cur

    async def mysql_execute(self, sql):
        conn, cur = await self.get_mysql_cursor()
        logger.info('SQL:%s' % sql)
        try:
            await cur.execute(sql)
            return conn, cur
        except Exception as e:
            logger.error("mysql SQL:{} failure:{}".format(sql, e.args[0]))
            raise e

    async def mysql_insert_one(self, sql):
        conn, cur = None, None
        try:
            conn, cur = await self.mysql_execute(sql)
            num = cur.rowcount
            return num
        except Exception as e:
            logger.error("mysql INSERT failure:{}".format(e.args[0]))
            sys.exit(1)
        finally:
            if conn:
                await self.pool.release(conn)

    async def mysql_query_one(self, sql):
        conn, cur = None, None
        try:
            conn, cur = await self.mysql_execute(sql)
            return await cur.fetchone()
        except Exception as e:
            logger.error("mysql QUERY failure:{}".format(e.args[0]))
            sys.exit(1)
        finally:
            if conn:
                await self.pool.release(conn)

    async def mysql_query_many(self, sql):
        conn, cur = None, None
        try:
            conn, cur = await self.mysql_execute(sql)
            return await cur.fetchall()
        except Exception as e:
            logger.error("mysql QUERY failure:{}".format(e.args[0]))
            raise e
        finally:
            if conn:
                await self.pool.release(conn)

    async def mysql_insert_many(self, sql, data):
        conn, cur = await self.get_mysql_cursor()
        logger.info('SQL MANY:%s' % sql)
        try:
            await cur.executemany(sql, data)
            num = cur.rowcount
            #logger.info('%s row affected' % num)
            return num
        except Exception as e:
            logger.error("mysql INSERT failure:{}".format(e.args[0]))
            sys.exit(1)
        finally:
            await self.pool.release(conn)

    async def get_status(self, name):
        try:
            result = await self.mysql_query_one("SELECT update_height FROM status WHERE name='%s';" % name)
            if result:
                uh = result[0]
                logger.info('database %s height: %s' % (name,uh))
                return uh
            logger.info('database %s height: -1' % name)
            return -1
        except Exception as e:
            logger.error("mysql SELECT failure:{}".format(e.args[0]))
            raise e

    async def update_status(self, name, height):
        sql = "INSERT INTO status(name,update_height) VALUES ('%s',%s) ON DUPLICATE KEY UPDATE update_height=%s;" % (name,height,height)
        await self.mysql_insert_one(sql)

    async def insert_node(self, node_dict):
        '''插入节点'''
        fields = []
        values = []
        update_fields = []
        for k in node_dict:
            fields.append(k)
            if isinstance(node_dict[k], str):
                values.append("'{}'".format(node_dict[k]))
                if k != 'address':
                    update_fields.append("{}='{}'".format(k, node_dict[k]))
            else:
                values.append("{}".format(node_dict[k]))
                update_fields.append("{}={}".format(k, node_dict[k]))

        sql = "INSERT INTO node({}) VALUES ({}) ON DUPLICATE KEY UPDATE {};".format(fields, values, update_fields)
        await self.mysql_insert_one(sql)

    async def get_max_node_layer(self):
        sql = 'SElECT max(layer) FROM node;'
        r = await self.mysql_query_one(sql)
        if r and r[0]:
            return r[0]
        return 0

    async def get_node_for_bonus(self, layer):
        sql = "SELECT id,status,referrer,address,amount,days,layer,nextbonustime,nodelevel,performance,teamlevelinfo,referrals,bonusadvancetable,areaadvancetable,burned,signin FROM node WHERE layer = %s;" % layer
        results = await self.mysql_query_many(sql)
        nodes = []
        for r in results:
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
            node.bonus_advance_table_encode = r[12]
            node.area_advance_tabel_encode = r[13]
            node.burned = r[14]
            node.signin = r[15]
            node.bonus_advance_table = decode_advance_bonus_table(node.bonus_advance_table_encode)
            node.area_advance_tabel = decode_advance_area_table(node.area_advance_tabel_encode)
            nodes.append(node)
        return nodes

    async def get_node_by_address(self, address):
        '''根据地址查询节点'''
        sql = "SELECT id,status,referrer,address,amount,days,layer,nextbonustime,nodelevel,performance,teamlevelinfo,referrals,bonusadvancetable,areaadvancetable,burned FROM node WHERE address = '%s';" % address
        results = await self.mysql_query_many(sql)
        for r in results:
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
            node.bonus_advance_table_encode = r[12]
            node.area_advance_tabel_encode = r[13]
            node.burned = r[14]
            node.bonus_advance_table = decode_advance_bonus_table(node.bonus_advance_table_encode)
            node.area_advance_tabel = decode_advance_area_table(node.area_advance_tabel_encode)
            return node
        return None

    async def update_node_status_exit(self):
        '''节点到期，更新节点状态为-2'''
        sql = 'UPDATE node node1, (SELECT id FROM node WHERE status=days) node2 ' \
              'SET status=-2,nextbonustime=0 ' \
              'WHERE node1.id=node2.id;'
        conn, _ = await self.mysql_execute(sql)
        if conn:
            await self.pool.release(conn)

    async def get_nodes_by_status(self, status):
        '''根据状态查出节点'''
        sql = "SELECT id,txid FROM node WHERE status = %s;" % status
        results = await self.mysql_query_many(sql)
        nodes = []
        for r in results:
            node = {}
            node['id'] = r[0]
            node['txid'] = r[1]
            nodes.append(node)
        return nodes

    async def update_node_by_id(self, node_dict):
        '''更新节点数据'''
        update_fields = []
        for k in node_dict:
            if k == 'id':
                continue
            if isinstance(node_dict[k], str):
                update_fields.append("{}='{}'".format(k, node_dict[k]))
            else:
                update_fields.append("{}={}".format(k, node_dict[k]))

        sql = "UPDATE node SET {} WHERE id = {};".format(','.join(update_fields), node_dict['id'])
        conn, _ = await self.mysql_execute(sql)
        if conn:
            await self.pool.release(conn)

    async def update_node_by_address(self, node_dict):
        '''更新节点数据'''
        update_fields = []
        for k in node_dict:
            if k == 'id':
                continue
            if isinstance(node_dict[k], str):
                update_fields.append("{}='{}'".format(k, node_dict[k]))
            else:
                update_fields.append("{}={}".format(k, node_dict[k]))

        sql = "UPDATE node SET {} WHERE address = '{}';".format(','.join(update_fields), node_dict['address'])
        conn, _ = await self.mysql_execute(sql)
        if conn:
            await self.pool.release(conn)

    async def insert_node_bonus(self, address, locked_bonus, referrals_bonus, signin_bonus, team_bonus, amount, total, remain, bonus_time):
        '''插入分红记记录'''
        sql = 'INSERT INTO node_bonus(address,lockedbonus,teambonus,amount,total,remain,bonustime,referralsbonus, signinbonus) ' \
              'VALUES("{}","{}","{}","{}","{}","{}",{},"{}","{}");'.format(address, locked_bonus, team_bonus, amount, total, remain, bonus_time, referrals_bonus, signin_bonus)
        await self.mysql_insert_one(sql)

    async def get_lastest_node_bonus(self, address):
        '''获得节点最新分红记录'''
        sql = 'SELECT total,remain,bonustime,id FROM node_bonus WHERE address="{}" ORDER BY bonustime DESC LIMIT 1;'.format(address)
        r = await self.mysql_query_one(sql)
        b = {}
        if r:
            b['total'] = r[0]
            b['remain'] = r[1]
            b['bonus_time'] = r[2]
            b['id'] = r[3]
        return b

    async def update_node_bonus_by_id(self, node_bonus):
        '''更新节点收益表'''
        update_fields = []
        for k in node_bonus:
            if k == 'id':
                continue
            if isinstance(node_bonus[k], str):
                update_fields.append("{}='{}'".format(k, node_bonus[k]))
            else:
                update_fields.append("{}={}".format(k, node_bonus[k]))

        sql = "UPDATE node_bonus SET {} WHERE id = {};".format(','.join(update_fields), node_bonus['id'])
        conn, _ = await self.mysql_execute(sql)
        if conn:
            await self.pool.release(conn)

    async def add_node_bonus(self, node, bonus_time):
        '''增加分红记录，并更新节点状态'''
        if node.can_bonus(bonus_time): #增加分红记录
            amount = node.locked_bonus + node.team_bonus + node.referrals_bonus + node.signin_bonus
            total, remain = amount, amount
            # 先找出最新的分红记录
            prev_bonus_record = await self.get_lastest_node_bonus(node.address)
            add = True
            if prev_bonus_record:
                if prev_bonus_record['bonus_time'] + C.get_bonus_interval() == bonus_time:
                    total += float(prev_bonus_record['total'])
                    remain += float(prev_bonus_record['remain'])
                else:
                    add = False
                    logger.warning("you are going to add bonus for bonus_time({}), but prev bonus_time({}) is not the right time".format(bonus_time, prev_bonus_record['bonus_time']))

            if add:
                await self.insert_node_bonus(node.address, node.locked_bonus, node.referrals_bonus, node.signin_bonus, node.team_bonus,
                    amount, total, remain, bonus_time)

        update, up_status = node.is_need_update(bonus_time)
        if not update:
            return

        update_field = {}
        update_field['nodelevel'] = node.level
        update_field['referrals'] = node.referrals
        update_field['performance'] = node.performance
        update_field['teamlevelinfo'] = node.team_level_info
        update_field['bonusadvancetable'] = node.bonus_advance_table_encode
        update_field['areaadvancetable'] = node.area_advance_tabel_encode
        update_field['burned'] = node.burned
        update_field['signin'] = node.signin

        if up_status:
            update_field['status'] = node.status+1
            update_field['nextbonustime'] = bonus_time + C.get_bonus_interval()

        update_fields = []
        for k in update_field:
            if isinstance(update_field[k], str):
                update_fields.append("{}='{}'".format(k, update_field[k]))
            else:
                update_fields.append("{}={}".format(k, update_field[k]))

        sql = "UPDATE node SET {} WHERE id = {};".format(','.join(update_fields), node.id)
        conn, _ = await self.mysql_execute(sql)
        if conn:
            await self.pool.release(conn)

    async def get_node_updates(self):
        '''获得节点的更新数据'''
        sql = "SELECT id,address,operation,referrer,amount,days,penalty,txid FROM node_update;"
        results = await self.mysql_query_many(sql)
        updates = []
        for r in results:
            update = {}
            update['id'] = r[0]
            update['address'] = r[1]
            update['operation'] = r[2]
            update['referrer'] = r[3]
            update['amount'] = r[4]
            update['days'] = r[5]
            update['penalty'] = r[6]
            update['txid'] = r[7]
            updates.append(update)
        return updates

    async def del_node_update(self, id):
        '''删除用户节点更新记录'''
        sql = "DELETE FROM node_update WHERE id = {};".format(id)
        conn, _ = await self.mysql_execute(sql)
        if conn:
            await self.pool.release(conn)

    async def insert_node_withdraw(self, node_withdraw):
        '''插入收益提取记录'''
        sql = 'INSERT INTO node_withdraw(address,txid,amount,timepoint,status) ' \
              'VALUES("{}","{}","{}",{},{});'.format(node_withdraw['address'], node_withdraw['txid'],
                        node_withdraw['amount'], node_withdraw['timepoint'], node_withdraw['status'])
        await self.mysql_insert_one(sql)
