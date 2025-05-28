import tkinter as tk
from tkinter import messagebox, Label, Button, Frame
from PIL import Image, ImageTk
import picamera2
from picamera2 import Picamera2
from picamera2 import controls # AwbModeEnum 등을 사용하기 위해 임포트
import requests
import os
import time
import datetime
import threading
import cv2
import numpy as np
from gpiozero import Servo
from gpiozero.pins.pigpio import PiGPIOFactory # pigpio 팩토리 명시적 임포트
from concurrent.futures import ThreadPoolExecutor

# --- 설정 변수 ---
SAVE_DIR = "/home/hsb/crack_images_undistorted"
SERVER_URL = "https://50e1-220-89-47-154.ngrok-free.app/image"
PREVIEW_WIDTH = 640
PREVIEW_HEIGHT = 480
CAPTURE_WIDTH = 1920
CAPTURE_HEIGHT = 1080
camera_matrix = np.array([[1000., 0., CAPTURE_WIDTH / 2],
                          [0., 1000., CAPTURE_HEIGHT / 2],
                          [0., 0., 1.]])
distortion_coefficients = np.array([0.1, -0.05, 0.001, 0.001, 0.01])
SERVO_GPIO_PIN = 18
INITIAL_SERVO_VALUE = 0
SERVO_VALUE_STEP = 30 / 90 
MIN_SERVO_VALUE = -0.9
MAX_SERVO_VALUE = 0.9
MIN_PULSE_WIDTH_SERVO = 0.0005 # 0.5ms
MAX_PULSE_WIDTH_SERVO = 0.0025 # 2.5ms

# --- 줌 설정 변수 ---
INITIAL_ZOOM_LEVEL = 1.0
MAX_ZOOM_LEVEL = 4.0
ZOOM_STEP = 1.0

# --- 밝기 설정 변수 ---
INITIAL_BRIGHTNESS = 0.15

# --- 전역 변수 ---
picam2 = None
preview_active = False
last_capture_path = None
capture_config = None
preview_config_global = None
servo_motor = None
current_servo_value = INITIAL_SERVO_VALUE
USE_PIGPIO_FACTORY = True # pigpio 사용을 기본으로 시도 (흔들림 개선에 중요)
factory = None # PiGPIOFactory 객체 저장용
is_closing = False
root = None
status_label = None
current_zoom_level = INITIAL_ZOOM_LEVEL
full_sensor_width = 0
full_sensor_height = 0
zoom_status_label = None
image_file_counter = 0
thread_pool = ThreadPoolExecutor(max_workers=1) 

# --- 함수 정의 ---

def schedule_gui_update(callable_func, *args):
    global is_closing, root
    if is_closing: 
        return
    if root and root.winfo_exists():
        root.after(0, lambda: callable_func(*args))

def update_zoom_display():
    global zoom_status_label, current_zoom_level
    if zoom_status_label and zoom_status_label.winfo_exists():
        zoom_status_label.config(text=f"줌: {current_zoom_level:.2f}x")

def apply_zoom():
    global picam2, current_zoom_level, full_sensor_width, full_sensor_height
    if not picam2 or not picam2.started:
        print("줌 적용 불가: 카메라가 준비되지 않았습니다.")
        return
    if full_sensor_width == 0 or full_sensor_height == 0:
        print("줌 적용 불가: 카메라 센서 크기 정보를 사용할 수 없습니다.")
        cam_props = picam2.camera_properties
        if cam_props and 'PixelArraySize' in cam_props:
            full_sensor_width, full_sensor_height = cam_props['PixelArraySize']
            print(f"  (재시도) 카메라 전체 센서 해상도 확인됨: {full_sensor_width}x{full_sensor_height}")
        else:
            print("  (재시도 실패) 여전히 센서 크기를 알 수 없어 줌 적용 불가.")
            return
    crop_rect = (0,0,0,0) 
    if current_zoom_level < INITIAL_ZOOM_LEVEL:
        current_zoom_level = INITIAL_ZOOM_LEVEL
    print(f"\n--- apply_zoom 호출됨 ---")
    print(f"요청된 줌 레벨: {current_zoom_level:.2f}x")
    print(f"카메라 전체 센서 크기: {full_sensor_width}x{full_sensor_height}")
    if abs(current_zoom_level - INITIAL_ZOOM_LEVEL) < 0.001:
        crop_rect = (0, 0, full_sensor_width, full_sensor_height) 
        print(f"줌 레벨 {INITIAL_ZOOM_LEVEL:.2f}x (기본): ScalerCrop 전체 센서 사용 -> {crop_rect} 요청")
    elif current_zoom_level > INITIAL_ZOOM_LEVEL:
        crop_w = int(full_sensor_width / current_zoom_level)
        crop_h = int(full_sensor_height / current_zoom_level)
        crop_w = max(1, crop_w) 
        crop_h = max(1, crop_h) 
        crop_x = int((full_sensor_width - crop_w) / 2)
        crop_y = int((full_sensor_height - crop_h) / 2)
        crop_rect = (crop_x, crop_y, crop_w, crop_h)
        print(f"줌 레벨 {current_zoom_level:.2f}x: ScalerCrop 계산됨 -> {crop_rect}")
    try:
        picam2.set_controls({"ScalerCrop": crop_rect})
        print(f"  카메라에 ScalerCrop {crop_rect} 설정 요청 완료.")
    except Exception as e:
        print(f"ScalerCrop 설정 중 오류 발생: {e}")
    finally:
        schedule_gui_update(update_zoom_display)
    print(f"--- apply_zoom 종료 ---\n")

def zoom_in():
    global current_zoom_level
    if not picam2 or not picam2.started:
        if root and root.winfo_exists(): messagebox.showwarning("줌 오류", "카메라가 준비되지 않았습니다.")
        return
    current_zoom_level = min(MAX_ZOOM_LEVEL, round(current_zoom_level + ZOOM_STEP, 2))
    apply_zoom()

def zoom_out():
    global current_zoom_level
    if not picam2 or not picam2.started:
        if root and root.winfo_exists(): messagebox.showwarning("줌 오류", "카메라가 준비되지 않았습니다.")
        return
    current_zoom_level = max(INITIAL_ZOOM_LEVEL, round(current_zoom_level - ZOOM_STEP, 2))
    apply_zoom()

def setup_peripherals_gpiozero():
    global servo_motor, current_servo_value, factory
    pin_factory_to_use = None 
    try:
        if USE_PIGPIO_FACTORY:
            try:
                factory = PiGPIOFactory() 
                print("성공: pigpio 팩토리 사용됨. (터미널에서 'sudo systemctl status pigpiod'로 데몬 실행 상태 확인)")
                pin_factory_to_use = factory
            except (ImportError, NameError, OSError, Exception) as e_pigpio: 
                print(f"경고: pigpio 팩토리 초기화 실패 ({type(e_pigpio).__name__}: {e_pigpio}).")
                print("  기본 gpiozero 핀 팩토리(RPi.GPIO 등)를 사용합니다. 서보 모터 흔들림이 발생할 수 있습니다.")
                print("  흔들림 개선을 위해 다음을 확인하세요:")
                print("    1. 'sudo apt install pigpio python3-pigpio'로 pigpio 관련 패키지 설치")
                print("    2. 'sudo systemctl start pigpiod'로 pigpio 데몬 실행")
                print("    3. 'sudo systemctl enable pigpiod'로 부팅 시 자동 실행 설정")
                factory = None 
                pin_factory_to_use = None 
        else:
            print("기본 gpiozero 핀 팩토리(RPi.GPIO 등)를 사용합니다. (USE_PIGPIO_FACTORY=False)")
            factory = None 
            pin_factory_to_use = None

        servo_motor = Servo(
            SERVO_GPIO_PIN, 
            initial_value=INITIAL_SERVO_VALUE, 
            min_pulse_width=MIN_PULSE_WIDTH_SERVO, 
            max_pulse_width=MAX_PULSE_WIDTH_SERVO, 
            pin_factory=pin_factory_to_use 
        )
        current_servo_value = INITIAL_SERVO_VALUE
        # 초기 위치 설정 후 바로 detach 하여 초기 떨림 방지 시도
        if servo_motor:
            print(f"서보 모터 초기화 완료 (GPIO {SERVO_GPIO_PIN}, 초기 값: {current_servo_value})")
            print("  초기 위치 설정 후 detach 시도...")
            time.sleep(0.5) # 모터가 초기 위치로 이동할 시간
            servo_motor.detach()
            print("  초기 detach 완료.")
        return True
    except Exception as e:
        print(f"!!! gpiozero 주변 장치 초기화 중 오류 발생: {type(e).__name__} - {e}")
        if root and root.winfo_exists():
             messagebox.showerror("GPIO 오류", f"주변 장치를 초기화할 수 없습니다: {e}\n(터미널에서 상세 오류를 확인하세요.)")
        else:
            print("GPIO 오류 메시지 박스 표시 실패: root 윈도우가 아직 생성되지 않음.")
        return False

def set_servo_value_gpiozero(value):
    global current_servo_value, servo_motor
    if servo_motor is None:
        print("서보 모터가 초기화되지 않았습니다.")
        return
    
    # gpiozero.Servo는 값을 설정하면 자동으로 펄스를 다시 보내기 시작합니다.
    # 별도의 attach() 호출은 필요 없습니다.
    value = max(MIN_SERVO_VALUE, min(MAX_SERVO_VALUE, value))
    try:
        print(f"서보 값 설정 시도: {value:.3f}")
        servo_motor.value = value
        current_servo_value = servo_motor.value # 실제 적용된 값으로 업데이트
        print(f"서보 값 실제 적용됨: {current_servo_value:.3f}") 
        
        # 모터가 위치에 도달할 시간을 줍니다.
        time.sleep(0.3) # 이 시간 동안은 펄스가 계속 나가서 위치를 유지하려고 함.
        
        # 위치 도달 후 펄스 중단 (떨림 방지)
        if servo_motor: # servo_motor가 None이 아닌지 다시 확인
            print(f"  서보 위치 ({current_servo_value:.3f}) 도달 후 detach 시도...")
            servo_motor.detach() # 펄스 전송 중단
            print(f"  서보 detach 완료.")
            
    except Exception as e:
        print(f"서보 값 설정 또는 detach 중 오류 발생: {e}")


def rotate_camera_left_gpiozero():
    global current_servo_value
    print("왼쪽 회전 버튼 클릭됨")
    new_value = current_servo_value - SERVO_VALUE_STEP
    set_servo_value_gpiozero(new_value)

def rotate_camera_right_gpiozero():
    global current_servo_value
    print("오른쪽 회전 버튼 클릭됨")
    new_value = current_servo_value + SERVO_VALUE_STEP
    set_servo_value_gpiozero(new_value)

def setup_camera():
    global picam2, preview_active, capture_config, preview_config_global, full_sensor_width, full_sensor_height, current_zoom_level, INITIAL_BRIGHTNESS
    try:
        picam2 = Picamera2()
        cam_props = picam2.camera_properties
        if cam_props and 'PixelArraySize' in cam_props:
            full_sensor_width, full_sensor_height = cam_props['PixelArraySize']
            print(f"카메라 전체 센서 해상도 확인됨: {full_sensor_width}x{full_sensor_height}")
        else:
            print("경고: 카메라 전체 센서 해상도를 가져올 수 없습니다. 기본값을 사용합니다.")
            full_sensor_width = 2592 
            full_sensor_height = 1944
        preview_config_global = picam2.create_preview_configuration(
            main={"size": (PREVIEW_WIDTH, PREVIEW_HEIGHT)},
            lores={"size": (PREVIEW_WIDTH // 2, PREVIEW_HEIGHT // 2)},
            display="main"
        )
        picam2.configure(preview_config_global)
        capture_config = picam2.create_still_configuration(
             main={"size": (CAPTURE_WIDTH, CAPTURE_HEIGHT)},
        )
        picam2.start()
        print("AWB 및 AE 안정화 시도 중...")
        try:
            picam2.set_controls({"AwbEnable": True, "AwbMode": controls.AwbModeEnum.Auto, "AeEnable": True})
            time.sleep(1.0) 
            print("AWB 및 AE 안정화 시간 부여 완료.")
        except Exception as e_awb_ae:
            print(f"AWB/AE 설정 중 오류 발생: {e_awb_ae}")
        try:
            picam2.set_controls({"Brightness": INITIAL_BRIGHTNESS})
            print(f"초기 밝기 설정됨: {INITIAL_BRIGHTNESS}")
        except Exception as e_brightness:
            print(f"밝기 설정 중 오류 발생: {e_brightness}")
            print("  (카메라 또는 드라이버가 밝기 조절을 지원하지 않을 수 있습니다.)")
        current_zoom_level = INITIAL_ZOOM_LEVEL 
        apply_zoom() 
        preview_active = True
        print("카메라 시작됨.")
        return True
    except Exception as e:
        print(f"카메라 초기화 오류: {e}")
        if root and root.winfo_exists():
            messagebox.showerror("카메라 오류", f"카메라를 시작할 수 없습니다: {e}")
        return False

def update_preview():
    global preview_active, picam2, root, preview_label
    if not preview_active or not picam2 or not root or not root.winfo_exists():
        return
    try:
        frame = picam2.capture_array("main")
        img_pil = Image.fromarray(frame)
        img_tk = ImageTk.PhotoImage(image=img_pil)
        if preview_label and preview_label.winfo_exists():
            preview_label.imgtk = img_tk
            preview_label.configure(image=img_tk)
        if preview_active and root.winfo_exists():
            root.after(50, update_preview) # 약 20fps
    except Exception as e:
        if preview_active:
            if isinstance(e, RuntimeError) and ("Camera controls cancelled" in str(e) or "no capture request available" in str(e)):
                pass
            elif isinstance(e, ReferenceError) and "weakly-referenced object no longer exists" in str(e):
                print("미리보기 업데이트 중단됨 (GUI 객체 소멸).") 
            else:
                pass 

def undistort_image(img_array, mtx, dist):
    h, w = img_array.shape[:2]
    new_camera_mtx, roi = cv2.getOptimalNewCameraMatrix(mtx, dist, (w, h), 1, (w, h))
    undistorted_img = cv2.undistort(img_array, mtx, dist, None, new_camera_mtx)
    return undistorted_img, new_camera_mtx, roi

def _update_status_label(text_to_set):
    global status_label
    if status_label and status_label.winfo_exists():
        status_label.config(text=text_to_set)

def _show_messagebox_error(title, message):
    global root
    if root and root.winfo_exists():
        messagebox.showerror(title, message)

def upload_to_server(image_bytes, original_filename):
    global SERVER_URL
    if SERVER_URL == "YOUR_SERVER_UPLOAD_URL" or not SERVER_URL or "ngrok-free.app" not in SERVER_URL :
        error_msg = "서버 URL이 올바르게 설정되지 않았습니다!\n코드에서 SERVER_URL 변수를 ngrok 주소로 수정하세요."
        if "ngrok-free.app" not in SERVER_URL and SERVER_URL != "YOUR_SERVER_UPLOAD_URL":
             error_msg = f"현재 SERVER_URL: {SERVER_URL}\nngrok 주소 형식이 아닙니다. 확인해주세요."
        print(f"전송 오류: {error_msg}")
        schedule_gui_update(_update_status_label, f"전송 오류: 서버 URL 확인 필요")
        schedule_gui_update(_show_messagebox_error, "전송 오류", error_msg)
        return

    schedule_gui_update(_update_status_label, f"전송 중: {original_filename}")
    print(f"서버로 이미지 바이트 스트림 전송 시도: {SERVER_URL}")
    headers = {'Content-Type': 'image/jpeg', 'X-Filename': original_filename }
    try:
        response = requests.post(SERVER_URL, data=image_bytes, headers=headers, timeout=60)
        response.raise_for_status()
        print("이미지 바이트 스트림 전송 성공!")
        print(f"서버 응답: {response.text}")
        schedule_gui_update(_update_status_label, f"전송 성공: {original_filename}")
    except requests.exceptions.RequestException as e:
        error_detail = str(e)
        if hasattr(e, 'response') and e.response is not None:
             error_detail = f"{e.response.status_code} {e.response.reason} - {e}"
        print(f"이미지 바이트 스트림 전송 실패: {error_detail}")
        schedule_gui_update(_update_status_label, f"전송 실패: {type(e).__name__}")
        schedule_gui_update(_show_messagebox_error, "전송 오류", f"이미지 전송 중 오류 발생:\n{error_detail}")
    except Exception as e:
        print(f"이미지 바이트 스트림 전송 중 기타 오류 발생: {e}")
        schedule_gui_update(_update_status_label, f"전송 오류: 알 수 없음")
        schedule_gui_update(_show_messagebox_error, "전송 오류", f"이미지 전송 중 알 수 없는 오류 발생:\n{e}")

def process_and_upload_image_task(captured_array_rgb, filename_for_log, filepath_for_log):
    global last_capture_path, camera_matrix, distortion_coefficients
    print(f"백그라운드 작업 시작: {filename_for_log}")
    try:
        schedule_gui_update(_update_status_label, "왜곡 보정 중...")
        print("백그라운드 작업: 이미지 왜곡 보정 시작...")
        undistorted_img_array_rgb, _, _ = undistort_image(captured_array_rgb, camera_matrix, distortion_coefficients)
        print("백그라운드 작업: 왜곡 보정 완료.")
        undistorted_img_array_bgr = cv2.cvtColor(undistorted_img_array_rgb, cv2.COLOR_RGB2BGR)
        schedule_gui_update(_update_status_label, "JPEG 인코딩 중...")
        print(f"백그라운드 작업: 이미지를 JPEG 바이트 스트림으로 인코딩 중...")
        is_success, image_bytes_np_array = cv2.imencode(".jpg", undistorted_img_array_bgr)
        if not is_success:
            raise RuntimeError("이미지를 JPEG 바이트 스트림으로 인코딩하는 데 실패했습니다.")
        image_bytes = image_bytes_np_array.tobytes()
        print("백그라운드 작업: JPEG 바이트 스트림 인코딩 완료.")
        try:
            with open(filepath_for_log, 'wb') as f_log:
                f_log.write(image_bytes)
            print(f"백그라운드 작업: 이미지가 로컬에도 저장됨: {filepath_for_log}")
            last_capture_path = filepath_for_log
            schedule_gui_update(_update_status_label, f"로컬 저장: {filename_for_log}")
        except Exception as e_save_local:
            print(f"백그라운드 작업: 로컬에 이미지 저장 실패: {e_save_local}")
        upload_to_server(image_bytes, filename_for_log)
    except Exception as e:
        print(f"백그라운드 이미지 처리/업로드 작업 중 오류 발생: {type(e).__name__} - {e}")
        schedule_gui_update(_update_status_label, "오류 발생 (백그라운드)")
        schedule_gui_update(_show_messagebox_error, "백그라운드 오류", f"이미지 처리/업로드 중 오류:\n{e}")
    finally:
        print(f"백그라운드 작업 완료: {filename_for_log}")


def capture_and_send():
    global preview_active, capture_config, picam2, preview_config_global, root, status_label, SAVE_DIR, current_servo_value, is_closing, thread_pool, image_file_counter

    if is_closing:
        print("프로그램 종료 중이므로 촬영/전송을 시작할 수 없습니다.")
        return

    if not picam2 or not picam2.started or capture_config is None or preview_config_global is None:
        if root and root.winfo_exists():
            messagebox.showwarning("카메라 오류", "카메라 또는 설정이 준비되지 않았습니다.")
        else:
            print("카메라 오류: 카메라 또는 설정이 준비되지 않음 (GUI 없음)")
        return

    original_preview_active_state = preview_active
    captured_array_rgb = None

    if original_preview_active_state:
        preview_active = False
        if root and root.winfo_exists(): root.update_idletasks() 
        time.sleep(0.05) 

    if status_label and status_label.winfo_exists(): status_label.config(text="촬영 준비 중...")
    if root and root.winfo_exists(): root.update_idletasks()

    try:
        print(f"고해상도 사진 촬영 모드로 전환...")
        if status_label and status_label.winfo_exists(): status_label.config(text="촬영 모드 전환 중...")
        if root and root.winfo_exists(): root.update_idletasks()
        picam2.switch_mode(capture_config)
        # time.sleep(0.1) 

        print(f"고해상도 사진 캡처 (배열)...")
        if status_label and status_label.winfo_exists(): status_label.config(text="고해상도 사진 캡처 중...")
        if root and root.winfo_exists(): root.update_idletasks()
        captured_array_rgb = picam2.capture_array("main")
        print("배열 캡처 완료.")

    except Exception as e_capture:
        print(f"캡처 중 오류 발생: {type(e_capture).__name__} - {e_capture}")
        if status_label and status_label.winfo_exists(): status_label.config(text="캡처 오류")
        if root and root.winfo_exists(): messagebox.showerror("캡처 오류", f"사진 캡처 중 오류:\n{e_capture}")
    finally:
        if not is_closing:
            print("캡처 작업 후 미리보기 모드로 다시 전환 중...")
            if status_label and status_label.winfo_exists(): status_label.config(text="미리보기 복원 중...")
            if root and root.winfo_exists(): root.update_idletasks()
            try:
                if picam2 and picam2.started:
                     picam2.switch_mode(preview_config_global)
                     apply_zoom() 
                     print("미리보기 모드로 전환 및 줌 레벨 재적용 완료 (캡처 작업 후).")
                else:
                    print("카메라가 실행 중이지 않아 미리보기 모드로 전환할 수 없습니다 (캡처 작업 후).")
            except Exception as e_switch_back_finally:
                print(f"미리보기 모드 복원 오류 (캡처 작업 후 finally): {e_switch_back_finally}")

            if original_preview_active_state: 
                preview_active = True
                if root and root.winfo_exists():
                    root.after(10, update_preview) 
                print("미리보기 재시작됨 (캡처 작업 후).")
            
            if captured_array_rgb is not None and not (status_label and "오류" in status_label.cget("text")):
                 if status_label and status_label.winfo_exists(): status_label.config(text="이미지 처리/전송 시작 (백그라운드)")


    if captured_array_rgb is not None: 
        if not os.path.exists(SAVE_DIR):
            try:
                os.makedirs(SAVE_DIR)
                print(f"폴더 생성: {SAVE_DIR}")
            except OSError as e_mkdir:
                 print(f"폴더 생성 실패 {SAVE_DIR}: {e_mkdir}")

        timestamp_str = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
        filename_for_log = f"crack_num_{image_file_counter}_{timestamp_str}.jpg"
        image_file_counter += 1 
        
        filepath_for_log = os.path.join(SAVE_DIR, filename_for_log)

        print(f"새 파일 이름: {filename_for_log}")
        print("백그라운드 이미지 처리 및 업로드 작업을 ThreadPoolExecutor에 제출...")
        thread_pool.submit(process_and_upload_image_task, captured_array_rgb, filename_for_log, filepath_for_log)
    else:
        print("캡처된 이미지 데이터가 없어 백그라운드 처리를 시작하지 않습니다.")
        if status_label and status_label.winfo_exists() and "오류" not in status_label.cget("text"):
            status_label.config(text="캡처 실패. 다시 시도하세요.")


def on_closing():
    global preview_active, picam2, root, servo_motor, factory, is_closing, thread_pool
    
    if is_closing:
        print("이미 종료 절차 진행 중입니다.")
        return
    is_closing = True 
    print("종료 요청 접수됨.")

    preview_active = False 
    
    user_confirmed_exit = False
    if root and root.winfo_exists():
        root.update_idletasks() 
        try:
            user_confirmed_exit = messagebox.askokcancel("종료 확인", "프로그램을 종료하시겠습니까?")
            print(f"사용자 종료 확인 결과: {user_confirmed_exit}")
        except tk.TclError as e: 
            print(f"종료 확인 대화상자 표시 중 오류 (GUI 이미 파괴됨?): {e}")
            user_confirmed_exit = True 
    else:
        print("GUI 없음. 확인 없이 종료 진행.")
        user_confirmed_exit = True

    if user_confirmed_exit:
        print("실제 프로그램 종료 절차 시작...")

        print("  ThreadPoolExecutor 종료 시도 (진행 중인 작업 완료 대기)...")
        thread_pool.shutdown(wait=True) 
        print("  ThreadPoolExecutor 종료 완료.")

        if picam2:
            print("  카메라 정지 및 해제 중...")
            try:
                if picam2.started: picam2.stop()
                picam2.close()
                print("  카메라 정지 및 해제 완료.")
            except Exception as e: print(f"  카메라 정지 중 오류: {e}")
            finally: picam2 = None
        
        if servo_motor:
            print("  서보 모터 해제 중...")
            try:
                # 서보 모터를 detach (이미 set_servo_value_gpiozero에서 하고 있음)
                # servo_motor.detach() 
                servo_motor.close()
                print("  서보 모터 해제 완료.")
            except Exception as e: print(f"  서보 모터 해제 중 오류: {e}")
            finally: servo_motor = None
        
        if factory: 
            print("  pin_factory 해제 중...")
            try:
                factory.close()
                print("  pin_factory 해제 완료.")
            except Exception as e: print(f"  pin_factory 해제 중 오류: {e}")
            finally: factory = None
        
        print("모든 주변 장치 리소스 해제 시도 완료.")

        if root and root.winfo_exists():
            print("  GUI 창 닫는 중...")
            try:
                root.destroy()
                print("  GUI 창 닫힘.")
            except tk.TclError as e:
                print(f"  GUI 창 닫는 중 오류 (이미 닫혔을 수 있음): {e}")
            finally: root = None
        else:
            print("  GUI 창이 이미 닫혔거나 존재하지 않음.")
        
        print("프로그램이 완전히 종료됩니다.")
    else:
        print("프로그램 종료가 사용자에 의해 취소되었습니다.")
        is_closing = False 
        if picam2 and picam2.started and not preview_active: 
            preview_active = True
            if root and root.winfo_exists():
                root.after(10, update_preview)
            print("종료 취소 후 미리보기 재시작됨.")


# --- GUI 설정 ---
root = tk.Tk()
root.title("카메라 미리보기 및 촬영 (줌/렉/파일명 최종 개선)")
root.geometry(f"{PREVIEW_WIDTH+60}x{PREVIEW_HEIGHT+220}") 
preview_label = Label(root)
preview_label.pack(pady=10)
zoom_frame = Frame(root)
zoom_frame.pack(pady=2)
zoom_out_button = Button(zoom_frame, text="축소 (-)", command=zoom_out, width=8)
zoom_out_button.pack(side=tk.LEFT, padx=3)
zoom_status_label = Label(zoom_frame, text=f"줌: {INITIAL_ZOOM_LEVEL:.2f}x", width=10)
zoom_status_label.pack(side=tk.LEFT, padx=3)
zoom_in_button = Button(zoom_frame, text="확대 (+)", command=zoom_in, width=8)
zoom_in_button.pack(side=tk.LEFT, padx=3)
control_frame = Frame(root)
control_frame.pack(pady=5)
rotate_left_button = Button(control_frame, text="⬅ 좌회전", command=rotate_camera_left_gpiozero, width=10, height=2)
rotate_left_button.pack(side=tk.LEFT, padx=5)
capture_button = Button(control_frame, text="📷 촬영/전송", command=capture_and_send, width=12, height=2)
capture_button.pack(side=tk.LEFT, padx=5)
rotate_right_button = Button(control_frame, text="➡ 우회전", command=rotate_camera_right_gpiozero, width=10, height=2)
rotate_right_button.pack(side=tk.LEFT, padx=5)
status_label = Label(root, text="초기화 중...", anchor='w', justify='left')
status_label.pack(fill=tk.X, padx=10, pady=(5,0)) 
exit_button_frame = Frame(root) 
exit_button_frame.pack(pady=(5,10)) 
exit_button = Button(exit_button_frame, text="종료", command=on_closing, width=10, height=2, bg="salmon", fg="white")
exit_button.pack()

# --- 메인 로직 ---
if setup_peripherals_gpiozero(): 
    if setup_camera():
        status_label.config(text="카메라 및 주변 장치 준비 완료.\n버튼을 사용하세요.")
        update_preview()
    else:
        status_label.config(text="카메라 시작 실패.\n프로그램을 종료하세요.")
        capture_button.config(state=tk.DISABLED)
        rotate_left_button.config(state=tk.DISABLED)
        rotate_right_button.config(state=tk.DISABLED)
        zoom_in_button.config(state=tk.DISABLED)
        zoom_out_button.config(state=tk.DISABLED)
else:
    status_label.config(text="주변 장치 초기화 실패.\nGPIO 설정을 확인하세요.")
    capture_button.config(state=tk.DISABLED)
    rotate_left_button.config(state=tk.DISABLED)
    rotate_right_button.config(state=tk.DISABLED)

root.protocol("WM_DELETE_WINDOW", on_closing) 
try:
    root.mainloop()
except KeyboardInterrupt:
    print("KeyboardInterrupt 수신. 프로그램 종료 중...")
    if not is_closing: 
        on_closing() 
finally:
    if 'thread_pool' in globals() and thread_pool and not thread_pool._shutdown: 
        print("메인 루프 외부에서 ThreadPoolExecutor 강제 종료 시도...")
        thread_pool.shutdown(wait=False, cancel_futures=True) 
        print("ThreadPoolExecutor 강제 종료 완료 (메인 루프 외부).")

print("Tkinter mainloop 종료됨.")
