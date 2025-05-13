from flask import Flask, render_template, send_from_directory
from db.db_insert import fetch_risk_data
from collections import Counter
# from pyngrok import ngrok
import os
import re

app = Flask(__name__)

# 이미지 저장 경로
RESULT_FOLDER = "dataset/results"
os.makedirs(RESULT_FOLDER, exist_ok=True)

# 숫자가 포함된 파일 정렬 함수
def sorted_numerically(files):
    return sorted(files, key=lambda x: int(re.findall(r'\d+', x)[0]) if re.findall(r'\d+', x) else x)

# 이미지 파일 목록 가져오기 (정렬 포함)
def get_files(folder):
    if os.path.exists(folder) and os.path.isdir(folder):
        files = [img for img in os.listdir(folder) if img.endswith(('.jpg', '.png', '.jpeg'))]
        return sorted_numerically(files)  # 숫자 기준으로 정렬
    return []

@app.route("/")
def home():
    result_images = get_files(RESULT_FOLDER)
    danger_levels = fetch_risk_data()

    # 위험도 높은 순으로 정렬
    result_images.sort(key=lambda img: danger_levels.get(img, {}).get("level", 0), reverse=True)

    # ✅ 위험도 분포 집계
    levels = [danger_levels[img]["level"] for img in result_images if img in danger_levels]
    level_counts = Counter(levels)
    
    # Chart.js에 넘길 순서 맞춰 정리
    risk_distribution = [level_counts.get(i, 0) for i in range(1, 6)]  # 1~5 위험도

    return render_template(
        "index.html",
        result_images=result_images,
        danger_levels=danger_levels,
        risk_distribution=risk_distribution
    )
    
# 업로드된 이미지 제공
@app.route("/results/<filename>")
def uploaded_file(filename):
    return send_from_directory(RESULT_FOLDER, filename)

if __name__ == "__main__":
    
    app.run(debug=True)
