
def dec_to_n(n,x):
    '''十进制转为N进制'''
    #n为待转换的十进制数，x为进制，取值为2-20
    a = [0,1,2,3,4,5,6,7,8,9,'A','b','C','D','E','F','G','H','I','J']
    b = []
    while True:
        s = n//x  # 商
        y = n%x  # 余数
        b = b+[y]
        if s == 0:
            break
        n = s
    b.reverse()
    res = ''
    for i in b:
        res += str(a[i])
    return res

def complete_median(value, n):
    '''位数补全, 补前置0'''
    v = str(value)
    if len(v) >= n:
        return value
    for i in range(n-len(v)):
        v = '0'+ v
    return v

class Node:
    id = 0 #节点数据库id
    address = '' #地址
    layer = -1 #层级
    level = 0 #等级
    locked_amount = 0 #锁仓数量
    locked_bonus = 0 #锁仓分红
    team_bonus = 0 # 团队分红
    referrer = '' #推荐人
    referrals = 0 # 直推人数量
    days = 0 #锁仓天数
    status = -1 #节点状态
    next_bonus_time = 0 #下次分红时间
    performance = 0 #团队业绩
    team_level_info = '' # 团队等级信息，记录各等级数量

    need_updated = False # 是否需要更新

    bonus_advance_table = {} #记录推荐人为各等级时的静态收益分类

    area_advance_tabel = {} #大小区表

    children = []  #子节点

    def set_children(self, children):
        self.children = children

    def clear_children(self):
        self.children = []

    def is_root(self):
        '''判断是否为根节点，即最高领导人'''
        return self.layer == 1

    def is_leaf(self):
        '''判断是否为叶子节点'''
        return len(self.children) == 0

    def can_bonus(self, bonus_time):
        '''能否进行分红'''
        return self.status >= 0 and self.status < self.days and self.next_bonus_time == bonus_time

    def can_compute_in_team(self):
        '''是否能够算进团队业绩'''
        return self.status >= 0 and self.status <= self.days

    def compute_performance(self):
        '''计算团队锁仓业绩'''
        performance = 0
        for node in self.children:
            performance += node.performance
            # 判断子节点能否算进团队业绩
            if node.can_compute_in_team():
                performance += node.locked_amount
        if self.performance != performance:
            self.need_updated = True
        self.performance = performance
        return performance

    def compute_referrals(self):
        '''计算直推人数量'''
        referrals = 0
        for child in self.children:
            if child.can_compute_in_team():
                referrals += 1
        if self.referrals != referrals:
            self.need_updated = True
        self.referrals = referrals
        return referrals

    def get_team_level_info(self):
        '''获得团队各等级数量信息'''
        level_num_dict = {}
        for i in range(0, len(self.team_level_info), 4):
            level_num_dict[i/4+1] = int(self.team_level_info[i:i+4], 18)
        return level_num_dict

    def set_team_level_info(self, level_num_dict):
        '''设置团队各等级数量信息'''
        levels = level_num_dict.keys()
        sorted(levels)
        info = ''
        for level in levels:
            info += complete_median(dec_to_n(level_num_dict[level], 18), 4)
        if self.team_level_info != info:
            self.need_updated = True
        self.team_level_info = info
        return info

    def compute_team_level(self):
        '''计算团队等级数量信息'''
        level_num_dict = {}
        for i in range(24):
            level_num_dict[i+1] = 0
        for child in self.children:
            d = child.get_team_level_info()
            for k in d.keys():
                level_num_dict[k] += d[k]
            # 子节点是否加进去
            if child.can_compute_in_team():
                level_num_dict[child.level] += 1
        return self.set_team_level_info(level_num_dict)

    def compute_level(self):
        '''计算节点等级'''
        level = 0
        if self.check_performance(3001000) and self.check_team_level(11, 4, 7, 11):
            level = 12
        elif self.check_performance(1001000) and self.check_team_level(9, 4, 6, 10):
            level = 11
        elif self.check_performance(301000) and self.check_team_level(7, 4, 5, 9):
            level = 10
        elif self.check_performance(101000) and self.check_team_level(5, 4, 4, 8):
            level = 9
        elif self.check_performance(51000) and self.check_team_level(4, 4, 3, 7):
            level = 8
        elif self.check_performance(11000) and self.check_team_level(3, 2, 2, 6):
            level = 7
        elif self.check_performance(5000) and self.check_team_level(2, 1, 0, 0):
            level = 6
        elif self.check_performance(1000):
            level = 5
        elif self.locked_amount == 10000:
            level = 4
        elif self.locked_amount == 5000:
            level = 3
        elif self.locked_amount == 3000:
            level = 2
        elif self.locked_amount == 1000:
            level = 1
        else:
            level = 0
        if self.level != level:
            self.need_updated = True
        self.level = level
        return level

    def check_performance(self, low, high=0):
        '''检测业绩范围'''
        if high == 0:
            return self.performance >= low
        return self.performance >= low and self.performance <= high

    def check_team_level(self, referral_num, referral_level, referral_team_num, referral_team_level):
        '''检测团队等级是否满足对应的条件'''
        referrals = 0
        referral_teams = 0
        for child in self.children:
            # 判断直推人是否满足等级
            if child.can_compute_in_team() and child.level >= referral_level:
                referrals += 1
                team_level_dict = child.get_team_level_info()
                f = False
                for k in team_level_dict.keys():
                    # 判断直推人的旗下是否满足等级要求
                    if k >= referral_team_level and team_level_dict[k] > 0:
                        f = True
                        break
                if f:
                    referral_teams += 1
        if referral_team_num == 0:
            return referrals >= referral_num
        return referrals >= referral_num and referral_teams >= referral_team_num

    def is_need_update(self, bonus_time):
        ''''是否需要更新数据， 第二个返回值是是否需要更新状态'''
        if self.next_bonus_time == bonus_time:
            return True, self.status >= 0 and self.status < self.days
        return self.need_updated, False

    def compute_advance_bonus_table(self):
        '''计算提前静态收益表'''
        locked_bonus = 0
        if self.can_compute_in_team():
            locked_bonus = self.locked_bonus

        def sum_from_children(level):
            all = {
                'high_level': 0,
                "equal_level": 0,
                "low_one": 0,
                "normal": 0
            }
            for child in self.children:
                one = child.bonus_advance_table[level]
                all['high_level'] += one['high_level']
                all['equal_level'] += one['equal_level']
                all['low_one'] += one['low_one']
                all['normal'] += one['normal']
            return all

        bonus_advance_table = {}
        for l in range(1, 25):
            item = {
                'high_level': 0,
                "equal_level": 0,
                "low_one": 0,
                "normal": 0
            }
            info_from_child = sum_from_children(l)
            if not self.can_compute_in_team():
                bonus_advance_table[l] = info_from_child
                continue
            if l < self.level:  #越级
                item['high_level'] += info_from_child['high_level']
                item['high_level'] += info_from_child['equal_level']
                item['high_level'] += info_from_child['low_one']
                item['high_level'] += info_from_child['normal']
                item['high_level'] += locked_bonus
            elif l == self.level: #平级
                item['high_level'] += info_from_child['high_level']
                item['equal_level'] += info_from_child['equal_level']
                item['equal_level'] += info_from_child['low_one']
                item['equal_level'] += info_from_child['normal']
                item['equal_level'] += locked_bonus
            elif l == self.level + 1:#低一级
                item['high_level'] += info_from_child['high_level']
                item['equal_level'] += info_from_child['equal_level']
                item['low_one'] += info_from_child['low_one']
                item['low_one'] += info_from_child['normal']
                item['low_one'] += locked_bonus
            else: #正常
                item['high_level'] += info_from_child['high_level']
                item['equal_level'] += info_from_child['equal_level']
                item['low_one'] += info_from_child['low_one']
                item['normal'] += info_from_child['normal']
                item['normal'] += locked_bonus
            bonus_advance_table[l] = item
        self.bonus_advance_table = bonus_advance_table

    def compute_dynamic_bonus_cate(self):
        '''计算动态的收益分类'''
        all = {
            'high_level': 0,
            "equal_level": 0,
            "low_one": 0,
            "normal": 0
        }
        for child in self.children:
            one = child.bonus_advance_table[self.level]
            all['high_level'] += one['high_level']
            all['equal_level'] += one['equal_level']
            all['low_one'] += one['low_one']
            all['normal'] += one['normal']
        return all

    def compute_area_advance_tabel(self):
        '''计算大小区表'''
        locked_amount = 0
        if self.can_compute_in_team():
            locked_amount = self.locked_amount

        def sum_from_children(level):
            all = {
                'small': 0,
                "big": []
            }
            for child in self.children:
                info = child.area_advance_tabel[level]
                all['small'] += info['small']
                all['big'].extend(info['big'])
            return all

        area_advance_tabel = {}
        for l in range(1, 25):
            info_from_child = sum_from_children(l)
            if not self.can_compute_in_team():
                area_advance_tabel[l] = info_from_child
                continue

            item = {
                'small': 0,
                "big": []
            }
            if l == self.level + 1: #大区
                item['big'].append(sum(info_from_child['big'], info_from_child['small']+locked_amount))
            else: #小区
                item['small'] = info_from_child['small'] + locked_amount
                item['big'] = info_from_child['big']
            area_advance_tabel[l] = item
        self.area_advance_tabel = area_advance_tabel

    def compute_big_small_area(self):
        '''计算大小区'''
        all = {
            'small': 0,
            "big": []
        }
        for child in self.children:
            info = child.area_advance_tabel[self.level]
            all['small'] += info['small']
            all['big'].extend(info['big'])

        return all
