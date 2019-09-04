import unittest
import time

from node import Node

def get_zero_team_level_dict():
    d = {}
    for i in range(24):
        d[+1] = 0
    return d

class TestNode(unittest.TestCase):
    def test_can_bonus(self):
        now = time.time()
        node = Node()
        node.status = -1
        node.days = 30
        node.next_bonus_time = now
        assert not node.can_bonus(now)

        node.status = 0
        assert node.can_bonus(now)

    def test_compute_performance(self):
        children = []
        node1 = Node()
        node1.performance = 1000
        node1.locked_amount = 1000
        node1.status = 0
        node1.days = 30
        children.append(node1)

        node2 = Node()
        node2.performance = 1000
        node2.locked_amount = 1000
        node2.status = -2
        node2.days = 30
        children.append(node2)

        parent = Node()
        parent.set_children(children)
        parent.compute_performance()
        assert parent.performance == 3000

    def test_compute_referrals(self):
        children = []
        node1 = Node()
        node1.performance = 1000
        node1.locked_amount = 1000
        node1.status = 0
        node1.days = 30
        children.append(node1)

        node2 = Node()
        node2.performance = 1000
        node2.locked_amount = 1000
        node2.status = -2
        node2.days = 30
        children.append(node2)

        parent = Node()
        parent.set_children(children)
        parent.compute_referrals()
        assert parent.referrals == 1

    def test_get_team_level_info(self):
        node = Node()
        for i in range(96):
            node.team_level_info += '0'
        info = node.get_team_level_info()
        for i in range(24):
            assert i+1 in info.keys()
            assert info[i+1] == 0

        for i in range(24):
            info[i+1] = i + 1
        node.set_team_level_info(info)

        new_info = node.get_team_level_info()
        for i in range(24):
            assert i+1 in new_info.keys()
            assert new_info[i+1] == i+1

    def test_compute_team_level(self):
        children = []
        node1 = Node()
        node1.performance = 1000
        node1.locked_amount = 1000
        node1.status = 0
        node1.days = 30
        node1.level = 1
        team_level_dict = get_zero_team_level_dict()
        team_level_dict[1] = 1
        node1.set_team_level_info(team_level_dict)
        children.append(node1)

        node2 = Node()
        node2.performance = 1000
        node2.locked_amount = 1000
        node2.status = -2
        node2.days = 30
        node2.level = 1
        team_level_dict = get_zero_team_level_dict()
        team_level_dict[1] = 1
        node2.set_team_level_info(team_level_dict)
        children.append(node2)

        parent = Node()
        parent.set_children(children)
        parent.compute_team_level()

        info = parent.get_team_level_info()
        assert info[1] == 3

    def test_compute_level(self):
        pass

    def test_check_performance(self):
        node = Node()
        node.performance = 12000
        assert node.check_performance(10000)
        assert node.check_performance(10000, 20000)

    def test_check_team_level(self):
        children = []
        node1 = Node()
        node1.level = 5
        node1.status = 0
        team_level_dict = get_zero_team_level_dict()
        team_level_dict[1] = 1
        team_level_dict[3] = 3
        team_level_dict[4] = 1
        node1.set_team_level_info(team_level_dict)
        children.append(node1)

        node2 = Node()
        node2.level = 4
        node2.status = 0
        team_level_dict = get_zero_team_level_dict()
        team_level_dict[1] = 2
        team_level_dict[2] = 3
        team_level_dict[3] = 4
        node2.set_team_level_info(team_level_dict)
        children.append(node2)

        parent = Node()
        parent.set_children(children)
        assert parent.check_team_level(2, 1, 0, 0)
        assert parent.check_team_level(2, 4, 2, 3)
        assert not parent.check_team_level(3, 1, 0, 0)
        assert not parent.check_team_level(2, 5, 0, 0)
