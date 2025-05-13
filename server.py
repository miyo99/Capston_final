from fastapi import FastAPI, Request
from PIL import Image
import io
import os
import shutil

app = FastAPI()

#  기존 디렉토리 유지
POST_DIR = "C:/Users/corge/flask/DashBoard_test/dataset/post"
TEST_DIR = "C:/Users/corge/flask/DashBoard_test/dataset/test"

@app.post("/image")
async def create_item(request: Request):
    # 1. 바디에서 바이트스트링 읽기
    body_bytes = await request.body()

    try:
        # 2. 바이트스트림 → 이미지 변환
        image = Image.open(io.BytesIO(body_bytes))

        # 3. post 폴더에 임시 저장
        temp_path = os.path.join(POST_DIR, "temp.jpg")
        image.save(temp_path)

        # 4. test 폴더에 넘버링된 이름 만들기
        existing_files = [f for f in os.listdir(TEST_DIR) if f.endswith(".jpg")]
        numbers = [int(f.split('.')[0]) for f in existing_files if f.split('.')[0].isdigit()]
        next_num = max(numbers) + 1 if numbers else 1
        filename = f"{str(next_num).zfill(5)}.jpg"

        # 5. 이동 + 최종 저장
        final_path = os.path.join(TEST_DIR, filename)
        shutil.move(temp_path, final_path)

        return {"message": "이미지 저장 성공!", "filename": f"dataset/test/{filename}"}

    except Exception as e:
        return {"error": "이미지 저장 실패", "detail": str(e)}
