#include <iostream>
#include <mysql_driver.h>
#include <mysql_connection.h>
#include <cppconn/statement.h>
#include <cppconn/resultset.h>
#include <cppconn/prepared_statement.h>
#include <aws/core/Aws.h>
#include <aws/core/utils/Outcome.h>
#include <aws/core/utils/Outcome.h>
#include <aws/dynamodb/DynamoDBClient.h>
#include <aws/dynamodb/model/PutItemRequest.h>
#include <aws/dynamodb/model/Attribute.h>
#include <dlib/opencv.h>
#include <dlib/image_processing/frontal_face_detector.h>
#include <dlib/image_processing.h>
#include <dlib/gui_widgets.h>
#include <opencv2/opencv.hpp>
#include <json/json.h>

using namespace std;
using namespace cv;

sql::mysql::MySQL_Driver *driver;
sql::Connection *con;
sql::Statement *stmt;
sql::ResultSet *res;
Aws::SDKOptions options;
Aws::InitAPI(options);
Aws::Client::ClientConfiguration clientConfig;
clientConfig.region = "ap-northeast-2";
Aws::DynamoDB::DynamoDBClient dynamoClient(clientConfig);

dlib::frontal_face_detector detector = dlib::get_frontal_face_detector();
dlib::shape_predictor predictor;
dlib::deserialize("shape_predictor_68_face_landmarks.dat") >> predictor;

void registerFace(int macId, int faceId) {
    VideoCapture videoCapture(0);

    if (!videoCapture.isOpened()) {
        cout << "카메라가 정상적으로 작동하지 않습니다. 프로그램을 종료합니다." << endl;
        return;
    }

    cout << "카메라가 정상적으로 작동합니다. 얼굴을 등록하세요." << endl;

    while (true) {
        Mat frame;
        videoCapture >> frame;

        cvtColor(frame, frame, COLOR_BGR2GRAY);
        dlib::cv_image<unsigned char> dlibFrame(frame);

        std::vector<dlib::rectangle> faces = detector(dlibFrame);

        if (faces.size() == 1) {
            dlib::rectangle face = faces[0];
            auto shape = predictor(dlibFrame, face);

            for (int n = 0; n < 68; ++n) {
                int x = shape.part(n).x();
                int y = shape.part(n).y();
                circle(frame, Point(x, y), 1, Scalar(0, 0, 255), -1);
            }

            // 얼굴 인코딩
            std::vector<dlib::rectangle> faceRectangles = { face };
            std::vector<dlib::full_object_detection> faceShapes = { shape };
            std::vector<matrix<float,0,1>> faceDescriptors = dlib::get_face_chips(dlibFrame, faceShapes);

            // 얼굴 인코딩을 JSON으로 변환하여 저장
            Json::Value faceEncodingJson;
            for (auto& desc : faceDescriptors[0]) {
                faceEncodingJson.append(desc);
            }
            Json::StreamWriterBuilder writer;
            std::string faceEncodingJsonString = Json::writeString(writer, faceEncodingJson);

            // MariaDB에 이름과 얼굴 인코딩 저장
            stmt = con->createStatement();
            sql::PreparedStatement *pstmt = con->prepareStatement("INSERT INTO face_data (faceid, macid, encoding) VALUES (?, ?, ?)");
            pstmt->setInt(1, faceId);
            pstmt->setInt(2, macId);
            pstmt->setString(3, faceEncodingJsonString);
            pstmt->executeUpdate();
            delete pstmt;

            // DynamoDB에 데이터 저장
            Aws::DynamoDB::Model::PutItemRequest putRequest;
            putRequest.WithTableName("ycj");
            Aws::DynamoDB::Model::AttributeValue macIdAttr;
            macIdAttr.SetN(to_string(macId));
            Aws::DynamoDB::Model::AttributeValue faceIdAttr;
            faceIdAttr.SetN(to_string(faceId));
            Aws::DynamoDB::Model::AttributeValue encodingAttr;
            encodingAttr.SetS(faceEncodingJsonString);
            putRequest.AddItem("macid", macIdAttr);
            putRequest.AddItem("faceid", faceIdAttr);
            putRequest.AddItem("encoding", encodingAttr);
            dynamoClient.PutItem(putRequest);

            cout << "faceid : " << faceId << " 의 얼굴 등록 완료!" << endl;
            break;
        }
    }

    con->commit();
    videoCapture.release();
}

void recognizeFace() {
    VideoCapture videoCapture(0);

    if (!videoCapture.isOpened()) {
        cout << "카메라가 정상적으로 작동하지 않습니다. 프로그램을 종료합니다." << endl;
        return;
    }

    cout << "카메라가 정상적으로 작동합니다. 얼굴을 인식하세요." << endl;
    auto startTime = time(nullptr);

    while (true) {
        Mat frame;
        videoCapture >> frame;

        cvtColor(frame, frame, COLOR_BGR2GRAY);
        dlib::cv_image<unsigned char> dlibFrame(frame);

        std::vector<dlib::rectangle> faces = detector(dlibFrame);

        if (faces.size() == 1) {
            dlib::rectangle face = faces[0];
            auto shape = predictor(dlibFrame, face);

            std::vector<matrix<float,0,1>> faceDescriptors = dlib::get_face_chips(dlibFrame, shape);
            matrix<float,0,1> faceEncoding = faceDescriptors[0];

            // MariaDB에서 등록된 얼굴 불러오기
            stmt = con->createStatement();
            res = stmt->executeQuery("SELECT * FROM face_data");
            while (res->next()) {
                int savedMacId = res->getInt("macid");
                int savedFaceId = res->getInt("faceid");
                std::string savedEncodingJson = res->getString("encoding");

                Json::CharReaderBuilder reader;
                Json::CharReader* jsonReader = reader.newCharReader();
                Json::Value savedEncodingJsonRoot;
                std::istringstream encodingStream(savedEncodingJson);
                JSONCPP_STRING errs;
                Json::parseFromStream(reader, encodingStream, &savedEncodingJsonRoot, &errs);

                std::vector<float> savedEncodingVector;
                for (const Json::Value& elem : savedEncodingJsonRoot) {
                    savedEncodingVector.push_back(elem.asFloat());
                }

                matrix<float,0,1> savedEncoding = dlib::mat(savedEncodingVector);
                bool result = dlib::length(faceEncoding - savedEncoding) < 0.6;

                if (result) {
                    cout << "안녕하세요! faceid: " << savedFaceId << ", mac_id: " << savedMacId << endl;
                    auto elapsedTime = difftime(time(nullptr), startTime);
                    cout << "입출입 시스템이 " << elapsedTime << "초 동안 수행되었습니다." << endl;
                    return;
                }
            }
            delete res;
            delete stmt;
        }
    }

    videoCapture.release();
}

int main() {
    try {
        driver = get_driver_instance();
        con = driver->connect("tcp://127.0.0.1:3306", "root", "1234");
        con->setSchema("mysql");

        cout << "Mariadb Server is running" << endl;

        while (true) {
            cout << "1. 사용자 등록" << endl;
            cout << "2. 사용자 인식" << endl;
            cout << "번호를 선택하세요 (0 입력시 종료): ";
            int choice;
            cin >> choice;

            if (choice == 1) {
                int macId, faceId;
                cout << "등록할 사용자의 macid를 입력하세요: ";
                cin >> macId;
                cout << "등록할 사용자의 faceid를 입력하세요: ";
                cin >> faceId;
                registerFace(macId, faceId);
                cout << "안면 등록 과정 끝" << endl;
            } else if (choice == 2) {
                cout << "얼굴 인식을 시작하겠습니다." << endl;
                recognizeFace();
                cout << "안면인식 수행 과정 끝" << endl;
            } else if (choice == 0) {
                break;
            } else {
                cout << "올바른 번호를 입력하세요." << endl;
            }
        }

        delete con;
    } catch (sql::SQLException &e) {
        cout << "# ERR: SQLException in " << __FILE__;
        cout << "(" << __FUNCTION__ << ") on line " << __LINE__ << endl;
        cout << "# ERR: " << e.what();
        cout << " (MySQL error code: " << e.getErrorCode();
        cout << ", SQLState: " << e.getSQLState() << " )" << endl;
    }

    Aws::ShutdownAPI(options);
    return 0;
}
