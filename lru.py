import cv2
import dlib
import face_recognition
import mysql.connector
import boto3
import json
import time
import numpy as np
from collections import OrderedDict

# MariaDB 연결
conn = mysql.connector.connect(
    host='localhost',
    user='root',
    password='1234',
    database='mysql'
)
print("Mariadb Server is running")
cursor = conn.cursor()

# AWS 자격 증명 설정
session = boto3.Session(
    aws_access_key_id='---',
    aws_secret_access_key='---',
    region_name='---'
)

# AWS DynamoDB 연결
dynamodb = session.resource('dynamodb', region_name='---') 
table = dynamodb.Table('---') 
print("dynamodb server is running")

# 얼굴 검출기 초기화
detector = dlib.get_frontal_face_detector()

# 얼굴 특징 포인트 예측기 초기화
predictor = dlib.shape_predictor("shape_predictor_68_face_landmarks.dat")
print("안면인식 준비 완료")

# LRU Cache 초기화
class LRUCache(OrderedDict):
    def __init__(self, capacity):
        self.capacity = capacity
        super().__init__()

    def __getitem__(self, key):
        value = super().__getitem__(key)
        self.move_to_end(key)  # 최근에 사용된 아이템으로 이동
        return value

    def __setitem__(self, key, value):
        if len(self) >= self.capacity:
            oldest = next(iter(self))
            del self[oldest]  # 가장 오래된 아이템 삭제
        super().__setitem__(key, value)

# LRU Cache 인스턴스 생성
face_cache = LRUCache(capacity=5)  # 원하는 캐시 크기로 조절

def register_face(mac_id, face_id):
    # 카메라 초기화
    video_capture = cv2.VideoCapture(0)

    if not video_capture.isOpened():
        print("카메라가 정상적으로 작동하지 않습니다. 프로그램을 종료합니다.")
        return

    print("카메라가 정상적으로 작동합니다. 얼굴을 등록하세요.")

    while True:
        # 비디오 프레임 읽기
        ret, frame = video_capture.read()

        # 그레이스케일로 변환
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

        # 얼굴 검출
        faces = detector(gray)

        if len(faces) == 1:
            face = faces[0]

            # 얼굴 영역 특징 포인트 예측
            landmarks = predictor(gray, face)

            # 예측한 얼굴 특징을 이용하여 얼굴 영역에 사각형 그리기
            for n in range(0, 68):
                x = landmarks.part(n).x
                y = landmarks.part(n).y
                cv2.circle(frame, (x, y), 1, (0, 0, 255), -1)

            # 얼굴 인코딩
            face_encoding = face_recognition.face_encodings(frame, [(face.top(), face.right(), face.bottom(), face.left())])[0]

            # 얼굴 인코딩을 JSON으로 변환하여 저장
            face_encoding_json = json.dumps(face_encoding.tolist())

            # 데이터베이스에 이름과 얼굴 인코딩 저장
            insert_query = "INSERT INTO face_data (faceid, macid, encoding) VALUES (%s, %s, %s)"
            cursor.execute(insert_query, (int(face_id), str(mac_id), face_encoding_json))

            # 데이터베이스에 데이터 저장 (DynamoDB)
            table.put_item(
                Item={
                    'macid': str(mac_id),
                    'faceid': int(face_id),
                    'encoding': face_encoding_json
                }
            )

            # 캐시에 얼굴 데이터 저장 (LRU)
            face_cache[int(face_id)] = face_encoding

            print(f'faceid : {face_id} 의 얼굴 등록 완료!')
            break

    # 데이터베이스에 변경사항 저장
    conn.commit()

    # 연결 해제
    video_capture.release()

def recognize_face():
    # 카메라 초기화
    video_capture = cv2.VideoCapture(0)

    if not video_capture.isOpened():
        print("카메라가 정상적으로 작동하지 않습니다. 프로그램을 종료합니다.")
        return

    print("카메라가 정상적으로 작동합니다. 얼굴을 인식하세요.")
    start_time = time.time()

    while True:
        # 비디오 프레임 읽기
        ret, frame = video_capture.read()

        # 그레이스케일로 변환
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

        # 얼굴 검출
        faces = detector(gray)

        if len(faces) == 1:
            face = faces[0]

            # 얼굴 영역 특징 포인트 예측
            landmarks = predictor(gray, face)
            face_encoding = face_recognition.face_encodings(frame, [(face.top(), face.right(), face.bottom(), face.left())])[0]

            # 데이터베이스에서 등록된 얼굴 불러오기
            select_query = "SELECT * FROM face_data"
            cursor.execute(select_query)
            rows = cursor.fetchall()

            for row in rows:
                saved_encoding_json = row[2]
                saved_encoding_list = json.loads(saved_encoding_json)
                saved_encoding = np.array(saved_encoding_list)

                # 캐시에서 얼굴 데이터 확인 (LRU)
                if int(row[0]) in face_cache:
                    face_encoding = face_cache[int(row[0])]
                else:
                    face_encoding = face_recognition.face_encodings(frame, [(face.top(), face.right(), face.bottom(), face.left())])[0]

                    # 캐시에 얼굴 데이터 저장 (LRU)
                    face_cache[int(row[0])] = face_encoding

                result = face_recognition.compare_faces([saved_encoding], face_encoding)

                if result[0]:
                    face_id = row[0]
                    mac_id = row[1]
                    print(f"안녕하세요! faceid: {face_id}, mac_id: {mac_id}")
                    break

            elapsed_time = time.time() - start_time  # 경과 시간 계산
            print(f"입출입 시스템이 {elapsed_time:.4f}초 동안 수행되었습니다.")  # 경과 시간 출력
            break

    video_capture.release()

# 메인 루프
while True:
    print("1. 사용자 등록")
    print("2. 사용자 인식")
    choice = input("번호를 선택하세요 (0 입력시 종료): ")

    if choice == '1':
        mac_id = input("등록할 사용자의 macid를 입력하세요: ")
        face_id = input("등록할 사용자의 faceid를 입력하세요: ")
        register_face(mac_id, face_id)
        print("안면 등록 과정 끝")
    elif choice == '2':
        print("얼굴 인식을 시작하겠습니다.")
        recognize_face()
        print("안면인식 수행 과정 끝")
    elif choice == '0':
        break
    else:
        print("올바른 번호를 입력하세요.")

# 데이터베이스 연결 해제
cursor.close()
conn.close()
