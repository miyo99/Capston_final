import sqlite3
import os
from datetime import datetime

DB_PATH = os.path.join("db", "crack_detection.db")
os.makedirs("db", exist_ok=True)

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS crack_images (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            image_path TEXT NOT NULL,
            timestamp TEXT NOT NULL,
            detected_crack INTEGER NOT NULL,
            yolo_conf REAL,
            opencv_conf REAL,
            risk_level INTEGER DEFAULT 1,
            risk_desc TEXT,
            upload_status INTEGER DEFAULT 0
        )
    ''')
    conn.commit()
    conn.close()

def insert_image(image_path, detected_crack, yolo_conf, opencv_conf, risk_level, risk_desc, upload_status=0):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO crack_images (
            image_path, timestamp, detected_crack,
            yolo_conf, opencv_conf,
            risk_level, risk_desc, upload_status
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        image_path,
        datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        int(detected_crack),
        yolo_conf,
        opencv_conf,
        risk_level,
        risk_desc,
        upload_status
    ))
    conn.commit()
    conn.close()

def fetch_risk_data():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('SELECT image_path, risk_level, risk_desc FROM crack_images')
    data = cursor.fetchall()
    conn.close()
    return {os.path.basename(row[0]): {"level": row[1], "desc": row[2]} for row in data}