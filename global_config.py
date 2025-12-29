from pathlib import Path

class Global_Config:
    ProjectRoot = Path(__file__).resolve().parent
    #image
    selectSwitchArea = str(ProjectRoot/'image'/'fullscreen.jpg')
    live_capture_path = str(ProjectRoot/'image'/'live_capture.png')
    history_capture_dir = str(ProjectRoot/ 'image' / 'Hand_capture')
    #data
    rule_path = ProjectRoot/'data'/'rules'
    test_rule = ProjectRoot/'data'/'rules'/'长动.json'
    union_find_json_path = ProjectRoot/'data'/'union_find.json'
    rule_csv_path = ProjectRoot/'data'/'rule.csv'
    label_csv = str(ProjectRoot/'data'/'label.csv')
    new_result_json = ProjectRoot / 'data' / 'result' / 'new'/ "result.json"
    old_result_json = ProjectRoot / 'data' / 'result' / 'old'/ "result.json"
    #weights
    Hand_and_switch = ProjectRoot/'weights'/'hand_and_switch.pt'

    # rule server
    rule_server_ip = '127.0.0.1'  # 默认教师端IP
    rule_server_port = 8000       # 默认端口号

    switch_status = True
    error_wiring_count = 0

    # 全局分数管理
    flag=0        #判断标志
    total_score = 0   # 总分
    current_session_score = 0     # 当前会话得分
    wired_status = ""
    current_A = ""     #当前触点A
    current_B = ""     #当前触点B
    wiring_results = []           # 接线结果历史
    score_history = []            # 分数历史记录
    is_first_score = False

class Login_Session:
    user_id = ''
    username = ''
    account_name = ''
    sno = ''

# 分数管理函数
def reset_global_score():
    """重置全局分数 - 每次启动程序时调用"""
    Global_Config.total_score = 0
    Global_Config.current_session_score = 0
    Global_Config.wiring_results = []
    Global_Config.score_history = []
    print("全局分数已重置为0")

def add_global_score(score):
    """添加分数到全局总分"""
    Global_Config.total_score += score
    Global_Config.current_session_score += score
    print(f"全局分数更新: +{score}分, 当前总分: {Global_Config.total_score}分")
    return Global_Config.total_score

def get_global_score():
    """获取全局总分"""
    return Global_Config.total_score

def get_current_session_score():
    """获取当前会话得分"""
    return Global_Config.current_session_score

def add_wiring_result(end1, end2, score):
    """添加接线结果到全局记录"""
    import time
    result = {
        'end1': end1,
        'end2': end2,
        'score': score,
        'timestamp': time.time()
    }
    Global_Config.wiring_results.append(result)
    return result

def get_wiring_results():
    """获取所有接线结果"""
    return Global_Config.wiring_results.copy()

def save_session_to_history():
    """保存当前会话到历史记录"""
    import time
    if Global_Config.current_session_score > 0:
        session_record = {
            'score': Global_Config.current_session_score,
            'wiring_results': Global_Config.wiring_results.copy(),
            'timestamp': time.time()
        }
        Global_Config.score_history.append(session_record)
        print(f"会话已保存到历史记录: {Global_Config.current_session_score}分")
    return Global_Config.score_history


