import cv2
import threading
import time
from dataclasses import dataclass
from typing import Optional, Callable
from ultralytics import YOLO
from script.split import split_image_by_regions
from script.detect_contact import detect_and_save
from script.merge_result import merge_txt_files
from global_config import Global_Config
from tools.Python.MvImport.MvCameraControl_class import *
from script.compare_csv import validate_and_move_files
from script.update_contact import update_connected_components
from script.calculateScore import match_subgraphs
import numpy as np

# ========= 你原先程序里的可配置项 =========
MODEL_PATH = Global_Config.Hand_and_switch

# 空气开关 ROI
x1_s, y1_s = 137, 268
x2_s, y2_s = 734, 837

# 置信度阈值
CONF_THRESHOLD = 0.6

# 截图保存路径（手掌消失瞬间）
SAVE_PATH = Global_Config.live_capture_path


# ========================================


@dataclass
class VisionStatus:
    switch_state: str  # 'ON' / 'OFF' / 'UNKNOWN'
    hand_detected: bool
    hand_alert_count: int
    fps: float
    last_snapshot_path: Optional[str] = None
    ts: float = 0.0  # 单调时钟时间戳


class YoloDetector:
    """将原先 while 循环封为可 start/stop 的检测器"""

    def __init__(
            self,
            model_path: str = MODEL_PATH,
            conf_thres: float = CONF_THRESHOLD,
            roi: tuple = (x1_s, y1_s, x2_s, y2_s),
            on_update: Optional[Callable[[VisionStatus], None]] = None
    ):
        self.model = YOLO(model_path)
        self.conf_thres = conf_thres
        self.roi = roi
        self.on_update = on_update

        self._cap = None
        self._frame = None
        self._frame_lock = threading.Lock()
        self._stop = threading.Event()

        self._t_cap: Optional[threading.Thread] = None
        self._t_loop: Optional[threading.Thread] = None

        # 状态量（延续你原先的逻辑）
        self._prev_time = time.monotonic()
        self._hand_alarm_triggered = False
        self._prev_hand_detected = False
        self._hand_alert_count = 0
        self._last_snapshot_path: Optional[str] = None

        # 手掌消失计时相关
        self._hand_absent_since: Optional[float] = None  # 手掌开始“完全消失”的时间
        self._snapshot_done_this_absence: bool = False  # 当前这次“消失周期”是否已经截过图

    # =============== 公共接口 ===============
    def start(self, blocking: bool = False):
        """启动采集与检测线程；与 app-backup.py 的约定兼容"""
        if self._t_cap or self._t_loop:
            return self  # 已启动

        # 采集线程
        self._t_cap = threading.Thread(target=self._capture_worker, daemon=True)
        self._t_cap.start()
        # 检测线程
        self._t_loop = threading.Thread(target=self._detect_worker, daemon=True)
        self._t_loop.start()

        if blocking:
            self._t_loop.join()
        return self

    def stop_detection(self):
        """供 app-backup.py 调用的停止方法"""
        self._stop.set()
        # 等待线程退出
        if self._t_cap:
            self._t_cap.join(timeout=5)
        if self._t_loop:
            self._t_loop.join(timeout=5)
        # 释放资源
        if self._cap:
            try:
                self._cap.release()
            except Exception:
                pass

    # =============== 内部线程 ===============
    def _capture_worker(self):
        """使用海康工业相机取帧"""
        # 初始化 SDK
        MvCamera.MV_CC_Initialize()

        deviceList = MV_CC_DEVICE_INFO_LIST()
        tlayerType = (MV_GIGE_DEVICE | MV_USB_DEVICE)
        ret = MvCamera.MV_CC_EnumDevices(tlayerType, deviceList)
        if ret != 0 or deviceList.nDeviceNum == 0:
            print("[ERROR] 未检测到海康工业相机！")
            self._stop.set()
            return

        # 默认选择第 0 号设备
        stDeviceList = cast(deviceList.pDeviceInfo[0], POINTER(MV_CC_DEVICE_INFO)).contents
        cam = MvCamera()

        ret = cam.MV_CC_CreateHandle(stDeviceList)
        if ret != 0:
            print("[ERROR] 创建相机句柄失败！")
            self._stop.set()
            return

        ret = cam.MV_CC_OpenDevice(MV_ACCESS_Exclusive, 0)
        if ret != 0:
            print("[ERROR] 打开相机失败！")
            self._stop.set()
            return

        # 设置为连续采集模式
        cam.MV_CC_SetEnumValue("TriggerMode", MV_TRIGGER_MODE_OFF)
        cam.MV_CC_StartGrabbing()

        print("[INFO] 海康工业相机取流中... 按 stop_detection 停止")

        stOutFrame = MV_FRAME_OUT()
        memset(byref(stOutFrame), 0, sizeof(stOutFrame))

        while not self._stop.is_set():
            ret = cam.MV_CC_GetImageBuffer(stOutFrame, 1000)
            if ret != 0 or stOutFrame.pBufAddr is None:
                continue

            # 图像转换
            stConvertParam = MV_CC_PIXEL_CONVERT_PARAM_EX()
            memset(byref(stConvertParam), 0, sizeof(stConvertParam))
            stConvertParam.pSrcData = stOutFrame.pBufAddr
            stConvertParam.nSrcDataLen = stOutFrame.stFrameInfo.nFrameLen
            stConvertParam.enSrcPixelType = stOutFrame.stFrameInfo.enPixelType
            stConvertParam.nWidth = stOutFrame.stFrameInfo.nWidth
            stConvertParam.nHeight = stOutFrame.stFrameInfo.nHeight
            stConvertParam.enDstPixelType = PixelType_Gvsp_RGB8_Packed

            buf_size = stOutFrame.stFrameInfo.nWidth * stOutFrame.stFrameInfo.nHeight * 3
            DstBuffer = (c_ubyte * buf_size)()
            stConvertParam.pDstBuffer = DstBuffer
            stConvertParam.nDstBufferSize = buf_size

            ret = cam.MV_CC_ConvertPixelTypeEx(stConvertParam)
            if ret == 0:
                frame = np.frombuffer(DstBuffer, dtype=np.uint8).reshape(
                    stOutFrame.stFrameInfo.nHeight, stOutFrame.stFrameInfo.nWidth, 3
                )
                frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)

                with self._frame_lock:
                    self._frame = frame

            cam.MV_CC_FreeImageBuffer(stOutFrame)

        # 停止取流并释放资源
        cam.MV_CC_StopGrabbing()
        cam.MV_CC_CloseDevice()
        cam.MV_CC_DestroyHandle()
        MvCamera.MV_CC_Finalize()
        print("[INFO] 海康相机线程退出")

    def _detect_worker(self):
        while not self._stop.is_set():
            with self._frame_lock:
                frame = None if self._frame is None else self._frame.copy()
            if frame is None:
                time.sleep(0.02)
                continue

            now = time.monotonic()  # 当前帧时间，用于计时和 FPS

            x1, y1, x2, y2 = self.roi
            switch_roi = frame[y1:y2, x1:x2]

            # 1) 空气开关 ROI 检测
            results_switch = self.model(switch_roi, agnostic_nms=True, verbose=False)[0]
            switch_detected = None  # True: on, False: off, None: unknown

            for box in results_switch.boxes:
                conf = float(box.conf.item())
                if conf < self.conf_thres:
                    continue
                cls_id = int(box.cls.cpu())
                cls_name = results_switch.names[cls_id]
                if cls_name == 'switch-on':
                    switch_detected = True
                elif cls_name == 'switch-off':
                    switch_detected = False

            if switch_detected is None:
                switch_state = 'UNKNOWN'
            else:
                switch_state = True if switch_detected else False
                # 更新空气开关状态
                Global_Config.switch_status = switch_state
                print("空气开关状态:" + str(Global_Config.switch_status))

            # 2) 全图手掌检测
            results_hand = self.model(frame, agnostic_nms=True, verbose=False)[0]
            hand_detected = False
            for box in results_hand.boxes:
                conf = float(box.conf.item())
                if conf < self.conf_thres:
                    continue
                cls_id = int(box.cls.cpu())
                cls_name = results_hand.names[cls_id]
                if cls_name == 'hand':
                    hand_detected = True
                    break

            # 报警节流：开关 ON + 首次出现手掌 -> 计数+1
            if switch_state == True and hand_detected and not self._hand_alarm_triggered:
                self._hand_alert_count += 1
                print(f"[ALERT] 非法操作报警次数：{self._hand_alert_count}")
                Global_Config.error_wiring_count = self._hand_alert_count
                print("全局变量:" + str(Global_Config.error_wiring_count))
                self._hand_alarm_triggered = True

            # 手掌完全消失 -> 允许下一次报警
            if not hand_detected:
                self._hand_alarm_triggered = False

            # ====== 手掌“完全消失 1s 后”再截图 ======
            if hand_detected:
                # 一旦再次检测到手掌，重置“消失周期”
                self._hand_absent_since = None
                self._snapshot_done_this_absence = False
            else:
                # 本帧没有检测到手掌
                if self._prev_hand_detected:
                    # 刚从“有手”变成“无手”的这一帧，记录起始时间
                    self._hand_absent_since = now
                    self._snapshot_done_this_absence = False

                # 如果已经连续“无手”一段时间，且当前这个“消失周期”还没截过图
                if (
                        self._hand_absent_since is not None
                        and not self._snapshot_done_this_absence
                        and (now - self._hand_absent_since) >= 0.5  # 这里控制等待时间，单位秒
                ):
                    try:
                        cv2.imwrite(SAVE_PATH, frame)
                        self._last_snapshot_path = SAVE_PATH
                        self._snapshot_done_this_absence = True
                        #保存一张副本
                        ts = time.strftime("%Y%m%d_%H%M%S", time.localtime())
                        hist_path = os.path.join(Global_Config.history_capture_dir,f"hand_gone_{ts}.jpg")
                        cv2.imwrite(hist_path, frame)
                        print(f"[INFO] 手掌消失超过 1s，截图保存：{SAVE_PATH}")

                    ###################################################################################################################################################################################



                    ####################################################################################################################################################################
                    except Exception as e:
                        print(f"[ERROR] 保存截图失败：{e}")

            # FPS
            now = time.monotonic()
            fps = 1.0 / max(1e-6, (now - self._prev_time))
            self._prev_time = now

            # 发布状态
            status = VisionStatus(
                switch_state=switch_state,
                hand_detected=hand_detected,
                hand_alert_count=self._hand_alert_count,
                fps=round(fps, 1),
                last_snapshot_path=self._last_snapshot_path,
                ts=now
            )

            # a) 回调
            if self.on_update:
                try:
                    self.on_update(status)
                except Exception as e:
                    print(f"[WARN] on_update 回调异常：{e}")

            # b) SocketIO 广播（若可用）
            # —— 尝试获取 socketio（若由 app-backup.py 启动，已初始化）——

            # 适度休眠降低 GPU/CPU 压力
            time.sleep(0.5)

            # 更新"上一帧"手掌状态
            self._prev_hand_detected = hand_detected


# ========== 按 app-backup.py 预期暴露的 API ==========
_detector_singleton: Optional[YoloDetector] = None


def start_hand_detection(blocking: bool = False):
    """
    被 app-backup.py 的 DetectionManager 调用：
      detector = start_hand_detection(blocking=False)
    并保存返回的 detector, 以便后续调用 detector.stop_detection()
    """
    global _detector_singleton
    if _detector_singleton is None:
        _detector_singleton = YoloDetector()
        detection_thread = threading.Thread(target=_detector_singleton.start, args=(False,))
        detection_thread.start()
    return _detector_singleton, detection_thread


def stop_hand_detection():
    global _detector_singleton
    if _detector_singleton is not None:
        _detector_singleton.stop_detection()
        _detector_singleton = None