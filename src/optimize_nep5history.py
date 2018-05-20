'''
https://note.youdao.com/share/?id=430050a6b496978dc21aa844b6a4e80b&type=note#/
'''
import os
import asyncio
from pymongo import ASCENDING
import motor.motor_asyncio
from logzero import logger
from dotenv import load_dotenv, find_dotenv
load_dotenv(find_dotenv(), override=True)
import uvloop
asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())


def get_mongo_uri():
    mongo_uri    = os.environ.get('MONGOURI')
    if mongo_uri: return mongo_uri
    mongo_server = os.environ.get('MONGOSERVER')
    mongo_port   = os.environ.get('MONGOPORT')
    mongo_user   = os.environ.get('MONGOUSER')
    mongo_pass   = os.environ.get('MONGOPASS')
    if mongo_user and mongo_pass:
        return 'mongodb://%s:%s@%s:%s' % (mongo_user, mongo_pass, mongo_server, mongo_port)
    else:
        return 'mongodb://%s:%s' % (mongo_server, mongo_port)

get_mongo_db = lambda:os.environ.get('MONGODB')

async def create_index(collection):
    await collection.create_index([("address", ASCENDING), ("asset", ASCENDING)])

async def optimize(client, collection, mongo_db):
    await create_index(collection)


if __name__ == "__main__":
    logger.info('STARTING...')
    mongo_uri = get_mongo_uri()
    mongo_db = get_mongo_db()
    client = motor.motor_asyncio.AsyncIOMotorClient(mongo_uri)
    co = client[mongo_db].nep5history
    loop = asyncio.get_event_loop() 
    loop.run_until_complete(optimize(client, co, mongo_db))
    loop.close()
