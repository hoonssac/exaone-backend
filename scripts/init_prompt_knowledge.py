"""
프롬프트 지식 베이스 초기화 스크립트

이 스크립트는 EXAONE 자연어-SQL 변환을 위한 지식 베이스를 초기화합니다.
- prompt_table: 제조 데이터 테이블 메타데이터
- prompt_column: 테이블 컬럼 메타데이터
- prompt_dict: 한글 용어 사전 (자동 보정 용도)
- prompt_knowledge: 도메인 지식 (쿼리 생성 참고)

실행: python scripts/init_prompt_knowledge.py
"""

import os
import sys
from datetime import datetime
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

# 환경변수 설정
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://exaone_user:exaone_password@localhost:5432/exaone_app"
)

# PostgreSQL 엔진 및 세션 생성
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)

def init_prompt_tables():
    """프롬프트 지식 베이스 초기화"""
    session = SessionLocal()

    try:
        # 1. prompt_table 초기화 (제조 데이터 테이블 메타데이터)
        print("📋 프롬프트 테이블 초기화 중...")

        tables_data = [
            {
                "name": "production_data",
                "description": "생산 실적 데이터 (생산량, 불량량, 생산 시간 등)"
            },
            {
                "name": "defect_data",
                "description": "불량 데이터 (불량 코드, 불량 유형, 불량률 등)"
            },
            {
                "name": "equipment_data",
                "description": "설비 가동 데이터 (설비 상태, 가동시간, 정지시간 등)"
            },
            {
                "name": "daily_production_summary",
                "description": "일별 생산 통계 (일일 생산량, 불량률, 달성률 등)"
            },
            {
                "name": "hourly_production_summary",
                "description": "시간별 생산 통계 (시간당 생산량, 불량률 등)"
            }
        ]

        for table_data in tables_data:
            session.execute(text("""
                INSERT INTO prompt_table (name, description, created_at)
                VALUES (:name, :description, :created_at)
                ON CONFLICT (name) DO NOTHING
            """), {
                "name": table_data["name"],
                "description": table_data["description"],
                "created_at": datetime.now()
            })

        session.commit()
        print(f"✅ {len(tables_data)}개의 테이블 메타데이터 저장됨")

        # 2. prompt_column 초기화 (컬럼 메타데이터)
        print("\n📊 컬럼 메타데이터 초기화 중...")

        columns_data = [
            # production_data columns
            {"table_name": "production_data", "name": "id", "description": "생산 ID (PK)", "data_type": "BIGINT"},
            {"table_name": "production_data", "name": "line_id", "description": "생산 라인 ID", "data_type": "VARCHAR"},
            {"table_name": "production_data", "name": "product_code", "description": "제품 코드", "data_type": "VARCHAR"},
            {"table_name": "production_data", "name": "product_name", "description": "제품명", "data_type": "VARCHAR"},
            {"table_name": "production_data", "name": "planned_quantity", "description": "계획 생산량", "data_type": "INT"},
            {"table_name": "production_data", "name": "actual_quantity", "description": "실제 생산량", "data_type": "INT"},
            {"table_name": "production_data", "name": "defect_quantity", "description": "불량 수량", "data_type": "INT"},
            {"table_name": "production_data", "name": "production_date", "description": "생산 일자", "data_type": "DATE"},
            {"table_name": "production_data", "name": "production_hour", "description": "생산 시간 (0-23)", "data_type": "TINYINT"},
            {"table_name": "production_data", "name": "shift", "description": "근무 조 (주간/야간)", "data_type": "VARCHAR"},
            {"table_name": "production_data", "name": "created_at", "description": "등록 일시", "data_type": "TIMESTAMP"},

            # defect_data columns
            {"table_name": "defect_data", "name": "id", "description": "불량 ID (PK)", "data_type": "BIGINT"},
            {"table_name": "defect_data", "name": "production_id", "description": "생산 ID (FK)", "data_type": "BIGINT"},
            {"table_name": "defect_data", "name": "defect_code", "description": "불량 코드", "data_type": "VARCHAR"},
            {"table_name": "defect_data", "name": "defect_name", "description": "불량명", "data_type": "VARCHAR"},
            {"table_name": "defect_data", "name": "defect_quantity", "description": "불량 수량", "data_type": "INT"},
            {"table_name": "defect_data", "name": "defect_rate", "description": "불량률 (%)", "data_type": "DECIMAL"},
            {"table_name": "defect_data", "name": "defect_type", "description": "불량 유형 (외관/기능/치수)", "data_type": "VARCHAR"},
            {"table_name": "defect_data", "name": "detected_at", "description": "감지 일시", "data_type": "TIMESTAMP"},

            # equipment_data columns
            {"table_name": "equipment_data", "name": "id", "description": "설비 ID (PK)", "data_type": "BIGINT"},
            {"table_name": "equipment_data", "name": "equipment_id", "description": "설비 ID", "data_type": "VARCHAR"},
            {"table_name": "equipment_data", "name": "equipment_name", "description": "설비명", "data_type": "VARCHAR"},
            {"table_name": "equipment_data", "name": "line_id", "description": "라인 ID", "data_type": "VARCHAR"},
            {"table_name": "equipment_data", "name": "status", "description": "가동 상태 (가동/정지/점검)", "data_type": "VARCHAR"},
            {"table_name": "equipment_data", "name": "operation_time", "description": "가동 시간 (분)", "data_type": "INT"},
            {"table_name": "equipment_data", "name": "downtime", "description": "정지 시간 (분)", "data_type": "INT"},
            {"table_name": "equipment_data", "name": "downtime_reason", "description": "정지 사유", "data_type": "VARCHAR"},
            {"table_name": "equipment_data", "name": "recorded_date", "description": "기록 일자", "data_type": "DATE"},
            {"table_name": "equipment_data", "name": "recorded_hour", "description": "기록 시간 (0-23)", "data_type": "TINYINT"},
            {"table_name": "equipment_data", "name": "created_at", "description": "등록 일시", "data_type": "TIMESTAMP"},
        ]

        for col_data in columns_data:
            # 테이블 ID 조회
            table_result = session.execute(text("""
                SELECT id FROM prompt_table WHERE name = :table_name
            """), {"table_name": col_data["table_name"]}).scalar()

            if table_result:
                session.execute(text("""
                    INSERT INTO prompt_column (table_id, name, description, data_type, created_at)
                    VALUES (:table_id, :name, :description, :data_type, :created_at)
                    ON CONFLICT (table_id, name) DO NOTHING
                """), {
                    "table_id": table_result,
                    "name": col_data["name"],
                    "description": col_data["description"],
                    "data_type": col_data["data_type"],
                    "created_at": datetime.now()
                })

        session.commit()
        print(f"✅ {len(columns_data)}개의 컬럼 메타데이터 저장됨")

        # 3. prompt_dict 초기화 (용어 사전)
        print("\n📖 용어 사전 초기화 중...")

        dict_data = [
            # 시간/날짜 관련
            {"key": "오늘", "value": "CURDATE()"},
            {"key": "어제", "value": "DATE_SUB(CURDATE(), INTERVAL 1 DAY)"},
            {"key": "지난주", "value": "DATE_SUB(CURDATE(), INTERVAL 7 DAY)"},
            {"key": "지난달", "value": "DATE_SUB(CURDATE(), INTERVAL 30 DAY)"},
            {"key": "이번달", "value": "DATE_TRUNC('month', CURDATE())"},

            # 생산 라인 관련
            {"key": "1라인", "value": "LINE-01"},
            {"key": "2라인", "value": "LINE-02"},
            {"key": "3라인", "value": "LINE-03"},
            {"key": "라인1", "value": "LINE-01"},
            {"key": "라인2", "value": "LINE-02"},
            {"key": "라인3", "value": "LINE-03"},

            # 제품 관련
            {"key": "제품A", "value": "P001"},
            {"key": "제품B", "value": "P002"},
            {"key": "제품C", "value": "P003"},
            {"key": "상품A", "value": "P001"},
            {"key": "상품B", "value": "P002"},
            {"key": "상품C", "value": "P003"},

            # 설비 관련
            {"key": "Loading", "value": "로딩기"},
            {"key": "Unloader", "value": "언로더"},
            {"key": "프레스", "value": "프레스 기계"},
            {"key": "용접", "value": "용접 기계"},
            {"key": "조립", "value": "조립 라인"},
            {"key": "검사", "value": "검사 기계"},
            {"key": "포장", "value": "포장 기계"},

            # 상태 관련
            {"key": "가동중", "value": "가동"},
            {"key": "정지", "value": "정지"},
            {"key": "점검중", "value": "점검"},
            {"key": "유지보수", "value": "정지"},

            # 근무 관련
            {"key": "주간", "value": "주간"},
            {"key": "야간", "value": "야간"},
            {"key": "낮", "value": "주간"},
            {"key": "밤", "value": "야간"},

            # 불량 유형
            {"key": "외관", "value": "외관"},
            {"key": "기능", "value": "기능"},
            {"key": "치수", "value": "치수"},
            {"key": "스크래치", "value": "스크래치"},
        ]

        for dict_entry in dict_data:
            session.execute(text("""
                INSERT INTO prompt_dict (key, value, created_at)
                VALUES (:key, :value, :created_at)
                ON CONFLICT (key) DO NOTHING
            """), {
                "key": dict_entry["key"],
                "value": dict_entry["value"],
                "created_at": datetime.now()
            })

        session.commit()
        print(f"✅ {len(dict_data)}개의 용어 사전 항목 저장됨")

        # 4. prompt_knowledge 초기화 (도메인 지식)
        print("\n🧠 도메인 지식 초기화 중...")

        knowledge_data = [
            "생산량은 production_data 테이블의 actual_quantity 컬럼을 합산합니다.",
            "계획 생산량은 production_data 테이블의 planned_quantity 컬럼을 합산합니다.",
            "불량율은 (defect_quantity / actual_quantity * 100)으로 계산합니다.",
            "달성률은 (actual_quantity / planned_quantity * 100)으로 계산합니다.",
            "생산 일자는 production_date를 기준으로 필터링합니다.",
            "생산 시간은 production_hour (0-23)로 시간별 데이터를 조회합니다.",
            "라인별 생산량은 line_id로 그룹화하여 조회합니다.",
            "제품별 생산량은 product_code나 product_name으로 그룹화합니다.",
            "근무조별 생산량은 shift (주간/야간)로 필터링합니다.",
            "설비 상태는 equipment_data의 status 컬럼으로 조회합니다 (가동/정지/점검).",
            "설비 다운타임은 equipment_data의 downtime (분) 컬럼으로 확인합니다.",
            "설비 가동률은 (operation_time / (operation_time + downtime) * 100)으로 계산합니다.",
            "불량 데이터는 defect_data 테이블에서 조회하며, production_id로 생산 데이터와 연결됩니다.",
            "불량 유형은 defect_type (외관/기능/치수)으로 분류할 수 있습니다.",
            "일별 생산 통계는 daily_production_summary VIEW에서 조회할 수 있습니다.",
            "시간별 생산 통계는 hourly_production_summary VIEW에서 조회할 수 있습니다.",
            "모든 쿼리 결과는 LIMIT 100으로 제한되어 성능을 보장합니다.",
            "날짜 필터링 시 production_date (DATE 타입)와 recorded_date (DATE 타입)를 구분합니다.",
        ]

        for knowledge in knowledge_data:
            session.execute(text("""
                INSERT INTO prompt_knowledge (content, created_at)
                VALUES (:content, :created_at)
            """), {
                "content": knowledge,
                "created_at": datetime.now()
            })

        session.commit()
        print(f"✅ {len(knowledge_data)}개의 도메인 지식 항목 저장됨")

        # 5. 초기화 완료 메시지
        print("\n" + "="*60)
        print("✅ 프롬프트 지식 베이스 초기화 완료!")
        print("="*60)
        print(f"📊 저장된 데이터:")
        print(f"  - 테이블 메타데이터: {len(tables_data)}개")
        print(f"  - 컬럼 메타데이터: {len(columns_data)}개")
        print(f"  - 용어 사전: {len(dict_data)}개")
        print(f"  - 도메인 지식: {len(knowledge_data)}개")
        print("="*60)

    except Exception as e:
        print(f"\n❌ 초기화 오류: {str(e)}")
        session.rollback()
        sys.exit(1)
    finally:
        session.close()

if __name__ == "__main__":
    print("🚀 프롬프트 지식 베이스 초기화를 시작합니다...\n")
    init_prompt_tables()
    print("\n✨ 초기화가 완료되었습니다!")
