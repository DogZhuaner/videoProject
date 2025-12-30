#!/usr/bin/env python3
import json
import os
import sys
import requests
import tempfile
import shutil

# 添加项目根目录到Python路径
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '.')))

# 测试API端点
BASE_URL = 'http://localhost:5000/api'

def test_get_rules():
    """测试获取规则文件列表API"""
    print("测试获取规则文件列表API...")
    try:
        # 使用直接调用函数的方式测试
        from ui.student_webui.app import get_rules
        
        # 创建Flask测试上下文
        from flask import Flask, jsonify
        app = Flask(__name__)
        
        with app.test_request_context():
            response = get_rules()
            data = json.loads(response.get_data(as_text=True))
            
            print(f"状态: {'成功' if data['success'] else '失败'}")
            if data['success']:
                print(f"可用规则文件: {data['rules']}")
            else:
                print(f"错误信息: {data['message']}")
                
        return data
    except Exception as e:
        print(f"测试失败: {e}")
        return None

def test_set_rule(rule_name):
    """测试设置规则文件API"""
    print(f"测试设置规则文件API (规则: {rule_name})...")
    try:
        # 使用直接调用函数的方式测试
        from ui.student_webui.app import set_rule
        from flask import Flask, jsonify, request
        app = Flask(__name__)
        
        # 创建临时测试规则文件
        rules_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), 'data/rules/'))
        test_file_path = os.path.join(rules_dir, f"test_{rule_name}")
        final_file_path = os.path.join(rules_dir, "final_rule.json")
        
        # 保存原final_rule.json内容（如果存在）
        original_content = None
        if os.path.exists(final_file_path):
            with open(final_file_path, 'r', encoding='utf-8') as f:
                original_content = f.read()
        
        # 准备测试数据
        test_data = {
            "rule": rule_name
        }
        
        with app.test_request_context('/api/set_rule', method='POST', 
                                     data=json.dumps(test_data),
                                     content_type='application/json'):
            response = set_rule()
            data = json.loads(response.get_data(as_text=True))
            
            print(f"状态: {'成功' if data['success'] else '失败'}")
            if data['success']:
                print(f"成功信息: {data['message']}")
                # 验证文件是否被正确复制
                if os.path.exists(final_file_path):
                    with open(final_file_path, 'r', encoding='utf-8') as f:
                        final_content = f.read()
                    with open(os.path.join(rules_dir, rule_name), 'r', encoding='utf-8') as f:
                        rule_content = f.read()
                    
                    if final_content == rule_content:
                        print("✓ 规则文件已成功覆盖final_rule.json")
                    else:
                        print("✗ 规则文件覆盖失败")
            else:
                print(f"错误信息: {data['message']}")
        
        return data
    except Exception as e:
        print(f"测试失败: {e}")
        return None

if __name__ == "__main__":
    print("测试考试规则选择API...")
    print("=" * 50)
    
    # 测试获取规则文件列表
    get_rules_result = test_get_rules()
    
    print("\n" + "=" * 50)
    
    # 如果获取规则成功，测试设置规则
    if get_rules_result and get_rules_result['success'] and get_rules_result['rules']:
        test_rule = get_rules_result['rules'][0]  # 使用第一个规则文件进行测试
        test_set_rule(test_rule)
    else:
        print("没有可用的规则文件进行测试")
    
    print("\n" + "=" * 50)
    print("测试完成")
