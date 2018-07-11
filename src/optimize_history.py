'''
https://note.youdao.com/share/?id=430050a6b496978dc21aa844b6a4e80b&type=note#/
'''
import asyncio
from pymongo import ASCENDING
import motor.motor_asyncio
from logzero import logger
import uvloop
asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
from Config import Config as C


async def create_index(collection):
    await collection.create_index([("address", ASCENDING), ("asset", ASCENDING)])

async def optimize(client, collection, mongo_db):
    await create_index(collection)


if __name__ == "__main__":
    logger.info('STARTING...')
    mongo_uri = C.get_mongo_uri()
    mongo_db = C.get_mongo_db()
    client = motor.motor_asyncio.AsyncIOMotorClient(mongo_uri)
    co = client[mongo_db].history
    loop = asyncio.get_event_loop() 
    loop.run_until_complete(optimize(client, co, mongo_db))
    loop.close()
