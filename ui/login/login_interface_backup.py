import os
import sys
import logging
from datetime import datetime
from flask import Flask, render_template, request, jsonify, redirect, url_for
from flask_socketio import SocketIO, emit

# 配置日志
log_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'logs')
os.makedirs(log_dir, exist_ok=True)

log_file = os.path.join(log_dir, f'login_interface_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log')
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_file),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger('LoginInterface')

# 创建Flask应用
app = Flask(__name__, template_folder='templates')
app.config['SECRET_KEY'] = 'login-interface-secret-key'

# 初始化SocketIO
# 使用eventlet作为异步引擎
try:
    import eventlet

    eventlet.monkey_patch()
    socketio = SocketIO(app, async_mode='eventlet')
    logger.info("使用eventlet作为SocketIO异步引擎")
except ImportError:
    # 如果eventlet不可用，回退到默认引擎
    socketio = SocketIO(app)
    logger.warning("eventlet不可用，使用默认异步引擎")

# 导入登录检查模块
login_checker = None
try:
    from ui.login.src.loginCheck import loginCheck
    login_checker = loginCheck()
    logger.info("登录检查模块导入成功")
except ImportError as e:
    logger.error(f"无法导入登录检查模块: {e}")
    sys.exit(1)  # 如果无法导入登录检查模块，直接退出应用

# 全局变量，用于跟踪人脸识别状态
face_detection_sessions = {}


# 路由定义
@app.route('/')
def index():
    """主页路由，重定向到登录页面"""
    return redirect(url_for('login_page'))


@app.route('/login_page')
def login_page():
    """登录页面"""
    logger.info("用户访问登录页面")
    return render_template('login_1.html')


@app.route('/login', methods=['POST'])
def login():
    """处理登录请求"""
    try:
        # 获取表单数据
        username = request.form.get('username')
        password = request.form.get('password')
        identity = request.form.get('identity')  # 'student' 或 'teacher'

        logger.info(f"接收到登录请求: 用户名={username}, 身份={identity}")

        # 验证输入
        if not username or not password or not identity:
            return jsonify({'success': False, 'message': '请填写所有必填字段'})

        # 调用登录检查模块验证用户
        success, user_info, message = login_checker.verify_user(username, password, identity)

        if success:
            logger.info(f"用户登录成功: {username}")
            # 根据用户身份重定向到相应的界面，并传递用户信息
            if identity == 'student':
                # 构造带用户信息的重定向URL
                redirect_url = f"/student?student_id={user_info['id']}&student_name={user_info['name']}"
                return jsonify({'success': True, 'redirect': redirect_url})
            else:
                # 构造带用户信息的重定向URL
                redirect_url = f"/teacher?teacher_id={user_info['id']}&teacher_name={user_info['name']}"
                return jsonify({'success': True, 'redirect': redirect_url})
        else:
            logger.warning(f"用户登录失败: {username}, 原因: {message}")
            return jsonify({'success': False, 'message': message})

    except Exception as e:
        logger.error(f"登录过程中发生错误: {e}")
        return jsonify({'success': False, 'message': f'系统错误: {str(e)}'})


@app.route('/face_detection/start', methods=['POST'])
def start_face_detection():
    """开始人脸识别的代码，这里仅模拟识别成功"""
    try:
        data = request.get_json()
        identity = data.get('identity', '')

        if not identity:
            return jsonify({'success': False, 'message': '请指定身份'})

        logger.info(f"接收到人脸识别请求: 身份={identity}")

        # 在实际应用中，这里会启动摄像头并开始人脸检测
        # 这里仅模拟成功响应
        session_id = f"session_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}"
        face_detection_sessions[session_id] = {
            'identity': identity,
            'status': 'detecting',
            'start_time': datetime.now()
        }

        # 模拟人脸检测过程
        # 实际应用中，这里会通过WebSocket实时更新检测状态
        logger.info(f"开始人脸识别会话: {session_id}")

        return jsonify({
            'success': True,
            'message': '人脸识别已开始',
            'session_id': session_id
        })

    except Exception as e:
        logger.error(f"启动人脸识别时发生错误: {e}")
        return jsonify({'success': False, 'message': f'系统错误: {str(e)}'})


@app.route('/face_detection/stop', methods=['POST'])
def stop_face_detection():
    """停止人脸识别"""
    try:
        data = request.get_json()
        session_id = data.get('session_id', '')

        if session_id and session_id in face_detection_sessions:
            del face_detection_sessions[session_id]
            logger.info(f"停止人脸识别会话: {session_id}")

        return jsonify({
            'success': True,
            'message': '人脸识别已停止'
        })

    except Exception as e:
        logger.error(f"停止人脸识别时发生错误: {e}")
        return jsonify({'success': False, 'message': f'系统错误: {str(e)}'})


@app.route('/face_detection/verify', methods=['POST'])
def verify_face():
    """验证人脸信息"""
    try:
        data = request.get_json()
        face_id = data.get('face_id', '')

        logger.info(f"接收到人脸验证请求: face_id={face_id}")

        # 调用登录检查模块验证人脸ID
        success, user_info, message = login_checker.verify_face_id(face_id)

        if success:
            logger.info(f"人脸验证成功: {user_info['username']}")
            # 根据用户身份重定向到相应的界面，并传递用户信息
            if user_info['identity'] == 'student':
                # 构造带用户信息的重定向URL
                redirect_url = f"/student?student_id={user_info['id']}&student_name={user_info.get('name', user_info['username'])}&face_verified=true"
            else:
                # 构造带用户信息的重定向URL
                redirect_url = f"/teacher?teacher_id={user_info['id']}&teacher_name={user_info.get('name', user_info['username'])}&face_verified=true"
            return jsonify({
                'success': True,
                'message': message,
                'redirect': redirect_url,
                'user_info': user_info
            })
        else:
            logger.warning(f"人脸验证失败: {message}")
            return jsonify({'success': False, 'message': message})

    except Exception as e:
        logger.error(f"人脸验证过程中发生错误: {e}")
        return jsonify({'success': False, 'message': f'系统错误: {str(e)}'})


@app.route('/student')
def student_redirect():
    """重定向到学生端应用"""
    logger.info("用户访问学生界面")
    # 获取URL参数并传递给学生端应用
    student_id = request.args.get('student_id')
    student_name = request.args.get('student_name')
    
    if student_id and student_name:
        redirect_url = f'http://localhost:8088/?student_id={student_id}&student_name={student_name}'
    else:
        redirect_url = 'http://localhost:8088/'
        
    logger.info(f"重定向到学生端应用: {redirect_url}")
    return redirect(redirect_url)


@app.route('/teacher')
def teacher_redirect():
    """重定向到教师端应用"""
    logger.info("用户访问教师界面")
    # 获取URL参数并传递给教师端应用
    teacher_id = request.args.get('teacher_id')
    teacher_name = request.args.get('teacher_name')
    
    if teacher_id and teacher_name:
        redirect_url = f'http://localhost:8094/?teacher_id={teacher_id}&teacher_name={teacher_name}'
    else:
        redirect_url = 'http://localhost:8094/'
        
    logger.info(f"重定向到教师端应用: {redirect_url}")
    return redirect(redirect_url)


# SocketIO事件处理器
@socketio.on('connect')
def handle_connect():
    """处理客户端连接"""
    client_id = request.sid
    logger.info(f"客户端连接: {client_id}")
    emit('face_detection_status', {'status': 'ready', 'message': '请点击开始人脸识别'})


@socketio.on('disconnect')
def handle_disconnect():
    """处理客户端断开连接"""
    client_id = request.sid
    logger.info(f"客户端断开连接: {client_id}")
    # 清理相关的会话资源
    for session_id, session_info in list(face_detection_sessions.items()):
        if session_info.get('client_id') == client_id:
            del face_detection_sessions[session_id]
            logger.info(f"清理会话资源: {session_id}")
            break


# 错误处理
@app.errorhandler(404)
def page_not_found(error):
    """处理404错误"""
    logger.warning(f"页面未找到: {request.path}")
    return jsonify({'success': False, 'message': '页面未找到'}), 404


@app.errorhandler(500)
def internal_server_error(error):
    """处理500错误"""
    logger.error(f"服务器内部错误: {str(error)}")
    return jsonify({'success': False, 'message': '服务器内部错误'}), 500


# 启动应用
if __name__ == '__main__':
    # 确保templates目录存在
    templates_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'templates')
    if not os.path.exists(templates_dir):
        os.makedirs(templates_dir)
        logger.info(f"创建templates目录: {templates_dir}")

    logger.info("电路配盘接线系统 - 统一登录界面 启动中...")
    logger.info(f"启动时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info(f"服务将在 http://localhost:5000 启动")

    try:
        # 启动SocketIO服务器
        socketio.run(app, host='0.0.0.0', port=5000, debug=False, allow_unsafe_werkzeug=True)
    except KeyboardInterrupt:
        logger.info("接收到中断信号，正在停止服务...")
    except Exception as e:
        logger.error(f"服务启动失败: {e}")
        sys.exit(1)
    finally:
        logger.info("服务已停止")