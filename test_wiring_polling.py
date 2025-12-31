#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试程序：用于测试学生端轮询机制
功能：动态修改全局变量中的接线和拆除导线，观察前端是否能正确响应
"""

import time
import threading
import requests
import json

# 学生端API地址
API_URL = "http://localhost:8088/api/test_set_wiring_data"

class WiringPollingTester:
    def __init__(self):
        self.running = False
        self.test_thread = None
        self.test_type = "add"  # add: 添加接线, undo: 拆除接线, mixed: 混合模式
        self.interval = 3  # 每3秒修改一次
        
    def reset_global_vars(self):
        """通过API重置全局变量"""
        try:
            data = {
                'total_score': 0,
                'add_pairs': [],
                'undo_pairs': []
            }
            response = requests.post(API_URL, json=data)
            if response.status_code == 200:
                print("✅ 全局变量已通过API重置")
            else:
                print(f"❌ API重置失败: {response.text}")
        except Exception as e:
            print(f"❌ 重置全局变量时出错: {e}")
    
    def generate_test_data(self, action):
        """生成测试数据"""
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        
        if action == "add":
            # 生成新增接线数据 - 注意：前端期望的格式是 contact1 和 contact2
            test_pairs = [
                {'contact1': 'FU1-1', 'contact2': 'QS1-1', 'score': 10.0, 'timestamp': timestamp},
                {'contact1': 'SB3-3/NO', 'contact2': 'SB3-4/NO', 'score': 5.0, 'timestamp': timestamp},
                {'contact1': 'KM1-1', 'contact2': 'KM1-2', 'score': 8.0, 'timestamp': timestamp}
            ]
            return test_pairs
        else:
            # 生成拆除接线数据 - 注意：前端期望的格式是 contact1 和 contact2
            test_pairs = [
                {'contact1': 'FU1-1', 'contact2': 'QS1-1', 'score': -10.0, 'timestamp': timestamp},
                {'contact1': 'SB3-3/NO', 'contact2': 'SB3-4/NO', 'score': -5.0, 'timestamp': timestamp}
            ]
            return test_pairs
    
    def test_loop(self):
        """测试主循环"""
        counter = 0
        total_score = 0  # 本地跟踪总分
        
        while self.running:
            counter += 1
            print(f"\n🔄 第 {counter} 次测试更新")
            
            try:
                if self.test_type == "add":
                    # 只添加接线
                    test_data = self.generate_test_data("add")
                    print(f"📝 生成的添加数据: {test_data}")
                    
                    # 更新总分
                    total_score += sum(pair['score'] for pair in test_data)
                    
                    # 准备API请求数据
                    api_data = {
                        'add_pairs': test_data,
                        'undo_pairs': [],
                        'total_score': total_score
                    }
                    
                    # 发送API请求
                    response = requests.post(API_URL, json=api_data)
                    response_data = response.json()
                    
                    if response.status_code == 200 and response_data['success']:
                        print(f"✅ API调用成功")
                        print(f"📥 添加了 {len(test_data)} 条接线")
                        print(f"📊 当前总分: {total_score}")
                    else:
                        print(f"❌ API调用失败: {response_data.get('message', '未知错误')}")
                
                elif self.test_type == "undo":
                    # 只拆除接线
                    test_data = self.generate_test_data("undo")
                    print(f"📝 生成的拆除数据: {test_data}")
                    
                    # 更新总分
                    total_score += sum(pair['score'] for pair in test_data)
                    
                    # 准备API请求数据
                    api_data = {
                        'add_pairs': [],
                        'undo_pairs': test_data,
                        'total_score': total_score
                    }
                    
                    # 发送API请求
                    response = requests.post(API_URL, json=api_data)
                    response_data = response.json()
                    
                    if response.status_code == 200 and response_data['success']:
                        print(f"✅ API调用成功")
                        print(f"📤 拆除了 {len(test_data)} 条接线")
                        print(f"📊 当前总分: {total_score}")
                    else:
                        print(f"❌ API调用失败: {response_data.get('message', '未知错误')}")
                
                elif self.test_type == "mixed":
                    # 混合模式：交替添加和拆除
                    if counter % 2 == 1:
                        # 奇数轮添加
                        test_data_add = self.generate_test_data("add")
                        test_data_undo = []
                        action = "添加"
                    else:
                        # 偶数轮拆除
                        test_data_add = []
                        test_data_undo = self.generate_test_data("undo")
                        action = "拆除"
                    
                    print(f"📝 生成的添加数据: {test_data_add}")
                    print(f"📝 生成的拆除数据: {test_data_undo}")
                    
                    # 更新总分
                    total_score += sum(pair['score'] for pair in test_data_add) + sum(pair['score'] for pair in test_data_undo)
                    
                    # 准备API请求数据
                    api_data = {
                        'add_pairs': test_data_add,
                        'undo_pairs': test_data_undo,
                        'total_score': total_score
                    }
                    
                    # 发送API请求
                    response = requests.post(API_URL, json=api_data)
                    response_data = response.json()
                    
                    if response.status_code == 200 and response_data['success']:
                        print(f"✅ API调用成功")
                        print(f"🔄 {action} 接线")
                        print(f"📥 添加: {len(test_data_add)} 条")
                        print(f"📤 拆除: {len(test_data_undo)} 条")
                        print(f"📊 当前总分: {total_score}")
                    else:
                        print(f"❌ API调用失败: {response_data.get('message', '未知错误')}")
            except Exception as e:
                print(f"❌ 测试循环出错: {e}")
            
            # 等待指定时间
            time.sleep(self.interval)
    
    def start(self, test_type="add", interval=3):
        """开始测试"""
        self.test_type = test_type
        self.interval = interval
        self.running = True
        
        # 重置全局变量
        self.reset_global_vars()
        
        # 启动测试线程
        self.test_thread = threading.Thread(target=self.test_loop)
        self.test_thread.daemon = True
        self.test_thread.start()
        
        print(f"🚀 测试已启动")
        print(f"📋 测试类型: {test_type}")
        print(f"⏱️ 更新间隔: {interval}秒")
        print(f"💡 前端应每2秒更新一次数据")
        print(f"\n按 Ctrl+C 停止测试")
    
    def stop(self):
        """停止测试"""
        self.running = False
        if self.test_thread:
            self.test_thread.join()
        print("\n🛑 测试已停止")
        self.reset_global_vars()

def main():
    """主函数"""
    print("=" * 60)
    print("🧪 学生端轮询机制测试程序")
    print("=" * 60)
    print("功能：动态修改全局变量，观察前端是否能正确响应")
    print("\n测试类型：")
    print("  1. 添加接线 (add)")
    print("  2. 拆除接线 (undo)")
    print("  3. 混合模式 (mixed)")
    print("=" * 60)
    
    # 自动测试模式 - 无需用户输入
    try:
        print("🤖 自动测试模式已启动")
        print("📋 自动选择测试类型: mixed (混合模式)")
        print("⏱️ 自动设置更新间隔: 3秒")
        print("=" * 60)
        
        test_type = "mixed"  # 自动选择混合模式
        interval = 3.0  # 自动设置3秒间隔
        
        # 创建测试对象并启动测试
        tester = WiringPollingTester()
        tester.start(test_type, interval)
        
        # 保持主程序运行
        while True:
            time.sleep(1)
            
    except KeyboardInterrupt:
        tester.stop()
    except Exception as e:
        print(f"\n❌ 测试出错: {e}")
        if 'tester' in locals():
            tester.stop()

if __name__ == "__main__":
    main()