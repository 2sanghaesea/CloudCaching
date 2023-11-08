import mysql.connector
import numpy as np
import json

# MariaDB 연결
conn = mysql.connector.connect(
    host='localhost',
    user='root',
    password='1234',
    database='mysql'
)
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



# 100개의 무작위 얼굴 인코딩 값 생성 및 삽입
for face_id in range(10001, 30001):  
    random_face_encoding = np.random.rand(128).tolist()  # 128은 face_recognition 라이브러리에서 사용되는 인코딩의 차원
    face_encoding_json = json.dumps(random_face_encoding)
    cursor.execute("INSERT INTO face_data (faceid, macid, encoding) VALUES (%s, %s, %s)",
                   (face_id, f'random_mac_id_{face_id}', face_encoding_json))
     # 데이터베이스에 데이터 저장 (DynamoDB)
            table.put_item(
                Item={
                    'macid': str(mac_id),
                    'faceid': int(face_id),
                    'encoding': face_encoding_json
                }

# 변경사항 저장
conn.commit()

# 데이터베이스 연결 해제
cursor.close()
conn.close()

