#! /usr/bin/env python3
# coding: utf-8
# flow@SEA
# Licensed under the MIT License.

from functools import wraps
import datetime
from message import MSG
from .tools import Tool, check_decimal, sci_to_str, big_or_little


get_now_timestamp = lambda:int(datetime.datetime.now().timestamp())

def valid_domain(domain, request):
    domain = domain.split(".")
    if len(domain) < 2: return False
    if not domain[0]: return False
    if 'testnet' == request.app['net'] and domain[-1] not in ["test"]: return False
    if 'mainnet' == request.app['net'] and domain[-1] not in ["neo"]: return False
    return True

def format_result(validation):
    def dec(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            kwargs['request']['result'] = {"server_time":get_now_timestamp(),"code":200,"message":""}
            if 'net' in validation and kwargs['net'] != kwargs['request'].app['net']:
                kwargs['request']['result'].update(MSG['WRONG_NET'])
                return kwargs['request']['result']
            if 'address' in validation and not Tool.validate_address(kwargs['address']):
                kwargs['request']['result'].update(MSG['WRONG_ADDRESS'])
                return kwargs['request']['result']
            if 'platform' in validation and kwargs['platform'] not in ['ios', 'android']:
                kwargs['request']['result'].update(MSG['WRONG_PLATFORM'])
                return kwargs['request']['result']
            if 'domain' in validation and not valid_domain(kwargs['domain'], kwargs['request']):
                kwargs['request']['result'].update(MSG['WRONG_DOMAIN'])
                return kwargs['request']['result']
            await func(*args, **kwargs)
            return kwargs['request']['result']
        return wrapper
    return dec
