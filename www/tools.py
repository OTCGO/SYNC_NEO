from pycoin.ecdsa.numbertheory import modular_sqrt
from ecdsa import SigningKey, NIST256p, VerifyingKey
from decimal import Decimal as D
from base58 import b58decode,b58encode
import binascii
import bitcoin
import asyncio
import hashlib
import math
from random import randint

def sci_to_str(sciStr):
    '''科学计数法转换成字符串'''
    assert type('str')==type(sciStr),'invalid format'
    s = '%.8f' % float(sciStr)
    while '0' == s[-1] and '.' in s:
        s = s[:-1]
    if '.' == s[-1]:
        s = s[:-1]
    return s

def check_decimal(num, dn):
    '''wheather num's decimal <= dn'''
    ns = sci_to_str(str(num))
    if '.' in ns:
        while '0' == ns[-1]:
            ns = ns[:-1]
        return len(ns.split('.')[1]) <= dn
    else:
        return True

def big_or_little(arr):
    '''大小端互转'''
    arr = bytearray(str(arr),'ascii')
    length = len(arr)
    for idx in range(length//2):
        if idx%2 == 0:
            arr[idx], arr[length-2-idx] = arr[length-2-idx], arr[idx]
        else:
            arr[idx], arr[length - idx] = arr[length - idx], arr[idx]
    return arr.decode('ascii')


class Tool:
    @staticmethod
    def hash256(b):
        return hashlib.sha256(hashlib.sha256(b).digest()).digest()

    @classmethod
    def validate_address(self, address):
        if len(address) not in [33,34]: return False
        if 'A' != address[0]: return False
        tmp = b58decode(address)
        x,check = tmp[:-4],tmp[-4:]
        return self.hash256(x)[:4] == check

    @staticmethod
    def validate_cpubkey(pubkey):
        '''validate compressed publickey'''
        if 66 != len(pubkey): return False
        if pubkey.startswith('02') or pubkey.startswith('03'): return True
        return False

    @staticmethod
    def decimal_to_hex(ds, length=8, decimals=8):
        if 1 == decimals: decimals = 0
        hex_str = hex(int(ds*D(math.pow(10,decimals))))[2:]
        if len(hex_str)%2:
            hex_str = '0' + hex_str
        for i in range(length - len(hex_str)//2):
            hex_str = '00' + hex_str
        return big_or_little(hex_str)

    @staticmethod
    def get_random_byte():
        '''
        获得单个16进制字符串
        '''
        tmp = hex(randint(0,255))[2:]
        if 1 == len(tmp): return '0'+tmp
        return tmp

    @classmethod
    def get_random_byte_str(cls, num):
        '''
        获得指定长度的16进制字符串
        '''
        return ''.join([cls.get_random_byte() for i in range(0,num)])

    @staticmethod
    def hex_to_num_str(fixed8_str, decimals=8):
        hex_str = big_or_little(fixed8_str)
        d = D(int('0x' + hex_str, 16))
        return sci_to_str(str(d/D(math.pow(10, decimals))))

    @staticmethod
    def address_to_scripthash(address):
        return binascii.hexlify(b58decode(address)[1:-4]).decode('utf-8')

    @staticmethod
    def bin_hash160(s):
        intermed = hashlib.sha256(s).digest()
        return hashlib.new('ripemd160', intermed).digest()

    @staticmethod
    def cpubkey_to_redeem(pubkey):
        return binascii.unhexlify('21' + pubkey + 'ac')

    @classmethod
    def redeem_to_scripthash(cls, redeem):
        return cls.bin_hash160(redeem)

    @classmethod
    def scripthash_to_address(cls, sh):
        tmp = binascii.unhexlify('17' + sh.hex())
        return b58encode(tmp + cls.hash256(tmp)[:4])

    @classmethod
    def cpubkey_to_address(cls, pubkey):
        redeem = cls.cpubkey_to_redeem(pubkey)
        scripthash = cls.redeem_to_scripthash(redeem)
        address = cls.scripthash_to_address(scripthash)
        if isinstance(address, bytes):
            address = address.decode('utf8')
        return address

    @staticmethod
    def uncompress_pubkey(cpk):
        '''将压缩版公钥转换为完整版公钥'''
        p = 0xFFFFFFFF00000001000000000000000000000000FFFFFFFFFFFFFFFFFFFFFFFF
        a = -3
        b = 0x5AC635D8AA3A93E7B3EBBD55769886BC651D06B0CC53B0F63BCE3C3E27D2604B
        prefix = cpk[:2]
        x = int(cpk[2:],16)
        y_squared = (x**3 + a*x + b)%p
        y = modular_sqrt(y_squared, p)
        y_hex = '%x' % y
        if (1==int(y_hex[-1],16)%2 and '02' == prefix) or (0==int(y_hex[-1],16)%2 and '03' == prefix):
            y = p - y
        return '04%064x%064x' % (x,y)

    @staticmethod
    def get_right_utxo(utxos, value, assetId):
        '''
        utxo选取原则:
            1.如果所有utxo相加后小于该金额,返回空
            2.排序
            3.如果存在正好等于该金额的,就取该utxo
            4.如果存在大于该金额的,就取大于该金额的最小的utxo
            5.取最大的utxo并移除,然后回到第3步以获取剩余金额的utxo
        '''
        result = []
        for u in utxos:
            u['value'] = D(u['value'])
        sortedUtxos = sorted(utxos, key=lambda k:k['value']) #sort little --> big
        while value:
            if value in [s['value'] for s in sortedUtxos]:
                for s in sortedUtxos:
                    if value == s['value']:
                        result.append(s)
                        value = D('0')
                        break
            elif value < sortedUtxos[-1]['value']:
                for s in sortedUtxos:
                    if value < s['value']:
                        result.append(s)
                        value = D('0')
                        break
            else:
                result.append(sortedUtxos[-1])
                value = value - sortedUtxos[-1]['value']
                del sortedUtxos[-1]
        return result

    @staticmethod
    def pubkey_to_compress(pubkey):
        '''生成压缩版公钥'''
        assert 130==len(pubkey),'Wrong pubkey length'
        x,y = pubkey[2:66],pubkey[66:]
        prefix = '03' if int('0x'+y[-1],16)%2 else '02'
        return prefix + x

    @classmethod
    def claim_transaction(cls, address, details):
        if D(details['available']):
            tx = '0200' + cls.num_to_hex_str(len(details['claims']))
            for c in details['claims']:
                tx += big_or_little(c[0]) + cls.num_to_hex_str(int(c[1]), 2)
            tx += '000001e72d286979ee6cb1b7e65dfddfb2e384100b8d148e7758de42e4168b71792c60'
            tx += cls.decimal_to_hex(D(details['available']))
            tx += cls.address_to_scripthash(address)
            return tx, True, ''
        return '', False, 'No Gas'

    @classmethod
    def ong_claim_transaction(cls, address, amount, net):
        if D(amount):
            mysh = cls.address_to_scripthash(address)
            ontsh = '0000000000000000000000000000000000000001'
            apphash = '0000000000000000000000000000000000000002'
            s = '00'    #version
            s += 'd1'   #TransactionType
            s += cls.get_random_byte_str(4) #Nonce
            s += 'f401000000000000'        #GasPrice
            s += '204e000000000000'        #GasLimit
            s += mysh                      #Payer
            script = '00c66b14' + mysh + '6a7cc814' + ontsh + '6a7cc814' + mysh + '6a7cc8'
            fa = cls.decimal_to_hex(D(amount), 8, 9)
            faLen = hex(len(fa)//2)[2:]
            if 1 == len(faLen) % 2:
                faLen = '0' + faLen
            script += faLen + fa + '6a7cc86c' + '0c7472616e7366657246726f6d' + '14' + apphash + '0068164f6e746f6c6f67792e4e61746976652e496e766f6b65'
            scriptLen = hex(len(script)//2)[2:]
            if 1 == len(scriptLen) % 2:
                scriptLen = '0' + scriptLen
            s += scriptLen + script + '00'
            return s, True, ''
        return '', False, 'No Ong'

    @staticmethod
    async def compute_gas(height,old_claims,db):
        if not old_claims: old_claims = [] 
        claims = {}
        for v in old_claims:
            k = v['_id'][2:]
            new_v = {}
            new_v['startIndex'] = v['height']
            new_v['value'] = v['value']
            if 'spent_height' in v.keys():
                new_v['stopIndex'] = v['spent_height']
                new_v['stopHash'] = v['spent_txid']
                new_v['status'] = True
            else:
                new_v['stopIndex'] = height
                new_v['stopHash'] = ''
                new_v['status'] = False
            claims[k] = new_v
        del old_claims
        decrementInterval = 2000000
        generationAmount = [8, 7, 6, 5, 4, 3, 2, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1] 
        available = unavailable = D('0')
        heights = list(set(
            [v['startIndex']-1 for v in claims.values() if v['startIndex'] != 0] + 
            [v['stopIndex']-1 for v in claims.values()]))
        fresult = await asyncio.gather(*[db.blocks.find_one({'_id':h}) for h in heights])
        fees = {-1:0,0:0}
        for i in range(len(heights)):
            h = heights[i]
            if h not in fees.keys():
                fees[h] = fresult[i]['total_sys_fee']
        for k,v in claims.items():
            amount = D('0')
            ustart = v['startIndex'] // decrementInterval
            if ustart < len(generationAmount):
                istart = v['startIndex'] % decrementInterval
                uend =   v['stopIndex'] // decrementInterval
                iend =   v['stopIndex'] % decrementInterval
                if uend >= len(generationAmount):
                    uend = len(generationAmount)
                    iend = 0
                if 0 == iend:
                    uend -= 1
                    iend = decrementInterval
                while ustart < uend:
                    amount += (decrementInterval - istart) * generationAmount[ustart]
                    ustart += 1
                    istart = 0
                assert ustart == uend,'error X'
                amount += (iend - istart) * generationAmount[ustart]
            amount += fees[v['stopIndex']-1] - fees[v['startIndex']-1]
            if v['status']:
                available += D(v['value']) / 100000000 * amount
            else:
                unavailable += D(v['value']) / 100000000 * amount
        base = {'available':sci_to_str(str(available)),'unavailable':sci_to_str(str(unavailable))}
        base['claims'] = [i.split('_') for i in claims.keys() if claims[i]['stopHash']]
        return base

    @classmethod
    def transfer_nep5(cls,apphash,source,dest,value,decimals=8):
        '''
        构建NEP5代币转账InvocationTransaction
        '''
        s = 'd101'
        script = ''
        fa = cls.decimal_to_hex(value, 8, decimals)
        faLen = hex(len(fa)//2)[2:]
        if 1 == len(faLen) % 2:
            faLen = '0' + faLen
        script += faLen + fa + '14' + cls.address_to_scripthash(dest) + '14' + cls.address_to_scripthash(source) + '53c1087472616e7366657267' + big_or_little(apphash) + 'f166' + cls.get_random_byte_str(8)
        scriptLen = hex(len(script)//2)[2:]
        if 1 == len(scriptLen) % 2:
            scriptLen = '0' + scriptLen
        s += scriptLen + script + '0000000000000000' + '0120' + cls.address_to_scripthash(source) + '0000'
        return s

    @classmethod
    def transfer_ontology(cls,net,apphash,source,dest,value,decimals):
        '''
        构建ontology代币转账InvocationTransaction
        '''
        s = '00'    #version
        s += 'd1'   #TransactionType
        s += cls.get_random_byte_str(4) #Nonce
        s += 'f401000000000000'        #GasPrice
        s += '204e000000000000'        #GasLimit
        s += cls.address_to_scripthash(source) #Payer
        script = '00c66b14' + cls.address_to_scripthash(source) + '6a7cc814' + cls.address_to_scripthash(dest) + '6a7cc8'
        fa = cls.decimal_to_hex(value, 8, decimals)
        faLen = hex(len(fa)//2)[2:]
        if 1 == len(faLen) % 2:
            faLen = '0' + faLen
        script += faLen + fa + '6a7cc8' + '6c51c1' + '087472616e73666572' + '14' + apphash + '0068164f6e746f6c6f67792e4e61746976652e496e766f6b65'
        scriptLen = hex(len(script)//2)[2:]
        if 1 == len(scriptLen) % 2:
            scriptLen = '0' + scriptLen
        s += scriptLen + script + '00'
        return s

    @classmethod
    def transfer_global(cls, address, utxos, items, assetId):
        '''
        return:transaction,result,errmsg
        '''
        inputs = []
        outputs = []
        value = sum([i[1] for i in items])
        if not isinstance(value, D): value = D(str(value))
        rightUtxo = cls.get_right_utxo(utxos, value, assetId)
        assert rightUtxo
        for r in rightUtxo:
            inputs.append((r['prevHash'], r['prevIndex']))#prevHash,prevIndex
        for i in items:
            outputs.append((assetId, i[1], i[0]))#asset,value:Decimal,address
        returnValue = sum([i['value'] for i in rightUtxo]) - value
        if returnValue:
            outputs.append((assetId, returnValue, address))
        #构建交易
        if 65536 <= len(inputs) : return '',False,'too many inputs'
        if 65536 <= len(outputs): return '',False,'too many outputs'
        tx = '8000' #ContractTransaction+version
        tx += '00'  #attribute length
        tx += cls.num_to_hex_str(len(inputs)) #inputs length
        for i in range(len(inputs)):
            tx += big_or_little(inputs[i][0]) + cls.num_to_hex_str(inputs[i][1], 2)
        tx += cls.num_to_hex_str(len(outputs))
        for i in range(len(outputs)):
            tx += big_or_little(outputs[i][0]) + cls.decimal_to_hex(outputs[i][1]) + cls.address_to_scripthash(outputs[i][2])
        return tx,True,''

    @staticmethod
    def num_to_hex_str(num, length=1):
        s = hex(num)[2:]
        if 1==len(s)%2: s = '0' + s
        return big_or_little('00'*(length - len(s)//2) + s)
        
    @classmethod
    def compute_txid(cls, tx):
        '''计算txid'''
        return big_or_little(binascii.hexlify(cls.hash256(binascii.unhexlify(tx))).decode('ascii'))

    @staticmethod
    def get_transaction(cpubkey, signature, transaction):
        return transaction + '014140' + signature + '2321' + cpubkey + 'ac'

    @staticmethod
    def get_transaction_ontology(cpubkey, signature, transaction):
        return transaction + '014140' + signature + '2321' + cpubkey + 'ac'

    @classmethod
    def verify(cls, cpubkey, signature, message):
        '''refer:https://github.com/cityofzion/neo-python/neo/Cryptography/Crypto.py'''
        bitcoin.change_curve(
            int("FFFFFFFF00000001000000000000000000000000FFFFFFFFFFFFFFFFFFFFFFFF", 16),
            int("FFFFFFFF00000000FFFFFFFFFFFFFFFFBCE6FAADA7179E84F3B9CAC2FC632551", 16),
            int("FFFFFFFF00000001000000000000000000000000FFFFFFFFFFFFFFFFFFFFFFFC", 16),
            int("5AC635D8AA3A93E7B3EBBD55769886BC651D06B0CC53B0F63BCE3C3E27D2604B", 16),
            int("6B17D1F2E12C4247F8BCE6E563A440F277037D812DEB33A0F4A13945D898C296", 16),
            int("4FE342E2FE1A7F9B8EE7EB4A7C0F9E162BCE33576B315ECECBB6406837BF51F5", 16)
        )
        try:
            pubkey = cls.uncompress_pubkey(cpubkey)
            pubkey = binascii.unhexlify(pubkey)[1:]
        except Exception as e:
            return False,'wrong publickey'
        try:
            m = binascii.unhexlify(message)
        except Exception as e:
            return False,"wrong transaction"
        try:
            s = binascii.unhexlify(signature)
        except Exception as e:
            return False,'wrong signature'
        try:
            vk = VerifyingKey.from_string(pubkey, curve=NIST256p, hashfunc=hashlib.sha256)
            res = vk.verify(s, m, hashfunc=hashlib.sha256)
            return res,''
        except Exception as e:
            print('verify failth:%s' % e)
        return False,'failth'
