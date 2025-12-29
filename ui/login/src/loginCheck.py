# auth_service.py

import hashlib
import logging

from global_config import Login_Session
from tools.connector import MySQLConnector

# 配置日志
logger = logging.getLogger('LoginCheck')


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
                # 学生登录逻辑 - 使用student表，包含name字段
                sql = "SELECT sno, student_password, name FROM student WHERE sno = %s"
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
                        'identity': 'student',
                        'name': user_data[2]  # 包含姓名信息
                    }
                    # 设置会话信息
                    Login_Session.user_id = user_data[0]
                    Login_Session.username = user_data[0]
                    Login_Session.account_name = user_data[2]  # 设置为真实姓名
                    Login_Session.sno = int(user_data[0])
                    return True, user_info, "登录成功"
                else:
                    return False, None, "密码错误"
            else:
                # 教师登录逻辑 - 使用teacher表，包含name字段
                sql = "SELECT tno, teacher_password, name FROM teacher WHERE tno = %s"
                logger.info(f"执行教师登录查询: {sql}, 参数: {username}")
                results = self.db.query(sql, (username,))

                if not results:
                    return False, None, "教师账号不存在"

                user_data = results[0]
                stored_password = user_data[1]

                # 验证密码
                if password == stored_password:
                    user_info = {
                        'id': user_data[0],
                        'username': user_data[0],  # 使用教师ID作为用户名
                        'identity': 'teacher',
                        'name': user_data[2]  # 包含姓名信息
                    }
                    # 设置会话信息
                    Login_Session.user_id = user_data[0]
                    Login_Session.username = user_data[0]
                    Login_Session.account_name = user_data[2]  # 设置为真实姓名
                    return True, user_info, "登录成功"
                else:
                    return False, None, "密码错误"

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

    def register_user(self, user_id, password, user_type, user_name, user_approve):
        try:
            if self.db is None:
                self.db = MySQLConnector()
                if self.db is None:
                    raise Exception("Failed to initialize database connection")

            check_sql = "SELECT user_id FROM register WHERE user_id = %s"
            existing_user = self.db.query(check_sql, (user_id,))

            if existing_user:
                return False, "User already exists"

            insert_sql = "INSERT INTO register (user_id, user_name, user_password, user_type, user_approve) VALUES (%s, %s, %s, %s, %s)"
            self.db.execute(insert_sql, (user_id, user_name, password, user_type, user_approve))

            return True, "Registration successful"
        except Exception as e:
            logger.error(f"User registration error: {e}")
            return False, "Registration failed, please try again later"
        finally:
            if hasattr(self, 'db') and self.db:
                try:
                    self.db.close()
                except Exception as e:
                    logger.error(f"Failed to close database connection: {e}")
    def verify_approving_teacher(self, teacher_id):
        try:
            if self.db is None:
                self.db = MySQLConnector()
                if self.db is None:
                    raise Exception("Failed to initialize database connection")

            sql = "SELECT tno FROM teacher WHERE tno = %s"
            results = self.db.query(sql, (teacher_id,))

            if results:
                return True, "Approving teacher verification successful"
            else:
                return False, "Approving teacher ID not found or invalid"

        except Exception as e:
            logger.error(f"Approving teacher verification error: {e}")
            return False, "System error, please try again later"
        finally:
            if hasattr(self, 'db') and self.db:
                try:
                    self.db.close()
                except Exception as e:
                    logger.error(f"Failed to close database connection: {e}")

    def verify_face_id(self, face_id):
        """
        验证人脸ID
        返回: (success, user_info, message)
        """
        try:
            # 检查数据库连接
            if self.db is None:
                self.db = MySQLConnector()
                if self.db is None:
                    raise Exception("无法初始化数据库连接")

            # 实际应用中应该有一个人脸数据表，这里只是一个临时实现
            # 假设face_id的格式为 "student_face_123" 或 "teacher_face_123"
            # 其中123是学号或教师ID

            # 解析face_id，提取身份和ID信息
            parts = face_id.split('_')
            if len(parts) < 3:
                return False, None, "无效的人脸ID格式"

            identity = parts[0]  # student或teacher
            if identity not in ['student', 'teacher']:
                return False, None, "无效的身份类型"

            # 尝试从face_id中提取用户ID
            user_id_part = face_id.replace(f"{identity}_face_", "")

            if identity == 'student':
                # 学生人脸验证逻辑
                # 假设face_id中的最后部分是学号的一部分或完整学号
                # 这里需要根据实际的人脸数据表结构修改
                sql = "SELECT student_id, student_password, name FROM student WHERE student_id LIKE %s"
                logger.info(f"执行学生人脸验证查询: {sql}, 参数: %{user_id_part}%")
                results = self.db.query(sql, (f"%{user_id_part}%",))

                if not results:
                    return False, None, "未找到匹配的学生信息"

                # 如果找到多个匹配，取第一个
                user_data = results[0]
                user_info = {
                    'id': user_data[0],
                    'username': user_data[0],  # 使用学号作为用户名
                    'identity': 'student',
                    'face_id': face_id,
                    'name': user_data[2]  # 包含姓名信息
                }
                return True, user_info, "人脸识别验证成功"
            else:
                # 教师人脸验证逻辑
                # 使用teacher表，根据face_id匹配教师信息
                # 实际应用中应该有一个人脸数据表关联face_id和teacher_id
                # 这里假设face_id中的最后部分与教师ID相关
                sql = "SELECT teacher_id, teacher_password, name FROM teacher WHERE teacher_id LIKE %s"
                logger.info(f"执行教师人脸验证查询: {sql}, 参数: %{user_id_part}%")
                results = self.db.query(sql, (f"%{user_id_part}%",))

                if not results:
                    return False, None, "未找到匹配的教师信息"

                # 如果找到多个匹配，取第一个
                user_data = results[0]
                user_info = {
                    'id': user_data[0],
                    'username': user_data[0],  # 使用教师ID作为用户名
                    'identity': 'teacher',
                    'face_id': face_id,
                    'name': user_data[2]  # 包含姓名信息
                }
                return True, user_info, "人脸识别验证成功"

        except Exception as e:
            logger.error(f"人脸验证错误：{e}")
            return False, None, "系统错误，请稍后重试"
        finally:
            # 确保关闭数据库连接
            if hasattr(self, 'db') and self.db:
                try:
                    self.db.close()
                except Exception as e:
                    logger.error(f"关闭数据库连接失败: {e}")