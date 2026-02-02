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
    echo=False,  # 프로덕션에서는 비활성화 (성능 개선)
    pool_size=10,  # 동시 연결 수 (너무 크면 DB 과부하)
    max_overflow=5,  # 추가 연결 (제한적)
    pool_pre_ping=True,  # 연결 풀 재시작 전 연결 테스트
    pool_recycle=1800,  # 30분마다 연결 재활성화 (더 자주)
    connect_args={
        "connect_timeout": 10,  # 연결 타임아웃 10초
        "keepalives": 1,  # TCP keepalive 활성화
        "keepalives_idle": 30,
    },
)

# MySQL 엔진 (제조 데이터)
mysql_engine = create_engine(
    MYSQL_URL,
    echo=False,  # 프로덕션에서는 비활성화
    pool_size=10,
    max_overflow=5,
    pool_pre_ping=True,
    pool_recycle=1800,
    connect_args={
        "charset": "utf8mb4",
        "connect_timeout": 10,
    },
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
        # 연결 풀 상태 로깅 (디버깅용)
        pool = postgres_engine.pool
        checked_out = pool.checkedout()
        size = pool.size()
        if checked_out > size * 0.8:  # 80% 이상 사용 중
            print(f"⚠️ PostgreSQL 연결 풀 사용률 높음: {checked_out}/{size}")

        yield db
    except Exception as e:
        print(f"⚠️ PostgreSQL 세션 오류: {str(e)[:100]}")
        try:
            db.rollback()
        except:
            pass
        raise
    finally:
        # 명시적으로 롤백 후 닫기
        try:
            db.rollback()
        except:
            pass
        try:
            db.close()
        except Exception as e:
            print(f"⚠️ PostgreSQL 세션 닫기 오류: {str(e)[:50]}")


# 의존성: MySQL 세션
def get_mysql_db() -> Generator[Session, None, None]:
    """MySQL 데이터베이스 세션 반환"""
    db = MysqlSessionLocal()
    try:
        # 연결 풀 상태 로깅 (디버깅용)
        pool = mysql_engine.pool
        checked_out = pool.checkedout()
        size = pool.size()
        if checked_out > size * 0.8:  # 80% 이상 사용 중
            print(f"⚠️ MySQL 연결 풀 사용률 높음: {checked_out}/{size}")

        yield db
    except Exception as e:
        print(f"⚠️ MySQL 세션 오류: {str(e)[:100]}")
        try:
            db.rollback()
        except:
            pass
        raise
    finally:
        # 명시적으로 롤백 후 닫기
        try:
            db.rollback()
        except:
            pass
        try:
            db.close()
        except Exception as e:
            print(f"⚠️ MySQL 세션 닫기 오류: {str(e)[:50]}")


# 데이터베이스 테이블 생성
def create_all_tables():
    """모든 테이블 생성"""
    Base.metadata.create_all(bind=postgres_engine)
    print("✅ PostgreSQL 테이블 생성 완료")

    # message_embeddings 테이블 생성 (RAG용)
    try:
        with postgres_engine.connect() as connection:
            # pgvector 확장
            connection.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))

            # message_embeddings 테이블
            connection.execute(text("""
                CREATE TABLE IF NOT EXISTS message_embeddings (
                    id SERIAL PRIMARY KEY,
                    thread_id INT NOT NULL,
                    message TEXT NOT NULL,
                    embedding TEXT,
                    result_data JSONB,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """))

            # 인덱스
            connection.execute(text(
                "CREATE INDEX IF NOT EXISTS idx_msg_embed_thread ON message_embeddings(thread_id)"
            ))
            connection.execute(text(
                "CREATE INDEX IF NOT EXISTS idx_msg_embed_created ON message_embeddings(created_at DESC)"
            ))

            # schema_embeddings 테이블 (스키마 기반 RAG)
            connection.execute(text("""
                CREATE TABLE IF NOT EXISTS schema_embeddings (
                    id SERIAL PRIMARY KEY,
                    schema_type VARCHAR(20),          -- 'table' 또는 'column'
                    table_id INT,                     -- prompt_table.id
                    column_id INT,                    -- prompt_column.id
                    name VARCHAR(255),                -- 테이블/컬럼 이름
                    description TEXT,                 -- 설명
                    embedding TEXT,                   -- JSON 배열 (TF-IDF 벡터)
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """))

            # 인덱스
            connection.execute(text(
                "CREATE INDEX IF NOT EXISTS idx_schema_embed_type ON schema_embeddings(schema_type)"
            ))
            connection.execute(text(
                "CREATE INDEX IF NOT EXISTS idx_schema_embed_table ON schema_embeddings(table_id)"
            ))

            connection.commit()
            print("✅ RAG 테이블 생성 완료 (message_embeddings + schema_embeddings)")
    except Exception as e:
        print(f"⚠️ RAG 테이블 생성 오류: {str(e)}")


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
