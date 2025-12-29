from flask import Flask, request, jsonify
from deepface import DeepFace
import base64, cv2, numpy as np, requests, os, time
from urllib.parse import urljoin
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter, Retry
from flask_cors import CORS
from tools.connector import MySQLConnector
app = Flask(__name__)
CORS(app)

# ========= 配置 =========
FACES_URL = os.getenv("FACES_URL", "http://192.168.1.105/faces/")  # Nginx autoindex 目录
MODEL_NAME = os.getenv("MODEL_NAME", "VGG-Face")
DIST_METRIC = os.getenv("DIST_METRIC", "cosine")
REQUEST_TIMEOUT = 10
LIST_CACHE_TTL = 30

# HTTP 会话（带重试）
session = requests.Session()
session.headers.update({"User-Agent": "FaceClient/1.0"})
retries = Retry(total=3, backoff_factor=0.3, status_forcelist=[429, 500, 502, 503, 504])
session.mount("http://", HTTPAdapter(max_retries=retries))
session.mount("https://", HTTPAdapter(max_retries=retries))

# 目录缓存
_gallery_cache = {"ts": 0, "files": []}


# ---------- 工具函数 ----------
def log(msg):
    """统一日志输出"""
    print(time.strftime("[%Y-%m-%d %H:%M:%S]"), msg, flush=True)

def decode_data_url(data_url: str):
    b64 = data_url.split(",", 1)[1]
    img_bytes = base64.b64decode(b64)
    arr = np.frombuffer(img_bytes, np.uint8)
    return cv2.imdecode(arr, cv2.IMREAD_COLOR)

def url_to_cv2(url: str):
    resp = session.get(url, timeout=REQUEST_TIMEOUT)
    resp.raise_for_status()
    arr = np.frombuffer(resp.content, np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    return img

def list_gallery_autoindex():
    now = time.time()
    if _gallery_cache["files"] and now - _gallery_cache["ts"] < LIST_CACHE_TTL:
        return _gallery_cache["files"]

    log(f"📂 正在从 {FACES_URL} 获取目录列表...")
    html = session.get(FACES_URL, timeout=REQUEST_TIMEOUT).text
    soup = BeautifulSoup(html, "html.parser")

    files = []
    for a in soup.find_all("a"):
        href = (a.get("href") or "").strip()
        if not href or href in ("../", "./") or href.endswith("/"):
            continue
        low = href.lower()
        if low.endswith((".jpg", ".jpeg", ".png")):
            files.append(href.split("/")[-1])

    _gallery_cache["files"] = files
    _gallery_cache["ts"] = now
    log(f"✅ 获取到 {len(files)} 张人脸图片")
    return files

def get_user_info(emp_id: str):
    """
    根据 emp_id(user_no) 查询用户信息：
    1. 从 users 表获取 user_id 和 role
    2. 若 role=student，则取 student.name
       若 role=teacher，则取 teacher.name
    3. 一次 SQL 查询完成（使用 CASE + LEFT JOIN）
    返回:
        {
            "user_id": int,
            "role": "student" | "teacher",
            "name": str
        }
    若查无结果返回 None
    """
    db = MySQLConnector()
    sql = """
    SELECT 
        u.user_id,
        u.role,
        CASE 
            WHEN u.role = 'student' THEN s.name
            WHEN u.role = 'teacher' THEN t.name
        END AS name
    FROM users u
    LEFT JOIN student s ON u.user_id = s.user_id AND u.role = 'student'
    LEFT JOIN teacher t ON u.user_id = t.user_id AND u.role = 'teacher'
    WHERE u.user_no = %s
    LIMIT 1;
    """

    try:
        results = db.query(sql, (emp_id,))
        if not results:
            print("⚠️ 未找到该用户")
            return None

        user_id, role, name = results[0]
        return {
            "user_id": user_id,
            "role": role,
            "name": name
        }

    except Exception as e:
        print(f"❌ 查询用户信息出错：{e}")
        return None

    finally:
        db.close()

# ---------- 接口 ----------
@app.route("/health", methods=["GET"])
def health():
    try:
        flist = list_gallery_autoindex()
        return jsonify({"ok": True, "faces": len(flist)})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/recognize_face", methods=["POST"])
def recognize_face():
    try:
        data = request.get_json(silent=True) or {}
        data_url = data.get("image")
        if not data_url:
            return jsonify({"success": False, "message": "未接收到图像数据"}), 400

        # 解码图像
        probe = decode_data_url(data_url)
        log("🖼️ 收到一帧截图，开始识别...")

        gallery_files = list_gallery_autoindex()
        if not gallery_files:
            log("❌ 无法读取人脸库或人脸库为空")
            return jsonify({"success": False, "message": "人脸库为空或不可访问"}), 500

        # 逐张对比
        for idx, fname in enumerate(gallery_files, 1):
            face_url = urljoin(FACES_URL, fname)
            try:
                candidate = url_to_cv2(face_url)
                result = DeepFace.verify(
                    img1_path=probe,
                    img2_path=candidate,
                    model_name=MODEL_NAME,
                    distance_metric=DIST_METRIC,
                    enforce_detection=False
                )

                verified = result.get("verified")
                distance = result.get("distance")
                log(f"比对[{idx}/{len(gallery_files)}] {fname} → 结果: {verified} 距离: {distance:.4f}")

                if verified:
                    emp_id = os.path.splitext(fname)[0]
                    log(f"✅ 识别成功！匹配工号：{emp_id}")
                    result = get_user_info(emp_id)
                    print(result)
                    return jsonify({"success": True,
                                    "emp_id": emp_id,
                                    "role":result['role'],
                                    "name":result['name']
                                    })

            except Exception as e:
                log(f"[警告] 比对 {fname} 出错: {e}")

        log("🚫 未匹配到任何人脸")
        return jsonify({"success": False, "message": "未匹配到人脸"})

    except Exception as e:
        log(f"🔥 服务器错误: {e}")
        return jsonify({"success": False, "message": f"服务器错误: {e}"}), 500


if __name__ == "__main__":
    log(f"🚀 Flask 人脸识别服务启动中 | 端口: 6000 | FACES_URL: {FACES_URL}")
    app.run(host="0.0.0.0", port=6001)
