# -*- coding: utf-8 -*-
"""
YOLO 标注质量检查工具 - Tkinter 图形界面版

功能：
1. 手动选择 YOLO 权重文件、图片文件、标注 txt 文件。
2. 使用权重对图片进行检测，将：
   - 标注信息（txt）
   - 模型预测信息（YOLO）
   在界面左右两栏进行对比展示。
3. 根据检测结果对标注质量进行打分（满分 100 分），
   漏标、错标、过大、过小、位置偏差都会扣分，结果中文输出。
"""

import os
import json
from typing import List, Tuple, Dict

from PIL import Image  # 用于读取图片尺寸
from ultralytics import YOLO  # YOLO 检测：pip install ultralytics

import tkinter as tk
from tkinter import filedialog, messagebox, ttk


# ========================
# 一些基础数据结构 & 工具函数
# ========================

class DetectionBox:
    """通用的框结构，统一使用像素坐标 (x1, y1, x2, y2)"""

    def __init__(self, cls_id: int, x1: float, y1: float, x2: float, y2: float, conf: float = 1.0):
        self.cls_id = cls_id
        self.x1 = float(x1)
        self.y1 = float(y1)
        self.x2 = float(x2)
        self.y2 = float(y2)
        self.conf = float(conf)

    def area(self) -> float:
        """计算框面积"""
        return max(0.0, self.x2 - self.x1) * max(0.0, self.y2 - self.y1)


def iou(box1: DetectionBox, box2: DetectionBox) -> float:
    """计算两个框的 IoU"""
    inter_x1 = max(box1.x1, box2.x1)
    inter_y1 = max(box1.y1, box2.y1)
    inter_x2 = min(box1.x2, box2.x2)
    inter_y2 = min(box1.y2, box2.y2)

    inter_w = max(0.0, inter_x2 - inter_x1)
    inter_h = max(0.0, inter_y2 - inter_y1)
    inter_area = inter_w * inter_h

    if inter_area <= 0:
        return 0.0

    union_area = box1.area() + box2.area() - inter_area
    if union_area <= 0:
        return 0.0

    return inter_area / union_area


def load_yolo_txt_label(label_path: str, img_w: int, img_h: int) -> List[DetectionBox]:
    """
    加载 YOLO txt 标注：
    每一行：class cx cy w h（归一化到 0~1）
    转换为像素坐标的 DetectionBox 列表
    """
    boxes = []
    if not os.path.exists(label_path):
        return boxes

    with open(label_path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            parts = line.split()
            if len(parts) != 5:
                continue
            cls_id = int(float(parts[0]))
            cx = float(parts[1]) * img_w
            cy = float(parts[2]) * img_h
            w = float(parts[3]) * img_w
            h = float(parts[4]) * img_h
            x1 = cx - w / 2
            y1 = cy - h / 2
            x2 = cx + w / 2
            y2 = cy + h / 2
            boxes.append(DetectionBox(cls_id, x1, y1, x2, y2))
    return boxes


# ========================
# 评分配置
# ========================

class ScoreConfig:
    """
    评分相关参数，可以根据项目需要自行微调
    """
    # YOLO 预测阈值
    conf_thres: float = 0.5      # 只保留大于这个置信度的预测框

    # 匹配阈值
    iou_good_match: float = 0.5  # IOU>=0.5 认为是比较好的匹配
    iou_exist_match: float = 0.3 # IOU>=0.3 认为标签和预测大致对应，但位置/大小可能不太准

    # 标注过大/过小判定：用“面积比”来判断
    # ratio = 标注框面积 / YOLO预测框面积
    big_ratio: float = 1.6       # ratio > 1.6 认为“标注偏大”
    small_ratio: float = 0.6     # ratio < 0.6 认为“标注偏小”

    # 各类错误扣分
    penalty_missing_label: int = 15   # 漏标：YOLO 有预测但没有对应标签
    penalty_extra_label: int = 10     # 多标/错误标：有标签但 YOLO 认为没有这个目标
    penalty_big_small: int = 5        # 过大/过小：一个问题扣 5 分
    penalty_bad_location: int = 5     # 位置偏差较大（IOU 太低）：扣 5 分

    # 最终分数范围
    min_score: int = 0
    max_score: int = 100


# ========================
# 核心评估逻辑
# ========================

def yolo_predict_boxes(model: YOLO, image_path: str, conf_thres: float) -> List[DetectionBox]:
    """调用 YOLO 模型预测，并转换为 DetectionBox 列表"""
    results = model(image_path)[0]
    boxes = []
    for b in results.boxes:
        conf = float(b.conf[0])
        if conf < conf_thres:
            continue
        cls_id = int(b.cls[0])
        x1, y1, x2, y2 = b.xyxy[0].tolist()
        boxes.append(DetectionBox(cls_id, x1, y1, x2, y2, conf))
    return boxes


def greedy_match(preds: List[DetectionBox],
                 gts: List[DetectionBox],
                 iou_thresh: float) -> List[Tuple[int, int, float]]:
    """
    贪心匹配算法：
    - 只匹配同类别框
    - IoU 大于 iou_thresh 才允许匹配
    - 先从最大 IoU 开始匹配，避免“一对多”
    返回：[(pred_idx, gt_idx, iou), ...]
    """
    pairs = []
    candidates = []
    for i, p in enumerate(preds):
        for j, g in enumerate(gts):
            if p.cls_id != g.cls_id:
                continue
            inter = iou(p, g)
            if inter >= iou_thresh:
                candidates.append((inter, i, j))

    # 按 IoU 从大到小排序
    candidates.sort(reverse=True, key=lambda x: x[0])

    matched_pred = set()
    matched_gt = set()
    for inter, i, j in candidates:
        if i in matched_pred or j in matched_gt:
            continue
        matched_pred.add(i)
        matched_gt.add(j)
        pairs.append((i, j, inter))
    return pairs


def evaluate_single_image(model: YOLO,
                          image_path: str,
                          label_path: str,
                          config: ScoreConfig = ScoreConfig()) -> Tuple[Dict, List[DetectionBox], List[DetectionBox]]:
    """
    对单张图片 + 对应 txt 标注进行质量评分
    返回:
        result: 分数和统计信息字典
        pred_boxes: 模型预测框列表
        gt_boxes:   标注框列表
    """
    # 1. 读取图片大小，加载标注框
    img = Image.open(image_path)
    img_w, img_h = img.size

    gt_boxes = load_yolo_txt_label(label_path, img_w, img_h)

    # 2. 用 YOLO 做预测
    pred_boxes = yolo_predict_boxes(model, image_path, config.conf_thres)

    # 3. 特殊情况：完全没有目标 & 没有标签 -> 直接 100 分
    if len(pred_boxes) == 0 and len(gt_boxes) == 0:
        result = {
            "score": config.max_score,
            "detail": {
                "pred_count": 0,
                "gt_count": 0,
                "missing_label": 0,
                "extra_label": 0,
                "big_boxes": 0,
                "small_boxes": 0,
                "bad_location": 0,
                "total_penalty": 0
            }
        }
        return result, pred_boxes, gt_boxes

    # 4. 用较低的阈值先匹配“存在关系”
    pairs_exist = greedy_match(pred_boxes, gt_boxes, config.iou_exist_match)

    matched_pred_idx = {p[0] for p in pairs_exist}
    matched_gt_idx = {p[1] for p in pairs_exist}

    # 统计信息
    missing_label = 0  # 漏标（YOLO 预测到了，标签文件没有）
    extra_label = 0    # 多标/错误标（标签有，YOLO 认为没有）
    big_boxes = 0      # 标注框过大
    small_boxes = 0    # 标注框过小
    bad_location = 0   # 位置偏差大（IOU 偏低）

    # 4.1 未匹配到的预测框 => 认为是漏标
    for i, _ in enumerate(pred_boxes):
        if i not in matched_pred_idx:
            missing_label += 1

    # 4.2 未匹配到的标注框 => 认为是多标/错误标
    for j, _ in enumerate(gt_boxes):
        if j not in matched_gt_idx:
            extra_label += 1

    # 4.3 对匹配到的框，进一步分析大小和位置
    for pred_idx, gt_idx, inter in pairs_exist:
        pred = pred_boxes[pred_idx]
        gt = gt_boxes[gt_idx]

        # 位置偏差：IOU 低于“好的匹配”阈值
        if inter < config.iou_good_match:
            bad_location += 1

        # 大小偏差：用面积比判断
        if pred.area() <= 0 or gt.area() <= 0:
            continue
        ratio = gt.area() / pred.area()  # 标注框 / 预测框

        if ratio > config.big_ratio:
            big_boxes += 1
        elif ratio < config.small_ratio:
            small_boxes += 1

    # 5. 计算总分
    total_penalty = (
        missing_label * config.penalty_missing_label +
        extra_label * config.penalty_extra_label +
        (big_boxes + small_boxes) * config.penalty_big_small +
        bad_location * config.penalty_bad_location
    )
    raw_score = config.max_score - total_penalty
    final_score = max(config.min_score, min(config.max_score, raw_score))

    result = {
        "score": final_score,
        "detail": {
            "pred_count": len(pred_boxes),
            "gt_count": len(gt_boxes),
            "missing_label": missing_label,
            "extra_label": extra_label,
            "big_boxes": big_boxes,
            "small_boxes": small_boxes,
            "bad_location": bad_location,
            "total_penalty": total_penalty
        }
    }
    return result, pred_boxes, gt_boxes


# ========================
# Tkinter 图形界面
# ========================

class LabelQualityApp(tk.Tk):
    """标注质量评估 GUI 主窗口"""

    def __init__(self):
        super().__init__()

        self.title("YOLO 标注质量检测工具（Tkinter）")
        self.geometry("1200x700")

        # 路径变量
        self.weight_path = ""
        self.image_path = ""
        self.label_path = ""

        # 界面显示用变量
        self.weight_var = tk.StringVar()
        self.image_var = tk.StringVar()
        self.label_var = tk.StringVar()

        # YOLO 模型及配置
        self.model = None
        self.loaded_weight_path = None
        self.config = ScoreConfig()

        # 构建界面
        self.create_widgets()

    # ---------- 界面布局 ----------
    def create_widgets(self):
        # =======================
        # 最外层布局：把底部结果区权重调大
        # =======================
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=0)  # 顶部路径选择，占很少高度
        self.rowconfigure(1, weight=1)  # 中间左右对比
        self.rowconfigure(2, weight=3)  # 底部评估结果，更高

        # 顶部：路径选择区域
        path_frame = tk.LabelFrame(self, text="路径选择", padx=10, pady=10)
        path_frame.grid(row=0, column=0, sticky="nsew", padx=10, pady=5)

        # 权重选择
        tk.Label(path_frame, text="权重文件：").grid(row=0, column=0, sticky="e")
        tk.Entry(path_frame, textvariable=self.weight_var, width=70,
                 state="readonly").grid(row=0, column=1, padx=5)
        tk.Button(path_frame, text="选择...", command=self.choose_weight).grid(row=0, column=2, padx=5)

        # 图片选择
        tk.Label(path_frame, text="图像文件：").grid(row=1, column=0, sticky="e", pady=3)
        tk.Entry(path_frame, textvariable=self.image_var, width=70,
                 state="readonly").grid(row=1, column=1, padx=5)
        tk.Button(path_frame, text="选择...", command=self.choose_image).grid(row=1, column=2, padx=5)

        # 标注选择
        tk.Label(path_frame, text="标注 TXT：").grid(row=2, column=0, sticky="e")
        tk.Entry(path_frame, textvariable=self.label_var, width=70,
                 state="readonly").grid(row=2, column=1, padx=5)
        tk.Button(path_frame, text="选择...", command=self.choose_label).grid(row=2, column=2, padx=5)

        # =======================
        # 中间：左右两栏对比（高度减小）
        # =======================
        middle_frame = tk.Frame(self)
        middle_frame.grid(row=1, column=0, sticky="nsew", padx=10, pady=5)
        middle_frame.columnconfigure(0, weight=1)
        middle_frame.columnconfigure(1, weight=1)
        middle_frame.rowconfigure(0, weight=1)

        # 左：标注信息
        left_frame = tk.LabelFrame(middle_frame, text="标注信息（TXT）", padx=5, pady=5)
        left_frame.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)
        left_frame.rowconfigure(0, weight=1)
        left_frame.columnconfigure(0, weight=1)

        # 给上方对比栏设置一个相对小一点的高度，例如 10 行
        self.text_gt = tk.Text(left_frame, wrap="none", font=("Consolas", 10), height=10)
        scroll_y_left = tk.Scrollbar(left_frame, orient="vertical", command=self.text_gt.yview)
        scroll_x_left = tk.Scrollbar(left_frame, orient="horizontal", command=self.text_gt.xview)
        self.text_gt.configure(yscrollcommand=scroll_y_left.set, xscrollcommand=scroll_x_left.set)

        self.text_gt.grid(row=0, column=0, sticky="nsew")
        scroll_y_left.grid(row=0, column=1, sticky="ns")
        scroll_x_left.grid(row=1, column=0, sticky="ew")

        # 右：预测信息
        right_frame = tk.LabelFrame(middle_frame, text="模型预测信息（YOLO）", padx=5, pady=5)
        right_frame.grid(row=0, column=1, sticky="nsew", padx=5, pady=5)
        right_frame.rowconfigure(0, weight=1)
        right_frame.columnconfigure(0, weight=1)

        self.text_pred = tk.Text(right_frame, wrap="none", font=("Consolas", 10), height=10)
        scroll_y_right = tk.Scrollbar(right_frame, orient="vertical", command=self.text_pred.yview)
        scroll_x_right = tk.Scrollbar(right_frame, orient="horizontal", command=self.text_pred.xview)
        self.text_pred.configure(yscrollcommand=scroll_y_right.set, xscrollcommand=scroll_x_right.set)

        self.text_pred.grid(row=0, column=0, sticky="nsew")
        scroll_y_right.grid(row=0, column=1, sticky="ns")
        scroll_x_right.grid(row=1, column=0, sticky="ew")

        # =======================
        # 底部：评估结果（加高）
        # =======================
        bottom_frame = tk.LabelFrame(self, text="评估结果", padx=10, pady=10)
        bottom_frame.grid(row=2, column=0, sticky="nsew", padx=10, pady=5)
        bottom_frame.columnconfigure(0, weight=1)
        bottom_frame.rowconfigure(1, weight=1)  # 让结果文本框随区域一起撑大

        btn_eval = tk.Button(bottom_frame, text="开始评估",
                             command=self.run_evaluate, width=15)
        btn_eval.grid(row=0, column=0, sticky="w")

        # 把结果框的高度调大一点，比如 14 行
        self.result_text = tk.Text(bottom_frame, height=14, font=("Microsoft YaHei", 10))
        self.result_text.grid(row=1, column=0, sticky="nsew", pady=5)

    # ---------- 文件选择 ----------
    def choose_weight(self):
        """选择 YOLO 权重文件"""
        path = filedialog.askopenfilename(
            title="选择 YOLO 权重文件",
            filetypes=[("YOLO 权重文件", "*.pt *.pth"), ("所有文件", "*.*")]
        )
        if path:
            self.weight_path = path
            self.weight_var.set(path)
            # 如果更换了权重，下次需要重新加载模型
            self.model = None
            self.loaded_weight_path = None

    def choose_image(self):
        """选择图片文件"""
        path = filedialog.askopenfilename(
            title="选择图像文件",
            filetypes=[("图像文件", "*.jpg *.jpeg *.png *.bmp"), ("所有文件", "*.*")]
        )
        if path:
            self.image_path = path
            self.image_var.set(path)

    def choose_label(self):
        """选择标注 txt 文件"""
        path = filedialog.askopenfilename(
            title="选择标注 TXT 文件",
            filetypes=[("文本文件", "*.txt"), ("所有文件", "*.*")]
        )
        if path:
            self.label_path = path
            self.label_var.set(path)

    # ---------- 执行评估 ----------
    def run_evaluate(self):
        """执行一次评估流程"""
        # 检查路径是否齐全
        if not self.weight_path or not self.image_path or not self.label_path:
            messagebox.showwarning("缺少路径", "请先选择权重文件、图片文件和标注 TXT 文件。")
            return

        # 加载模型（如有需要）
        try:
            if self.model is None or self.loaded_weight_path != self.weight_path:
                self.model = YOLO(self.weight_path)
                self.loaded_weight_path = self.weight_path
        except Exception as e:
            messagebox.showerror("模型加载失败", f"加载 YOLO 权重失败：\n{e}")
            return

        # 清空文本框
        self.text_gt.delete("1.0", tk.END)
        self.text_pred.delete("1.0", tk.END)
        self.result_text.delete("1.0", tk.END)

        # 执行评估
        try:
            result, pred_boxes, gt_boxes = evaluate_single_image(
                self.model,
                self.image_path,
                self.label_path,
                self.config
            )
        except Exception as e:
            messagebox.showerror("评估失败", f"评估过程中出现错误：\n{e}")
            return

        # 显示标注信息
        self.show_boxes_info(
            text_widget=self.text_gt,
            title="标注框列表（来自 TXT，坐标为像素）",
            boxes=gt_boxes,
            show_conf=False
        )

        # 显示预测信息
        self.show_boxes_info(
            text_widget=self.text_pred,
            title="预测框列表（YOLO 检测结果，坐标为像素）",
            boxes=pred_boxes,
            show_conf=True
        )

        # 显示中文评分结果
        self.show_result(result)

    def show_boxes_info(self, text_widget: tk.Text, title: str,
                        boxes: List[DetectionBox], show_conf: bool = False):
        """在某个文本框中输出框列表信息"""
        text_widget.insert(tk.END, f"{title}\n")
        text_widget.insert(tk.END, "-" * 60 + "\n")
        if not boxes:
            text_widget.insert(tk.END, "（无）\n")
            return

        for idx, box in enumerate(boxes, start=1):
            if show_conf:
                line = (f"[{idx}] 类别: {box.cls_id:>3d}，"
                        f"置信度: {box.conf:.2f}，"
                        f"像素框: ({box.x1:.1f}, {box.y1:.1f}, {box.x2:.1f}, {box.y2:.1f})，"
                        f"面积: {box.area():.1f}\n")
            else:
                line = (f"[{idx}] 类别: {box.cls_id:>3d}，"
                        f"像素框: ({box.x1:.1f}, {box.y1:.1f}, {box.x2:.1f}, {box.y2:.1f})，"
                        f"面积: {box.area():.1f}\n")
            text_widget.insert(tk.END, line)

    def show_result(self, result: Dict):
        """在底部文本框中输出中文结果说明"""
        detail = result.get("detail", {})
        score = result.get("score", 0)

        lines = []
        lines.append(f"评分结果：{score} 分（满分 {self.config.max_score}）")
        lines.append("")
        lines.append(f"YOLO 预测目标数：{detail.get('pred_count', 0)}")
        lines.append(f"标注框数量：{detail.get('gt_count', 0)}")
        lines.append("")
        lines.append(f"漏标：{detail.get('missing_label', 0)} 个（模型检测到，但标注中没有对应框）")
        lines.append(f"多标 / 错误标注：{detail.get('extra_label', 0)} 个（标注中有框，但模型认为不存在该目标）")
        lines.append(f"标注过大：{detail.get('big_boxes', 0)} 个（标注框面积明显大于模型预测框）")
        lines.append(f"标注过小：{detail.get('small_boxes', 0)} 个（标注框面积明显小于模型预测框）")
        lines.append(f"位置偏差较大：{detail.get('bad_location', 0)} 个（粗匹配到同一目标，但 IoU < {self.config.iou_good_match}）")
        lines.append("")
        lines.append(f"总扣分：{detail.get('total_penalty', 0)} 分")
        lines.append("")
        lines.append("说明：")
        lines.append("1）漏标（模型有预测但标注缺失）是最严重的问题，所以每个扣 15 分。")
        lines.append("2）多标 / 错误标注每个扣 10 分。")
        lines.append("3）标注框过大或过小，以及位置明显偏移，都按每个扣 5 分处理。")
        lines.append("4）最终分数限制在 0 ~ 100 之间。")

        self.result_text.insert(tk.END, "\n".join(lines))


if __name__ == "__main__":
    # 运行 Tkinter 应用
    app = LabelQualityApp()
    app.mainloop()
