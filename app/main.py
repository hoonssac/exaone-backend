from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
import os
from dotenv import load_dotenv
import time

# 모델 import (테이블 생성을 위해 필요)
from app.models.user import User
from app.models.chat import ChatThread, ChatMessage
from app.models.prompt import PromptTable, PromptColumn, PromptDict, PromptKnowledge
from app.models.admin import Term, Knowledge, SchemaField, FilterableField, AdminEntity
from app.db.database import create_all_tables, test_postgres_connection, test_mysql_connection, PostgresSessionLocal
from app.service.schema_rag_service import SchemaRAGService

# 환경변수 로드
load_dotenv()


# 모든 HTTP 요청 로깅 미들웨어
class RequestLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # 요청 정보 로깅
        method = request.method
        path = request.url.path
        query = request.url.query
        client = request.client.host if request.client else "unknown"

        print(f"\n📨 HTTP 요청 수신:")
        print(f"   클라이언트: {client}")
        print(f"   메서드: {method} {path}")
        if query:
            print(f"   쿼리: {query}")

        start_time = time.time()

        try:
            response = await call_next(request)
            elapsed = time.time() - start_time
            print(f"   상태: {response.status_code} ({elapsed:.2f}초)")
            return response
        except Exception as e:
            elapsed = time.time() - start_time
            print(f"   ❌ 오류: {str(e)[:100]} ({elapsed:.2f}초)")
            raise


# FilterableField 초기화 함수
def init_filterable_fields(db):
    """FilterableField 초기 데이터 등록 및 업데이트"""
    try:
        # FilterableField 테이블 존재 확인
        try:
            db.query(FilterableField).first()
        except Exception as e:
            print(f"⚠️ FilterableField 테이블 없음 (테이블 생성 필요): {str(e)[:50]}")
            return

        # 사출기 필터
        machine_filter = db.query(FilterableField).filter(
            FilterableField.field_name == "machine_id"
        ).first()

        if not machine_filter:
            machine_filter = FilterableField(
                field_name="machine_id",
                display_name="사출기",
                description="사출 기계 ID",
                field_type="numeric"
            )
            db.add(machine_filter)

        # 항상 최신 설정으로 업데이트
        # "1번", "1호", "사출기 1" 모두 처리
        machine_filter.extraction_pattern = r"(\d+)\s*(?:번|호|호기)|(?:사출기|기계)\s*(\d+)"
        machine_filter.extraction_keywords = [
            "1번", "1호", "1호기", "사출기 1", "기계 1",
            "2번", "2호", "2호기", "사출기 2", "기계 2",
            "3번", "3호", "3호기", "사출기 3", "기계 3",
            "4번", "4호", "4호기", "사출기 4", "기계 4",
            "5번", "5호", "5호기", "사출기 5", "기계 5"
        ]
        machine_filter.value_mapping = None
        machine_filter.is_optional = True
        machine_filter.multiple_allowed = False
        # valid_values는 관리자 API를 통해 동적으로 업데이트됨
        if not machine_filter.valid_values:
            machine_filter.valid_values = ["1", "2", "3", "4", "5"]
        machine_filter.validation_type = "exact"

        # 날짜 필터
        date_filter = db.query(FilterableField).filter(
            FilterableField.field_name == "cycle_date"
        ).first()

        if not date_filter:
            date_filter = FilterableField(
                field_name="cycle_date",
                display_name="날짜",
                description="사이클 실행 날짜",
                field_type="date"
            )
            db.add(date_filter)

        # 항상 최신 설정으로 업데이트
        date_filter.extraction_pattern = r"\d{4}-\d{2}-\d{2}|\d{4}년\s*\d{1,2}월\s*\d{1,2}일"
        date_filter.extraction_keywords = [
            "오늘", "어제", "내일", "지난주", "이번주",
            "지난달", "이번달", "모레", "그저께"
        ]
        date_filter.value_mapping = {
            "오늘": "CURDATE()",
            "어제": "DATE_SUB(CURDATE(), INTERVAL 1 DAY)",
            "내일": "DATE_ADD(CURDATE(), INTERVAL 1 DAY)",
            "모레": "DATE_ADD(CURDATE(), INTERVAL 1 DAY)",
            "그저께": "DATE_SUB(CURDATE(), INTERVAL 2 DAY)",
            # 범위 표현은 Agent가 직접 처리 (단일 날짜 아님)
            "지난주": "__PERIOD__:past_week",
            "이번주": "__PERIOD__:this_week",
            "지난달": "__PERIOD__:past_month",
            "이번달": "__PERIOD__:this_month",
        }
        date_filter.is_optional = True
        date_filter.multiple_allowed = False

        # 금형 필터
        mold_filter = db.query(FilterableField).filter(
            FilterableField.field_name == "mold_id"
        ).first()

        if not mold_filter:
            mold_filter = FilterableField(
                field_name="mold_id",
                display_name="금형",
                description="사용된 금형 ID",
                field_type="numeric"
            )
            db.add(mold_filter)

        # 항상 최신 설정으로 업데이트
        # "DC1", "DC2", "금형 1" 형식 모두 처리
        mold_filter.extraction_pattern = r"(?:DC|금형)\s*(\d+)"
        mold_filter.extraction_keywords = ["DC", "금형"]
        mold_filter.value_mapping = None
        mold_filter.is_optional = True
        mold_filter.multiple_allowed = True
        mold_filter.valid_values = ["1"]  # 유효한 금형 ID
        mold_filter.validation_type = "exact"

        # 재료 필터
        material_filter = db.query(FilterableField).filter(
            FilterableField.field_name == "material_id"
        ).first()

        if not material_filter:
            material_filter = FilterableField(
                field_name="material_id",
                display_name="재료",
                description="원재료 ID",
                field_type="numeric"
            )
            db.add(material_filter)

        # 항상 최신 설정으로 업데이트
        # "HIPS1", "PP2", "재료 1" 형식 모두 처리
        material_filter.extraction_pattern = r"(?:재료|HIPS|PP)\s*(\d+)"
        material_filter.extraction_keywords = ["HIPS", "PP", "재료"]
        material_filter.value_mapping = None
        material_filter.is_optional = True
        material_filter.multiple_allowed = True
        material_filter.valid_values = ["1"]  # 유효한 재료 ID
        material_filter.validation_type = "exact"

        db.commit()
        print("✅ FilterableField 데이터 업데이트 완료")
    except Exception as e:
        print(f"⚠️ FilterableField 초기화 오류: {str(e)}")
        db.rollback()


# AdminEntity 초기화 함수
def init_admin_entities(db):
    """AdminEntity 초기 데이터 등록 및 업데이트"""
    try:
        # AdminEntity 테이블 존재 확인
        try:
            db.query(AdminEntity).first()
        except Exception as e:
            print(f"⚠️ AdminEntity 테이블 없음 (테이블 생성 필요): {str(e)[:50]}")
            return

        print("🔄 AdminEntity 초기화 중...")

        entities_config = [
            {
                "entity_name": "machines",
                "display_name": "사출기",
                "description": "사용 가능한 사출 기계 목록",
                "db_type": "mysql",
                "table_name": "injection_molding_machine",
                "id_column": "id",
                "name_column": "equipment_name",
                "query": "SELECT id, equipment_name as name FROM injection_molding_machine WHERE deleted_at IS NULL ORDER BY id",
            },
            {
                "entity_name": "materials",
                "display_name": "재료",
                "description": "사용 가능한 원재료 목록",
                "db_type": "mysql",
                "table_name": "material_spec",
                "id_column": "id",
                "name_column": "material_type",
                "query": "SELECT id, material_type as name FROM material_spec WHERE deleted_at IS NULL ORDER BY id",
            },
            {
                "entity_name": "molds",
                "display_name": "금형",
                "description": "사용 가능한 금형 목록",
                "db_type": "mysql",
                "table_name": "mold_info",
                "id_column": "id",
                "name_column": "mold_name",
                "query": "SELECT id, mold_name as name FROM mold_info WHERE deleted_at IS NULL ORDER BY id",
            },
        ]

        for config in entities_config:
            # 기존 엔티티 조회
            existing = db.query(AdminEntity).filter(
                AdminEntity.entity_name == config["entity_name"]
            ).first()

            if existing:
                # 기존 엔티티 업데이트
                for key, value in config.items():
                    if key != "entity_name":
                        setattr(existing, key, value)
                print(f"✅ {config['display_name']} 엔티티 업데이트")
            else:
                # 새 엔티티 생성
                new_entity = AdminEntity(**config)
                db.add(new_entity)
                print(f"✅ {config['display_name']} 엔티티 생성")

        db.commit()
        print("✅ AdminEntity 초기화 완료")

    except Exception as e:
        db.rollback()
        print(f"⚠️ AdminEntity 초기화 오류: {str(e)}")


# FastAPI 앱 생성
app = FastAPI(
    title="EXAONE API",
    description="EXAONE AI 기반 제조 데이터 조회 API",
    version="1.0.0"
)

# 요청 로깅 미들웨어 추가 (CORS 전에)
app.add_middleware(RequestLoggingMiddleware)

# CORS 설정
CORS_ORIGINS = [
    "http://localhost:8080",
    "http://10.0.2.2:8080",  # Android 에뮬레이터
    "http://localhost:3000",
    "https://dxs20.iptime.org:8443",  # 프로덕션 프론트엔드
    "https://dxs20.iptime.org",  # 프로덕션 프론트엔드 (포트 없음)
    "*",  # 개발/테스트용 - 모든 origin 허용
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 애플리케이션 시작 시 테이블 생성
@app.on_event("startup")
async def startup_event():
    """애플리케이션 시작 시 실행"""
    print("🚀 EXAONE API 서버 시작...")

    try:
        # 데이터베이스 연결 테스트
        postgres_ok = test_postgres_connection()
        mysql_ok = test_mysql_connection()

        if not postgres_ok:
            print("❌ PostgreSQL 연결 실패 - 테이블을 생성할 수 없습니다")
            return

        # 테이블 생성
        try:
            create_all_tables()
            print("✅ 테이블 생성 완료")
        except Exception as e:
            print(f"⚠️ 테이블 생성 오류: {str(e)}")

        # 마이그레이션 실행 (실패해도 계속 진행)
        try:
            import sys
            from pathlib import Path
            migrations_path = Path(__file__).parent.parent / "migrations"

            # 기존 경로 제거 후 추가 (중복 방지)
            if str(migrations_path) in sys.path:
                sys.path.remove(str(migrations_path))
            sys.path.insert(0, str(migrations_path))

            print("🔄 마이그레이션 001 실행 중...")
            from migration_001_add_valid_values_to_filterable_fields import migrate_up as migrate_001
            migrate_001()
            print("✅ 마이그레이션 001 완료")

            print("🔄 마이그레이션 002 실행 중...")
            from migration_002_add_admin_entities import migrate_up as migrate_002
            migrate_002()
            print("✅ 마이그레이션 002 완료")
        except ImportError as e:
            print(f"⚠️ 마이그레이션 import 실패 (무시함): {str(e)}")
        except Exception as e:
            print(f"⚠️ 마이그레이션 실행 중 오류 (무시함): {str(e)}")

        # FilterableField 초기 데이터 등록
        try:
            print("🔄 FilterableField 초기화 중...")
            db = PostgresSessionLocal()
            try:
                init_filterable_fields(db)
                print("✅ FilterableField 초기화 완료")
            finally:
                db.rollback()
                db.close()
        except Exception as e:
            print(f"⚠️ FilterableField 초기화 오류: {str(e)}")

        # AdminEntity 초기 데이터 등록
        try:
            print("🔄 AdminEntity 초기화 중...")
            db = PostgresSessionLocal()
            try:
                init_admin_entities(db)
                print("✅ AdminEntity 초기화 완료")
            finally:
                db.rollback()
                db.close()
        except Exception as e:
            print(f"⚠️ AdminEntity 초기화 오류: {str(e)}")

        # 스키마 임베딩 초기화 (Schema-based RAG) - 실패해도 무시
        try:
            print("🔄 스키마 임베딩 초기화 중...")
            db = PostgresSessionLocal()
            SchemaRAGService.initialize_schema_embeddings(db)
            db.close()
            print("✅ 스키마 임베딩 초기화 완료")
        except Exception as e:
            print(f"⚠️ 스키마 임베딩 초기화 오류 (무시함): {str(e)}")

        # Supertonic TTS 초기화 - 실패해도 무시
        try:
            print("🔄 Supertonic TTS 초기화 중...")
            from app.service.supertonic_service import SupertonicService
            SupertonicService.initialize()
            print("✅ Supertonic TTS 초기화 완료")
        except Exception as e:
            print(f"⚠️ Supertonic TTS 초기화 오류 (무시함): {str(e)}")

        print("✅ 모든 시작 절차 완료 (일부 오류는 무시됨)")

    except Exception as e:
        print(f"❌ startup_event 중 치명적 오류: {str(e)}")
        import traceback
        traceback.print_exc()

# 헬스체크 엔드포인트
@app.get("/health")
async def health_check():
    """헬스체크 엔드포인트"""
    postgres_ok = test_postgres_connection()
    mysql_ok = test_mysql_connection()

    return {
        "status": "healthy" if (postgres_ok and mysql_ok) else "degraded",
        "postgresql": "connected" if postgres_ok else "disconnected",
        "mysql": "connected" if mysql_ok else "disconnected"
    }


# 데이터베이스 연결 풀 상태 확인 (디버깅용)
@app.get("/debug/db-pool-status")
async def db_pool_status():
    """데이터베이스 연결 풀 상태 확인"""
    from app.db.database import postgres_engine, mysql_engine

    try:
        pg_pool = postgres_engine.pool
        mysql_pool = mysql_engine.pool

        return {
            "postgresql": {
                "pool_size": pg_pool.size(),
                "checked_out": pg_pool.checkedout(),
                "overflow": pg_pool.overflow(),
                "total": pg_pool.size() + pg_pool.overflow(),
                "checked_in": pg_pool.checkedin(),
            },
            "mysql": {
                "pool_size": mysql_pool.size(),
                "checked_out": mysql_pool.checkedout(),
                "overflow": mysql_pool.overflow(),
                "total": mysql_pool.size() + mysql_pool.overflow(),
                "checked_in": mysql_pool.checkedin(),
            }
        }
    except Exception as e:
        return {
            "error": str(e),
            "message": "연결 풀 상태를 조회할 수 없습니다"
        }

# 메인 엔드포인트
@app.get("/")
async def root():
    """API 루트 엔드포인트"""
    return {
        "message": "EXAONE API Server",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/health"
    }

# API 라우트
from app.api import auth, query, admin
app.include_router(auth.router)
app.include_router(query.router)
app.include_router(admin.router)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8080,
        reload=True
    )
