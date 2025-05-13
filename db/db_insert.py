from db.db_core import get_connection
from datetime import datetime
import os


def fetch_risk_data():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute('''
        SELECT results_path, risk_level, risk_desc
        FROM results_images
        ORDER BY id DESC
    ''')
    rows = cur.fetchall()
    conn.close()

    return {
        os.path.basename(path): {
            "level": level,
            "desc": desc
        } for path, level, desc in rows
    }


def insert_raw_image(filename: str, filetext: str):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute('''
        INSERT INTO raw_images (filename, filetext)
        VALUES (%s, %s)
        RETURNING id
    ''', (filename, filetext))
    raw_id = cur.fetchone()[0]
    conn.commit()
    conn.close()
    return raw_id


def insert_results_image(raw_id, results_path, yolo_conf, opencv_conf,
                         risk_level, risk_desc, detected=True):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute('''
        INSERT INTO results_images (
            raw_id, results_path, yolo_conf, opencv_conf,
            risk_level, risk_desc, detected
        ) VALUES (%s, %s, %s, %s, %s, %s, %s)
        RETURNING id
    ''', (
        raw_id, results_path, yolo_conf, opencv_conf,
        risk_level, risk_desc, detected
    ))
    results_id = cur.fetchone()[0]
    conn.commit()
    conn.close()
    return results_id


def insert_backup(raw_id, results_id, note=""):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute('''
        INSERT INTO backup (raw_id, results_id, note)
        VALUES (%s, %s, %s)
    ''', (raw_id, results_id, note))
    conn.commit()
    conn.close()
