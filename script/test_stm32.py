import tkinter as tk
from tkinter import ttk
from serial_tools import STM32Tool
from calculate_score_total import evaluate_pairs
from deal_StmResult import generate_by_name_json
from global_config import Global_Config
stm32_tool = STM32Tool(port='COM4')

class DetectUI(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("检测控制面板")
        self.geometry("360x200")
        self.resizable(False, False)

        self._build_ui()

    def _build_ui(self):
        container = ttk.Frame(self, padding=16)
        container.pack(fill="both", expand=True)

        title = ttk.Label(container, text="电路检测控制", font=("Microsoft YaHei UI", 14))
        title.pack(pady=(0, 12))

        btn_frame = ttk.Frame(container)
        btn_frame.pack(fill="x")

        self.btn_start = ttk.Button(btn_frame, text="开始检测", command=self.on_start_detect)
        self.btn_read = ttk.Button(btn_frame, text="读取结果", command=self.on_read_result)
        self.btn_stop = ttk.Button(btn_frame, text="关闭检测", command=self.on_close_detect)

        # 让按钮纵向排列、宽度一致
        for btn in (self.btn_start, self.btn_read, self.btn_stop):
            btn.pack(fill="x", pady=6)

        self.status_var = tk.StringVar(value="状态：就绪")
        status = ttk.Label(container, textvariable=self.status_var)
        status.pack(pady=(12, 0), anchor="w")

    # ===== 按钮绑定函数（留空，你自行补充逻辑） =====
    def on_start_detect(self):
        """开始检测：TODO 在这里写你的逻辑"""
        stm32_tool.start_detection_mode()

    def on_read_result(self):
        """读取结果：TODO 在这里写你的逻辑"""
        result = stm32_tool.query_and_parse()
        print(result)
        generate_by_name_json(result, Global_Config.label_csv, Global_Config.new_result_json)
        score = evaluate_pairs(Global_Config.new_result_json, Global_Config.test_rule)
        print(score)
    def on_close_detect(self):
        """关闭检测：TODO 在这里写你的逻辑"""
        stm32_tool.stop_detection_mode()



if __name__ == "__main__":
    app = DetectUI()
    app.mainloop()
