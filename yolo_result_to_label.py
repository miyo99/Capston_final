# yolo_result_to_label.py
# 감지된 YOLO 결과를 기반으로 자동 라벨링 + train/val 분리 스크립트

import os
import shutil
import numpy as np
import random
from ultralytics import YOLO
from PIL import Image

# 경로 설정 (원하는 경로로 수정)
IMG_INPUT_DIR = "dataset/images/train"  # 원본 이미지 위치
LABEL_OUTPUT_DIR = "dataset/labels/train"  # 라벨 위치

# 최종 분리 대상 경로
FINAL_IMAGE_DIR = "dataset/images/val"  # 이미지 저장 최종 경로
FINAL_LABEL_DIR = "dataset/labels/val"  # 라벨 저장 최종 경로

# YOLO 모델 설정
yolo_model = YOLO("yolov8n-seg.pt")
CONF_THRESHOLD = 0.10
IOU_THRESHOLD = 0.3

# val 분할 비율
VAL_RATIO = 0.2

def convert_to_yolo_format(points, img_w, img_h):
    normalized = []
    for x, y in points:
        nx = x / img_w
        ny = y / img_h
        normalized.extend([nx, ny])
    return normalized

def auto_label_images():
    image_files = [f for f in os.listdir(IMG_INPUT_DIR) if f.lower().endswith((".jpg", ".jpeg", ".png"))]

    for image_name in image_files:
        image_path = os.path.join(IMG_INPUT_DIR, image_name)
        label_path = os.path.join(LABEL_OUTPUT_DIR, os.path.splitext(image_name)[0] + ".txt")

        print(f"🔍 감지 중: {image_name}")
        results = yolo_model(image_path, conf=CONF_THRESHOLD, iou=IOU_THRESHOLD)

        img = Image.open(image_path)
        img_w, img_h = img.size

        yolo_lines = []
        for r in results:
            if r.masks is None:
                continue
            for mask in r.masks.xy:
                points = np.array(mask, dtype=np.float32)
                yolo_seg = convert_to_yolo_format(points, img_w, img_h)
                line = "0 " + " ".join([f"{p:.6f}" for p in yolo_seg])
                yolo_lines.append(line)

        with open(label_path, 'w', encoding='utf-8') as f:
            f.write("\n".join(yolo_lines))

        print(f"✅ 저장됨 → {label_path}")

    print("🎯 자동 라벨링 완료!")

def split_train_val():
    image_files = [f for f in os.listdir(IMG_INPUT_DIR) if f.lower().endswith((".jpg", ".jpeg", ".png"))]
    random.shuffle(image_files)

    val_count = int(len(image_files) * VAL_RATIO)
    val_images = image_files[:val_count]

    print(f"🔄 총 {len(image_files)}장 중 {val_count}장 val로 이동")

    for img_file in val_images:
        name, _ = os.path.splitext(img_file)
        label_file = name + ".txt"

        # 이미지 이동
        src_img = os.path.join(IMG_INPUT_DIR, img_file)
        dst_img = os.path.join(FINAL_IMAGE_DIR, img_file)
        shutil.move(src_img, dst_img)

        # 라벨 이동
        src_label = os.path.join(LABEL_OUTPUT_DIR, label_file)
        dst_label = os.path.join(FINAL_LABEL_DIR, label_file)
        if os.path.exists(src_label):
            shutil.move(src_label, dst_label)
        else:
            print(f"⚠️ 라벨 없음: {label_file}")

    print(" train/val 분할 완료!")

def main():
    # 라벨링 먼저 실행
    auto_label_images()

    # 그 후 train/val 분리 실행
    split_train_val()

if __name__ == "__main__":
    main()
