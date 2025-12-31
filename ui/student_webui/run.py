#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
学生端Web界面启动脚本
"""

import os
import sys


def check_dependencies():
    """检查依赖是否安装"""
    try:
        import flask
        import flask_socketio
        import eventlet
        print("? 所有依赖已安装")
        return True
    except ImportError as e:
        print(f"? 缺少依赖: {e}")
        print("请运行: pip install -r requirements.txt")
        return False


def main():
    """主函数"""
    print("? 启动学生端Web界面")
    print("=" * 50)

    # 检查依赖
    if not check_dependencies():
        return 1

    # 添加项目根目录到Python路径
    current_dir = os.path.dirname(os.path.abspath(__file__))
    parent_dir = os.path.dirname(current_dir)
    sys.path.insert(0, parent_dir)

    print("? 启动Web服务器...")
    print("? 请在浏览器中访问: http://localhost:8088")
    print("=" * 50)

    try:
        # 导入并运行Flask应用
        from app import app, socketio
        socketio.run(app, host='127.0.0.1', port=8088, debug=False)
    except KeyboardInterrupt:
        print("\n? 服务器已停止")
    except Exception as e:
        print(f"? 启动失败: {e}")
        return 1

    return 0


if __name__ == '__main__':
    main()