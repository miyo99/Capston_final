# main.py
import multiprocessing
import time
import os

def run_web():
    os.system("python app.py")

def run_watcher():
    os.system("python file_watcher.py")
    
def run_server():
    os.system("python server.py")

if __name__ == "__main__":
    web_proc = multiprocessing.Process(target=run_web)
    watcher_proc = multiprocessing.Process(target=run_watcher)
    server_proc = multiprocessing.Process(target=run_server)

    web_proc.start()
    watcher_proc.start()
    server_proc.start()

    print("🚀 Flask 웹 서버와 Watchdog을 동시에 실행 중...")

    web_proc.join()
    watcher_proc.join()
    server_proc.join()
