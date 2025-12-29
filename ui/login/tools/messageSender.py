# 简单测试示例 - 只需复制这两个函数到你的项目中使用

import socket
import json
import time
import os

def send_ui_message(message, host='localhost', port=9999):
    """
    向UI窗口发送消息

    Args:
        message (str): 要发送的消息内容

    Returns:
        bool: 发送是否成功
    """
    try:
        print(f"尝试发送消息到 {host}:{port}: {message}")
        client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        client_socket.settimeout(3)
        client_socket.connect((host, port))

        message_data = {
            'type': 'info',
            'content': message
        }

        json_message = json.dumps(message_data, ensure_ascii=False)
        client_socket.send(json_message.encode('utf-8'))
        response = client_socket.recv(1024)
        client_socket.close()
        print(f"消息发送成功，收到响应: {response.decode('utf-8')}")
        return True
    except Exception as e:
        print(f"发送失败: {e}")
        return False


def update_score(score, host='localhost', port=9999):
    """
    更新UI界面中的得分显示

    Args:
        score (int): 新的得分值
        host (str): 服务器地址，默认为localhost
        port (int): 服务器端口，默认为9999

    Returns:
        bool: 更新是否成功
    """
    try:
        print(f"尝试更新得分到 {host}:{port}: {score}分")
        client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        client_socket.settimeout(3)
        client_socket.connect((host, port))

        message_data = {
            'type': 'update_score',
            'score': score,
            'content': f'得分更新为 {score}分'
        }

        json_message = json.dumps(message_data, ensure_ascii=False)
        client_socket.send(json_message.encode('utf-8'))
        response = client_socket.recv(1024)
        client_socket.close()
        print(f"得分更新成功，收到响应: {response.decode('utf-8')}")
        return True
    except Exception as e:
        print(f"更新得分失败: {e}")
        return False


def send_wiring_result(end1, end2, score, host='localhost', port=9999):
    """
    发送接线结果到UI界面

    Args:
        end1 (str): 导线一端名称
        end2 (str): 导线另一端名称
        score (int): 得分
        host (str): 服务器地址，默认为localhost
        port (int): 服务器端口，默认为9999

    Returns:
        bool: 发送是否成功
    """
    try:
        print(f"尝试发送接线结果到 {host}:{port}: {end1} -> {end2} (得分: {score})")
        client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        client_socket.settimeout(3)
        client_socket.connect((host, port))

        message_data = {
            'type': 'wiring_result',
            'end1': end1,
            'end2': end2,
            'score': score,
            'content': f'接线结果: {end1} -> {end2} (得分: {score})'
        }

        json_message = json.dumps(message_data, ensure_ascii=False)
        client_socket.send(json_message.encode('utf-8'))
        response = client_socket.recv(1024)
        client_socket.close()
        print(f"接线结果发送成功，收到响应: {response.decode('utf-8')}")
        return True
    except Exception as e:
        print(f"发送接线结果失败: {e}")
        return False


def restore_loading_effect(host='localhost', port=9999):
    """
    恢复按钮的动态"正在检测中"效果

    Returns:
        bool: 操作是否成功
    """
    try:
        print(f"尝试恢复动态效果到 {host}:{port}")
        client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        client_socket.settimeout(3)
        client_socket.connect((host, port))

        message_data = {
            'type': 'restore_loading',
            'content': '恢复动态检测效果'
        }

        json_message = json.dumps(message_data, ensure_ascii=False)
        client_socket.send(json_message.encode('utf-8'))
        response = client_socket.recv(1024)
        client_socket.close()
        print(f"动态效果恢复成功，收到响应: {response.decode('utf-8')}")
        return True
    except Exception as e:
        print(f"恢复动态效果失败: {e}")
        return False


def test_connection(host='localhost', port=9999):
    """
    测试与UI界面的连接是否正常
    
    Returns:
        bool: 连接是否成功
    """
    try:
        print(f"测试连接到 {host}:{port}")
        client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        client_socket.settimeout(3)
        client_socket.connect((host, port))
        
        # 发送测试消息
        test_data = {
            'type': 'test_connection',
            'content': '连接测试'
        }
        json_message = json.dumps(test_data, ensure_ascii=False)
        client_socket.send(json_message.encode('utf-8'))
        response = client_socket.recv(1024)
        client_socket.close()
        
        print(f"连接测试成功，收到响应: {response.decode('utf-8')}")
        return True
    except Exception as e:
        print(f"连接测试失败: {e}")
        return False


# 测试函数
def test_ui_communication():
    """
    测试UI通信功能
    """
    print("开始测试UI通信...")
    
    # 首先测试连接
    if not test_connection():
        print("❌ 无法连接到学生界面，请确保学生界面已启动")
        return

    # 发送各种消息
    send_ui_message("系统启动")
    time.sleep(1)

    send_ui_message("正在初始化摄像头...")
    time.sleep(1)

    send_ui_message("摄像头初始化成功")
    time.sleep(1)

    send_ui_message("正在加载模型...")
    time.sleep(2)

    send_ui_message("模型加载完成")
    time.sleep(1)

    # 恢复动态效果
    print("恢复动态效果...")
    restore_loading_effect()
    time.sleep(2)

    # 发送更多消息
    send_ui_message("开始手势检测...")
    time.sleep(1)

    # 测试接线结果和得分更新
    current_score = 0

    send_wiring_result("A1端子", "B1端子", 25)
    current_score += 25
    update_score(current_score)
    time.sleep(1)

    send_wiring_result("A2端子", "B2端子", 30)
    current_score += 30
    update_score(current_score)
    time.sleep(1)

    send_wiring_result("A3端子", "B5端子", 0)  # 错误接线，得分为0
    update_score(current_score)  # 总分不变
    time.sleep(1)

    send_wiring_result("A4端子", "B4端子", 25)
    current_score += 25
    update_score(current_score)
    time.sleep(1)

    send_ui_message("检测完成")
    time.sleep(1)

    print(f"测试完成! 最终得分: {current_score}分")


def test_score_update():
    """
    专门测试得分更新功能
    """
    print("开始测试得分更新功能...")
    
    # 首先测试连接
    if not test_connection():
        print("❌ 无法连接到学生界面，请确保学生界面已启动")
        return

    # 测试不同得分的显示效果
    scores = [0, 25, 50, 65, 80, 95, 100]

    for score in scores:
        print(f"更新得分为: {score}分")
        update_score(score)
        time.sleep(1.5)

    print("得分更新测试完成!")


if __name__ == "__main__":
    print("选择测试模式:")
    print("1 - 完整功能测试")
    print("2 - 得分更新测试")
    print("3 - 连接测试")
    choice = input("请选择 (1, 2 或 3): ").strip()

    print("确保学生端UI程序已启动，然后按Enter开始测试...")
    input()

    if choice == "2":
        test_score_update()
    elif choice == "3":
        test_connection()
    else:
        test_ui_communication()