import os
import time
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from crack_detection import detect_crack_with_yolo
from db.db_insert import insert_raw_image, insert_results_image, insert_backup  # ⬅️ DB 연동 함수 가져오기

IMAGE_FOLDER = os.path.join("dataset", "test")
RESULT_FOLDER = os.path.join("dataset", "results")
os.makedirs(RESULT_FOLDER, exist_ok=True)

class ImageHandler(FileSystemEventHandler):
    def on_created(self, event):
        if event.is_directory:
            return
        if event.src_path.endswith(('.jpg', '.png', '.jpeg')):
            time.sleep(5)
            filename = os.path.basename(event.src_path)
            print(f"🆕 새로운 이미지 감지됨: {filename} → 원본 저장 및 분석 시작")

            # ✅ 1. 원본 DB 저장
            raw_id = insert_raw_image(filename, event.src_path)

            # ✅ 2. 분석
            output_path = os.path.join(RESULT_FOLDER, f"{os.path.splitext(filename)[0]}_detected.jpg")
            result = detect_crack_with_yolo(event.src_path, output_path)

            if result:  # 분석 성공 시만 기록
                results_id = insert_results_image(
                    raw_id=raw_id,
                    results_path=output_path,
                    yolo_conf=result["yolo_conf"],
                    opencv_conf=result["opencv_conf"],
                    risk_level=result["risk_level"],
                    risk_desc=result["risk_desc"],
                    detected=result["detected"]
                )
                
                insert_backup(raw_id, results_id, note="자동 분석 백업")

def start_watching():
    event_handler = ImageHandler()
    observer = Observer()
    observer.schedule(event_handler, path=IMAGE_FOLDER, recursive=False)
    observer.start()
    print(f"📂 {IMAGE_FOLDER} 폴더를 실시간 감시 중...")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()

if __name__ == "__main__":
    start_watching()
