import os
import cv2
import numpy as np
from ultralytics import YOLO

# 모델 및 폴더 설정
model = YOLO("runs/segment/King_crack_V4/weights/best.pt")
DATASET_FOLDER = "dataset/test"
RESULT_FOLDER = os.path.join(DATASET_FOLDER, "results")
CROP_FOLDER = os.path.join(RESULT_FOLDER, "crop") 

def detect_crack_opencv(image_path):
    image = cv2.imread(image_path, cv2.IMREAD_GRAYSCALE)
    blurred = cv2.GaussianBlur(image, (5, 5), 0)
    edges = cv2.Canny(blurred, 50, 150)
    thresh = cv2.adaptiveThreshold(edges, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                   cv2.THRESH_BINARY, 11, 2)
    contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    return contours

def analyze_crack_size(contours):
    max_length = 0
    max_width = 0
    for cnt in contours:
        rect = cv2.minAreaRect(cnt)
        width, height = rect[1]
        length = max(width, height)
        thickness = min(width, height)
        if length > max_length:
            max_length = length
        if thickness > max_width:
            max_width = thickness
    return max_length, max_width

def calculate_risk_level_by_area(contours, image_shape):
    image_area = image_shape[0] * image_shape[1]
    crack_area = sum([cv2.contourArea(cnt) for cnt in contours])
    ratio = crack_area / image_area

    print(f"이미지 면적: {image_area} px²")
    print(f"크랙 전체 면적: {int(crack_area)} px²")
    print(f"면적 비율: {ratio:.4f} ({ratio * 100:.2f}%)")

    if ratio < 0.50:
        return 1, "양호"
    elif ratio < 0.70:
        return 2, "경미"
    elif ratio < 0.85:
        return 3, "주의"
    elif ratio < 0.95:
        return 4, "심각"
    else:
        return 5, "위험"


def detect_crack_with_yolo(image_path, output_path):
    original_image = cv2.imread(image_path)
    yolo_input_image = original_image.copy()
    output_image = original_image.copy()

    yolo_conf = 0.2
    detected_crack = False
    cropped_contour_image = None

    contours = detect_crack_opencv(image_path)

    if contours:
        print(f"🔍 OpenCV 감지 완료: 크랙 영역 {len(contours)}개 → YOLO 실행")
        detected_crack = True

        results = model.predict(source=yolo_input_image, conf=0.05, iou=0.1, save=False, show=False)
        result = results[0]

        if len(result.boxes) > 0:
            yolo_conf = float(result.boxes.conf[0])

        if result.masks is not None:
            for mask in result.masks.xy:
                mask = np.array(mask, dtype=np.int32)
                cv2.polylines(output_image, [mask], isClosed=True, color=(0, 0, 255), thickness=2)

        cv2.drawContours(output_image, contours, -1, (255, 0, 0), 1)


    # ✅ 전체 이미지 저장
    cv2.imwrite(output_path, output_image)
    print(f"✅ 전체 이미지 저장 완료 → {output_path}")

    # ✅ 위험도 분석
    length, width = analyze_crack_size(contours)
    image_shape = output_image.shape
    risk_level, risk_desc = calculate_risk_level_by_area(contours, image_shape)


    return {
        "yolo_conf": yolo_conf,
        "opencv_conf": len(contours) / 100.0,
        "risk_level": risk_level,
        "risk_desc": risk_desc,
        "detected": detected_crack,
        "crop_image_saved": cropped_contour_image is not None
    }
