import os
import cv2
import numpy as np
from ultralytics import YOLO
from db import insert_image, init_db

# 모델 및 폴더 설정
model = YOLO("yolov8n-seg.pt")
DATASET_FOLDER = "dataset"
RESULT_FOLDER = os.path.join(DATASET_FOLDER, "results")
os.makedirs(RESULT_FOLDER, exist_ok=True)
init_db()

def detect_crack_opencv(image_path):
    image = cv2.imread(image_path, cv2.IMREAD_GRAYSCALE)
    blurred = cv2.GaussianBlur(image, (5, 5), 0)
    edges = cv2.Canny(blurred, 50, 150)
    thresh = cv2.adaptiveThreshold(edges, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 11, 2)
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

def calculate_risk_level(length, width):
    if length < 20 and width < 3:
        return 1, "양호"
    elif length < 50 and width < 5:
        return 2, "경미"
    elif length < 100 and width < 10:
        return 3, "주의"
    elif length < 200 and width < 15:
        return 4, "심각"
    else:
        return 5, "위험"

def detect_crack_with_yolo(image_path, output_path):
    contours = detect_crack_opencv(image_path)
    color_image = cv2.imread(image_path)
    yolo_conf = 0.0
    detected_crack = False

    if len(contours) > 0:
        print(f"🔍 OpenCV 감지 완료: 크랙 영역 {len(contours)}개 → YOLO 실행")
        detected_crack = True
        results = model(image_path, conf=0.01, iou=0.1)

        for result in results:
            if len(result.boxes) > 0:
                yolo_conf = float(result.boxes.conf[0])

            for box in result.boxes:
                class_id = int(box.cls[0].item())
                x_center, y_center, width, height = box.xywhn[0].tolist()
                h, w, _ = color_image.shape
                x_min = int((x_center - width / 2) * w)
                y_min = int((y_center - height / 2) * h)
                x_max = int((x_center + width / 2) * w)
                y_max = int((y_center + height / 2) * h)
                cv2.rectangle(color_image, (x_min, y_min), (x_max, y_max), (0, 255, 0), 2)
                cv2.putText(color_image, f"Crack {class_id}", (x_min, y_min - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)

            if result.masks is not None:
                for mask in result.masks.xy:
                    mask = np.array(mask, dtype=np.int32)
                    cv2.polylines(color_image, [mask], isClosed=True, color=(0, 0, 255), thickness=2)
    else:
        print(f"❌ OpenCV 감지 실패: 크랙을 찾지 못함 → YOLO 실행 안 함")

    cv2.drawContours(color_image, contours, -1, (255, 0, 0), 1)
    cv2.imwrite(output_path, color_image)
    print(f"✅ 크랙 감지 완료 → 저장 경로: {output_path}")

    length, width = analyze_crack_size(contours)
    risk_level, risk_desc = calculate_risk_level(length, width)

    insert_image(
        image_path=output_path,
        detected_crack=detected_crack,
        yolo_conf=yolo_conf,
        opencv_conf=len(contours) / 100.0,
        risk_level=risk_level,
        risk_desc=risk_desc
    )