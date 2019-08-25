import asyncio
import aiomysql
from logzero import logger
import sys

from node import Node

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

    async def get_max_node_layer(self):
        return 1

    async def get_node_for_bonus(self, layer):
        sql = "SELECT status,referrer,address,amount,days,layer,nextbonustime,nodelevel FROM node WHERE layer = %s;" % layer
        results = await self.mysql_query_many(sql)
        nodes = []
        for r in results:
            node = Node()
            node.status = r[0]
            node.referrer = r[1]
            node.address = r[2]
            node.locked_amount = r[3]
            node.days = r[4]
            node.layer = r[5]
            node.next_bonus_time = r[6]
            node.level = r[7]
            nodes.append(node)
        return nodes

    async def insert_node_bonus(self, address, locked_bonus, team_bonus, amount, total, remain, bonus_time):
        '''插入分红记记录'''

    async def get_node_bonus(self, address, bonus_time):
        '''获得节点分红记录'''

    async def add_node_bonus(self, node):
        '''增加分红记录，并更新节点状态'''