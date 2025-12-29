import base64
import json
import requests
from pathlib import Path

FLASK_URL = "http://127.0.0.1:6001/recognize_face"


def test_flask_face(image_path: str):
    """
    向 Flask 后端发送指定图片，测试人脸识别接口功能。

    参数:
        image_path (str): 本地图片路径（绝对路径或相对路径）
    返回:
        dict: 后端返回的 JSON 响应
    """

    path = Path(image_path)
    if not path.exists():
        print(f"❌ 图片路径不存在: {path}")
        return None

    # 将图片转为 base64 data URL 格式
    img_bytes = path.read_bytes()
    b64 = base64.b64encode(img_bytes).decode("utf-8")
    mime_type = "image/jpeg" if path.suffix.lower() in [".jpg", ".jpeg"] else "image/png"
    data_url = f"data:{mime_type};base64,{b64}"

    payload = {"image": data_url}

    print(f"🚀 正在向 {FLASK_URL} 发送图片: {path.name}")
    try:
        resp = requests.post(FLASK_URL, headers={"Content-Type": "application/json"}, data=json.dumps(payload),
                             timeout=30)
        print(f"✅ HTTP 状态码: {resp.status_code}")
        print("📦 返回内容:", resp.json())
        return resp.json()
    except Exception as e:
        print("❌ 请求失败:", e)
        return None


# -------------------------------
# 示例调用
# -------------------------------
if __name__ == "__main__":
    # 传入本地图片路径测试
    test_flask_face("test.jpg")  # 示例：同目录下的 test.jpg
