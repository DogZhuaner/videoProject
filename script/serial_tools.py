import serial
import time

class STM32Tool:
    def __init__(self, port='COM4', baudrate=38400, timeout=3):
        # 初始化串口设置
        self.port = port
        self.baudrate = baudrate
        self.timeout = timeout

    def open_serial_connection(self):
        """打开串口连接"""
        self.ser = serial.Serial(self.port, self.baudrate, timeout=self.timeout)
        self.ser.setRTS(True)  # 设置RTS为True
        self.ser.setDTR(False)  # 设置DTR为False

    def close_serial_connection(self):
        """关闭串口连接"""
        if self.ser:
            self.ser.close()

    def start_detection_mode(self):
        """向STM32发送指令开启检测模式"""
        self.open_serial_connection()  # 打开串口连接
        command = bytearray([0xF1, 0xF2, 0x02, 0x01, 0x01, 0xF3, 0xF4])
        self.ser.write(command)  # 发送数据
        print("Command sent to STM32 to start detection mode.")
        time.sleep(3)  # 给 STM32 一些时间来响应

        # 检查是否收到开启成功的返回
        if self.ser.in_waiting > 0:
            data = self.ser.read(8)  # 读取返回的8字节数据
            print(f"Received data: {data.hex()}")
            if data == bytearray([0xF5, 0xF6, 0x02, 0x01, 0x01, 0xF7, 0xF8]):
                print("Detection mode started successfully.")
                self.close_serial_connection()  # 关闭串口连接
                return True
            else:
                print("Failed to start detection mode.")
                self.close_serial_connection()  # 关闭串口连接
                return False
        else:
            print("No data received from STM32.")
            self.close_serial_connection()  # 关闭串口连接
            return False

    def stop_detection_mode(self):
        """向STM32发送指令关闭检测模式"""
        self.open_serial_connection()  # 打开串口连接
        command = bytearray([0xF1, 0xF2, 0x03, 0x01, 0x01, 0xF3, 0xF4])
        self.ser.write(command)  # 发送数据
        print("Command sent to STM32 to stop detection mode.")
        time.sleep(2)  # 给 STM32 一些时间来响应

        # 检查是否收到关闭成功的返回
        if self.ser.in_waiting > 0:
            data = self.ser.read(8)  # 读取返回的8字节数据
            print(f"Received data: {data.hex()}")
            if data == bytearray([0xF5, 0xF6, 0x02, 0x01, 0x01, 0xF7, 0xF8]):
                print("Detection mode stopped successfully.")
                self.close_serial_connection()  # 关闭串口连接
                return True
            else:
                print("Failed to stop detection mode.")
                self.close_serial_connection()  # 关闭串口连接
                return False
        else:
            print("No data received from STM32.")
            self.close_serial_connection()  # 关闭串口连接
            return False

    def query_and_parse(self):
        """向STM32发送查询指令并解析返回的数据"""
        self.open_serial_connection()  # 打开串口连接
        command = bytearray([0xF1, 0xF2, 0x01, 0x01, 0x01, 0xF3, 0xF4])
        self.ser.write(command)  # 发送数据
        print("Command sent to STM32 for querying.")
        time.sleep(2)  # 给 STM32 一些时间来响应

        # 检查是否有数据返回
        if self.ser.in_waiting > 0:
            # 读取 STM32 返回的 5007 字节数据
            data = self.ser.read(5007)
            print(f"Received data: {len(data)} bytes")

            # 去除前3个字节头标记和后4个字节尾标记
            data = data[3:-4]

            # 检查数据长度是否与预期的矩阵大小匹配
            expected_data_length = 200 * 200 // 8  # 200×200 矩阵，每个字节表示 8 个管脚的状态
            if len(data) != expected_data_length:
                print("Error: Data length does not match expected length.")
                self.close_serial_connection()  # 关闭串口连接
                return []

            # 解析数据为200x200矩阵
            rows = 200
            cols = 200
            matrix = []

            # 每个字节代表8个管脚的状态
            for i in range(rows):
                row = []
                for j in range(cols // 8):  # 每8个bit代表一列
                    byte_data = data[i * (cols // 8) + j]
                    row.extend([((byte_data >> bit) & 1) for bit in range(7, -1, -1)])  # 按位解析
                matrix.append(row)

            # 查找值为1的位置并返回行列号列表，只输出 i < j 的位置
            connections = []
            for i in range(rows):
                for j in range(i + 1, cols):  # 只遍历上三角部分
                    if matrix[i][j] == 1:
                        connections.append((i + 1, j + 1))  # 输出行列号，i+1 和 j+1 使其从 1 开始
            self.close_serial_connection()  # 关闭串口连接
            return connections
        else:
            print("No data received from STM32.")
            self.close_serial_connection()  # 关闭串口连接
            return []
