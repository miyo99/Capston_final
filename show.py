import cv2
import os

# 설정
IMG_DIR = "dataset/images/train"
LABEL_DIR = "dataset/labels/train"

def draw_yolo_segmentation(img_path, label_path):
    img = cv2.imread(img_path)
    h, w = img.shape[:2]

    if not os.path.exists(label_path):
        print(f"❌ 라벨 파일 없음: {label_path}")
        return img

    with open(label_path, 'r') as f:
        for line in f.readlines():
            parts = line.strip().split()
            if len(parts) < 3: continue  # 점 데이터가 부족하면 스킵

            # 세그멘테이션 좌표 추출
            class_id = int(parts[0])
            points = list(map(float, parts[1:]))
            xy_pairs = [(int(points[i] * w), int(points[i+1] * h)) for i in range(0, len(points), 2)]

            # 윤곽선 그리기
            for i in range(len(xy_pairs)):
                pt1 = xy_pairs[i]
                pt2 = xy_pairs[(i+1) % len(xy_pairs)]
                cv2.line(img, pt1, pt2, (0, 255, 0), 2)

    return img

def main():
    image_files = [f for f in os.listdir(IMG_DIR) if f.lower().endswith((".jpg", ".jpeg", ".png"))]

    for image_name in image_files:
        img_path = os.path.join(IMG_DIR, image_name)
        label_path = os.path.join(LABEL_DIR, os.path.splitext(image_name)[0] + ".txt")

        print(f"🔍 확인 중: {image_name}")
        img_with_label = draw_yolo_segmentation(img_path, label_path)

        cv2.imshow("YOLO 라벨 미리보기", img_with_label)
        key = cv2.waitKey(0)

        if key == ord('q'):  # 'q' 키 누르면 종료
            break

    cv2.destroyAllWindows()

if __name__ == "__main__":
    main()
