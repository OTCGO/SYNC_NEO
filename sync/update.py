#! /usr/bin/env python3
# coding: utf-8
# flow@SEA
# Licensed under the MIT License.

import sys
import uvloop
import asyncio
asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
from logzero import logger
from Crawler import Crawler
from Config import Config as C


class UPT(Crawler):
    def __init__(self, name, mysql_args, neo_uri, loop, super_node_uri, tasks='1000'):
        super(Asset,self).__init__(name, mysql_args, neo_uri, loop, super_node_uri, tasks)

    async def infinite_loop(self):
        while True:
            current_height = await self.get_block_count()
            time_a = CT.now()
            if self.start < current_height:
                stop = self.start + self.max_tasks
                if stop >= current_height:
                    stop = current_height
                self.processing.extend([i for i in range(self.start,stop)])
                self.max_height = max(self.processing)
                self.min_height = self.processing[0]
                await asyncio.wait([self.cache_block(h) for h in self.processing])
                if self.processing != sorted(self.cache.keys()):
                    msg = 'can not cache so much blocks one time(cache != processing)'
                    logger.error(msg)
                    self.max_tasks -= 10
                    if self.max_tasks > 0:
                        continue
                    else:
                        sys.exit(1)

                time_b = CT.now()
                logger.info('reached %s ,cost %.6fs to sync %s blocks ,total cost: %.6fs' % 
                        (self.max_height, time_b-time_a, stop-self.start, time_b-self.start_time))
                await self.update_status(self.max_height)
                self.start = self.max_height + 1
                del self.processing
                del self.cache
                self.processing = []
                self.cache = {}
            else:
               await asyncio.sleep(0.5)

    async def crawl(self):
        self.pool = await self.get_mysql_pool()
        if not self.pool:
            sys.exit(1)
        try:
            await self.infinite_loop()
        except Exception as e:
            logger.error('CRAWL EXCEPTION: {}'.format(e.args[0]))
        finally:
            self.pool.close()
            await self.pool.wait_closed()
            await self.session.close()


if __name__ == "__main__":
    mysql_args = {
                    'host':     C.get_mysql_host(),
                    'port':     C.get_mysql_port(),
                    'user':     C.get_mysql_user(),
                    'password': C.get_mysql_pass(),
                    'db':       C.get_mysql_db(),
                    'autocommit':True
                }
    neo_uri         = C.get_neo_uri()
    loop            = asyncio.get_event_loop()
    super_node_uri  = C.get_super_node()
    tasks           = C.get_tasks()

    u = UPT('utxo', mysql_args, neo_uri, loop, super_node_uri, tasks)

    try:
        loop.run_until_complete(u.crawl())
    except Exception as e:
        logger.error('LOOP EXCEPTION: {}'.format(e.args[0]))
    finally:
        loop.close()
