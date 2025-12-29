# -- coding: utf-8 --
import cv2
import threading
import time
import numpy as np
from ultralytics import YOLO
from tools.Python.MvImport.MvCameraControl_class import *
import global_config as config

# 模型路径
MODEL_PATH = config.Global_Config.Hand_and_switch

# Switch ROI 坐标（空气开关区域）
x1_s, y1_s = 137, 268
x2_s, y2_s = 734, 837

# 置信度阈值
CONF_THRESHOLD = 0.4

# 全局变量
current_frame = None
frame_lock = threading.Lock()
stop_flag = False

# 加载模型
model = YOLO(MODEL_PATH)

# ====================== 海康工业相机采集线程 ======================
def capture_thread():
    """使用海康工业相机实时取帧"""
    global current_frame, stop_flag

    # 初始化 SDK
    MvCamera.MV_CC_Initialize()

    deviceList = MV_CC_DEVICE_INFO_LIST()
    tlayerType = (MV_GIGE_DEVICE | MV_USB_DEVICE)
    ret = MvCamera.MV_CC_EnumDevices(tlayerType, deviceList)
    if ret != 0 or deviceList.nDeviceNum == 0:
        print("[ERROR] 未检测到海康工业相机！")
        stop_flag = True
        return

    # 默认使用第 0 号设备
    stDeviceList = cast(deviceList.pDeviceInfo[0], POINTER(MV_CC_DEVICE_INFO)).contents
    cam = MvCamera()

    ret = cam.MV_CC_CreateHandle(stDeviceList)
    if ret != 0:
        print("[ERROR] 创建句柄失败！")
        stop_flag = True
        return

    ret = cam.MV_CC_OpenDevice(MV_ACCESS_Exclusive, 0)
    if ret != 0:
        print("[ERROR] 打开设备失败！")
        stop_flag = True
        return

    # 设置连续采集
    cam.MV_CC_SetEnumValue("TriggerMode", MV_TRIGGER_MODE_OFF)
    cam.MV_CC_StartGrabbing()

    print("[INFO] 海康工业相机开始取流...")

    stOutFrame = MV_FRAME_OUT()
    memset(byref(stOutFrame), 0, sizeof(stOutFrame))

    while not stop_flag:
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
            with frame_lock:
                current_frame = frame

        cam.MV_CC_FreeImageBuffer(stOutFrame)

    # 停止取流
    cam.MV_CC_StopGrabbing()
    cam.MV_CC_CloseDevice()
    cam.MV_CC_DestroyHandle()
    MvCamera.MV_CC_Finalize()
    print("[INFO] 海康相机线程退出")

# ====================== 主检测循环 ======================
# 启动取帧线程
threading.Thread(target=capture_thread, daemon=True).start()

prev_time = time.time()
hand_alarm_triggered = False
prev_hand_detected = False
hand_alert_count = 0
save_path = config.Global_Config.live_capture_path

while not stop_flag:
    with frame_lock:
        if current_frame is None:
            time.sleep(0.05)
            continue
        frame = current_frame.copy()

    # ========== 检测空气开关状态 ==========
    switch_roi = frame[y1_s:y2_s, x1_s:x2_s]
    results_switch = model(switch_roi, agnostic_nms=True, verbose=False)[0]
    switch_detected = None

    for box in results_switch.boxes:
        conf = float(box.conf.item())
        if conf < CONF_THRESHOLD:
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
        switch_state = 'ON' if switch_detected else 'OFF'

    # ========== 检测手掌 ==========
    results_hand = model(frame, agnostic_nms=True, verbose=False)[0]
    hand_detected = False
    for box in results_hand.boxes:
        conf = float(box.conf.item())
        if conf < CONF_THRESHOLD:
            continue
        cls_id = int(box.cls.cpu())
        cls_name = results_hand.names[cls_id]
        if cls_name == 'hand':
            hand_detected = True
            break

    # ========== 报警逻辑 ==========
    if switch_state == 'ON' and hand_detected and not hand_alarm_triggered:
        hand_alert_count += 1
        print(f"[ALERT] 非法操作报警次数: {hand_alert_count}")
        hand_alarm_triggered = True

    if not hand_detected:
        hand_alarm_triggered = False

    if prev_hand_detected and not hand_detected:
        cv2.imwrite(save_path, frame)
        print(f"[INFO] 手掌消失，截图保存: {save_path}")

    prev_hand_detected = hand_detected

    # 计算FPS
    current_time = time.time()
    fps = 1.0 / max(1e-6, current_time - prev_time)
    prev_time = current_time
    print(f"Switch: {switch_state}, Hand: {hand_detected}, FPS: {fps:.1f}")

    time.sleep(0.05)

stop_flag = True
