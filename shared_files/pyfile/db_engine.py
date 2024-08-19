from sqlalchemy import create_engine, text
from datetime import datetime
from sqlalchemy.exc import SQLAlchemyError
import redis
import os

# 환경 변수에서 데이터베이스 연결 정보 가져오기
db_user = os.getenv('DB_USER')
db_password = os.getenv('DB_PASSWORD')
db_host = os.getenv('DB_HOST')
db_name = os.getenv('DB_NAME')

# 데이터베이스 엔진 생성 (연결 풀 사용)
engine = create_engine(
    f"mysql+mysqlconnector://{db_user}:{db_password}@{db_host}:3306/{db_name}",
    pool_size=10,  # 기본 연결 수
    max_overflow=20,  # 추가 연결 수
    pool_pre_ping=True  # 연결 유효성 검사
)

# 데이터베이스 엔진을 반환하는 함수
def get_engine():
    return engine

# 오류 로그를 데이터베이스에 기록하는 함수
def log_error_to_db(level, service, message, tb, additional_info=None):
    try:
        with engine.begin() as connection:
            # 오류 로그 데이터를 테이블에 삽입하는 쿼리 작성
            insert_query = text("""
                INSERT INTO error_log (timestamp, level, service, message, traceback, additional_info)
                VALUES (:timestamp, :level, :service, :message, :traceback, :additional_info)
            """)
            
            # 쿼리에 사용할 데이터
            error_data = {
                'timestamp': datetime.now(),
                'level': level,
                'service': service,
                'message': message,
                'traceback': tb,
                'additional_info': additional_info
            }
            
            # 쿼리 실행
            connection.execute(insert_query, error_data)
    except SQLAlchemyError as e:
        print(f"Error logging to DB: {e}")

# Redis 클라이언트 생성
r = redis.Redis(host='redis', port=6379)

# Redis 클라이언트를 반환하는 함수
def get_redis():
    return r
