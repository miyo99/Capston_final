import os
import time
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from crack_detection import detect_crack_with_yolo

IMAGE_FOLDER = os.path.join("dataset", "test")
RESULT_FOLDER = os.path.join("dataset", "results")
os.makedirs(RESULT_FOLDER, exist_ok=True)

class ImageHandler(FileSystemEventHandler):
    def on_created(self, event):
        if event.is_directory:
            return
        if event.src_path.endswith(('.jpg', '.png', '.jpeg')):
            time.sleep(1)
            filename = os.path.basename(event.src_path)
            output_path = os.path.join(RESULT_FOLDER, filename)
            print(f"🆕 새로운 이미지 감지됨: {filename} → 분석 시작")
            detect_crack_with_yolo(event.src_path, output_path)

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
