class Node:
    address = '' #地址
    layer = -1 #层级
    level = 0 #等级
    locked_amount = 0 #锁仓数量
    locked_bonus = 0 #锁仓分红
    team_bonus = 0 # 团队分红
    referrer = '' #推荐人
    days = 0 #锁仓天数
    status = -1 #节点状态
    next_bonus_time = 0 #下次分红时间
    team_amount = 0 #团队业绩

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
        return self.status >= 0 and self.status < self.days

    def compute_team_amount(self):
        '''计算团队锁仓业绩'''
        team_amount = 0
        for node in self.children:
            team_amount += node.team_amount
            # 判断子节点能否算进团队业绩
            if node.can_compute_in_team():
                team_amount += node.locked_amount
        self.team_amount = team_amount
        return team_amount
