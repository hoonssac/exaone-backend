"""
Schema-based RAG (Retrieval-Augmented Generation)

사출 성형 제조 데이터베이스 스키마의 의미론적 검색으로
사용자 질문에서 올바른 테이블/칼럼을 자동으로 찾습니다.

예시:
- 사용자: "오늘 생산량은?" (생산량과 다른 표현)
- RAG: total_cycles_produced, good_products_count 자동 검색
- 결과: 정확한 SQL 생성
"""

import json
import logging
from typing import List, Dict, Any, Optional
from scipy.spatial.distance import cosine
from sklearn.feature_extraction.text import TfidfVectorizer
from sqlalchemy.orm import Session
from sqlalchemy import text
import numpy as np

logger = logging.getLogger(__name__)


class SchemaRAGService:
    """사출 성형 제조 데이터베이스 스키마 RAG 서비스"""

    _vectorizer: Optional[TfidfVectorizer] = None
    _fitted = False
    _schema_info: Dict[str, Any] = {}

    # ========================================================================
    # 사출 성형 제조 데이터베이스 스키마 정의
    # ========================================================================

    INJECTION_MOLDING_SCHEMA = {
        "tables": [
            {
                "id": 1,
                "name": "injection_molding_machine",
                "description": "사출기 설비 정보",
                "keywords": ["설비", "사출기", "장비", "기계"],
                "columns": [
                    {"name": "id", "type": "INT", "description": "설비 ID (PK)"},
                    {"name": "equipment_id", "type": "VARCHAR", "description": "설비 코드 (IM-850-001)"},
                    {"name": "equipment_name", "type": "VARCHAR", "description": "설비명"},
                    {"name": "manufacturer", "type": "VARCHAR", "description": "제조사"},
                    {"name": "capacity_ton", "type": "INT", "description": "사출 톤수 (850)"},
                    {"name": "installation_date", "type": "DATE", "description": "설치 일자"},
                    {"name": "last_maintenance_date", "type": "DATE", "description": "마지막 유지보수 일자"},
                    {"name": "status", "type": "VARCHAR", "description": "상태 (가동/정지/점검)"},
                    {"name": "operating_hours", "type": "BIGINT", "description": "누적 가동 시간"},
                    {"name": "created_at", "type": "DATETIME", "description": "등록 일시"},
                ]
            },
            {
                "id": 2,
                "name": "mold_info",
                "description": "금형 정보 (Cap Decor Upper)",
                "keywords": ["금형", "금형정보", "제품", "제품코드", "캐비티"],
                "columns": [
                    {"name": "id", "type": "INT", "description": "금형 ID (PK)"},
                    {"name": "mold_code", "type": "VARCHAR", "description": "금형 코드 (DC1)"},
                    {"name": "mold_name", "type": "VARCHAR", "description": "금형명"},
                    {"name": "product_code", "type": "VARCHAR", "description": "제품 코드"},
                    {"name": "product_name", "type": "VARCHAR", "description": "제품명"},
                    {"name": "cavity_count", "type": "INT", "description": "캐비티 수"},
                    {"name": "target_weight_g", "type": "DECIMAL", "description": "목표 제품 무게 (252.5g)"},
                    {"name": "target_weight_tolerance_minus", "type": "DECIMAL", "description": "무게 허용공차 -"},
                    {"name": "target_weight_tolerance_plus", "type": "DECIMAL", "description": "무게 허용공차 +"},
                    {"name": "runner_weight_g", "type": "DECIMAL", "description": "러너 무게"},
                    {"name": "total_weight_g", "type": "DECIMAL", "description": "총 무게 제품+러너 (519.0g)"},
                    {"name": "cooling_zones", "type": "INT", "description": "냉각 존 수"},
                    {"name": "hot_runner_zones", "type": "INT", "description": "핫 러너 존 수"},
                    {"name": "mold_manufacturer", "type": "VARCHAR", "description": "금형 제작사"},
                    {"name": "status", "type": "VARCHAR", "description": "상태 (사용중/정지/유지보수)"},
                    {"name": "created_at", "type": "DATETIME", "description": "등록 일시"},
                ]
            },
            {
                "id": 3,
                "name": "material_spec",
                "description": "원재료 사양 (HIPS)",
                "keywords": ["재료", "원재료", "자재", "HIPS", "재료온도"],
                "columns": [
                    {"name": "id", "type": "INT", "description": "자재 ID (PK)"},
                    {"name": "material_code", "type": "VARCHAR", "description": "자재 코드"},
                    {"name": "material_name", "type": "VARCHAR", "description": "자재명 (HIPS)"},
                    {"name": "material_grade", "type": "VARCHAR", "description": "등급"},
                    {"name": "color", "type": "VARCHAR", "description": "색상"},
                    {"name": "supplier", "type": "VARCHAR", "description": "공급사"},
                    {"name": "cylinder_temp_nh", "type": "INT", "description": "NH 온도 설정값 (220℃)"},
                    {"name": "cylinder_temp_h1", "type": "INT", "description": "H1 온도 설정값 (225℃)"},
                    {"name": "cylinder_temp_h2", "type": "INT", "description": "H2 온도 설정값 (230℃)"},
                    {"name": "cylinder_temp_h3", "type": "INT", "description": "H3 온도 설정값 (215℃)"},
                    {"name": "cylinder_temp_h4", "type": "INT", "description": "H4 온도 설정값 (200℃)"},
                    {"name": "melting_point_min", "type": "INT", "description": "최소 용융 온도 (180℃)"},
                    {"name": "melting_point_max", "type": "INT", "description": "최대 용융 온도 (240℃)"},
                    {"name": "created_at", "type": "DATETIME", "description": "등록 일시"},
                ]
            },
            {
                "id": 4,
                "name": "injection_cycle",
                "description": "개별 사이클 데이터 (585,920행) - 핵심 테이블",
                "keywords": ["사이클", "생산", "온도", "압력", "무게", "불량", "주기"],
                "columns": [
                    {"name": "id", "type": "BIGINT", "description": "사이클 ID (PK)"},
                    {"name": "machine_id", "type": "INT", "description": "설비 ID (사출기 1, 2, 3...)"},
                    {"name": "mold_id", "type": "INT", "description": "금형 ID (DC1 금형)"},
                    {"name": "material_id", "type": "INT", "description": "재료 ID (HIPS 등)"},
                    {"name": "cycle_date", "type": "DATE", "description": "사이클 실행 날짜"},
                    {"name": "cycle_hour", "type": "TINYINT", "description": "시간 (0-23)"},
                    {"name": "cycle_minute", "type": "TINYINT", "description": "분 (0-59)"},
                    {"name": "cycle_sequence", "type": "INT", "description": "시간 내 순서"},
                    {"name": "temp_nh", "type": "INT", "description": "NH 온도 (℃)"},
                    {"name": "temp_h1", "type": "INT", "description": "H1 온도 (℃)"},
                    {"name": "temp_h2", "type": "INT", "description": "H2 온도 (℃)"},
                    {"name": "temp_h3", "type": "INT", "description": "H3 온도 (℃)"},
                    {"name": "temp_h4", "type": "INT", "description": "H4 온도 (℃)"},
                    {"name": "temp_mold_fixed", "type": "INT", "description": "고정측 금형 온도 (℃)"},
                    {"name": "temp_mold_moving", "type": "INT", "description": "가동측 금형 온도 (℃)"},
                    {"name": "temp_hot_runner", "type": "INT", "description": "핫 러너 온도 (℃)"},
                    {"name": "pressure_primary", "type": "INT", "description": "1차 사출 압력 (bar)"},
                    {"name": "pressure_secondary", "type": "INT", "description": "2차 사출 압력 (bar)"},
                    {"name": "pressure_holding", "type": "INT", "description": "보압 (bar)"},
                    {"name": "product_weight_g", "type": "DECIMAL", "description": "제품 무게 (g)"},
                    {"name": "weight_deviation_g", "type": "DECIMAL", "description": "무게 편차 (g)"},
                    {"name": "weight_ok", "type": "BOOLEAN", "description": "무게 합격 여부"},
                    {"name": "has_defect", "type": "BOOLEAN", "description": "불량 여부"},
                    {"name": "defect_type_id", "type": "INT", "description": "불량 유형 ID"},
                    {"name": "defect_description", "type": "VARCHAR", "description": "불량 설명"},
                    {"name": "visual_inspection_ok", "type": "BOOLEAN", "description": "외관 검사 합격"},
                    {"name": "operator_id", "type": "VARCHAR", "description": "담당 작업자 ID"},
                    {"name": "created_at", "type": "DATETIME", "description": "등록 일시"},
                ]
            },
            {
                "id": 5,
                "name": "production_summary",
                "description": "시간별 생산 요약 (8,760행)",
                "keywords": ["시간별", "요약", "시간", "시간당", "시간별생산"],
                "columns": [
                    {"name": "id", "type": "BIGINT", "description": "요약 ID (PK)"},
                    {"name": "summary_date", "type": "DATE", "description": "요약 날짜"},
                    {"name": "summary_hour", "type": "TINYINT", "description": "시간 (0-23)"},
                    {"name": "machine_id", "type": "INT", "description": "설비 ID"},
                    {"name": "mold_id", "type": "INT", "description": "금형 ID"},
                    {"name": "total_cycles", "type": "INT", "description": "총 사이클 수"},
                    {"name": "good_products", "type": "INT", "description": "정상 제품 수"},
                    {"name": "defective_products", "type": "INT", "description": "불량 제품 수"},
                    {"name": "defect_rate", "type": "DECIMAL", "description": "불량률 (%)"},
                    {"name": "avg_weight_g", "type": "DECIMAL", "description": "평균 무게 (g)"},
                    {"name": "weight_variance", "type": "DECIMAL", "description": "무게 표준편차"},
                    {"name": "weight_out_of_spec", "type": "INT", "description": "규격 외 무게 개수"},
                    {"name": "avg_temp_h1", "type": "DECIMAL", "description": "평균 H1 온도 (℃)"},
                    {"name": "avg_temp_h2", "type": "DECIMAL", "description": "평균 H2 온도 (℃)"},
                    {"name": "avg_temp_mold", "type": "DECIMAL", "description": "평균 금형 온도 (℃)"},
                    {"name": "flash_count", "type": "INT", "description": "Flash 불량 수"},
                    {"name": "void_count", "type": "INT", "description": "Void 불량 수"},
                    {"name": "weld_line_count", "type": "INT", "description": "Weld Line 불량 수"},
                    {"name": "jetting_count", "type": "INT", "description": "Jetting 불량 수"},
                    {"name": "created_at", "type": "DATETIME", "description": "등록 일시"},
                ]
            },
            {
                "id": 6,
                "name": "daily_production",
                "description": "일별 생산 통계 (365행)",
                "keywords": ["일별", "일일", "매일", "날짜", "생산량", "생산", "통계"],
                "columns": [
                    {"name": "id", "type": "BIGINT", "description": "요약 ID (PK)"},
                    {"name": "production_date", "type": "DATE", "description": "생산 날짜"},
                    {"name": "machine_id", "type": "INT", "description": "설비 ID"},
                    {"name": "mold_id", "type": "INT", "description": "금형 ID"},
                    {"name": "total_cycles_produced", "type": "INT", "description": "총 사이클 수"},
                    {"name": "good_products_count", "type": "INT", "description": "정상 제품 개수"},
                    {"name": "defective_count", "type": "INT", "description": "불량 제품 개수"},
                    {"name": "defect_rate", "type": "DECIMAL", "description": "불량률 (%)"},
                    {"name": "target_production", "type": "INT", "description": "목표 생산량 (1,608)"},
                    {"name": "production_rate", "type": "DECIMAL", "description": "생산 달성률 (%)"},
                    {"name": "operating_hours_actual", "type": "INT", "description": "실제 가동 시간"},
                    {"name": "downtime_minutes", "type": "INT", "description": "정지 시간 (분)"},
                    {"name": "downtime_reason", "type": "VARCHAR", "description": "정지 사유"},
                    {"name": "avg_weight_g", "type": "DECIMAL", "description": "평균 무게 (g)"},
                    {"name": "weight_min_g", "type": "DECIMAL", "description": "최소 무게 (g)"},
                    {"name": "weight_max_g", "type": "DECIMAL", "description": "최대 무게 (g)"},
                    {"name": "weight_out_of_spec_count", "type": "INT", "description": "규격 외 무게 개수"},
                    {"name": "avg_cylinder_temp", "type": "DECIMAL", "description": "평균 실린더 온도 (℃)"},
                    {"name": "avg_mold_temp", "type": "DECIMAL", "description": "평균 금형 온도 (℃)"},
                    {"name": "temp_stability_ok", "type": "BOOLEAN", "description": "온도 안정성 여부"},
                    {"name": "flash_count", "type": "INT", "description": "Flash 불량 수"},
                    {"name": "void_count", "type": "INT", "description": "Void 불량 수"},
                    {"name": "weld_line_count", "type": "INT", "description": "Weld Line 불량 수"},
                    {"name": "jetting_count", "type": "INT", "description": "Jetting 불량 수"},
                    {"name": "flow_mark_count", "type": "INT", "description": "Flow Mark 불량 수"},
                    {"name": "other_defect_count", "type": "INT", "description": "기타 불량 수"},
                    {"name": "created_at", "type": "DATETIME", "description": "등록 일시"},
                ]
            },
            {
                "id": 7,
                "name": "injection_defect_type",
                "description": "불량 유형 정의 (Flash, Void, Weld Line 등 9가지)",
                "keywords": ["불량", "결함", "불량유형", "Flash", "Void", "Weld", "Jetting"],
                "columns": [
                    {"name": "id", "type": "INT", "description": "불량 유형 ID (PK)"},
                    {"name": "defect_code", "type": "VARCHAR", "description": "불량 코드 (D001-D009)"},
                    {"name": "defect_name_kr", "type": "VARCHAR", "description": "불량명 (한글)"},
                    {"name": "defect_name_en", "type": "VARCHAR", "description": "불량명 (영문)"},
                    {"name": "defect_category", "type": "VARCHAR", "description": "불량 분류 (외관/기능/치수)"},
                    {"name": "severity", "type": "VARCHAR", "description": "심각도 (경/중/심)"},
                    {"name": "cause_description", "type": "TEXT", "description": "원인 설명"},
                    {"name": "created_at", "type": "DATETIME", "description": "등록 일시"},
                ]
            },
            {
                "id": 8,
                "name": "equipment_maintenance",
                "description": "설비 유지보수 기록",
                "keywords": ["유지보수", "정비", "점검", "수리", "개선", "교체"],
                "columns": [
                    {"name": "id", "type": "BIGINT", "description": "유지보수 ID (PK)"},
                    {"name": "machine_id", "type": "INT", "description": "설비 ID"},
                    {"name": "maintenance_type", "type": "VARCHAR", "description": "유지보수 유형 (정기/수리/개선)"},
                    {"name": "scheduled_date", "type": "DATE", "description": "예정 일자"},
                    {"name": "actual_date", "type": "DATE", "description": "실제 시공 일자"},
                    {"name": "technician_name", "type": "VARCHAR", "description": "담당 기술자"},
                    {"name": "description", "type": "TEXT", "description": "작업 내용"},
                    {"name": "parts_replaced", "type": "VARCHAR", "description": "교체 부품"},
                    {"name": "cost", "type": "DECIMAL", "description": "작업 비용 (원)"},
                    {"name": "status", "type": "VARCHAR", "description": "상태 (예정/진행중/완료)"},
                    {"name": "created_at", "type": "DATETIME", "description": "등록 일시"},
                ]
            },
            {
                "id": 9,
                "name": "energy_usage",
                "description": "에너지 사용량 (시간별)",
                "keywords": ["에너지", "전력", "냉각수", "전기", "에너지사용"],
                "columns": [
                    {"name": "id", "type": "BIGINT", "description": "에너지 ID (PK)"},
                    {"name": "machine_id", "type": "INT", "description": "설비 ID"},
                    {"name": "energy_type", "type": "VARCHAR", "description": "에너지 유형 (전력/냉각수)"},
                    {"name": "usage_date", "type": "DATE", "description": "사용 날짜"},
                    {"name": "usage_hour", "type": "TINYINT", "description": "시간 (0-23)"},
                    {"name": "consumption_value", "type": "DECIMAL", "description": "사용량"},
                    {"name": "unit", "type": "VARCHAR", "description": "단위 (kWh/ton)"},
                    {"name": "cost", "type": "DECIMAL", "description": "비용 (원)"},
                    {"name": "created_at", "type": "DATETIME", "description": "등록 일시"},
                ]
            },
        ]
    }

    @classmethod
    def get_vectorizer(cls) -> TfidfVectorizer:
        """TfidfVectorizer 싱글톤"""
        if cls._vectorizer is None:
            cls._vectorizer = TfidfVectorizer(
                analyzer="char",
                ngram_range=(2, 3),
                lowercase=False,
                stop_words=None,
                max_features=1000,
            )
            logger.info("SchemaRAG: TfidfVectorizer 초기화")
        return cls._vectorizer

    @classmethod
    def initialize_schema_embeddings(cls, db: Session) -> None:
        """
        스키마 정보를 벡터화하여 메모리에 저장
        처음 한 번만 실행
        """
        try:
            cls._schema_info = cls.INJECTION_MOLDING_SCHEMA

            vectorizer = cls.get_vectorizer()

            # 모든 테이블 이름, 설명, 컬럼명 수집
            training_texts = []
            for table in cls.INJECTION_MOLDING_SCHEMA["tables"]:
                training_texts.append(table["name"])
                training_texts.append(table["description"])
                for col in table["columns"]:
                    training_texts.append(col["name"])
                    training_texts.append(col["description"])
                training_texts.extend(table["keywords"])

            # 벡터화기 학습
            if not cls._fitted and len(training_texts) > 0:
                vectorizer.fit(training_texts)
                cls._fitted = True
                logger.info(f"SchemaRAG: 스키마 정보 초기화 완료 ({len(cls.INJECTION_MOLDING_SCHEMA['tables'])} 테이블)")
        except Exception as e:
            logger.error(f"SchemaRAG 초기화 오류: {str(e)}")
            raise

    @classmethod
    def search_similar_tables(cls, user_query: str, top_k: int = 3) -> List[Dict[str, Any]]:
        """
        사용자 질문과 유사한 테이블 검색
        """
        if not cls._fitted or not cls._schema_info:
            return []

        vectorizer = cls.get_vectorizer()
        query_vector = vectorizer.transform([user_query]).toarray()[0]

        results = []
        for table in cls._schema_info.get("tables", []):
            table_text = f"{table['name']} {table['description']} {' '.join(table.get('keywords', []))}"
            table_vector = vectorizer.transform([table_text]).toarray()[0]

            # 코사인 유사도 계산
            try:
                similarity = 1 - cosine(query_vector, table_vector)
            except:
                similarity = 0

            results.append({
                "table": table["name"],
                "description": table["description"],
                "similarity": similarity,
                "columns": table["columns"]
            })

        # 유사도순 정렬
        results.sort(key=lambda x: x["similarity"], reverse=True)
        return results[:top_k]

    @classmethod
    def search_similar_columns(cls, user_query: str, table_name: str = None, top_k: int = 5) -> List[Dict[str, Any]]:
        """
        사용자 질문과 유사한 칼럼 검색
        """
        if not cls._fitted or not cls._schema_info:
            return []

        vectorizer = cls.get_vectorizer()
        query_vector = vectorizer.transform([user_query]).toarray()[0]

        results = []
        for table in cls._schema_info.get("tables", []):
            # 특정 테이블만 검색하면 제한
            if table_name and table["name"] != table_name:
                continue

            for col in table["columns"]:
                col_text = f"{col['name']} {col['description']}"
                col_vector = vectorizer.transform([col_text]).toarray()[0]

                try:
                    similarity = 1 - cosine(query_vector, col_vector)
                except:
                    similarity = 0

                results.append({
                    "table": table["name"],
                    "column": col["name"],
                    "description": col["description"],
                    "type": col["type"],
                    "similarity": similarity
                })

        # 유사도순 정렬
        results.sort(key=lambda x: x["similarity"], reverse=True)
        return results[:top_k]

    @classmethod
    def get_schema_context(cls) -> str:
        """
        AI 모델에 전달할 스키마 컨텍스트 생성
        """
        if not cls._schema_info:
            return ""

        context = "# 사출 성형 제조 데이터베이스 스키마\n\n"
        for table in cls._schema_info.get("tables", []):
            context += f"## {table['name']}\n"
            context += f"{table['description']}\n\n"
            context += "칼럼:\n"
            for col in table["columns"]:
                context += f"- {col['name']} ({col['type']}): {col['description']}\n"
            context += "\n"

        return context

    @classmethod
    def get_table_by_name(cls, table_name: str) -> Optional[Dict[str, Any]]:
        """
        테이블명으로 테이블 정보 조회
        """
        if not cls._schema_info:
            return None

        for table in cls._schema_info.get("tables", []):
            if table["name"] == table_name:
                return table
        return None

    @classmethod
    def get_column_by_name(cls, table_name: str, column_name: str) -> Optional[Dict[str, Any]]:
        """
        테이블명과 칼럼명으로 칼럼 정보 조회
        """
        table = cls.get_table_by_name(table_name)
        if not table:
            return None

        for col in table.get("columns", []):
            if col["name"] == column_name:
                return col
        return None

    @classmethod
    def search_similar_schema(
        cls,
        db: Session,
        query: str,
        top_k: int = 5
    ) -> Dict[str, Any]:
        """
        사용자 질문과 유사한 테이블과 컬럼을 함께 검색

        Args:
            db: SQLAlchemy Session
            query: 사용자 질문
            top_k: 반환할 결과 개수

        Returns:
            {
                "tables": [테이블 검색 결과],
                "columns": [컬럼 검색 결과]
            }
        """
        try:
            # 스키마 초기화 (필요시)
            if not cls._fitted or not cls._schema_info:
                cls.initialize_schema_embeddings(db)

            # 테이블 검색
            table_results = cls.search_similar_tables(query, top_k=3)

            # 컬럼 검색
            column_results = cls.search_similar_columns(query, top_k=top_k)

            return {
                "tables": table_results,
                "columns": column_results
            }
        except Exception as e:
            logger.error(f"Schema RAG 검색 오류: {str(e)}")
            return {"tables": [], "columns": []}

    @classmethod
    def format_schema_hint(cls, schema_results: Dict[str, Any]) -> str:
        """
        Schema RAG 검색 결과를 프롬프트용 문자열로 포맷

        Args:
            schema_results: search_similar_schema() 반환값

        Returns:
            프롬프트에 추가할 문자열
        """
        try:
            if not schema_results or (not schema_results.get("tables") and not schema_results.get("columns")):
                return ""

            hint = "## 추천 테이블/컬럼 (자동 검색)\n\n"

            # 테이블 결과
            tables = schema_results.get("tables", [])
            if tables:
                hint += "### 추천 테이블\n"
                for table in tables[:3]:
                    similarity = table.get("similarity", 0)
                    hint += f"- **{table['table']}** (유사도: {similarity:.2f})\n"
                    hint += f"  설명: {table['description']}\n"
                    # 테이블 내 주요 컬럼들 표시
                    cols = table.get("columns", [])[:3]
                    if cols:
                        hint += f"  컬럼: {', '.join([c['name'] for c in cols])}\n"
                hint += "\n"

            # 컬럼 결과
            columns = schema_results.get("columns", [])
            if columns:
                hint += "### 추천 컬럼\n"
                for col in columns[:5]:
                    similarity = col.get("similarity", 0)
                    table = col.get("table", "?")
                    column = col.get("column", "?")
                    desc = col.get("description", "N/A")
                    hint += f"- **{table}.{column}** (유사도: {similarity:.2f})\n"
                    hint += f"  타입: {col.get('type', 'unknown')}\n"
                    hint += f"  설명: {desc}\n"
                hint += "\n"

            hint += "위의 추천 테이블/컬럼을 참고하여 SQL을 작성하세요.\n"

            return hint
        except Exception as e:
            logger.error(f"Schema RAG 힌트 포맷 오류: {str(e)}")
            return ""
