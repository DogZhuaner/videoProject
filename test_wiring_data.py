#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试应用：模拟学生端点击开始连线操作后的一系列事件
"""

import json
import os
import sys
import time
from pathlib import Path

# 添加项目根目录到Python路径
sys.path.append(os.path.abspath(os.path.dirname(__file__)))

from global_config import Global_Config
from script.calculateScore import match_subgraphs


def create_mock_data():
    """
    创建模拟数据文件
    """
    print("创建模拟数据文件...")

    # 确保数据目录存在
    os.makedirs(os.path.dirname(Global_Config.union_find_json_path), exist_ok=True)
    os.makedirs(os.path.dirname(Global_Config.rule_json_path), exist_ok=True)

    # 创建模拟的union_find.json数据
    mock_union_find_data = [
        {
            "subgraph_id": 1,
            "nodes": [
                "QS1-2",
                "FU1-1",
                "FU2-1"
            ]
        },
        {
            "subgraph_id": 2,
            "nodes": [
                "QS1-4",
                "FU1-3",
                "FU2-3"
            ]
        },
        {
            "subgraph_id": 3,
            "nodes": [
                "QS1-6",
                "FU1-5"
            ]
        }
    ]

    # 写入union_find.json文件
    with open(Global_Config.union_find_json_path, 'w', encoding='utf-8') as f:
        json.dump(mock_union_find_data, f, ensure_ascii=False, indent=2)

    print(f"已创建模拟union_find.json文件: {Global_Config.union_find_json_path}")

    # 创建模拟的rule1.json数据
    mock_rule_data = [
        {
            "id": 1,
            "nodes": [
                "QS1-2",
                "FU1-1",
                "FU2-1"
            ],
            "score": 10
        },
        {
            "id": 2,
            "nodes": [
                "QS1-4",
                "FU1-3",
                "FU2-3"
            ],
            "score": 10
        },
        {
            "id": 3,
            "nodes": [
                "QS1-6",
                "FU1-5"
            ],
            "score": 10
        }
    ]

    # 写入rule1.json文件
    with open(Global_Config.rule_json_path, 'w', encoding='utf-8') as f:
        json.dump(mock_rule_data, f, ensure_ascii=False, indent=2)

    print(f"已创建模拟rule1.json文件: {Global_Config.rule_json_path}")

    return mock_union_find_data, mock_rule_data


def simulate_wiring_process():
    """
    模拟连线过程
    """
    print("\n模拟学生端点击开始连线操作...")
    print("=" * 50)

    # 1. 创建模拟数据
    union_find_data, rule_data = create_mock_data()

    # 2. 等待1秒，模拟连线过程
    print("\n模拟学生进行连线操作...")
    time.sleep(1)

    # 3. 调用算分函数
    print("\n调用算分函数计算得分...")
    matched_results = match_subgraphs()

    # 4. 显示结果
    print("\n" + "=" * 50)
    print("模拟连线过程完成")
    print(f"匹配结果: {matched_results}")
    print(f"总得分: {Global_Config.total_score}")
    print("\n请检查前端是否已更新得分和匹配结果")

    return matched_results


def main():
    """
    主函数
    """
    print("测试应用：模拟学生端点击开始连线操作后的一系列事件")
    print("=" * 50)

    # 模拟连线过程
    simulate_wiring_process()

    # 持续运行，等待前端更新
    print("\n测试应用持续运行中...")
    print("按 Ctrl+C 退出")
    print("=" * 50)

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n测试应用已退出")


if __name__ == "__main__":
    main()
