# connector.py

import mysql.connector
from mysql.connector import Error
from tools.config import DB_CONFIG


class MySQLConnector:
    def __init__(self, config=DB_CONFIG):
        self.config = config
        self.connection = None

    def connect(self):
        try:
            self.connection = mysql.connector.connect(**self.config)
            if self.connection.is_connected():
                print("✅ 数据库连接成功")
        except Error as e:
            print(f"❌ 数据库连接失败：{e}")
            self.connection = None

    def query(self, sql, params=None):
        """
        执行 SELECT 查询
        """
        cursor = None
        try:
            if self.connection is None or not self.connection.is_connected():
                self.connect()

            if self.connection is None or not self.connection.is_connected():
                print("❌ 数据库未连接，无法执行查询")
                return []

            cursor = self.connection.cursor()
            cursor.execute(sql, params or ())
            results = cursor.fetchall()
            return results
        except Error as e:
            print(f"❌ 查询出错：{e}")
            return []
        finally:
            if cursor:
                try:
                    cursor.close()
                except Exception as e:
                    print(f"❌ 关闭游标失败：{e}")

    def execute(self, sql, params=None):
        """
        执行 INSERT、UPDATE、DELETE 操作
        """
        cursor = None
        try:
            if self.connection is None or not self.connection.is_connected():
                self.connect()

            if self.connection is None or not self.connection.is_connected():
                print("❌ 数据库未连接，无法执行操作")
                return False

            cursor = self.connection.cursor()
            cursor.execute(sql, params or ())
            self.connection.commit()
            print("✅ SQL 执行成功")
            return True
        except Error as e:
            print(f"❌ SQL 执行失败：{e}")
            # 尝试回滚事务
            try:
                if self.connection and self.connection.is_connected():
                    self.connection.rollback()
            except Exception as rollback_error:
                print(f"❌ 事务回滚失败：{rollback_error}")
            return False
        finally:
            if cursor:
                try:
                    cursor.close()
                except Exception as e:
                    print(f"❌ 关闭游标失败：{e}")

    def close(self):
        if self.connection and self.connection.is_connected():
            try:
                self.connection.close()
                print("🔌 数据库连接已关闭")
            except Exception as e:
                print(f"❌ 关闭数据库连接失败：{e}")
if __name__ == '__main__':
    connector = MySQLConnector()
    connector.connect()