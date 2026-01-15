from sqlalchemy import create_engine, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool
import os
from typing import Generator

# 환경변수에서 데이터베이스 URL 가져오기
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://exaone_user:exaone_password@localhost:5432/exaone_app"
)

MYSQL_URL = os.getenv(
    "MYSQL_URL",
    "mysql+pymysql://exaone_user:exaone_password@localhost:3306/manufacturing"
)

# PostgreSQL 엔진 (앱 데이터)
postgres_engine = create_engine(
    DATABASE_URL,
    echo=True,  # SQL 로그 출력 (디버깅용)
    pool_pre_ping=True,  # 연결 풀 재시작 전 연결 테스트
)

# MySQL 엔진 (제조 데이터)
mysql_engine = create_engine(
    MYSQL_URL,
    echo=True,
    pool_pre_ping=True,
    connect_args={"charset": "utf8mb4"},
)

# 세션 설정
PostgresSessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=postgres_engine
)

MysqlSessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=mysql_engine
)

# ORM Base 클래스
Base = declarative_base()


# 의존성: PostgreSQL 세션
def get_postgres_db() -> Generator[Session, None, None]:
    """PostgreSQL 데이터베이스 세션 반환"""
    db = PostgresSessionLocal()
    try:
        yield db
    finally:
        db.close()


# 의존성: MySQL 세션
def get_mysql_db() -> Generator[Session, None, None]:
    """MySQL 데이터베이스 세션 반환"""
    db = MysqlSessionLocal()
    try:
        yield db
    finally:
        db.close()


# 데이터베이스 테이블 생성
def create_all_tables():
    """모든 테이블 생성"""
    Base.metadata.create_all(bind=postgres_engine)
    print("✅ PostgreSQL 테이블 생성 완료")


# 데이터베이스 연결 테스트
def test_postgres_connection():
    """PostgreSQL 연결 테스트"""
    try:
        with postgres_engine.connect() as connection:
            result = connection.execute(text("SELECT 1"))
            print("✅ PostgreSQL 연결 성공")
            return True
    except Exception as e:
        print(f"❌ PostgreSQL 연결 실패: {e}")
        return False


def test_mysql_connection():
    """MySQL 연결 테스트"""
    try:
        with mysql_engine.connect() as connection:
            result = connection.execute(text("SELECT 1"))
            print("✅ MySQL 연결 성공")
            return True
    except Exception as e:
        print(f"❌ MySQL 연결 실패: {e}")
        return False
