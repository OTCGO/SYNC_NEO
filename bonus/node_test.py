import unittest
import time

from node import Node, encode_advance_bonus_table, decode_advance_bonus_table,encode_advance_area_table, decode_advance_area_table

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
        assert parent.check_team_level(2, 1)
        assert parent.check_team_level(2, 4)
        assert not parent.check_team_level(3, 1)
        assert not parent.check_team_level(2, 5)

    def test_compute_advance_bonus_table(self):
        '''测试计算等级分红表'''
        '''测试节点, 每个节点静态收益为1，等级如下：单引号的节点为退出的节点
                     6
                   /   \
                 5       '4'
               /   \    /  \
             8      6 2      1
            / \    / \
           3   2  5   4
        '''
        def new_node(level, status):
            n = Node()
            n.status = status
            n.level = level
            n.locked_bonus = 1
            n.days = 30
            n.children = []
            for i in range(1, 25):
                n.bonus_advance_table[i] = {
                    'high_level': 0,
                    "equal_level": 0,
                    "low_one": 0,
                    "normal": 0
                }
            return n
        n1 = new_node(3, 0)
        n2 = new_node(2, 0)
        n3 = new_node(5, 0)
        n4 = new_node(4, 0)

        n5 = new_node(8, 0)
        n5.children.extend([n1, n2])
        n6 = new_node(6, 0)
        n6.children.extend([n3, n4])
        n7 = new_node(2, 0)
        n8 = new_node(1, 0)

        n9 = new_node(5, 0)
        n9.children.extend([n5, n6])
        n10 = new_node(4, -2)
        n10.children.extend([n7, n8])

        n11 = new_node(6, 0)
        n11.children.extend([n9, n10])

        n1.compute_advance_bonus_table()
        n2.compute_advance_bonus_table()
        n3.compute_advance_bonus_table()
        n4.compute_advance_bonus_table()
        n5.compute_advance_bonus_table()
        n6.compute_advance_bonus_table()
        n7.compute_advance_bonus_table()
        n8.compute_advance_bonus_table()
        n9.compute_advance_bonus_table()
        n10.compute_advance_bonus_table()
        n11.compute_advance_bonus_table()

        def check_result(node, levels, high_level, equal_level, low_one, normal):
            for i in range(levels[0], levels[1]+1):
                info = node.bonus_advance_table[i]
                self.assertEqual(high_level, info['high_level'])
                self.assertEqual(equal_level, info['equal_level'])
                self.assertEqual(low_one, info['low_one'])
                self.assertEqual(normal, info['normal'])
        check_result(n1, [1, 2], 1, 0, 0, 0)
        check_result(n1, [3, 3], 0, 1, 0, 0)
        check_result(n1, [4, 4], 0, 0, 1, 0)
        check_result(n1, [5, 24], 0, 0, 0, 1)

        check_result(n2, [1, 1], 1, 0, 0, 0)
        check_result(n2, [2, 2], 0, 1, 0, 0)
        check_result(n2, [3, 3], 0, 0, 1, 0)
        check_result(n2, [4, 24], 0, 0, 0, 1)

        check_result(n3, [1, 4], 1, 0, 0, 0)
        check_result(n3, [5, 5], 0, 1, 0, 0)
        check_result(n3, [6, 6], 0, 0, 1, 0)
        check_result(n3, [7, 24], 0, 0, 0, 1)

        check_result(n4, [1, 3], 1, 0, 0, 0)
        check_result(n4, [4, 4], 0, 1, 0, 0)
        check_result(n4, [5, 5], 0, 0, 1, 0)
        check_result(n4, [6, 24], 0, 0, 0, 1)

        check_result(n5, [1, 7], 3, 0, 0, 0)
        check_result(n5, [8, 8], 0, 3, 0, 0)
        check_result(n5, [9, 9], 0, 0, 3, 0)
        check_result(n5, [10, 24], 0, 0, 0, 3)

        check_result(n6, [1, 5], 3, 0, 0, 0)
        check_result(n6, [6, 6], 0, 3, 0, 0)
        check_result(n6, [7, 7], 0, 0, 3, 0)
        check_result(n6, [8, 24], 0, 0, 0, 3)

        check_result(n7, [1, 1], 1, 0, 0, 0)
        check_result(n7, [2, 2], 0, 1, 0, 0)
        check_result(n7, [3, 3], 0, 0, 1, 0)
        check_result(n7, [4, 24], 0, 0, 0, 1)

        check_result(n8, [1, 1], 0, 1, 0, 0)
        check_result(n8, [2, 2], 0, 0, 1, 0)
        check_result(n8, [3, 24], 0, 0, 0, 1)

        check_result(n9, [1, 4], 7, 0, 0, 0)
        check_result(n9, [5, 5], 6, 1, 0, 0)
        check_result(n9, [6, 6], 3, 3, 1, 0)
        check_result(n9, [7, 7], 3, 0, 3, 1)
        check_result(n9, [8, 8], 0, 3, 0, 4)
        check_result(n9, [9, 9], 0, 0, 3, 4)
        check_result(n9, [10, 24], 0, 0, 0, 7)

        check_result(n10, [1, 1], 1, 1, 0, 0)
        check_result(n10, [2, 2], 0, 1, 1, 0)
        check_result(n10, [3, 3], 0, 0, 1, 1)
        check_result(n10, [4, 24], 0, 0, 0, 2)

        check_result(n11, [1, 5], 10, 0, 0, 0)
        check_result(n11, [6, 6], 3, 7, 0, 0)
        check_result(n11, [7, 7], 3, 0, 7, 0)
        check_result(n11, [8, 8], 0, 3, 0, 7)
        check_result(n11, [9, 9], 0, 0, 3, 7)
        check_result(n11, [10, 24], 0, 0, 0, 10)

        def check_dynamic_bonus_cate(node, high_level, equal_level, low_one, normal):
            cate = node.compute_dynamic_bonus_cate()
            self.assertEqual(high_level, cate['high_level'])
            self.assertEqual(equal_level, cate['equal_level'])
            self.assertEqual(low_one, cate['low_one'])
            self.assertEqual(normal, cate['normal'])
        check_dynamic_bonus_cate(n1, 0, 0, 0, 0)
        check_dynamic_bonus_cate(n2, 0, 0, 0, 0)
        check_dynamic_bonus_cate(n3, 0, 0, 0, 0)
        check_dynamic_bonus_cate(n4, 0, 0, 0, 0)
        check_dynamic_bonus_cate(n5, 0, 0, 0, 2)
        check_dynamic_bonus_cate(n6, 0, 0, 1, 1)
        check_dynamic_bonus_cate(n7, 0, 0, 0, 0)
        check_dynamic_bonus_cate(n8, 0, 0, 0, 0)
        check_dynamic_bonus_cate(n9, 6, 0, 0, 0)
        check_dynamic_bonus_cate(n10, 0, 0, 0, 2)
        check_dynamic_bonus_cate(n11, 3, 3, 1, 2)

    def test_compute_area_advance_tabel(self):
        '''测试计算大小区'''
        '''测试节点, 每个节点锁仓为1，等级如下：单引号的节点为退出的节点
                     7
                   /   \
                 5       '4'
               /   \    /  \
             6      6 2      1
            / \    / \
           3   2  5   4
        '''
        def new_node(level, status):
            n = Node()
            n.status = status
            n.level = level
            n.locked_amount = 1
            n.days = 30
            n.children = []
            for i in range(1, 25):
                n.area_advance_tabel[i] = {
                    'small': 0,
                    "big": []
                }
            return n
        n1 = new_node(3, 0)
        n2 = new_node(2, 0)
        n3 = new_node(5, 0)
        n4 = new_node(4, 0)

        n5 = new_node(6, 0)
        n5.children.extend([n1, n2])
        n6 = new_node(6, 0)
        n6.children.extend([n3, n4])
        n7 = new_node(2, 0)
        n8 = new_node(1, 0)

        n9 = new_node(5, 0)
        n9.children.extend([n5, n6])
        n10 = new_node(4, -2)
        n10.children.extend([n7, n8])

        n11 = new_node(7, 0)
        n11.children.extend([n9, n10])

        n1.compute_area_advance_tabel()
        n2.compute_area_advance_tabel()
        n3.compute_area_advance_tabel()
        n4.compute_area_advance_tabel()
        n5.compute_area_advance_tabel()
        n6.compute_area_advance_tabel()
        n7.compute_area_advance_tabel()
        n8.compute_area_advance_tabel()
        n9.compute_area_advance_tabel()
        n10.compute_area_advance_tabel()
        n11.compute_area_advance_tabel()

        def check_result(node, levels, big, small):
            for i in range(levels[0], levels[1]+1):
                info = node.area_advance_tabel[i]
                self.assertEqual(small, info['small'], "node.level: {} parent.level: {}".format(node.level, i))
                self.assertEqual(big, info['big'], "node.level: {} parent.level: {}".format(node.level, i))
        check_result(n1, [1, 3], [], 1)
        check_result(n1, [4, 4], [1], 0)
        check_result(n1, [5, 24], [], 1)

        check_result(n2, [1, 2], [], 1)
        check_result(n2, [3, 3], [1], 0)
        check_result(n2, [4, 24], [], 1)

        check_result(n3, [1, 5], [], 1)
        check_result(n3, [6, 6], [1], 0)
        check_result(n3, [7, 24], [], 1)

        check_result(n4, [1, 4], [], 1)
        check_result(n4, [5, 5], [1], 0)
        check_result(n4, [6, 24], [], 1)

        check_result(n5, [1, 2], [], 3)
        check_result(n5, [3, 4], [1], 2)
        check_result(n5, [5, 6], [], 3)
        check_result(n5, [7, 7], [3], 0)
        check_result(n5, [8, 24], [], 3)

        check_result(n6, [1, 4], [], 3)
        check_result(n6, [5, 6], [1], 2)
        check_result(n6, [7, 7], [3], 0)
        check_result(n6, [8, 24], [], 3)

        check_result(n7, [1, 2], [], 1)
        check_result(n7, [3, 3], [1], 0)
        check_result(n7, [4, 24], [], 1)

        check_result(n8, [1, 1], [], 1)
        check_result(n8, [2, 2], [1], 0)
        check_result(n8, [3, 24], [], 1)

        check_result(n9, [1, 2], [], 7)
        check_result(n9, [3, 5], [1], 6)
        check_result(n9, [6, 6], [7], 0)
        check_result(n9, [7, 7], [3, 3], 1)
        check_result(n9, [8, 24], [], 7)

        check_result(n10, [1, 1], [], 2)
        check_result(n10, [2, 2], [1], 1)
        check_result(n10, [3, 3], [1], 1)
        check_result(n10, [4, 24], [], 2)

        check_result(n11, [1, 1], [], 10)
        check_result(n11, [2, 2], [1], 9)
        check_result(n11, [3, 3], [1, 1], 8)
        check_result(n11, [4, 5], [1], 9)
        check_result(n11, [6, 6], [7], 3)
        check_result(n11, [7, 7], [3, 3], 4)
        check_result(n11, [8, 8], [10], 0)
        check_result(n11, [9, 24], [], 10)

        def check_big_small_area(node, big, small):
            info = node.compute_big_small_area()
            self.assertEqual(big, info['big'])
            self.assertEqual(small, info['small'])

        check_big_small_area(n1, [], 0)
        check_big_small_area(n2, [], 0)
        check_big_small_area(n3, [], 0)
        check_big_small_area(n4, [], 0)
        check_big_small_area(n5, [], 2)
        check_big_small_area(n6, [1], 1)
        check_big_small_area(n7, [], 0)
        check_big_small_area(n8, [], 0)
        check_big_small_area(n9, [1], 5)
        check_big_small_area(n10, [], 2)
        check_big_small_area(n11, [3, 3], 3)

    def test_encode_advance_bonus_table(self):
        bonus_advance_table = {}
        for i in range(1, 25):
            bonus_advance_table[i] = {
                'high_level': 0,
                "equal_level": 0,
                "low_one": 0,
                "normal": 1
            }
        s = encode_advance_bonus_table(bonus_advance_table)
        self.assertDictEqual(bonus_advance_table, decode_advance_bonus_table(s))

    def test_encode_advance_area_table(self):
        area_advance_tabel = {}
        for i in range(1, 25):
            area_advance_tabel[i] = {
                'small': 2,
                "big": [1]
            }
        s = encode_advance_area_table(area_advance_tabel)
        self.assertDictEqual(area_advance_tabel, decode_advance_area_table(s))