import mysql.connector
import boto3
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

def sync_dynamodb_to_mariadb():
    # DynamoDB에서 데이터 가져오기
    response = table.scan()
    items = response['Items']

    for item in items:
        face_id = item['faceid']
        mac_id = item['macid']
        encoding_json = item['encoding']

        # 데이터베이스에 등록
        insert_query = "INSERT INTO face_data (encoding, faceid, macid) VALUES (%s, %s, %s)"
        cursor.execute(insert_query, (encoding_json, face_id, mac_id))

    # 중복 제거
    cursor.execute("DELETE f1 FROM face_data f1, face_data f2 WHERE f1.faceid = f2.faceid AND f1.macid = f2.macid AND f1.encoding > f2.encoding")

    # 데이터베이스에 변경사항 저장
    conn.commit()

    print("동기화가 완료되었습니다.")

# 동기화 실행
sync_dynamodb_to_mariadb()

# 데이터베이스 연결 해제
cursor.close()
conn.close()

