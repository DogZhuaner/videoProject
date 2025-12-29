import os
import sys
import time
from datetime import datetime
from flask import Flask, render_template, jsonify, request
from flask_socketio import SocketIO

# 添加项目根目录到Python路径
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
# 添加项目根目录到Python路径
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))
# 添加script目录到Python路径
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../script')))

from global_config import Global_Config
import global_config
from script.detect_SwtichHand import start_hand_detection, stop_hand_detection

# 添加tools目录到Python路径
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../tools')))
from tools.connector import MySQLConnector

# 导入项目模块 - 使用延迟导入提高启动速度
detect_module = None
rag_module = None
config_module = None
question_generator = None
score_visualizer = None


def reset_contact_status():
    import os,json,shutil
    union_path = Global_Config.union_find_json_path
    file_path = Global_Config.old_result_csv_path
    csv_path = os.path.join(file_path,'merge_result.csv')
    default_csv = os.path.join(Global_Config.rule_path,'merge_result.csv')
    # 检查文件是否存在
    if os.path.exists(union_path):
        try:
            with open(union_path, 'w') as f:
                json.dump([], f, ensure_ascii=False, indent=4)
            print("并查集缓存文件内容已清空。")
        except Exception as e:
            print(f"删除并查集文件时发生错误: {e}")
    else:
        print("并查集缓存文件不存在。")

    os.makedirs(Global_Config.result_csv_path, exist_ok=True)
    # 执行复制
    shutil.copy(default_csv, Global_Config.result_csv_path)
    shutil.copy(default_csv, csv_path)
    print("接线状态已重置，请重新开始接线。")


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
            config_module = {
                'Login_Session': Login_Session,
                'Global_Config': Global_Config,
                'reset_session_score': reset_session_score,
                'get_global_score': get_global_score
            }
        except ImportError:
            print("警告: 无法导入global_config模块，将使用模拟配置")

            class MockLoginSession:
                sno = "2024001"
                account_name = "测试学生"

            class MockGlobalConfig:
                student_json = "student_config.json"
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


def get_question_generator():
    global question_generator
    if question_generator is None:
        try:
            from scripts.question_generator import QuestionGenerator
            question_generator = QuestionGenerator()
        except ImportError as e:
            print(f"警告: 无法导入question_generator模块: {e}")
            question_generator = None
    return question_generator


def get_score_visualizer():
    global score_visualizer
    if score_visualizer is None:
        try:
            from scripts.score_visualizer import ScoreVisualizer
            score_visualizer = ScoreVisualizer()
        except ImportError as e:
            print(f"警告: 无法导入score_visualizer模块: {e}")
            score_visualizer = None
    return score_visualizer


app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-here'
socketio = SocketIO(app, cors_allowed_origins="*", transports=['websocket', 'polling'])

# 全局变量
detection_thread = None
detection_running = False
current_score = 0
wiring_results = []
student_info = {
    'student_id': '',
    'student_name': ''
}

detection_thread = None
detector = None


@app.route('/api/start_detection', methods=['POST'])
def start_detection():
    """启动手势检测"""
    global detector, detection_thread
    # 防止重复启动
    if detection_thread and detection_thread.is_alive():
        return jsonify({"success": False, "message": "检测已经在运行"})

    # 启动手势检测
    detector, detection_thread = start_hand_detection()
    return jsonify({"success": True, "message": "手势检测已启动"})


@app.route('/api/stop_detection', methods=['POST'])
def stop_detection():
    """停止手势检测"""
    global detector, detection_thread

    if not detector:
        return jsonify({"success": False, "message": "检测尚未启动"})

    # 停止手势检测
    stop_hand_detection()  # 不需要传入detector
    detection_thread.join()  # 等待线程结束
    detector = None
    return jsonify({"success": True, "message": "手势检测已停止"})


@app.route('/api/get_detection_status', methods=['GET'])
def get_detection_status():
    """获取手势检测状态"""
    if detector:
        status = "running" if detection_thread.is_alive() else "stopped"
        return jsonify({"success": True, "status": status})
    return jsonify({"success": False, "message": "检测未启动"})


@app.route('/')
def index():
    """主页面"""
    # 从URL参数中获取用户信息
    student_id = request.args.get('student_id')
    student_name = request.args.get('student_name')

    # 如果有用户信息，则更新全局配置
    if student_id and student_name:
        config = get_config_module()
        if hasattr(config['Login_Session'], 'sno'):
            config['Login_Session'].sno = student_id
        if hasattr(config['Login_Session'], 'account_name'):
            config['Login_Session'].account_name = student_name

        # 更新全局student_info字典
        global student_info
        student_info = {
            'student_id': student_id,
            'student_name': student_name
        }

        print(f"已更新学生信息: ID={student_id}, 姓名={student_name}")

    return render_template('index.html')


@app.route('/api/student_info', methods=['GET'])
def get_student_info():
    """获取学生信息"""
    config = get_config_module()
    return jsonify({
        'student_id': config['Login_Session'].sno if hasattr(config['Login_Session'], 'sno') else '',
        'student_name': config['Login_Session'].account_name if hasattr(config['Login_Session'], 'account_name') else ''
    })


@app.route('/api/ai_chat', methods=['POST'])
def ai_chat():
    """AI对话接口 - 使用Ollama模型"""
    try:
        import requests

        data = request.get_json()
        question = data.get('question', '').strip()
        ip = data.get('ip', '192.168.1.130')
        port = data.get('port', 11434)
        model_name = data.get('model_name', 'qwen2.5:1.5b')

        if not question:
            return jsonify({'success': False, 'message': '请输入问题'})

        # 组装对话prompt
        prompt = f"""你是一个智能的AI助手，专门帮助学生解答问题。请用友好、专业的态度回答以下问题：

问题：{question}

请提供详细、准确的回答："""

        # 调用Ollama API
        url = f"http://{ip}:{port}/api/generate"
        payload = {
            "model": model_name,
            "prompt": prompt,
            "stream": False
        }

        try:
            response = requests.post(url, json=payload, timeout=60)
            response.raise_for_status()
            result = response.json()

            # 获取生成的回答
            answer = result.get('response', '抱歉，我暂时无法回答这个问题。')

            return jsonify({
                'success': True,
                'answer': answer,
                'timestamp': datetime.now().strftime('%H:%M:%S')
            })

        except requests.exceptions.RequestException as e:
            return jsonify({'success': False, 'message': f'Ollama服务连接失败: {str(e)}'})
        except Exception as e:
            return jsonify({'success': False, 'message': f'Ollama调用失败: {str(e)}'})

    except Exception as e:
        return jsonify({'success': False, 'message': f'AI对话出错: {str(e)}'})


# 新增：题目生成相关路由
@app.route('/api/get_subjects', methods=['GET'])
def get_subjects():
    """获取可用学科列表"""
    try:
        generator = get_question_generator()
        if generator is None:
            return jsonify({'success': False, 'message': '题目生成器未初始化'})

        subjects = generator.get_available_subjects()
        return jsonify({'success': True, 'subjects': subjects})
    except Exception as e:
        return jsonify({'success': False, 'message': f'获取学科列表失败: {str(e)}'})


@app.route('/api/get_topics', methods=['GET'])
def get_topics():
    """根据学科获取知识点列表"""
    try:
        subject = request.args.get('subject', '')
        if not subject:
            return jsonify({'success': False, 'message': '请指定学科'})

        generator = get_question_generator()
        if generator is None:
            return jsonify({'success': False, 'message': '题目生成器未初始化'})

        knowledge_list = generator.get_knowledge_by_subject(subject)
        return jsonify({'success': True, 'topics': knowledge_list})
    except Exception as e:
        return jsonify({'success': False, 'message': f'获取知识点列表失败: {str(e)}'})


@app.route('/api/generate_question', methods=['POST'])
def generate_question():
    """生成题目"""
    try:
        data = request.get_json()
        subject = data.get('subject', '')
        knowledge = data.get('knowledge', '')

        generator = get_question_generator()
        if generator is None:
            return jsonify({'success': False, 'message': '题目生成器未初始化'})

        question = generator.generate_question(
            subject=subject if subject else None,
            knowledge=knowledge if knowledge else None
        )

        if "error" in question:
            return jsonify({'success': False, 'message': question['error']})

        return jsonify({'success': True, 'question': question})
    except Exception as e:
        return jsonify({'success': False, 'message': f'生成题目失败: {str(e)}'})


@app.route('/api/generate_multiple_questions', methods=['POST'])
def generate_multiple_questions():
    """生成多道题目"""
    try:
        data = request.get_json()
        count = data.get('count', 5)
        subject = data.get('subject', '')

        generator = get_question_generator()
        if generator is None:
            return jsonify({'success': False, 'message': '题目生成器未初始化'})

        questions = generator.generate_multiple_questions(
            count=count,
            subject=subject if subject else None
        )

        return jsonify({'success': True, 'questions': questions})
    except Exception as e:
        return jsonify({'success': False, 'message': f'生成题目失败: {str(e)}'})


# 新增：使用Ollama生成题目
@app.route('/api/generate_question_by_ollama', methods=['POST'])
def generate_question_by_ollama():
    """使用Ollama大模型生成题目"""
    try:
        import requests

        data = request.get_json()
        ip = data.get('ip', '127.0.0.1')
        port = data.get('port', 11434)
        model_name = data.get('model_name', 'qwen2.5:1.5b')
        subject_filter = data.get('subject', '电力拖动系统')  # 默认学科为电力拖动系统
        knowledge_filter = data.get('knowledge', '')  # 可选的知识点过滤

        # 如果没有指定知识点，使用默认知识点
        if not knowledge_filter:
            knowledge_filter = '电力拖动系统'

        # 组装prompt - 生成2道选择题+2道填空题+1道简答题
        prompt = f"""请根据以下知识点为电力拖动系统专业学生生成2道选择题、2道填空题和1道简答题：

学科：{subject_filter}
知识点：{knowledge_filter}

请严格按照以下格式生成题目，**不要添加任何额外的分隔符、标记或解释性文字**：

选择题1：
题目：题干内容
A. 选项A
B. 选项B
C. 选项C
D. 选项D
答案：A/B/C/D
解析：详细解析

选择题2：
题目：题干内容
A. 选项A
B. 选项B
C. 选项C
D. 选项D
答案：A/B/C/D
解析：详细解析

填空题1：
题目：题干内容
答案：参考答案
解析：详细解析

填空题2：
题目：题干内容
答案：参考答案
解析：详细解析

简答题：
题目：题干内容
答案：参考答案
解析：详细解析

要求：
1. 题目要专业准确，符合电力拖动系统教学要求
2. 选择题选项要合理，有干扰性
3. 填空题要考察学生对知识点的记忆和理解
4. 简答题要考察学生对知识点的深入理解和应用能力
5. 解析要详细，帮助学生理解知识点
6. **非常重要：不要生成任何额外的分隔符（如###、===等）或装饰性文本，只生成符合上述格式的题目内容**"""

        # 调用Ollama API
        url = f"http://{ip}:{port}/api/generate"
        payload = {
            "model": model_name,
            "prompt": prompt,
            "stream": False
        }

        try:
            response = requests.post(url, json=payload, timeout=60)
            response.raise_for_status()
            result = response.json()

            # 解析返回的题目内容
            generated_text = result.get('response', '')

            # 简单的格式解析
            question_data = {
                'subject': subject_filter,
                'knowledge': knowledge_filter,
                'question': generated_text,
                'raw_response': generated_text
            }

            return jsonify({'success': True, 'question': question_data})

        except requests.exceptions.RequestException as e:
            return jsonify({'success': False, 'message': f'Ollama服务连接失败: {str(e)}'})
        except Exception as e:
            return jsonify({'success': False, 'message': f'Ollama调用失败: {str(e)}'})

    except Exception as e:
        return jsonify({'success': False, 'message': f'生成题目失败: {str(e)}'})


@app.route('/api/test_ollama_connection', methods=['POST'])
def test_ollama_connection():
    """测试Ollama连接"""
    try:
        import requests

        data = request.get_json()
        ip = data.get('ip', '127.0.0.1')
        port = data.get('port', 11434)
        model_name = data.get('model_name', 'qwen2.5:1.5b')

        # 测试连接
        url = f"http://{ip}:{port}/api/tags"
        response = requests.get(url, timeout=10)
        response.raise_for_status()

        # 检查模型是否存在
        models = response.json().get('models', [])
        model_exists = any(model['name'] == model_name for model in models)

        if model_exists:
            return jsonify({'success': True, 'message': '连接成功，模型可用'})
        else:
            return jsonify(
                {'success': False, 'message': f'模型 {model_name} 不存在，可用模型: {[m["name"] for m in models]}'})

    except requests.exceptions.RequestException as e:
        return jsonify({'success': False, 'message': f'连接失败: {str(e)}'})
    except Exception as e:
        return jsonify({'success': False, 'message': f'测试失败: {str(e)}'})


# 新增：数据可视化相关路由
@app.route('/api/get_score_summary', methods=['GET'])
def get_score_summary():
    """获取成绩统计摘要"""
    try:
        visualizer = get_score_visualizer()
        if visualizer is None:
            return jsonify({'success': False, 'message': '数据可视化器未初始化'})

        summary = visualizer.get_score_summary()
        return jsonify({'success': True, 'summary': summary})
    except Exception as e:
        return jsonify({'success': False, 'message': f'获取成绩摘要失败: {str(e)}'})


@app.route('/api/get_score_distribution_plot', methods=['GET'])
def get_score_distribution_plot():
    """获取成绩分布图"""
    try:
        visualizer = get_score_visualizer()
        if visualizer is None:
            return jsonify({'success': False, 'message': '数据可视化器未初始化'})

        plot_data = visualizer.create_score_distribution_plot()
        if not plot_data:
            return jsonify({'success': False, 'message': '无法生成分布图'})

        return jsonify({'success': True, 'plot_data': plot_data})
    except Exception as e:
        return jsonify({'success': False, 'message': f'生成分布图失败: {str(e)}'})


@app.route('/api/get_knowledge_analysis_plot', methods=['GET'])
def get_knowledge_analysis_plot():
    """获取知识点分析图"""
    try:
        visualizer = get_score_visualizer()
        if visualizer is None:
            return jsonify({'success': False, 'message': '数据可视化器未初始化'})

        plot_data = visualizer.create_knowledge_analysis_plot()
        if not plot_data:
            return jsonify({'success': False, 'message': '无法生成知识点分析图'})

        return jsonify({'success': True, 'plot_data': plot_data})
    except Exception as e:
        return jsonify({'success': False, 'message': f'生成知识点分析图失败: {str(e)}'})


@app.route('/api/get_student_knowledge_heatmap', methods=['GET'])
def get_student_knowledge_heatmap():
    """获取学生-知识点热力图"""
    try:
        visualizer = get_score_visualizer()
        if visualizer is None:
            return jsonify({'success': False, 'message': '数据可视化器未初始化'})

        plot_data = visualizer.create_student_knowledge_heatmap()
        if not plot_data:
            return jsonify({'success': False, 'message': '无法生成热力图'})

        return jsonify({'success': True, 'plot_data': plot_data})
    except Exception as e:
        return jsonify({'success': False, 'message': f'生成热力图失败: {str(e)}'})


@app.route('/api/get_score_knowledge_correlation', methods=['GET'])
def get_score_knowledge_correlation():
    """获取成绩与知识点相关性分析"""
    try:
        visualizer = get_score_visualizer()
        if visualizer is None:
            return jsonify({'success': False, 'message': '数据可视化器未初始化'})

        plot_data = visualizer.create_score_knowledge_correlation()
        if not plot_data:
            return jsonify({'success': False, 'message': '无法生成相关性分析图'})

        return jsonify({'success': True, 'plot_data': plot_data})
    except Exception as e:
        return jsonify({'success': False, 'message': f'生成相关性分析图失败: {str(e)}'})


@app.route('/api/get_top_students', methods=['GET'])
def get_top_students():
    """获取前N名学生信息"""
    try:
        top_n = request.args.get('top_n', 5, type=int)
        visualizer = get_score_visualizer()
        if visualizer is None:
            return jsonify({'success': False, 'message': '数据可视化器未初始化'})

        top_students = visualizer.get_top_students(top_n)
        return jsonify({'success': True, 'top_students': top_students})
    except Exception as e:
        return jsonify({'success': False, 'message': f'获取学生信息失败: {str(e)}'})


@app.route('/api/get_knowledge_analysis', methods=['GET'])
def get_knowledge_analysis():
    """获取知识点分析数据"""
    try:
        visualizer = get_score_visualizer()
        if visualizer is None:
            return jsonify({'success': False, 'message': '数据可视化器未初始化'})

        analysis_data = visualizer.get_knowledge_analysis()
        return jsonify({'success': True, 'analysis': analysis_data})
    except Exception as e:
        return jsonify({'success': False, 'message': f'获取知识点分析失败: {str(e)}'})


@app.route('/api/get_knowledge_list', methods=['GET'])
def get_knowledge_list():
    """获取所有知识点列表"""
    try:
        # 直接返回用户提供的知识点列表
        knowledge_list = [
            '电力拖动系统', '负载转矩', '电磁转矩', '机械特性', '固有机械特性', '人为机械特性',
            '启动', '直接启动', '降压启动', '星 - 三角启动', '自耦变压器降压启动', '软启动',
            '调速', '无级调速', '有级调速', '变极调速', '变频调速', '变转差率调速', '串级调速',
            '制动', '能耗制动', '反接制动', '回馈制动', '直流电动机拖动', '交流异步电动机拖动',
            '交流同步电动机拖动', '伺服拖动系统', '步进电动机拖动', '拖动系统稳定性', '电机选型',
            '传动比', '飞轮矩', '动态响应', '静态转速降', '调速范围', '稳速精度', '电枢回路',
            '励磁回路', '变压调速（直流）', '弱磁调速（直流）', 'V/F 控制', '矢量控制',
            '直接转矩控制（DTC）', '负载特性', '恒转矩负载', '恒功率负载', '通风机类负载',
            '启动转矩', '最大转矩', '转差率', '同步转速', '额定转速', '过载能力', '启动电流',
            '制动电阻', '调速装置', '变频器', '伺服驱动器', '电枢电阻调速', '电磁制动',
            '机械制动', '拖动系统效率', '动态调速性能', '静态调速性能', '电机正反转控制',
            '拖动系统建模', '仿真分析', '实际运行调试', '负载匹配', '节能控制'
        ]
        return jsonify({'success': True, 'knowledge_list': knowledge_list})
    except Exception as e:
        return jsonify({'success': False, 'message': f'获取知识点列表失败: {str(e)}'})


@app.route('/api/get_air_switch_status', methods=['GET'])
def get_air_switch_status():
    air_switch_status = {
        "airSwitchClosed": global_config.Global_Config.switch_status,
        "errorWiringCount": global_config.Global_Config.error_wiring_count
    }
    return jsonify(air_switch_status)


@app.route('/api/get_score_and_contact', methods=['GET'])
def get_score_and_contact():
    score_wired_status = {
        "score": Global_Config.total_score,
        "contact_A": Global_Config.current_A,
        "contact_B": Global_Config.current_B,
        "wired_status": Global_Config.wired_status
    }
    return jsonify(score_wired_status)


@app.route('/api/get_wiring_status', methods=['GET'])
def get_wiring_status():
    """获取完整的接线情况数据"""
    try:
        from global_config import Global_Config

        # 获取最新的接线结果
        latest_contacts = []
        if Global_Config.current_A is not None and Global_Config.current_B is not None:
            latest_contacts = [Global_Config.current_A, Global_Config.current_B]

        # 获取所有接线结果历史
        wiring_results = []
        for result in Global_Config.wiring_results:
            wiring_results.append({
                'id': len(wiring_results) + 1,
                'end1': result['end1'],
                'end2': result['end2'],
                'score': result['score'],
                'timestamp': result['timestamp']
            })

        return jsonify({
            'success': True,
            'airSwitchClosed': Global_Config.switch_status,
            'errorWiringCount': Global_Config.error_wiring_count,
            'currentContacts': latest_contacts,
            'wiringResults': wiring_results,
            'totalScore': Global_Config.total_score
        })
    except Exception as e:
        return jsonify({'success': False, 'message': f'获取接线情况失败: {str(e)}'})


# 新的学生成绩可视化API
@app.route('/api/student/exams', methods=['GET'])
def get_student_exams():
    """获取学生参加过的所有考试"""
    try:
        # 获取当前登录学生的学号
        config = get_config_module()
        student_no = config['Login_Session'].sno

        if not student_no:
            return jsonify({'success': False, 'message': '未获取到学生学号'})

        # 连接数据库查询学生参加过的考试
        connector = MySQLConnector()
        sql = "SELECT DISTINCT test_id, test_name FROM exam_result WHERE student_no = %s ORDER BY test_id"
        results = connector.query(sql, (student_no,))

        # 格式化结果
        exams = []
        for row in results:
            exams.append({
                'test_id': row[0],
                'test_name': row[1]
            })

        return jsonify({'success': True, 'exams': exams})
    except Exception as e:
        return jsonify({'success': False, 'message': f'获取考试列表失败: {str(e)}'})


@app.route('/api/student/score', methods=['GET'])
def get_student_score():
    """获取学生的成绩详情"""
    try:
        # 获取当前登录学生的学号
        config = get_config_module()
        student_no = config['Login_Session'].sno

        if not student_no:
            return jsonify({'success': False, 'message': '未获取到学生学号'})

        # 连接数据库查询学生成绩
        connector = MySQLConnector()
        sql = "SELECT test_id, test_name, test_score FROM exam_result WHERE student_no = %s ORDER BY test_id"
        results = connector.query(sql, (student_no,))

        # 格式化结果
        scores = []
        for row in results:
            scores.append({
                'test_id': row[0],
                'test_name': row[1],
                'score': int(row[2])
            })

        return jsonify({'success': True, 'scores': scores})
    except Exception as e:
        return jsonify({'success': False, 'message': f'获取成绩详情失败: {str(e)}'})


@app.route('/api/student/knowledge', methods=['GET'])
def get_student_knowledge():
    """获取学生的易错知识点"""
    try:
        # 获取当前登录学生的学号
        config = get_config_module()
        student_no = config['Login_Session'].sno

        if not student_no:
            return jsonify({'success': False, 'message': '未获取到学生学号'})

        # 连接数据库查询学生易错知识点
        connector = MySQLConnector()
        sql = "SELECT knowledge FROM exam_result WHERE student_no = %s AND knowledge IS NOT NULL AND knowledge != ''"
        results = connector.query(sql, (student_no,))

        # 统计知识点出现频率
        knowledge_count = {}
        for row in results:
            # 分割知识点（如果有多个）
            knowledge_list = row[0].split('，')
            for knowledge in knowledge_list:
                knowledge = knowledge.strip()
                if knowledge:
                    knowledge_count[knowledge] = knowledge_count.get(knowledge, 0) + 1

        # 转换为列表格式
        knowledge_list = [{'name': k, 'count': v} for k, v in knowledge_count.items()]
        # 按出现次数排序
        knowledge_list.sort(key=lambda x: x['count'], reverse=True)

        return jsonify({'success': True, 'knowledge': knowledge_list})
    except Exception as e:
        return jsonify({'success': False, 'message': f'获取易错知识点失败: {str(e)}'})


@app.route('/api/get_current_score', methods=['GET'])
def get_current_score():
    """获取当前实时分数"""
    try:
        from global_config import Global_Config
        return jsonify({
            'success': True,
            'score': Global_Config.total_score
        })
    except Exception as e:
        return jsonify({'success': False, 'message': f'获取当前分数失败: {str(e)}'})


@app.route('/api/test_score_update', methods=['POST'])
def test_score_update():
    """测试更新分数"""
    try:
        # 调用match_subgraphs函数来测试分数更新
        matched_results = match_subgraphs()
        
        # 构建响应
        response = {
            "success": True,
            "message": "分数已更新",
            "matched_results": matched_results
        }
        return jsonify(response)
    except Exception as e:
        print(f"测试更新分数时出错: {e}")
        return jsonify({"success": False, "message": f"测试更新分数时出错: {e}"})

@app.route('/api/test_set_contact', methods=['GET', 'POST'])
def test_set_contact():
    """测试设置接线触点和分数"""
    try:
        from global_config import Global_Config
        
        # 设置模拟的接线触点和分数
        Global_Config.current_A = 'A1'
        Global_Config.current_B = 'B1'
        Global_Config.total_score = 10
        
        # 构建响应
        response = {
            "success": True,
            "message": "模拟接线情况设置完成",
            "contact_A": Global_Config.current_A,
            "contact_B": Global_Config.current_B,
            "score": Global_Config.total_score
        }
        return jsonify(response)
    except Exception as e:
        print(f"测试设置接线触点和分数时出错: {e}")
        return jsonify({"success": False, "message": f"测试设置接线触点和分数时出错: {e}"})

@app.route('/api/test_wired_status', methods=['GET'])
def test_wired_status():
    """测试不同的wired_status值"""
    try:
        from global_config import Global_Config
        
        # 获取请求参数
        wired_status = request.args.get('status', 'add')  # 默认值为'add'
        contact_A = request.args.get('contact_a', 'A' + str(int(time.time()) % 10))  # 随机A触点
        contact_B = request.args.get('contact_b', 'B' + str(int(time.time()) % 10))  # 随机B触点
        score = int(request.args.get('score', 10))  # 默认分数10
        
        # 设置全局变量
        Global_Config.current_A = contact_A
        Global_Config.current_B = contact_B
        # 根据不同的wired_status处理分数
        if wired_status == 'add' and score != 0:
            Global_Config.total_score += score  # 累加分数
        else:
            Global_Config.total_score = score  # 其他情况或分数为0时直接设置分数
        Global_Config.wired_status = wired_status
        
        # 构建响应，与get_score_and_contact接口返回相同的结构
        response = {
            "score": Global_Config.total_score,
            "contact_A": Global_Config.current_A,
            "contact_B": Global_Config.current_B,
            "wired_status": Global_Config.wired_status
        }
        return jsonify(response)
    except Exception as e:
        print(f"测试设置接线触点时出错: {e}")
        return jsonify({"success": False, "message": f"测试设置接线触点时出错: {e}"})


if __name__ == '__main__':
    # 启动模拟线程
    reset_contact_status()
    print("? 启动Web服务器...")
    print("? 请在浏览器中访问: http://localhost:8088")
    print("=" * 50)

    # 启动Flask应用
    try:
        socketio.run(app, host='127.0.0.1', port=8088, debug=False)  # 关闭debug模式提高性能
    except Exception as e:
        print(f"? 启动失败: {e}")
        print("请检查端口8088是否被占用")