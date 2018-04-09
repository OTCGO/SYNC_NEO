
NEO = '0xc56f33fc6ecfcd0c225c4ab356fee59390af8560be0e930faebe74a6daff7c9b'
NEP5 = {
        'ecc6b20d3ccac1ee9ef109af5a7cdb85706b1df9':'RPX',
        '0d821bd7b6d53f5c2b40e217c6defc8bbe896cf5':'QLC',
        'a0777c3ce2b169d4a23bcba4565e3225a0122d95':'APH',
        'b951ecbbc5fe37a9c280a76cb0ce0014827294cf':'DBC',
        'ac116d4b8d4ca55e6b6d4ecce2192039b51cccc5':'ZPT',
        '08e8c4400f1af2c20c28e0018f29535eb85d15b6':'TNC',
        '2328008e6f6c7bd157a342e789389eb034d9cbc4':'RHT',
        '7f86d61ff377f1b12e589a5907152b57e2ad9a7a':'ACAT',
        '546c5872a992b2754ef327154f4c119baabff65f':'BCS',
        '132947096727c84c7f9e076c90f08fec3bc17f18':'TKY',
        '45d493a6f73fa5f404244a5fb8472fc014ca5885':'CPX',
        '2e25d2127e0240c6deaf35394702feb236d4d7fc':'NRV',
        '34579e4614ac1a7bd295372d3de8621770c76cdc':'CGE',
        'a721d5893480260bd28ca1f395f2c465d0b5b1c2':'NRVE',
        '891daf0e1750a1031ebe23030828ad7781d874d6':'IAM',
        'ceab719b8baa2310f232ee0d277c061704541cfb':'ONT',
        '0e86a40588f715fcaf7acd1812d50af478e6e917':'OBT',
        'af7c7328eee5a275a3bcaee2bf0cf662b5e739be':'PKC',
        '67a5086bac196b67d5fd20745b0dc9db4d2930ed':'THOR',
        '9577c3f972d769220d69d1c4ddbd617c44d067aa':'GALA',
        '78e6d16b914fe15bc16150aeb11d0c2a8e532bdd':'SWH',
        'e8f98440ad0d7a6e76d84fb1c3d3f8a16e162e97':'EXT',
        '81c089ab996fc89c468a26c0a88d23ae2f34b5c0':'EDS',
        '06fa8be9b6609d963e8fc63977b9f8dc5f10895f':'LRN',
        }
GLOBAL = {
        'c56f33fc6ecfcd0c225c4ab356fee59390af8560be0e930faebe74a6daff7c9b':'GoverningToken',#NEO
        '602c79718b16e442de58778e148d0b1084e3b2dffd5de6b7b16cee7969282de7':'UtilityToken',  #GAS
        '7f48028c38117ac9e42c8e1f6f06ae027cdbb904eaf1a0bdc30c9d81694e045c':'Token',         #无忧宝
        'a52e3e99b6c2dd2312a94c635c050b4c2bc2485fcb924eecb615852bd534a63f':'Token',         #申一币
        '025d82f7b00a9ff1cfe709abe3c4741a105d067178e645bc3ebad9bc79af47d4':'Token',         #TestCoin
        '07de511668e6ecc90973d713451c831d625eca229242d34debf16afa12efc1c1':'Token',         #开拍学园币（KAC）
        '0ab0032ade19975183c4ac90854f1f3c3fc535199831e7d8f018dabb2f35081f':'Token',         #量子积分
        '1b504c5fb070aaca3d57c42b5297d811fe6f5a0c5d4cd4496261417cf99013a5':'Share',         #量子股份
        '459ef82138f528c5ff79dd67dcfe293e6a348e447ed8f6bce5b79dded2e63409':'Token',         #赏金（SJ-Money)
        '30e9636bc249f288139651d60f67c110c3ca4c3dd30ddfa3cbcec7bb13f14fd4':'Share',         #申一股份
        '439af8273fbe25fec2f5f2066679e82314fe0776d52a8c1c87e863bd831ced7d':'Token',         #Hello AntShares Mainnet
        '7ed4d563277f54a1535f4406e4826882287fb74d06a1a53e76d3d94d9b3b946a':'Share',         #宝贝评级
        'dd977e41a4e9d5166003578271f191aae9de5fc2de90e966c8d19286e37fa1e1':'Token',         #橙诺
        '9b63fa15ed58e93339483619175064ecadbbe953436a22c31c0053dedca99833':'Share',         #未来研究院
        '308b0b336e2ed3d718ef92693b70d30b4fe20821265e8e76aecd04a643d0d7fa':'Share',         #明星资本
        '6161af8875eb78654e385a33e7334a473a2a0519281d33c06780ff3c8bce15ea':'Token',         #量子人民币
        'cb453a56856a236cbae8b8f937db308a15421daada4ba6ce78123b59bfb7253c':'Token',         #人民币CNY
        'c0b3c094efd1849c125618519ae733e3b63c976d60fc7e3d0e88af86a65047e3':'Share',         #开拍学园
        '3ff74cf84869a7df96ede132de9fa62e13aa3ac8a6548e546ad316f4bda6460c':'Share',         #币区势
        'c39631b351c1f385afc1eafcc0ff365977b59f4aa4a09a0b7b1f5705241457b7':'Share',         #花季股
        }


def validate_asset(asset):
    al = len(asset)
    if al not in [40,64]: False
    if 40 == al: return asset in NEP5.keys()
    if 64 == al: return asset in GLOBAL.keys()

def get_asset_decimal(asset):
    al = len(asset)
    if 40 == al: return 8
    if 64 == al:
        t = GLOBAL[asset]
        if t in ['GoverningToken', 'Share']: return 0
        return 8

def get_asset_name(asset):
    al = len(asset)
    if 40 == al: return NEP5[asset]
    if 64 == al: return GLOBAL[asset]
