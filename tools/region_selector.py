
"""
图像区域选择器（矩形框选择版）
功能：在标准图上手动选择多个矩形区域，提取特征并保存
优化：图像放大显示，尽量占满UI界面
"""

import cv2
import numpy as np
import json
import os
from datetime import datetime
import tkinter as tk
from tkinter import messagebox, simpledialog
from PIL import Image, ImageTk

import global_config

base_dir = os.path.dirname(os.path.abspath(__file__))
reference_path = global_config.Global_Config.live_capture_path

class RegionSelector:
    def __init__(self, reference_image_path):
        self.reference_image_path = reference_image_path
        self.reference_image = None
        self.display_image = None
        self.current_rect = None  # 当前正在绘制的矩形 [x1, y1, x2, y2]
        self.regions = []  # 已完成的矩形区域列表
        self.region_features = []
        self.drawing = False  # 是否正在绘制
        self.start_x = 0
        self.start_y = 0
        self.scale_factor = 1.0

        # GUI相关
        self.root = None
        self.canvas = None
        self.canvas_image = None

        # 加载参考图像
        self.load_reference_image()

    def load_reference_image(self):
        """加载参考图像"""
        try:
            self.reference_image = cv2.imread(self.reference_image_path)
            if self.reference_image is None:
                raise ValueError(f"无法读取图像: {self.reference_image_path}")
            print(f"成功加载参考图像: {self.reference_image_path}")
            print(f"图像尺寸: {self.reference_image.shape}")
        except Exception as e:
            print(f"加载图像失败: {e}")
            raise

    def extract_region_features(self, rect_coords):
        """提取矩形区域特征"""
        try:
            x1, y1, x2, y2 = rect_coords
            # 确保坐标正确
            x1, x2 = min(x1, x2), max(x1, x2)
            y1, y2 = min(y1, y2), max(y1, y2)

            # 裁剪区域
            region_roi = self.reference_image[y1:y2, x1:x2]
            h, w = region_roi.shape[:2]

            if w == 0 or h == 0:
                return None

            features = {
                'bbox': [int(x1), int(y1), int(x2-x1), int(y2-y1)],  # [x, y, width, height]
                'coordinates': [int(x1), int(y1), int(x2), int(y2)],  # [x1, y1, x2, y2]
                'area': float((x2-x1) * (y2-y1))
            }

            # 1. 颜色特征 - HSV直方图
            hsv_roi = cv2.cvtColor(region_roi, cv2.COLOR_BGR2HSV)
            hist_h = cv2.calcHist([hsv_roi], [0], None, [50], [0, 180])
            hist_s = cv2.calcHist([hsv_roi], [1], None, [60], [0, 256])
            hist_v = cv2.calcHist([hsv_roi], [2], None, [60], [0, 256])

            features['color_hist'] = {
                'h': hist_h.flatten().tolist(),
                's': hist_s.flatten().tolist(),
                'v': hist_v.flatten().tolist()
            }

            # 2. 纹理特征 - LBP (简化版)
            gray_roi = cv2.cvtColor(region_roi, cv2.COLOR_BGR2GRAY)
            lbp_features = self.calculate_lbp_features(gray_roi)
            features['texture'] = lbp_features

            # 3. 形状特征（矩形特征）
            features['shape'] = {
                'width': float(x2 - x1),
                'height': float(y2 - y1),
                'aspect_ratio': float((x2-x1) / (y2-y1)) if (y2-y1) > 0 else 0,
                'perimeter': float(2 * ((x2-x1) + (y2-y1)))
            }

            # 4. SIFT关键点特征
            sift = cv2.SIFT_create()
            keypoints, descriptors = sift.detectAndCompute(gray_roi, None)

            if keypoints and descriptors is not None:
                features['sift'] = {
                    'keypoints': len(keypoints),
                    'descriptors': descriptors.tolist()
                }
            else:
                features['sift'] = {'keypoints': 0, 'descriptors': []}

            # 5. 统计特征
            features['statistics'] = {
                'mean_color': [float(np.mean(region_roi[:,:,i])) for i in range(3)],
                'std_color': [float(np.std(region_roi[:,:,i])) for i in range(3)],
                'mean_gray': float(np.mean(gray_roi)),
                'std_gray': float(np.std(gray_roi))
            }

            return features

        except Exception as e:
            print(f"特征提取失败: {e}")
            return None

    def calculate_lbp_features(self, gray_image):
        """计算LBP纹理特征"""
        try:
            height, width = gray_image.shape
            lbp = np.zeros_like(gray_image)

            # 简化的LBP计算
            for i in range(1, height-1):
                for j in range(1, width-1):
                    center = gray_image[i, j]
                    code = 0

                    # 8邻域LBP
                    neighbors = [
                        gray_image[i-1, j-1], gray_image[i-1, j], gray_image[i-1, j+1],
                        gray_image[i, j+1], gray_image[i+1, j+1], gray_image[i+1, j],
                        gray_image[i+1, j-1], gray_image[i, j-1]
                    ]

                    for idx, neighbor in enumerate(neighbors):
                        if neighbor >= center:
                            code |= (1 << idx)

                    lbp[i, j] = code

            # 计算LBP直方图
            hist = cv2.calcHist([lbp], [0], None, [256], [0, 256])
            return hist.flatten().tolist()

        except Exception as e:
            print(f"LBP计算失败: {e}")
            return [0] * 256

    def create_gui(self):
        """创建图形界面"""
        self.root = tk.Tk()
        self.root.title("区域选择器 - 拖拽选择矩形区域")
        self.root.geometry("1500x1100")

        # 控制面板
        control_frame = tk.Frame(self.root)
        control_frame.pack(side=tk.TOP, fill=tk.X, padx=5, pady=3)

        tk.Label(control_frame, text="操作：鼠标左键拖拽选择矩形区域",
                font=("Arial", 9)).pack(side=tk.LEFT)

        tk.Button(control_frame, text="保存", command=self.save_regions,
                 bg='#4CAF50', fg='white', font=("Arial", 9, "bold")).pack(side=tk.RIGHT, padx=2)

        tk.Button(control_frame, text="删除最后", command=self.delete_last_region,
                 bg='#FF9800', fg='white', font=("Arial", 9)).pack(side=tk.RIGHT, padx=2)

        tk.Button(control_frame, text="清空全部", command=self.clear_all_regions,
                 bg='#f44336', fg='white', font=("Arial", 9)).pack(side=tk.RIGHT, padx=2)

        # 信息面板
        info_frame = tk.Frame(self.root)
        info_frame.pack(side=tk.TOP, fill=tk.X, padx=5, pady=1)

        self.info_label = tk.Label(info_frame, text=f"已选择区域数量: 0", font=("Arial", 8))
        self.info_label.pack(side=tk.LEFT)

        # 图像显示区域
        self.canvas = tk.Canvas(self.root, bg='white', highlightthickness=0)
        self.canvas.pack(side=tk.TOP, fill=tk.BOTH, expand=True, padx=5, pady=5)

        # 绑定鼠标事件
        self.canvas.bind("<Button-1>", self.on_mouse_press)
        self.canvas.bind("<B1-Motion>", self.on_mouse_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_mouse_release)

        # 显示图像
        self.display_image_on_canvas()

    def display_image_on_canvas(self):
        """在画布上显示图像"""
        self.canvas.update()
        canvas_width = self.canvas.winfo_width()
        canvas_height = self.canvas.winfo_height()

        if canvas_width <= 1 or canvas_height <= 1:
            canvas_width = 1150
            canvas_height = 750

        canvas_width -= 20
        canvas_height -= 20

        h, w = self.reference_image.shape[:2]
        scale_w = canvas_width / w
        scale_h = canvas_height / h
        self.scale_factor = min(scale_w, scale_h)

        new_width = int(w * self.scale_factor)
        new_height = int(h * self.scale_factor)

        # 调整图像尺寸
        display_img = cv2.resize(self.reference_image, (new_width, new_height))
        display_img_rgb = cv2.cvtColor(display_img, cv2.COLOR_BGR2RGB)

        # 转换为PIL图像
        pil_img = Image.fromarray(display_img_rgb)
        self.canvas_image = ImageTk.PhotoImage(pil_img)

        # 在画布中央显示图像
        self.canvas.delete("all")
        self.canvas.config(scrollregion=self.canvas.bbox("all"))
        self.canvas_img_id = self.canvas.create_image(
            (canvas_width + 20)//2, (canvas_height + 20)//2,
            image=self.canvas_image, anchor="center"
        )

        # 重新绘制已有区域
        self.redraw_regions()

    def canvas_to_image_coords(self, canvas_x, canvas_y):
        """将画布坐标转换为原始图像坐标"""
        # 获取图像在画布中的位置
        img_center_x, img_center_y = self.canvas.coords(self.canvas_img_id)
        img_left = img_center_x - self.canvas_image.width()//2
        img_top = img_center_y - self.canvas_image.height()//2

        # 转换到图像坐标
        img_x = canvas_x - img_left
        img_y = canvas_y - img_top

        # 转换到原始图像坐标
        orig_x = int(img_x / self.scale_factor)
        orig_y = int(img_y / self.scale_factor)

        # 限制在图像范围内
        h, w = self.reference_image.shape[:2]
        orig_x = max(0, min(orig_x, w-1))
        orig_y = max(0, min(orig_y, h-1))

        return orig_x, orig_y

    def image_to_canvas_coords(self, img_x, img_y):
        """将原始图像坐标转换为画布坐标"""
        # 获取图像在画布中的位置
        img_center_x, img_center_y = self.canvas.coords(self.canvas_img_id)
        img_left = img_center_x - self.canvas_image.width()//2
        img_top = img_center_y - self.canvas_image.height()//2

        canvas_x = img_left + img_x * self.scale_factor
        canvas_y = img_top + img_y * self.scale_factor

        return canvas_x, canvas_y

    def on_mouse_press(self, event):
        """鼠标按下事件"""
        self.drawing = True
        self.start_x, self.start_y = self.canvas_to_image_coords(event.x, event.y)
        self.current_rect = [self.start_x, self.start_y, self.start_x, self.start_y]

    def on_mouse_drag(self, event):
        """鼠标拖拽事件"""
        if self.drawing:
            end_x, end_y = self.canvas_to_image_coords(event.x, event.y)
            self.current_rect = [self.start_x, self.start_y, end_x, end_y]
            self.redraw_regions()

    def on_mouse_release(self, event):
        """鼠标释放事件"""
        if self.drawing:
            self.drawing = False
            end_x, end_y = self.canvas_to_image_coords(event.x, event.y)

            # 确保矩形有一定大小
            if abs(end_x - self.start_x) > 5 and abs(end_y - self.start_y) > 5:
                self.current_rect = [self.start_x, self.start_y, end_x, end_y]
                self.complete_current_region()
            else:
                messagebox.showwarning("警告", "选择的区域太小，请重新选择")

            self.current_rect = None
            self.redraw_regions()

    def complete_current_region(self):
        """完成当前区域选择"""
        if self.current_rect:
            # 请求区域名称
            region_name = simpledialog.askstring("区域名称", "请输入区域名称:")
            if not region_name:
                region_name = f"区域_{len(self.regions) + 1}"

            # 提取特征
            features = self.extract_region_features(self.current_rect)
            if features:
                features['name'] = region_name
                features['id'] = len(self.regions)

                self.regions.append(self.current_rect.copy())
                self.region_features.append(features)

                x1, y1, x2, y2 = self.current_rect
                print(f"完成区域选择: {region_name}, 坐标: ({x1},{y1}) - ({x2},{y2})")
                self.update_info_label()
            else:
                messagebox.showerror("错误", "特征提取失败")

    def delete_last_region(self):
        """删除最后一个区域"""
        if self.regions:
            self.regions.pop()
            self.region_features.pop()
            self.redraw_regions()
            self.update_info_label()
            print("删除最后一个区域")

    def clear_all_regions(self):
        """清空所有区域"""
        self.regions = []
        self.region_features = []
        self.current_rect = None
        self.redraw_regions()
        self.update_info_label()
        print("清空所有区域")

    def redraw_regions(self):
        """重新绘制所有区域"""
        # 清除之前的绘制（保留图像）
        for item in self.canvas.find_all():
            if item != self.canvas_img_id:
                self.canvas.delete(item)

        # 绘制已完成的区域
        for i, rect in enumerate(self.regions):
            x1, y1, x2, y2 = rect
            canvas_x1, canvas_y1 = self.image_to_canvas_coords(x1, y1)
            canvas_x2, canvas_y2 = self.image_to_canvas_coords(x2, y2)

            # 绘制矩形框
            self.canvas.create_rectangle(canvas_x1, canvas_y1, canvas_x2, canvas_y2,
                                       outline='red', fill='', width=2, tags='completed')

            # 绘制区域标签
            center_x = (canvas_x1 + canvas_x2) / 2
            center_y = (canvas_y1 + canvas_y2) / 2
            self.canvas.create_text(center_x, center_y, text=f"区域{i+1}",
                                  fill='red', font=("Arial", 12, "bold"), tags='completed')

        # 绘制当前正在选择的矩形
        if self.current_rect:
            x1, y1, x2, y2 = self.current_rect
            canvas_x1, canvas_y1 = self.image_to_canvas_coords(x1, y1)
            canvas_x2, canvas_y2 = self.image_to_canvas_coords(x2, y2)

            self.canvas.create_rectangle(canvas_x1, canvas_y1, canvas_x2, canvas_y2,
                                       outline='blue', fill='', width=2, dash=(5, 5), tags='current')

    def update_info_label(self):
        """更新信息标签"""
        self.info_label.config(text=f"已选择区域数量: {len(self.regions)}")

    def save_regions(self):
        """保存所有区域特征"""
        if not self.region_features:
            messagebox.showwarning("警告", "没有选择任何区域")
            return

        try:
            # 生成文件名
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            save_path = f"regions_rules.json"

            # 保存数据
            save_data = {
                'reference_image': self.reference_image_path,
                'image_shape': self.reference_image.shape,
                'regions_count': len(self.region_features),
                'regions': self.region_features,
                'created_time': timestamp,
                'selection_type': 'rectangle'  # 标记为矩形选择
            }

            with open(save_path, 'w', encoding='utf-8') as f:
                json.dump(save_data, f, ensure_ascii=False, indent=2)

            messagebox.showinfo("成功", f"区域特征已保存到: {save_path}")
            print(f"保存成功: {save_path}")
            print(f"共保存 {len(self.region_features)} 个矩形区域")

        except Exception as e:
            messagebox.showerror("错误", f"保存失败: {e}")

    def run(self):
        """运行区域选择器"""
        self.create_gui()
        self.root.mainloop()

def main():
    # 配置参考图像路径
    REFERENCE_IMAGE_PATH = reference_path

    try:
        selector = RegionSelector(REFERENCE_IMAGE_PATH)
        selector.run()
    except Exception as e:
        print(f"程序运行失败: {e}")

if __name__ == "__main__":
    main()