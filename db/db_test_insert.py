from db.db_insert import insert_raw_image, insert_results_image, insert_backup
from pathlib import Path

# 1. 원본 이미지 업로드 시
file_path = Path("dataset/test/00001.jpg")

if file_path.exists():
    raw_id = insert_raw_image(file_path.name, str(file_path))
    print("✅ 파일 존재 → DB 저장 완료")
else:
    print("❌ 파일이 존재하지 않아서 저장하지 않음")

# 2. 감지/분석 완료 후
results_id = insert_results_image(
    raw_id=raw_id,
    results_path="results/00001_detected.jpg",
    yolo_conf=0.87,
    opencv_conf=0.31,
    risk_level=3,
    risk_desc="주의",
    detected=True
)
print(f"✅ Results inserted with ID: {results_id}")

# 3. 백업 저장
insert_backup(raw_id, results_id, note="자동 분석 백업")
print("💾 Backup insert 완료!")

