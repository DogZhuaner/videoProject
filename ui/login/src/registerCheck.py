import logging
import hashlib
import re

from global_config import Login_Session
from tools.connector import MySQLConnector

# 配置日志
logger = logging.getLogger('LoginCheck')

# 全局数据库管理器实例
_db_manager_instance = None

def get_db_manager():
    """获取数据库管理器实例"""
    global _db_manager_instance
    if _db_manager_instance is None:
        _db_manager_instance = loginCheck()
    return _db_manager_instance


class loginCheck:
    def __init__(self):
        try:
            self.db = MySQLConnector()
        except Exception as e:
            logger.error(f"初始化数据库连接失败: {e}")
            self.db = None

    def hash_password(self, password):
        """对密码进行哈希加密"""
        return hashlib.sha256(password.encode()).hexdigest()

    def verify_user(self, username, password, identity):
        """
        验证用户登录信息
        返回: (success, user_info, message)
        """
        try:
            # 检查数据库连接
            if self.db is None:
                self.db = MySQLConnector()
                if self.db is None:
                    raise Exception("无法初始化数据库连接")

            # 根据身份选择不同的查询逻辑
            if identity == 'student':
                # 学生登录逻辑 - 使用student表，sno和student_password列
                sql = "SELECT sno, student_password FROM student WHERE sno = %s"
                logger.info(f"执行学生登录查询: {sql}, 参数: {username}")
                results = self.db.query(sql, (username,))

                if not results:
                    return False, None, "学号不存在"

                user_data = results[0]
                stored_password = user_data[1]

                # 验证密码
                if password == stored_password:
                    user_info = {
                        'id': user_data[0],
                        'username': user_data[0],  # 使用学号作为用户名
                        'identity': 'student'
                    }
                    # 设置会话信息
                    Login_Session.user_id = user_data[0]
                    Login_Session.username = user_data[0]
                    Login_Session.account_name = user_data[0]  # 可以根据实际情况设置
                    Login_Session.sno = int(user_data[0])
                    return True, user_info, "登录成功"
                else:
                    return False, None, "密码错误"
            else:
                # 教师登录逻辑 - 使用teacher表，tno和teacher_password列
                sql = "SELECT tno, teacher_password, name FROM teacher WHERE tno = %s"
                logger.info(f"执行教师登录查询: {sql}, 参数: {username}")
                results = self.db.query(sql, (username,))

                if not results:
                    return False, None, "教师账号不存在"

                user_data = results[0]
                stored_password = user_data[1]

                # 验证密码
                # 注意：这里数据库中存储的是明文密码
                if password == stored_password:
                    user_info = {
                        'id': user_data[0],
                        'username': user_data[0],  # 使用工号作为用户名
                        'name': user_data[2],  # 教师姓名
                        'identity': 'teacher'
                    }
                    # 设置会话信息
                    Login_Session.user_id = user_data[0]
                    Login_Session.username = user_data[0]
                    Login_Session.account_name = user_data[2]  # 使用教师姓名
                    return True, user_info, "登录成功"
                else:
                    return False, None, "教师账号或密码错误"

        except Exception as e:
            logger.error(f"数据库查询错误：{e}")
            return False, None, "系统错误，请稍后重试"
        finally:
            # 确保关闭数据库连接
            if hasattr(self, 'db') and self.db:
                try:
                    self.db.close()
                except Exception as e:
                    logger.error(f"关闭数据库连接失败: {e}")

    def verify_approving_teacher(self, teacher_id):
        """
        验证审批教师是否存在
        去数据库的teacher表中查看用户注册提交的user_approve和teacher表中的teacher_id是否有匹配项
        返回: (success, message)
        """
        try:
            # 检查数据库连接
            if self.db is None:
                self.db = MySQLConnector()
                if self.db is None:
                    raise Exception("无法初始化数据库连接")

            # 查询教师表，检查教师ID是否存在
            sql = "SELECT tno FROM teacher WHERE tno = %s"
            logger.info(f"执行审批教师验证查询: {sql}, 参数: {teacher_id}")
            results = self.db.query(sql, (teacher_id,))

            if results:
                # 教师账号存在
                return True, "审批教师验证成功"
            else:
                # 教师账号不存在
                return False, "审批者工号不存在或不是有效的教师账号"

        except Exception as e:
            logger.error(f"审批教师验证错误：{e}")
            return False, "系统错误，请稍后重试"
        finally:
            # 确保关闭数据库连接
            if hasattr(self, 'db') and self.db:
                try:
                    self.db.close()
                except Exception as e:
                    logger.error(f"关闭数据库连接失败: {e}")

    def register_user(self, user_id, password, user_type, user_name, user_approve):
        """
        注册新用户
        返回: (success, message)
        """
        try:
            # 检查数据库连接
            if self.db is None:
                self.db = MySQLConnector()
                if self.db is None:
                    raise Exception("无法初始化数据库连接")

            # 检查用户是否已存在
            check_sql = "SELECT user_id FROM register WHERE user_id = %s"
            existing_user = self.db.query(check_sql, (user_id,))

            if existing_user:
                return False, "用户已存在"


            # 创建新用户，将数据插入到register表
            insert_sql = "INSERT INTO register (user_id, user_name, user_password, user_type, user_approve) VALUES (%s, %s, %s, %s, %s)"
            self.db.execute(insert_sql, (user_id, user_name, password, user_type, user_approve))

            return True, "注册成功"
        except Exception as e:
            logger.error(f"用户注册错误：{e}")
            return False, "注册失败，请稍后重试"
        finally:
            # 确保关闭数据库连接
            if hasattr(self, 'db') and self.db:
                try:
                    self.db.close()
                except Exception as e:
                    logger.error(f"关闭数据库连接失败: {e}")