import cv2

ref_point = []
cropping = False
scale_ratio = 1.0
original_image = None
display_image = None
clone = None

def click_and_crop(event, x, y, flags, param):
    global ref_point, cropping, display_image, scale_ratio

    if event == cv2.EVENT_LBUTTONDOWN:
        ref_point = [(x, y)]
        cropping = True

    elif event == cv2.EVENT_LBUTTONUP:
        ref_point.append((x, y))
        cropping = False

        cv2.rectangle(display_image, ref_point[0], ref_point[1], (0, 255, 0), 2)
        cv2.imshow("image", display_image)

        x1, y1 = ref_point[0]
        x2, y2 = ref_point[1]

        x1_o, y1_o = int(x1 / scale_ratio), int(y1 / scale_ratio)
        x2_o, y2_o = int(x2 / scale_ratio), int(y2 / scale_ratio)

        pts = [
            (min(x1_o, x2_o), min(y1_o, y2_o)),
            (max(x1_o, x2_o), min(y1_o, y2_o)),
            (min(x1_o, x2_o), max(y1_o, y2_o)),
            (max(x1_o, x2_o), max(y1_o, y2_o)),
        ]

        print("原图矩形四点坐标（左上、右上、左下、右下）：", pts)

def on_trackbar(val):
    global scale_ratio, display_image, clone
    if val < 1:
        val = 1
    scale_ratio = val / 100.0

    new_w = int(original_image.shape[1] * scale_ratio)
    new_h = int(original_image.shape[0] * scale_ratio)
    display_image = cv2.resize(original_image, (new_w, new_h))
    clone = display_image.copy()
    cv2.imshow("image", display_image)

if __name__ == "__main__":
    image_path = "../image/fullscreen.jpg"  # 修改为你的图片路径
    original_image = cv2.imread(image_path)

    if original_image is None:
        print("❌ 图片加载失败，请检查路径")
        exit()

    scale_ratio = 1.0
    display_image = original_image.copy()
    clone = display_image.copy()

    cv2.namedWindow("image", cv2.WINDOW_NORMAL)
    cv2.createTrackbar("缩放比例(%)", "image", 100, 300, on_trackbar)  # 最大放大3倍

    cv2.setMouseCallback("image", click_and_crop)

    print("鼠标拖拽选取矩形区域，按 q 键退出，按 r 键重置")

    while True:
        cv2.imshow("image", display_image)
        key = cv2.waitKey(1) & 0xFF

        if key == ord("q"):
            break
        elif key == ord("r"):
            display_image = clone.copy()
            print("重置图片，清除绘制")

    cv2.destroyAllWindows()
