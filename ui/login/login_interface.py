import os
import sys
import time
import base64
import logging
import cv2
import numpy as np
import requests
from datetime import datetime
from urllib.parse import urljoin
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter, Retry
from flask import Flask, render_template, request, jsonify, redirect, url_for
from flask_socketio import SocketIO, emit
from flask_cors import CORS

# 导入数据库连接器
from tools.connector import MySQLConnector

# ===================== 初始化 Flask 应用 =====================
app = Flask(__name__, template_folder='templates')
app.config['SECRET_KEY'] = 'unified-login-secret-key'
CORS(app)

# ===================== 初始化 SocketIO =====================
try:
    import eventlet
    eventlet.monkey_patch()
    socketio = SocketIO(app, async_mode='eventlet')
except ImportError:
    socketio = SocketIO(app)

# ===================== 日志配置 =====================
log_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'logs')
os.makedirs(log_dir, exist_ok=True)
log_file = os.path.join(log_dir, f'unified_login_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log')

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_file, encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger('UnifiedLogin')

# ===================== 人脸识别配置 =====================
FACES_URL = os.getenv("FACES_URL", "http://192.168.1.130/faces/")
MODEL_NAME = os.getenv("MODEL_NAME", "VGG-Face")
DIST_METRIC = os.getenv("DIST_METRIC", "cosine")
REQUEST_TIMEOUT = 10
LIST_CACHE_TTL = 30

# HTTP 会话
session = requests.Session()
retries = Retry(total=3, backoff_factor=0.3, status_forcelist=[429, 500, 502, 503, 504])
session.mount("http://", HTTPAdapter(max_retries=retries))
_gallery_cache = {"ts": 0, "files": []}

# ===================== 工具函数 =====================
def decode_data_url(data_url: str):
    """解析前端传来的Base64图像"""
    b64 = data_url.split(",", 1)[1]
    img_bytes = base64.b64decode(b64)
    arr = np.frombuffer(img_bytes, np.uint8)
    return cv2.imdecode(arr, cv2.IMREAD_COLOR)

def url_to_cv2(url: str):
    resp = session.get(url, timeout=REQUEST_TIMEOUT)
    resp.raise_for_status()
    return cv2.imdecode(np.frombuffer(resp.content, np.uint8), cv2.IMREAD_COLOR)

def list_gallery_autoindex():
    """从人脸库服务器中读取图片文件名"""
    now = time.time()
    if _gallery_cache["files"] and now - _gallery_cache["ts"] < LIST_CACHE_TTL:
        return _gallery_cache["files"]
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
    _gallery_cache.update({"files": files, "ts": now})
    return files

def get_user_info(emp_id: str):
    """根据工号查询用户信息"""
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
            return None
        user_id, role, name = results[0]
        return {"user_id": user_id, "role": role, "name": name}
    except Exception as e:
        logger.error(f"数据库查询出错: {e}")
        return None
    finally:
        db.close()

# ===================== 登录逻辑 =====================
try:
    from ui.login.src.loginCheck import loginCheck
    login_checker = loginCheck()
    logger.info("登录检查模块导入成功")
except ImportError as e:
    logger.error(f"无法导入登录检查模块: {e}")
    login_checker = None

face_detection_sessions = {}

# ===================== 路由 =====================
@app.route('/')
def index():
    return redirect(url_for('login_page'))

@app.route('/login_page')
def login_page():
    return render_template('login.html')

# ----------- 账号密码登录 -----------
@app.route('/login', methods=['POST'])
def login():
    try:
        username = request.form.get('username')
        password = request.form.get('password')
        identity = request.form.get('identity')
        if not all([username, password, identity]):
            return jsonify({'success': False, 'message': '请填写所有必填字段'})
        success, user_info, message = login_checker.verify_user(username, password, identity)
        if success:
            if identity == 'student':
                redirect_url = f"/student?student_id={user_info['id']}&student_name={user_info['name']}"
            else:
                redirect_url = f"/teacher?teacher_id={user_info['id']}&teacher_name={user_info['name']}"
            return jsonify({'success': True, 'redirect': redirect_url})
        else:
            return jsonify({'success': False, 'message': message})
    except Exception as e:
        logger.error(f"账号登录错误: {e}")
        return jsonify({'success': False, 'message': f'系统错误: {str(e)}'})
@app.route('/register', methods=['POST'])
def register():
    """处理注册请求"""
    try:
        # 获取表单数据
        user_id = request.form.get('user_id')
        user_name = request.form.get('user_name')
        user_password = request.form.get('user_password')
        user_type = request.form.get('user_type')  # 'student' 或 'teacher'
        user_approve = request.form.get('user_approve')

        logger.info(f"接收到注册请求: 用户ID={user_id}, 姓名={user_name}, 身份={user_type}")

        # 验证输入
        if not user_id or not user_name or not user_password or not user_type or not user_approve:
            return jsonify({'success': False, 'message': '请填写所有必填字段'})

        # 验证审批者是否为教师
        success, message = login_checker.verify_approving_teacher(user_approve)
        if not success:
            logger.warning(f"审批者验证失败: {user_approve}, 原因: {message}")
            return jsonify({'success': False, 'message': message})

        # 检查登录检查模块是否可用
        if login_checker is None:
            return jsonify({'success': False, 'message': '系统错误，登录模块不可用'})

        # 调用登录检查模块注册用户
        success, message = login_checker.register_user(user_id, user_password, user_type, user_name, user_approve)

        if success:
            logger.info(f"用户注册成功: {user_id}")
            return jsonify({'success': True, 'message': '注册成功，请等待对应教师审核'})
        else:
            logger.warning(f"用户注册失败: {user_id}, 原因: {message}")
            return jsonify({'success': False, 'message': message})

    except Exception as e:
        logger.error(f"注册过程中发生错误: {e}")
        return jsonify({'success': False, 'message': f'系统错误: {str(e)}'})

# ----------- 人脸识别登录 -----------
@app.route("/recognize_face", methods=["POST"])
def recognize_face():
    from deepface import DeepFace
    try:
        data = request.get_json(silent=True) or {}
        data_url = data.get("image")
        if not data_url:
            return jsonify({"success": False, "message": "未接收到图像数据"}), 400
        probe = decode_data_url(data_url)
        gallery_files = list_gallery_autoindex()
        if not gallery_files:
            return jsonify({"success": False, "message": "人脸库为空或不可访问"}), 500
        for fname in gallery_files:
            try:
                candidate = url_to_cv2(urljoin(FACES_URL, fname))
                result = DeepFace.verify(
                    img1_path=probe,
                    img2_path=candidate,
                    model_name=MODEL_NAME,
                    distance_metric=DIST_METRIC,
                    enforce_detection=False
                )
                if result.get("verified"):
                    emp_id = os.path.splitext(fname)[0]
                    user = get_user_info(emp_id)
                    if user:
                        logger.warning(f"匹配成功："+str(user))
                        return jsonify({
                            "success": True,
                            "emp_id": emp_id,
                            "role": user["role"],
                            "name": user["name"]
                        })
            except Exception as e:
                logger.warning(f"比对 {fname} 出错: {e}")
        return jsonify({"success": False, "message": "未匹配到人脸"})
    except Exception as e:
        logger.error(f"人脸识别错误: {e}")
        return jsonify({"success": False, "message": f"服务器错误: {str(e)}"}), 500

# ----------- 角色跳转 -----------
@app.route('/student')
def student_redirect():
    sid = request.args.get('student_id')
    sname = request.args.get('student_name')
    redirect_url = f'http://localhost:8088/?student_id={sid}&student_name={sname}'
    return redirect(redirect_url)

@app.route('/teacher')
def teacher_redirect():
    tid = request.args.get('teacher_id')
    tname = request.args.get('teacher_name')
    redirect_url = f'http://localhost:8090/?teacher_id={tid}&teacher_name={tname}'
    return redirect(redirect_url)

# ----------- 健康检查 -----------
@app.route('/health', methods=['GET'])
def health():
    try:
        flist = list_gallery_autoindex()
        return jsonify({"ok": True, "faces": len(flist)})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

# ===================== SocketIO 事件 =====================
@socketio.on('connect')
def handle_connect():
    emit('face_detection_status', {'status': 'ready', 'message': '请点击开始人脸识别'})

@socketio.on('disconnect')
def handle_disconnect():
    pass

# ===================== 启动服务 =====================
if __name__ == '__main__':
    logger.info("✅ 启动统一登录服务（账号密码 + 人脸识别）")
    logger.info("访问地址: http://localhost:5000/login_page")
    socketio.run(app, host='0.0.0.0', port=5000, debug=False, allow_unsafe_werkzeug=True)
