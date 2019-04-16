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
    await collection.create_index([("height", ASCENDING), ("spent_height", ASCENDING), ("asset", ASCENDING)])
    await collection.create_index([("height", ASCENDING), ("asset", ASCENDING), ("claim_height", ASCENDING)])
    await collection.create_index([("address", ASCENDING), ("spent_height", ASCENDING)])
    await collection.create_index([("address", ASCENDING), ("asset", ASCENDING)])

async def do_delete(client, collection, mongo_db):
    result = await client[mongo_db].state.find_one({'_id':'height'})
    height = result['value']
    await collection.delete_many({'height':{'$lte':height},
                                    'spent_height':{'$ne':None},
                                    'asset':{'$ne':'0xc56f33fc6ecfcd0c225c4ab356fee59390af8560be0e930faebe74a6daff7c9b'}})

    await collection.delete_many({'height':{'$lte':height},
                                    'asset':'0xc56f33fc6ecfcd0c225c4ab356fee59390af8560be0e930faebe74a6daff7c9b',
                                    'claim_height':{'$ne':None}})

async def optimize(client, collection, mongo_db):
    await create_index(collection)
    await do_delete(client, collection, mongo_db)


if __name__ == "__main__":
    logger.info('STARTING...')
    mongo_uri = C.get_mongo_uri()
    mongo_db = C.get_mongo_db()
    client = motor.motor_asyncio.AsyncIOMotorClient(mongo_uri)
    co = client[mongo_db].utxos
    loop = asyncio.get_event_loop() 
    loop.run_until_complete(optimize(client, co, mongo_db))
    loop.close()
