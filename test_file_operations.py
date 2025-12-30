#!/usr/bin/env python3
import os
import sys
import shutil
import json

# 设置规则文件目录
rules_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), 'data/rules/'))

print(f"规则文件目录: {rules_dir}")
print("=" * 60)

# 测试1: 获取规则文件列表
def test_get_rules():
    """测试获取规则文件列表"""
    print("测试1: 获取规则文件列表")
    try:
        rule_files = []
        for filename in os.listdir(rules_dir):
            if filename.endswith('.json') and filename != 'final_rule.json':
                rule_files.append(filename)
        
        print(f"✓ 成功获取规则文件列表")
        print(f"可用规则文件: {rule_files}")
        return rule_files
    except Exception as e:
        print(f"✗ 失败: {e}")
        return []

# 测试2: 检查规则文件是否存在
def test_check_rule_exists(rule_name):
    """测试检查规则文件是否存在"""
    print(f"\n测试2: 检查规则文件 {rule_name} 是否存在")
    try:
        rule_path = os.path.join(rules_dir, rule_name)
        exists = os.path.exists(rule_path)
        
        if exists:
            print(f"✓ 文件 {rule_name} 存在")
            with open(rule_path, 'r', encoding='utf-8') as f:
                content = f.read()
            print(f"   文件大小: {len(content)} 字节")
            return True
        else:
            print(f"✗ 文件 {rule_name} 不存在")
            return False
    except Exception as e:
        print(f"✗ 失败: {e}")
        return False

# 测试3: 测试文件复制操作
def test_copy_rule(rule_name):
    """测试复制规则文件到final_rule.json"""
    print(f"\n测试3: 复制规则文件 {rule_name} 到final_rule.json")
    try:
        source_path = os.path.join(rules_dir, rule_name)
        target_path = os.path.join(rules_dir, 'final_rule.json')
        
        # 保存原final_rule.json内容（如果存在）
        original_content = None
        if os.path.exists(target_path):
            with open(target_path, 'r', encoding='utf-8') as f:
                original_content = f.read()
            print("   已保存原final_rule.json内容")
        
        # 复制文件
        shutil.copy2(source_path, target_path)
        print(f"✓ 成功将 {rule_name} 复制到 final_rule.json")
        
        # 验证复制结果
        with open(source_path, 'r', encoding='utf-8') as f:
            source_content = f.read()
        with open(target_path, 'r', encoding='utf-8') as f:
            target_content = f.read()
        
        if source_content == target_content:
            print("✓ 文件内容验证成功")
            return True
        else:
            print("✗ 文件内容验证失败")
            return False
    except Exception as e:
        print(f"✗ 失败: {e}")
        return False

if __name__ == "__main__":
    # 运行测试
    rule_files = test_get_rules()
    
    if rule_files:
        # 测试第一个规则文件
        test_rule = rule_files[0]
        exists = test_check_rule_exists(test_rule)
        
        if exists:
            success = test_copy_rule(test_rule)
            
            if success:
                print(f"\n" + "=" * 60)
                print("🎉 所有测试通过！文件系统操作正常工作")
            else:
                print(f"\n" + "=" * 60)
                print("❌ 部分测试失败")
    
    print(f"\n" + "=" * 60)
    print("测试完成")
