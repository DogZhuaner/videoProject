from flask import Flask, render_template, request, jsonify, send_from_directory
import os
from flask_socketio import SocketIO, emit
import json
import sys
import threading
import time
from datetime import datetime

current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.insert(0, parent_dir)

# 导入数据库连接器
try:
    from tools.connector import MySQLConnector
    from tools.config import DB_CONFIG

    DB_AVAILABLE = True
    print("数据库连接模块加载成功")
except ImportError as e:
    print(f"数据库连接模块加载失败：{e}")
    DB_AVAILABLE = False

# 创建数据库连接实例
db_connector = None
try:
    if DB_AVAILABLE:
        db_connector = MySQLConnector(config=DB_CONFIG)
        print("数据库连接初始化成功")
except Exception as e:
    print(f"数据库连接初始化失败：{e}")
    db_connector = None

detect_module = None
rag_module = None
config_module = None
question_generator = None
score_visualizer = None


def get_detect_module():
    global detect_module
    if detect_module is None:
        try:
            from scripts.detect import start_hand_detection, stop_hand_detection
            detect_module = {
                'start_hand_detection': start_hand_detection,
                'stop_hand_detection': stop_hand_detection
            }
        except ImportError:
            print("警告: 无法导入detect模块，将使用模拟模式")
            detect_module = {
                'start_hand_detection': lambda: print("模拟: 开始手势检测"),
                'stop_hand_detection': lambda: print("模拟: 停止手势检测")
            }
    return detect_module


def get_rag_module():
    global rag_module
    if rag_module is None:
        try:
            from scripts.RAG_ui import answer_with_ollama
            rag_module = answer_with_ollama
        except ImportError:
            print("警告: 无法导入RAG_ui模块，将使用模拟AI回答")
            rag_module = lambda question: f"模拟AI回答: {question} (请检查Ollama服务是否运行)"
    return rag_module


def get_config_module():
    global config_module
    if config_module is None:
        try:
            from global_config import Login_Session, Global_Config, reset_session_score, get_global_score
            # 创建实例而不是使用类
            login_session = Login_Session()
            global_config = Global_Config()

            # 确保login_session有必要的属性
            if not hasattr(login_session, 'tno'):
                login_session.tno = "2024001"
            if not hasattr(login_session, 'account_name'):
                login_session.account_name = "测试教师"

            config_module = {
                'Login_Session': login_session,
                'Global_Config': global_config,
                'reset_session_score': reset_session_score,
                'get_global_score': get_global_score
            }
        except ImportError:
            print("警告: 无法导入global_config模块，将使用模拟配置")

            class MockLoginSession:
                def __init__(self):
                    # 添加缺失的tno和account_name属性
                    self.tno = "2024001"
                    self.account_name = "测试教师"

            class MockGlobalConfig:
                teacher_json = "teacher_config.json"
                rule_csv_path = "rule.csv"
                rule_server_ip = "localhost"
                rule_server_port = 8080

            config_module = {
                'Login_Session': MockLoginSession(),
                'Global_Config': MockGlobalConfig(),
                'reset_session_score': lambda: True,
                'get_global_score': lambda: current_score
            }
    return config_module


app = Flask(__name__)
app.config['SECRET_KEY'] = 'teacher-secret-key-here'
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='eventlet')

# 全局变量
current_score = 0
student_scores = {}
connected_students = {}


# 添加一些模拟成绩数据用于演示
def init_demo_data():
    """初始化演示数据"""
    global student_scores
    if not student_scores:  # 只在第一次调用时初始化
        demo_scores = {
            'S001': 85,
            'S002': 92,
            'S003': 78,
            'S004': 88,
            'S005': 95,
            'S006': 82,
            'S007': 76,
            'S008': 90,
            'S009': 87,
            'S010': 83
        }
        student_scores.update(demo_scores)
        print(f"已初始化 {len(student_scores)} 个学生的演示成绩数据")


STUDENTS_FILE = 'students.json'


def load_students():
    """从文件加载学生数据"""
    try:
        with open(STUDENTS_FILE, 'r') as file:
            return json.load(file)
    except FileNotFoundError:
        return []


def save_students(students):
    """将学生数据保存到文件"""
    with open(STUDENTS_FILE, 'w') as file:
        json.dump(students, file)


@app.route('/')
def index():
    """教师主页面"""
    # 从URL参数中获取用户信息
    teacher_id = request.args.get('teacher_id')
    teacher_name = request.args.get('teacher_name')

    # 如果有用户信息，则更新全局配置
    if teacher_id and teacher_name:
        config = get_config_module()
        if hasattr(config['Login_Session'], 'tno'):
            config['Login_Session'].tno = teacher_id
        if hasattr(config['Login_Session'], 'account_name'):
            config['Login_Session'].account_name = teacher_name

        print(f"已更新教师信息: ID={teacher_id}, 姓名={teacher_name}")

    return render_template('index.html')


# 添加新路由用于显示规则下载服务模态框
@app.route('/api/rule_download_service', methods=['GET'])
def rule_download_service():
    """规则下载服务模态框内容"""
    config = get_config_module()
    global_config = config['Global_Config']

    # 获取规则文件路径和服务器信息
    rule_file_path = global_config.rule_csv_path
    server_ip = global_config.rule_server_ip
    server_port = global_config.rule_server_port

    # 检查规则文件是否存在
    file_exists = os.path.exists(rule_file_path)
    file_size = os.path.getsize(rule_file_path) if file_exists else 0

    return jsonify({
        'title': '规则下载服务',
        'content': {
            'file_path': rule_file_path,
            'server_ip': server_ip,
            'server_port': server_port,
            'file_exists': file_exists,
            'file_size': file_size,
            'status': 'ready' if file_exists else 'missing'
        },
        'status': 'success'
    })


@app.route('/api/teacher_info', methods=['GET'])
def get_teacher_info():
    """获取教师信息"""
    config = get_config_module()
    teacher_info = {
        'teacher_id': config['Login_Session'].tno,
        'teacher_name': config['Login_Session'].account_name
    }
    return jsonify(teacher_info)


@app.route('/api/students', methods=['GET'])
def get_students():
    """获取所有学生信息"""
    students = load_students()
    # 获取排序参数
    sort_by = request.args.get('sort_by', 'sno')  # 默认按学号排序

    # 实现排序逻辑
    if sort_by == 'name':
        students.sort(key=lambda x: x.get('name', ''))
    elif sort_by == 'class':
        students.sort(key=lambda x: x.get('class_name', ''))
    else:  # 默认按学号排序
        students.sort(key=lambda x: x.get('sno', ''))

    return jsonify({
        'students': students,
        'total': len(students)
    })


@app.route('/api/student', methods=['POST'])
def add_student():
    """添加新学生"""
    data = request.get_json()
    sno = data.get('sno')
    name = data.get('name')
    class_name = data.get('class_name', '')  # 添加班级信息

    if not sno or not name:
        return jsonify({
            'success': False,
            'message': '学号和姓名不能为空'
        }), 400

    students = load_students()
    # 检查学号是否已存在
    if any(student['sno'] == sno for student in students):
        return jsonify({
            'success': False,
            'message': '学号已存在'
        }), 400

    students.append({
        'id': len(students) + 1,
        'sno': sno,
        'name': name,
        'class_name': class_name  # 添加班级信息
    })
    save_students(students)

    return jsonify({
        'success': True,
        'message': '学生添加成功'
    })


@app.route('/api/registration_requests', methods=['GET'])
def get_registration_requests():
    """获取当前教师需要审批的注册请求"""
    try:
        # 获取当前教师信息
        config = get_config_module()
        teacher_id = config['Login_Session'].tno

        if not teacher_id:
            return jsonify({
                'success': False,
                'message': '未找到教师信息'
            }), 400

        # 检查数据库连接
        if not DB_AVAILABLE or db_connector is None:
            return jsonify({
                'success': False,
                'message': '数据库连接不可用'
            }), 500

        # 查询需要该教师审批的注册请求
        sql = "SELECT user_id, user_name, user_type, user_approve FROM register WHERE user_approve = %s"
        results = db_connector.query(sql, (teacher_id,))

        # 格式化结果
        requests = []
        for row in results:
            user_type_text = '教师' if row[2] == 'teacher' else '学生'
            requests.append({
                'user_id': row[0],
                'user_name': row[1],
                'user_type': row[2],
                'user_type_text': user_type_text,
                'user_approve': row[3]
            })

        return jsonify({
            'success': True,
            'requests': requests,
            'total': len(requests)
        })
    except Exception as e:
        print(f"获取注册请求失败：{e}")
        return jsonify({
            'success': False,
            'message': f'获取注册请求失败：{str(e)}'
        }), 500


@app.route('/api/approve_registration', methods=['POST'])
def approve_registration():
    """批准注册请求"""
    try:
        data = request.get_json()
        user_id = data.get('user_id')

        if not user_id:
            return jsonify({
                'success': False,
                'message': '用户ID不能为空'
            }), 400

        # 检查数据库连接
        if not DB_AVAILABLE or db_connector is None:
            return jsonify({
                'success': False,
                'message': '数据库连接不可用'
            }), 500

        # 1. 从register表获取用户信息
        sql_get_user = "SELECT user_id, user_name, user_password, user_type FROM register WHERE user_id = %s"
        user_result = db_connector.query(sql_get_user, (user_id,))

        if not user_result:
            return jsonify({
                'success': False,
                'message': '用户不存在'
            }), 404

        user_data = user_result[0]

        # 2. 先将用户信息插入到users表中
        user_no = user_data[0]  # user_id作为user_no字段的值
        password = user_data[2]
        role = user_data[3]

        sql_add_user = "INSERT INTO users (user_no, password, role) VALUES (%s, %s, %s)"
        success = db_connector.execute(sql_add_user, (user_no, password, role))

        if not success:
            return jsonify({
                'success': False,
                'message': '添加用户到users表失败'
            }), 500

        # 获取刚刚插入到users表的自增ID
        # 假设db_connector有一个方法可以获取最后插入的ID
        try:
            # 尝试使用MySQL特有的方法获取最后插入的ID
            last_insert_id_result = db_connector.query("SELECT LAST_INSERT_ID()")
            if last_insert_id_result and len(last_insert_id_result) > 0:
                users_user_id = last_insert_id_result[0][0]
            else:
                # 如果无法获取，尝试通过user_no查询
                sql_get_user_id = "SELECT user_id FROM users WHERE user_no = %s"
                user_id_result = db_connector.query(sql_get_user_id, (user_no,))
                if user_id_result and len(user_id_result) > 0:
                    users_user_id = user_id_result[0][0]
                else:
                    raise Exception("无法获取插入的用户ID")
        except Exception as e:
            print(f"获取用户ID失败：{e}")
            return jsonify({
                'success': False,
                'message': f'获取用户ID失败：{str(e)}'
            }), 500

        # 3. 根据用户类型将用户添加到相应的表
        if user_data[3] == 'student':
            # 添加到student表，包含user_id字段
            sql_add_student = "INSERT INTO student (sno, name, student_password, user_id) VALUES (%s, %s, %s, %s)"
            success = db_connector.execute(sql_add_student, (user_data[0], user_data[1], user_data[2], users_user_id))
        else:
            # 添加到teacher表，包含user_id字段
            sql_add_teacher = "INSERT INTO teacher (tno, name, teacher_password, user_id) VALUES (%s, %s, %s, %s)"
            success = db_connector.execute(sql_add_teacher, (user_data[0], user_data[1], user_data[2], users_user_id))

        if not success:
            return jsonify({
                'success': False,
                'message': '添加用户到正式表失败'
            }), 500

        # 4. 从register表中删除记录（因为已批准）
        sql_delete = "DELETE FROM register WHERE user_id = %s"
        success = db_connector.execute(sql_delete, (user_id,))

        if not success:
            return jsonify({
                'success': False,
                'message': '更新注册状态失败'
            }), 500

        return jsonify({
            'success': True,
            'message': '注册请求已批准'
        })
    except Exception as e:
        print(f"批准注册请求失败：{e}")
        return jsonify({
            'success': False,
            'message': f'批准注册请求失败：{str(e)}'
        }), 500


@app.route('/api/reject_registration', methods=['POST'])
def reject_registration():
    """拒绝注册请求"""
    try:
        data = request.get_json()
        user_id = data.get('user_id')
        reason = data.get('reason', '未提供拒绝理由')

        if not user_id:
            return jsonify({
                'success': False,
                'message': '用户ID不能为空'
            }), 400

        # 检查数据库连接
        if not DB_AVAILABLE or db_connector is None:
            return jsonify({
                'success': False,
                'message': '数据库连接不可用'
            }), 500

        # 从register表中删除记录（因为已拒绝）
        sql = "DELETE FROM register WHERE user_id = %s"
        success = db_connector.execute(sql, (user_id,))

        if not success:
            return jsonify({
                'success': False,
                'message': '更新注册状态失败'
            }), 500

        return jsonify({
            'success': True,
            'message': '注册请求已拒绝'
        })
    except Exception as e:
        print(f"拒绝注册请求失败：{e}")
        return jsonify({
            'success': False,
            'message': f'拒绝注册请求失败：{str(e)}'
        }), 500


@app.route('/api/student/<int:student_id>', methods=['DELETE'])
def delete_student(student_id):
    """删除学生"""
    students = load_students()
    students = [student for student in students if student['id'] != student_id]
    # 重新分配ID以保持连续性
    for i, student in enumerate(students):
        student['id'] = i + 1
    save_students(students)

    return jsonify({
        'success': True,
        'message': '学生删除成功'
    })


# 添加编辑学生信息的路由
@app.route('/api/student/<int:student_id>', methods=['PUT'])
def edit_student(student_id):
    """编辑学生信息"""
    data = request.get_json()
    sno_new = data.get('sno')
    name = data.get('name')
    class_name = data.get('class_name', '')  # 添加班级信息

    if not sno_new or not name:
        return jsonify({
            'success': False,
            'message': '学号和姓名不能为空'
        }), 400

    students = load_students()

    # 查找要编辑的学生
    student_index = None
    for i, student in enumerate(students):
        if student['id'] == student_id:
            student_index = i
            break

    if student_index is None:
        return jsonify({
            'success': False,
            'message': '学生不存在'
        }), 404

    # 检查学号是否已存在
    for student in students:
        if student['sno'] == sno_new and student['id'] != student_id:
            return jsonify({
                'success': False,
                'message': '学号已存在'
            }), 400

    # 更新学生信息
    students[student_index].update({
        'sno': sno_new,
        'name': name,
        'class_name': class_name
    })

    save_students(students)

    return jsonify({
        'success': True,
        'message': '学生信息更新成功'
    })


@app.route('/api/student_score/<sno>', methods=['GET'])
def get_student_score(sno):
    """获取特定学生的成绩"""
    # 确保在需要时初始化演示数据
    if not student_scores:
        init_demo_data()
    score = student_scores.get(sno, 0)
    return jsonify({
        'sno': sno,
        'score': score
    })


@app.route('/api/get_score_summary', methods=['GET'])
def get_score_summary():
    """获取成绩统计摘要"""
    # 确保在需要时初始化演示数据
    if not student_scores:
        init_demo_data()

    if not student_scores:
        return jsonify({
            'success': True,
            'summary': {
                'average': 0,
                'highest': 0,
                'lowest': 0,
                'total': 0
            }
        })

    scores = list(student_scores.values())
    return jsonify({
        'success': True,
        'summary': {
            'average': round(sum(scores) / len(scores), 1),
            'highest': max(scores),
            'lowest': min(scores),
            'total': len(scores)
        }
    })


@app.route('/api/get_students_scores', methods=['GET'])
def get_students_scores():
    """获取所有学生成绩列表"""
    # 确保在需要时初始化演示数据
    if not student_scores:
        init_demo_data()

    # 基础学生信息
    base_students = [
        {'id': 'S001', 'sno': '2024001', 'name': '张三', 'exam_time': '2024-01-15 14:30:00',
         'duration': '45分钟'},
        {'id': 'S002', 'sno': '2024002', 'name': '李四', 'exam_time': '2024-01-15 14:35:00',
         'duration': '38分钟'},
        {'id': 'S003', 'sno': '2024003', 'name': '王五', 'exam_time': '2024-01-15 14:40:00',
         'duration': '52分钟'},
        {'id': 'S004', 'sno': '2024004', 'name': '赵六', 'exam_time': '2024-01-15 14:45:00',
         'duration': '41分钟'},
        {'id': 'S005', 'sno': '2024005', 'name': '钱七', 'exam_time': '2024-01-15 14:50:00',
         'duration': '35分钟'},
        {'id': 'S006', 'sno': '2024006', 'name': '孙八', 'exam_time': '2024-01-15 14:55:00',
         'duration': '48分钟'},
        {'id': 'S007', 'sno': '2024007', 'name': '周九', 'exam_time': '2024-01-15 15:00:00',
         'duration': '55分钟'},
        {'id': 'S008', 'sno': '2024008', 'name': '吴十', 'exam_time': '2024-01-15 15:05:00',
         'duration': '42分钟'},
        {'id': 'S009', 'sno': '2024009', 'name': '郑十一', 'exam_time': '2024-01-15 15:10:00',
         'duration': '44分钟'},
        {'id': 'S010', 'sno': '2024010', 'name': '王十二', 'exam_time': '2024-01-15 15:15:00',
         'duration': '47分钟'}
    ]

    # 添加每个学生的错误知识点
    student_weak_points = {
        'S001': ['电机控制', '电路分析'],
        'S002': ['安全规范', '故障诊断'],
        'S003': ['PLC编程', '电机控制'],
        'S004': ['电路分析', '安全规范'],
        'S005': ['故障诊断', 'PLC编程'],
        'S006': ['电机控制', '安全规范'],
        'S007': ['电路分析', '故障诊断'],
        'S008': ['PLC编程', '电机控制'],
        'S009': ['安全规范', 'PLC编程'],
        'S010': ['故障诊断', '电路分析']
    }

    # 将实际成绩数据和错误知识点合并到学生信息中
    students_data = []
    for student in base_students:
        student_id = student['id']
        score = student_scores.get(student_id, 0)  # 从实际成绩数据中获取分数
        student['score'] = score
        student['weak_points'] = student_weak_points.get(student_id, [])  # 添加错误知识点
        students_data.append(student)

    return jsonify({
        'success': True,
        'students': students_data
    })


@app.route('/api/get_score_distribution', methods=['GET'])
def get_score_distribution():
    """获取成绩分布数据"""
    # 确保在需要时初始化演示数据
    if not student_scores:
        init_demo_data()

    distribution = [
        {'range': '90-100分', 'count': 3},
        {'range': '80-89分', 'count': 4},
        {'range': '70-79分', 'count': 2},
        {'range': '60-69分', 'count': 1},
        {'range': '0-59分', 'count': 0}
    ]

    return jsonify({
        'success': True,
        'distribution': distribution
    })


@app.route('/api/create_exam', methods=['POST'])
def create_exam():
    """创建新考试"""
    try:
        data = request.get_json()

        # 验证必填字段
        required_fields = ['test_name', 'test_type', 'duration_minutes', 'publish_time', 'deadline_time']
        for field in required_fields:
            if field not in data or not data[field]:
                return jsonify({
                    'success': False,
                    'message': f'{field} 不能为空'
                }), 400

        # 获取当前教师信息
        config = get_config_module()
        teacher_id = config['Login_Session'].tno

        if not teacher_id:
            return jsonify({
                'success': False,
                'message': '未找到教师信息'
            }), 400

        # 检查数据库连接
        if not DB_AVAILABLE or db_connector is None:
            return jsonify({
                'success': False,
                'message': '数据库连接不可用'
            }), 500

        # 插入考试信息到exam_test表
        sql = """
        INSERT INTO exam_test (
            test_name, test_type, duration_minutes, 
            publish_time, deadline_time, teacher_id
        ) VALUES (%s, %s, %s, %s, %s, %s)
        """
        params = (
            data['test_name'],
            data['test_type'],
            data['duration_minutes'],
            data['publish_time'],
            data['deadline_time'],
            teacher_id
        )

        success = db_connector.execute(sql, params)

        if not success:
            return jsonify({
                'success': False,
                'message': '创建考试失败'
            }), 500

        # 获取刚刚插入的考试ID
        try:
            # 尝试使用MySQL的LAST_INSERT_ID()函数获取最后插入的ID
            last_insert_id_result = db_connector.query("SELECT LAST_INSERT_ID()")
            if last_insert_id_result and len(last_insert_id_result) > 0:
                exam_id = last_insert_id_result[0][0]
            else:
                raise Exception("无法获取插入的考试ID")
        except Exception as e:
            print(f"获取考试ID失败：{e}")
            return jsonify({
                'success': False,
                'message': f'获取考试ID失败：{str(e)}'
            }), 500

        return jsonify({
            'success': True,
            'exam_id': exam_id,
            'message': '考试创建成功'
        })
    except Exception as e:
        print(f"创建考试失败：{e}")
        return jsonify({
            'success': False,
            'message': f'创建考试失败：{str(e)}'
        }), 500


@app.route('/api/get_exams', methods=['GET'])
def get_exams():
    """获取考试列表"""
    try:
        # 获取当前教师信息
        config = get_config_module()
        teacher_id = config['Login_Session'].tno

        if not teacher_id:
            return jsonify({
                'success': False,
                'message': '未找到教师信息'
            }), 400

        # 检查数据库连接
        if not DB_AVAILABLE or db_connector is None:
            # 如果数据库不可用，返回模拟数据
            # 创建模拟教师信息
            teacher_info = {
                'tno': teacher_id,
                'teacher_name': '模拟教师'
            }

            exams = [
                {
                    'id': 'EXAM_001',
                    'name': '电机正反转控制电路考试',
                    'test_name': '电机正反转控制电路考试',  # 确保同时有name和test_name字段
                    'type': '实操考试',
                    'test_type': '实操考试',  # 确保同时有type和test_type字段
                    'duration': 60,
                    'duration_minutes': 60,  # 确保同时有duration和duration_minutes字段
                    'publish_time': '2024-01-15 14:00:00',
                    'deadline_time': '2024-01-15 16:00:00',
                    'create_time': '2024-01-10 09:00:00',
                    'update_time': '2024-01-10 09:00:00',
                    'teacher_info': teacher_info  # 添加教师信息
                },
                {
                    'id': 'EXAM_002',
                    'name': '星三角降压启动电路考试',
                    'test_name': '星三角降压启动电路考试',  # 确保同时有name和test_name字段
                    'type': '实操考试',
                    'test_type': '实操考试',  # 确保同时有type和test_type字段
                    'duration': 90,
                    'duration_minutes': 90,  # 确保同时有duration和duration_minutes字段
                    'publish_time': '2024-01-20 09:00:00',
                    'deadline_time': '2024-01-20 11:30:00',
                    'create_time': '2024-01-15 15:30:00',
                    'update_time': '2024-01-15 15:30:00',
                    'teacher_info': teacher_info  # 添加教师信息
                }
            ]
            return jsonify({
                'success': True,
                'exams': exams,
                'message': '使用模拟数据，数据库连接不可用',
                'teacher_info': teacher_info  # 同时在顶层返回教师信息
            })

        # 从数据库查询该教师创建的考试
        # 首先查询当前教师的信息
        sql_teacher = """
        SELECT tno, name FROM teacher WHERE tno = %s
        """
        teacher_result = db_connector.query(sql_teacher, (teacher_id,))
        teacher_info = None
        if teacher_result and len(teacher_result) > 0:
            teacher_info = {
                'tno': teacher_result[0][0],
                'teacher_name': teacher_result[0][1]
            }

        # 然后查询考试信息
        sql = """
        SELECT test_id, test_name, test_type, duration_minutes, 
               publish_time, deadline_time, create_time, update_time 
        FROM exam_test 
        WHERE teacher_id = %s 
        ORDER BY publish_time DESC
        """
        results = db_connector.query(sql, (teacher_id,))

        # 格式化结果
        exams = []
        for row in results:
            exams.append({
                'id': row[0],
                'name': row[1],
                'test_name': row[1],  # 确保同时有name和test_name字段
                'type': row[2],
                'test_type': row[2],  # 确保同时有type和test_type字段
                'duration': row[3],
                'duration_minutes': row[3],  # 确保同时有duration和duration_minutes字段
                'publish_time': row[4].strftime('%Y-%m-%d %H:%M:%S') if isinstance(row[4], datetime) else str(row[4]),
                'deadline_time': row[5].strftime('%Y-%m-%d %H:%M:%S') if isinstance(row[5], datetime) else str(row[5]),
                'create_time': row[6].strftime('%Y-%m-%d %H:%M:%S') if isinstance(row[6], datetime) else str(row[6]),
                'update_time': row[7].strftime('%Y-%m-%d %H:%M:%S') if isinstance(row[7], datetime) else str(row[7]),
                'teacher_info': teacher_info  # 添加教师信息
            })

        return jsonify({
            'success': True,
            'exams': exams,
            'total': len(exams),
            'teacher_info': teacher_info  # 同时在顶层返回教师信息
        })
    except Exception as e:
        print(f"获取考试列表失败：{e}")
        return jsonify({
            'success': False,
            'message': f'获取考试列表失败：{str(e)}'
        }), 500


@socketio.on('connect')
def handle_connect():
    """处理客户端连接"""
    teacher_id = request.sid
    print(f"教师 {teacher_id} 已连接")
    emit('connection_established', {'teacher_id': teacher_id})


@socketio.on('disconnect')
def handle_disconnect():
    """处理客户端断开连接"""
    teacher_id = request.sid
    print(f"教师 {teacher_id} 已断开连接")


@socketio.on('student_connect')
def handle_student_connect(data):
    """处理学生连接事件"""
    sno = data.get('sno')
    student_name = data.get('student_name')
    if sno and student_name:
        connected_students[sno] = {
            'sno': sno,
            'student_name': student_name,
            'connected_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
        print(f"学生 {sno} ({student_name}) 已连接")
        # 广播给所有教师客户端
        socketio.emit('student_connected', connected_students[sno])


@socketio.on('update_score')
def handle_update_score(data):
    """处理成绩更新事件"""
    sno = data.get('sno')
    score = data.get('score')
    if sno and score is not None:
        student_scores[sno] = score
        print(f"更新学生 {sno} 的成绩为 {score}")
        # 广播给所有教师客户端
        socketio.emit('score_updated', {
            'sno': sno,
            'score': score
        })


@app.route('/api/rule-server/start', methods=['POST'])
def start_rule_server():
    """启动规则下载服务"""
    try:
        # 这里应该实现实际的启动逻辑
        # 目前返回模拟成功响应
        return jsonify({
            'success': True,
            'message': '规则下载服务已启动',
            'status': 'running'
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'启动失败: {str(e)}'
        }), 500


@app.route('/api/rule-server/stop', methods=['POST'])
def stop_rule_server():
    """停止规则下载服务"""
    try:
        # 这里应该实现实际的停止逻辑
        # 目前返回模拟成功响应
        return jsonify({
            'success': True,
            'message': '规则下载服务已停止',
            'status': 'stopped'
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'停止失败: {str(e)}'
        }), 500


@app.route('/api/get_weak_knowledge_points', methods=['GET'])
def get_weak_knowledge_points():
    """获取学生易错知识点统计数据"""
    # 模拟易错知识点数据
    weak_points_data = [
        {'point': '电机控制', 'errorRate': 75},
        {'point': '电路分析', 'errorRate': 68},
        {'point': '安全规范', 'errorRate': 62},
        {'point': '故障诊断', 'errorRate': 55},
        {'point': 'PLC编程', 'errorRate': 48}
    ]

    return jsonify({
        'success': True,
        'weak_points': weak_points_data
    })


if __name__ == '__main__':
    print("教师端Web服务器启动中...")
    try:
        # 尝试使用eventlet
        import eventlet

        eventlet.monkey_patch()
        socketio.run(app, host='127.0.0.1', port=8090, debug=True, use_reloader=False)
    except Exception as e:
        print(f"使用eventlet启动失败: {e}")
        print("尝试使用默认模式启动...")
        # 使用默认模式
        socketio.run(app, host='127.0.0.1', port=8090, debug=True, use_reloader=False)