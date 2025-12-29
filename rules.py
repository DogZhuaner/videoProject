import sys
import csv
import json
import os


# 并查集算法用于识别相连的触点组
class UnionFind:
    def __init__(self):
        self.parent = {}
        self.score = {}

    def find(self, x):
        if self.parent[x] != x:
            self.parent[x] = self.find(self.parent[x])
        return self.parent[x]

    def union(self, x, y, score):
        if x not in self.parent:
            self.parent[x] = x
            self.score[x] = score
        if y not in self.parent:
            self.parent[y] = y
            self.score[y] = score

        root_x = self.find(x)
        root_y = self.find(y)

        if root_x != root_y:
            self.parent[root_y] = root_x
            # 合并时保持分值
            if score > self.score[root_x]:
                self.score[root_x] = score

    def get_groups(self):
        groups = {}
        for node in self.parent:
            root = self.find(node)
            if root not in groups:
                groups[root] = []
            groups[root].append(node)
        return groups, self.score


from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QGraphicsView, QGraphicsScene, QGraphicsEllipseItem,
    QGraphicsLineItem, QGraphicsTextItem, QGraphicsRectItem, QInputDialog, QFileDialog,
    QMenu, QAction, QPushButton, QVBoxLayout, QWidget, QLabel, QMessageBox
)
from PyQt5.QtGui import QPen, QBrush, QColor, QPainter, QFont
from PyQt5.QtCore import Qt, QPointF, QTimer
from global_config import Global_Config

CONFIG_FILE = "component_config.json"
RULE_FILE = Global_Config.rule_csv_path  # 使用全局变量


def load_component_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}


def save_component_config(config):
    with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
        json.dump(config, f, ensure_ascii=False, indent=2)


def save_rules_to_csv(wires):
    with open(RULE_FILE, "w", newline='', encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["起点", "终点", "分值"])
        for wire in wires:
            writer.writerow([wire.start_item.name, wire.end_item.name, wire.score])


def export_rules_to_json(wires, filename):
    # 使用并查集识别相连的触点组
    uf = UnionFind()
    for wire in wires:
        uf.union(wire.start_item.name, wire.end_item.name, wire.score)

    # 获取合并后的触点组和对应的分值
    groups, scores = uf.get_groups()

    # 生成JSON格式的数据
    rules = []
    rule_id = 1
    for root, nodes in groups.items():
        if len(nodes) > 0:  # 只添加有触点的组
            rules.append({
                "id": rule_id,
                "nodes": sorted(nodes),  # 按字母顺序排序触点名称
                "score": scores[root]
            })
            rule_id += 1

    # 写入JSON文件
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(rules, f, ensure_ascii=False, indent=2)


class ContactItem(QGraphicsEllipseItem):
    def __init__(self, x, y, name, parent, comp_id, contact_id, config):
        super().__init__(-12, -12, 24, 24, parent)  # 稍大触点，半径12像素
        self.setPos(x, y)
        # 更美观的触点样式
        self.setPen(QPen(QColor(80, 80, 80), 1.2))
        self.setBrush(QBrush(QColor(255, 223, 0)))
        self.setFlag(QGraphicsEllipseItem.ItemIsSelectable)
        self.name = name
        self.comp_id = comp_id
        self.contact_id = contact_id
        self.config = config
        # 优化文本样式和位置
        self.text = QGraphicsTextItem(name, self)
        self.text.setFont(QFont("SimHei", 9))
        self.text.setPos(18, -10)  # 增大与触点的间距
        self.text.setDefaultTextColor(Qt.black)
        # 鼠标悬停效果
        self.setAcceptHoverEvents(True)

    def hoverEnterEvent(self, event):
        # 鼠标悬停时高亮
        self.setBrush(QBrush(QColor(255, 255, 0)))
        super().hoverEnterEvent(event)

    def hoverLeaveEvent(self, event):
        # 鼠标离开时恢复原色
        self.setBrush(QBrush(QColor(255, 223, 0)))
        super().hoverLeaveEvent(event)

    def mouseDoubleClickEvent(self, event):
        new_name, ok = QInputDialog.getText(None, "修改触点名称", "输入新名称：", text=self.name)
        if ok and new_name:
            self.name = new_name
            self.text.setPlainText(new_name)
            if self.comp_id not in self.config:
                self.config[self.comp_id] = {'name': self.comp_id, 'contacts': {self.contact_id: new_name}}
            else:
                if 'contacts' not in self.config[self.comp_id]:
                    self.config[self.comp_id]['contacts'] = {}
                self.config[self.comp_id]['contacts'][self.contact_id] = new_name
            save_component_config(self.config)


class WireItem(QGraphicsLineItem):
    def __init__(self, start_item, end_item, score=0, scene=None):
        super().__init__()
        self.start_item = start_item
        self.end_item = end_item
        self.score = score
        self.setPen(QPen(QColor("blue"), 2))
        self.setFlag(QGraphicsLineItem.ItemIsSelectable)
        self.scene_ref = scene  # 保存scene引用
        # 文本单独加到scene上，只在score不为0时显示
        if scene is not None and score != 0:
            self.text = QGraphicsTextItem(str(self.score))
            scene.addItem(self.text)
        else:
            self.text = None
        self.update_position()

    def update_position(self):
        p1 = self.start_item.scenePos()
        p2 = self.end_item.scenePos()
        self.setLine(p1.x(), p1.y(), p2.x(), p2.y())
        if self.text and self.score != 0:
            mid = (p1 + p2) / 2
            self.text.setPos(mid.x(), mid.y())

    def contextMenuEvent(self, event):
        menu = QMenu()
        set_score = QAction("设置分值", menu)
        delete = QAction("删除连线", menu)
        set_score.triggered.connect(self.set_score_dialog)
        delete.triggered.connect(self.delete_self)
        menu.addAction(set_score)
        menu.addAction(delete)
        menu.exec_(event.screenPos())

    def set_score_dialog(self):
        score, ok = QInputDialog.getInt(None, "设置分值", "输入分值：", value=self.score)
        if ok:
            old_score = self.score
            self.score = score

            # 处理文本显示
            if score != 0:
                if not self.text and self.scene_ref:
                    self.text = QGraphicsTextItem(str(score))
                    self.scene_ref.addItem(self.text)
                elif self.text:
                    self.text.setPlainText(str(score))
            else:
                if self.text and self.scene_ref:
                    self.scene_ref.removeItem(self.text)
                    self.text = None

            # 更新规则文件
            if self.scene_ref:
                save_rules_to_csv(self.scene_ref.wires)
                # 如果设置了分值，更新JSON规则文件
                if score != 0:
                    self.scene_ref.export_current_rules_to_json()

    def delete_self(self):
        scene = self.scene()
        if scene:
            if self.text:
                scene.removeItem(self.text)
            scene.removeItem(self)
            if hasattr(scene, 'remove_wire'):
                scene.remove_wire(self)


class ComponentItem(QGraphicsRectItem):
    def __init__(self, x, y, w, h, name, contacts, comp_id, config):
        super().__init__(0, 0, w, h)
        self.setPos(x, y)
        # 设置更美观的边框和背景
        self.setPen(QPen(QColor(100, 100, 150), 1.5))
        self.setBrush(QBrush(QColor(245, 245, 250)))
        self.setFlag(QGraphicsRectItem.ItemIsMovable)
        self.setFlag(QGraphicsRectItem.ItemIsSelectable)
        self.comp_id = comp_id
        self.config = config
        self.name = config.get(comp_id, {}).get('name', name)
        # 优化名称文本样式和位置（居中显示）
        self.text = QGraphicsTextItem(self.name, self)
        self.text.setFont(QFont("SimHei", 10, QFont.Bold))
        self.text.setDefaultTextColor(QColor(70, 70, 120))
        # 计算居中位置
        text_width = self.text.boundingRect().width()
        self.text.setPos((w - text_width) / 2, -20)
        self.contacts = []
        for idx, (cx, cy, cname, cid) in enumerate(contacts):
            contact_name = config.get(comp_id, {}).get('contacts', {}).get(cid, cname)
            contact = ContactItem(w - 20, cy, contact_name, self, comp_id, cid, config)
            self.contacts.append(contact)

    def mouseDoubleClickEvent(self, event):
        new_name, ok = QInputDialog.getText(None, "修改元件名称", "输入新名称：", text=self.name)
        if ok and new_name:
            self.name = new_name
            self.text.setPlainText(new_name)
            if self.comp_id not in self.config:
                self.config[self.comp_id] = {'name': new_name, 'contacts': {}}
            else:
                self.config[self.comp_id]['name'] = new_name
            save_component_config(self.config)


class PanelScene(QGraphicsScene):
    def __init__(self):
        super().__init__()
        self.setSceneRect(0, 0, 1800, 1200)
        self.contacts = []
        self.wires = []
        self.temp_start = None
        self.config = load_component_config()
        self.init_layout()
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_all_wires)
        self.timer.start(50)
        # 新增：用于跟踪当前连线组
        self.active_group_id = None

    def init_layout(self, component_names=None, original_names=None):
        # 四个区域的触点名称
        regions = {
            'region_001': [
                'QS1-1', 'QS1-3', 'QS1-5', 'QS1-7', 'FU1-1', 'FU1-3', 'FU1-5', 'FU2-1', 'FU2-3', 'FU2-5',
                'KT1-A1', 'KT1-1L1', 'KT1-3L2', 'KT1-5L3', 'KT1-55', 'KT1-67', 'KT2-A1', 'KT2-1L1', 'KT2-3L2',
                'KT2-5L3', 'KT2-55', 'KT2-67', 'PLC-L', 'PLC-N', 'PLC-PE', 'PLC-L+', 'PLC-M', 'PLC-1M', 'PLC-X0',
                'PLC-X1', 'PLC-X2', 'PLC-X3', 'PLC-X4', 'PLC-X5', 'PLC-X6', 'PLC-X7'
            ],
            'region_002': [
                'QS1-2', 'QS1-4', 'QS1-6', 'QS1-8', 'FU1-2', 'FU1-4', 'FU1-6', 'FU2-2', 'FU2-4', 'FU2-6',
                'KT1-A2', 'KT1-2TA', 'KT1-4T2', 'KT1-6T3', 'KT1-56', 'KT1-68', 'KT2-A2', 'KT2-2T1', 'KT2-4T2',
                'KT2-6T3', 'KT2-56', 'KT2-68', 'PLC-1L', 'PLC-Y0', 'PLC-Y1', 'PLC-Y2', 'PLC-Y3', 'PLC-Y4',
                'PLC-2L', 'PLC-Y5', 'PLC-Y6', 'PLC-Y7', 'INV-L1', 'INV-L2', 'INV-L3', 'INV-5/DI0', 'INV-6/DI1',
                'INV-7/DI2', 'INV-8/DI3', 'INV-16/DI4', 'INV-17/DI5', 'INV-DO0', 'INV-U2', 'INV-V2', 'INV-W2'
            ],
            'region_003': [
                'KM1-A1', 'KM1-1L1', 'KM1-3L2', 'KM1-5L3', 'KM1-13', 'KM1-53', 'KM1-61', 'KM1-71', 'KM1-83',
                'KM2-A1', 'KM2-1L1', 'KM2-3L2', 'KM2-5L3', 'KM2-13', 'KM2-53', 'KM2-61', 'KM2-71', 'KM2-83',
                'KM3-A1', 'KM3-1L1', 'KM3-3L2', 'KM3-5L3', 'KM3-13', 'KM3-53', 'KM3-61', 'KM3-71', 'KM3-83',
                'FR1-1L1', 'FR1-3L2', 'FR1-5L3', 'FR2-1L1', 'FR2-3L2', 'FR2-5L3', 'SB1-1', 'SB1-2', 'SB1-3',
                'SB1-4', 'SB2-1', 'SB2-2', 'SB2-3', 'SB2-4', 'SB3-1', 'SB3-2', 'SB3-3', 'SB3-4', 'HL1-1',
                'HL1-2', 'HL2-1', 'HL2-2', 'HL3-1', 'HL3-2'
            ],
            'region_004': [
                'KM1-A2', 'KM1-2T1', 'KM1-4T2', 'KM1-6T3', 'KM1-14', 'KM1-54', 'KM1-62', 'KM1-72', 'KM1-84',
                'KM2-A2', 'KM2-2T1', 'KM2-4T2', 'KM2-6T3', 'KM2-14', 'KM2-54', 'KM2-62', 'KM2-72', 'KM2-84',
                'KM3-A2', 'KM3-2T1', 'KM3-4T2', 'KM3-6T3', 'KM3-14', 'KM3-54', 'KM3-62', 'KM3-72', 'KM3-84',
                'FR1-2T1', 'FR1-4T2', 'FR1-6T3', 'FR1-98', 'FR1-97', 'FR1-96', 'FR1-95', 'FR2-2T1', 'FR2-4T2',
                'FR2-6T3', 'FR2-98', 'FR2-97', 'FR2-96', 'FR2-95', 'XT1-1', 'XT1-2', 'XT1-3', 'XT1-4', 'XT1-5',
                'XT1-6', 'XT2-1', 'XT2-2', 'XT2-3', 'XT2-4', 'XT2-5', 'XT2-6'
            ]
        }

        comp_w = 90  # 缩减元件宽度
        min_contact_gap = 25  # 增加触点间距
        region_spacing = 300  # 区域水平间距
        # 四个竖直区域布局 (从左到右排列)
        region_positions = {
            'region_001': (60, 60),  # 第一列
            'region_002': (360, 60),  # 第二列
            'region_003': (660, 60),  # 第三列
            'region_004': (960, 60)  # 第四列
        }

        # 删除了区域标题
        # 为每个区域创建元器件和触点
        for region_name, region_contacts in regions.items():
            # 添加区域标题
            region_x, region_y = region_positions[region_name]

            # 按前缀分组触点
            contact_groups = {}
            for contact_name in region_contacts:
                prefix = contact_name.split('-')[0]
                if prefix not in contact_groups:
                    contact_groups[prefix] = []
                contact_groups[prefix].append(contact_name)

            # 创建元器件
            row_y = region_y
            for prefix, contacts in contact_groups.items():
                # 按触点名称排序
                contacts.sort()
                # 创建元器件
                comp_h = min_contact_gap * (len(contacts) + 1)
                comp_id = f"{region_name}_{prefix}"

                # 为每个触点创建坐标
                component_contacts = []
                for idx, contact_name in enumerate(contacts):
                    cy = min_contact_gap * (idx + 1)
                    component_contacts.append((comp_w - 30, cy, contact_name, contact_name))

                # 创建元器件
                c = ComponentItem(region_x, row_y, comp_w, comp_h, prefix, component_contacts, comp_id, self.config)
                self.addItem(c)
                self.contacts.extend(c.contacts)

                # 更新下一个元器件的Y坐标
                row_y += comp_h + 30  # 增加元器件垂直间距

        # 统计所有元器件的最大底部y坐标
        max_bottom = 0
        for item in self.items():
            if isinstance(item, ComponentItem):
                bottom = item.y() + item.rect().height()
                if bottom > max_bottom:
                    max_bottom = bottom

        # 删除了区域分隔线

        # 扩大场景宽度以适应四个竖直区域
        self.setSceneRect(0, 0, 1200, max_bottom + 100)

    def add_wire(self, wire):
        self.addItem(wire)
        self.wires.append(wire)
        save_rules_to_csv(self.wires)

    def remove_wire(self, wire):
        if wire in self.wires:
            self.wires.remove(wire)
            save_rules_to_csv(self.wires)

    def mousePressEvent(self, event):
        item = self.itemAt(event.scenePos(), self.views()[0].transform())
        if isinstance(item, ContactItem):
            if self.temp_start is None:
                # 开始新的连线组
                self.temp_start = item
                item.setBrush(QBrush(QColor("red")))
                # 初始化组ID
                self.active_group_id = 1
            else:
                if item != self.temp_start:
                    # 弹出连线选项对话框
                    reply = QMessageBox.question(None, '连线选项',
                                                 '是否继续连线？\n选择"是"继续连线（暂不设置分值），\n选择"否"设置分值并完成连线',
                                                 QMessageBox.Yes | QMessageBox.No, QMessageBox.No)

                    if reply == QMessageBox.Yes:
                        # 继续连线模式，创建没有分值的连线
                        wire = WireItem(self.temp_start, item, score=0, scene=self)
                        self.add_wire(wire)
                        # 保持当前触点为新的起点，继续连线
                        self.temp_start.setBrush(QBrush(QColor("yellow")))
                        self.temp_start = item
                        item.setBrush(QBrush(QColor("red")))
                    else:
                        # 设置分值并完成连线模式
                        score, ok = QInputDialog.getInt(None, "设置分值", "请输入本次连线的分值：", value=0)
                        if ok:
                            # 创建最后一条连线
                            wire = WireItem(self.temp_start, item, score=score, scene=self)
                            self.add_wire(wire)
                            # 立即将这一组导线规则写入rule1.json文件
                            self.export_current_rules_to_json()
                        # 完成连线，重置选择状态
                        self.temp_start.setBrush(QBrush(QColor("yellow")))
                        self.temp_start = None
                        self.active_group_id = None
        else:
            if self.temp_start:
                self.temp_start.setBrush(QBrush(QColor("yellow")))
                self.temp_start = None
                self.active_group_id = None
        super().mousePressEvent(event)

    def update_all_wires(self):
        for wire in self.wires:
            wire.update_position()

    def export_csv(self, filename):
        # 检查文件扩展名，如果是json则使用JSON格式导出
        if filename.lower().endswith('.json'):
            export_rules_to_json(self.wires, filename)
        else:
            # 保持原有的CSV格式导出功能
            with open(filename, "w", newline='', encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(["起点", "终点", "分值"])
                for wire in self.wires:
                    writer.writerow([wire.start_item.name, wire.end_item.name, wire.score])

    def export_current_rules_to_json(self):
        # 将当前的所有连线规则导出到指定的rule1.json文件
        rule_file = "d:\\videoProject\\data\\rules\\rule1.json"
        export_rules_to_json(self.wires, rule_file)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("电路配盘仿真UI")
        self.resize(1000, 700)
        self.scene = PanelScene()
        self.view = QGraphicsView(self.scene)
        self.view.setRenderHint(QPainter.Antialiasing)
        # 使用说明
        usage = (
            "使用说明：\n"
            "1. 连线：依次点击两个触点可生成连线，选择'继续连线'可连接多个触点，\n"
            "   选择'设置分值'完成一组连线并设置分值。\n"
            "2. 删除连线：左键选中连线后，右键点击连线，选择'删除连线'。\n"
            "3. 修改分值：左键选中连线后，右键点击连线，选择'设置分值'。\n"
            "4. 修改名称：双击元件或触点可修改名称。\n"
            "5. 导出：点击下方'导出连线规则'按钮可导出联系规则为JSON格式。"
        )
        self.usage_label = QLabel(usage)
        self.usage_label.setWordWrap(True)
        self.usage_label.setStyleSheet("color: #333366; font-size: 14px; margin: 6px;")
        export_btn = QPushButton("导出连线规则")
        export_btn.clicked.connect(self.export_csv)
        layout = QVBoxLayout()
        layout.addWidget(self.usage_label)
        layout.addWidget(self.view)
        layout.addWidget(export_btn)
        container = QWidget()
        container.setLayout(layout)
        self.setCentralWidget(container)

    def export_csv(self):
        # 设置默认保存路径为相对路径
        default_path = "data\\rules\\rule1.json"
        filename, _ = QFileDialog.getSaveFileName(self, "导出联系规则", default_path,
                                                  "JSON Files (*.json);;CSV Files (*.csv)")
        if filename:
            self.scene.export_csv(filename)

    # 移除了评测和得分功能


if __name__ == "__main__":
    app = QApplication(sys.argv)
    win = MainWindow()
    win.show()
    sys.exit(app.exec_())