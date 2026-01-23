"""
EXAONE AI 기반 자연어-SQL 변환 서비스

Mock 구현 (패턴 매칭 기반):
- 자연어 질문을 간단한 패턴 매칭 규칙으로 SQL 변환
- 폴백용으로 사용

실제 API 연동 (Friendli.ai):
- EXAONE API를 사용한 고급 NL-to-SQL 변환
- Few-shot 프롬프트 엔지니어링으로 정확한 SQL 생성
"""

import re
import os
import json
import requests
from typing import Optional, Dict, List, Any
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()


class ExaoneService:
    """EXAONE AI 자연어-SQL 변환 서비스"""

    # 사출 성형 도메인 관련 키워드 패턴
    PRODUCTION_KEYWORDS = [
        "생산", "생산량", "사이클", "주기", "개수",
        "불량", "결함", "에러", "오류", "불량율", "불량률", "불량유형",
        "온도", "압력", "무게", "무게 차이", "제품무게", "무게편차",
        "양호", "OK", "정상", "통과", "성공",
        "검사", "육안", "시험",
    ]

    EQUIPMENT_KEYWORDS = [
        "설비", "사출기", "기계", "장비", "기구",
        "금형", "몰드", "몰더", "MOLD", "몰더정보",
        "재료", "소재", "HIPS", "플라스틱", "흑색",
        "노즐", "배럴", "스크류", "히터",
        "가동", "정지", "점검", "유지보수", "유지",
        "온도", "발열", "쿨링", "냉각",
    ]

    TIME_KEYWORDS = {
        "오늘": "CURDATE()",
        "어제": "DATE_SUB(CURDATE(), INTERVAL 1 DAY)",
        "그저께": "DATE_SUB(CURDATE(), INTERVAL 2 DAY)",
        "재어제": "DATE_SUB(CURDATE(), INTERVAL 2 DAY)",
        "내일": "DATE_ADD(CURDATE(), INTERVAL 1 DAY)",
        "모레": "DATE_ADD(CURDATE(), INTERVAL 1 DAY)",
        "지난주": "DATE_SUB(CURDATE(), INTERVAL 7 DAY)",
        "지난달": "DATE_SUB(CURDATE(), INTERVAL 30 DAY)",
        "이번달": "DATE_FORMAT(CURDATE(), '%Y-%m-01')",
        "이번주": "DATE_SUB(CURDATE(), INTERVAL DAYOFWEEK(CURDATE())-1 DAY)",
        "최근7일": "DATE_SUB(CURDATE(), INTERVAL 7 DAY)",
        "최근30일": "DATE_SUB(CURDATE(), INTERVAL 30 DAY)",
    }

    @staticmethod
    def nl_to_sql(
        user_query: str,
        corrected_query: str,
        schema_info: Dict[str, Any],
        knowledge_base: Optional[List[str]] = None
    ) -> str:
        """
        자연어 질문을 SQL로 변환 (Mock 구현)

        Args:
            user_query: 원본 질문 (예: "오늘 생산량은?")
            corrected_query: 보정된 질문 (용어 사전 적용)
            schema_info: 스키마 메타데이터 (테이블, 컬럼 정보)
            knowledge_base: 도메인 지식 베이스

        Returns:
            생성된 SQL 쿼리 문자열
        """
        try:
            # 1. 질문 분석
            intent = ExaoneService._analyze_intent(corrected_query)

            # 2. 필요한 테이블과 컬럼 추출
            table_info = ExaoneService._determine_table(
                corrected_query,
                intent,
                schema_info
            )

            # 3. SQL 생성
            sql = ExaoneService._generate_sql(
                corrected_query,
                intent,
                table_info,
                schema_info
            )

            return sql

        except Exception as e:
            raise ValueError(f"SQL 생성 오류: {str(e)}")

    @staticmethod
    def _analyze_intent(query: str) -> Dict[str, Any]:
        """
        질문의 의도 분석

        Returns:
            {
                "action": "select|aggregate|filter|trend",
                "has_date_filter": bool,
                "has_groupby": bool,
                "is_question": bool
            }
        """
        query_lower = query.lower()

        intent = {
            "action": "select",
            "has_date_filter": False,
            "has_groupby": False,
            "is_question": query.endswith("?"),
            "is_aggregation": False,
        }

        # 집계 함수 감지
        # 1. 명시적 집계 키워드
        if any(keyword in query_lower for keyword in ["합계", "총", "평균", "최대", "최소", "몇개", "몇"]):
            intent["is_aggregation"] = True
            intent["action"] = "aggregate"
        # 2. 생산/불량 관련 키워드 (집계일 가능성 높음)
        elif any(keyword in query_lower for keyword in ["생산량", "생산", "불량량", "불량"]):
            intent["is_aggregation"] = True
            intent["action"] = "aggregate"

        # 날짜 필터 감지
        if any(keyword in query_lower for keyword in ExaoneService.TIME_KEYWORDS.keys()):
            intent["has_date_filter"] = True

        # 그룹화 감지
        if any(keyword in query_lower for keyword in ["라인별", "제품별", "시간별", "일별", "근무조별", "유형별"]):
            intent["has_groupby"] = True

        return intent

    @staticmethod
    def _determine_table(
        query: str,
        intent: Dict[str, Any],
        schema_info: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        질문에 필요한 테이블 결정 (사출 성형 스키마)

        Returns:
            {
                "table_name": str,
                "columns": List[str],
                "join_tables": List[str]
            }
        """
        query_lower = query.lower()
        table_name = "injection_cycle"
        columns = ["*"]
        join_tables = []

        # 설비 유지보수 관련 질문
        if any(keyword in query_lower for keyword in ["유지", "유지보수", "점검", "정비"]):
            table_name = "equipment_maintenance"
            columns = ["*"]

        # 에너지 관련 질문
        elif any(keyword in query_lower for keyword in ["에너지", "전력", "소비", "비용"]):
            table_name = "energy_usage"
            columns = ["*"]

        # 일별 통계 질문
        elif "일별" in query_lower or "날짜별" in query_lower:
            table_name = "daily_production"
            columns = ["*"]

        # 시간별 통계 질문
        elif "시간별" in query_lower or "시각별" in query_lower:
            table_name = "production_summary"
            columns = ["*"]

        # 금형/설비 정보 질문
        elif any(keyword in query_lower for keyword in ["금형", "몰드", "설비", "사출기"]):
            # 금형 정보는 injection_cycle과 함께 조회
            table_name = "injection_cycle"
            columns = ["*"]
            join_tables = ["mold_info"]

        # 기본값: injection_cycle (개별 사이클 데이터)
        else:
            table_name = "injection_cycle"
            columns = ["*"]

        return {
            "table_name": table_name,
            "columns": columns,
            "join_tables": join_tables
        }

    @staticmethod
    def _generate_sql(
        query: str,
        intent: Dict[str, Any],
        table_info: Dict[str, Any],
        schema_info: Dict[str, Any]
    ) -> str:
        """
        의도와 테이블 정보를 바탕으로 SQL 생성 (사출 성형 데이터)

        Rules:
        1. 집계(sum/count/avg)가 필요하면 SELECT SUM/COUNT/AVG
        2. 날짜 필터가 있으면 WHERE cycle_date = ...
        3. 그룹화가 필요하면 GROUP BY ...
        4. LIMIT 100 강제 추가
        """
        query_lower = query.lower()
        table_name = table_info["table_name"]

        # 1. SELECT 절 구성
        if intent["is_aggregation"]:
            select_clause = ExaoneService._build_aggregate_select(
                query, table_name
            )
        else:
            select_clause = "SELECT *"

        # 2. FROM 절
        from_clause = f"FROM {table_name}"

        # 3. WHERE 절 구성 (날짜, 불량 유형 등)
        where_clauses = []

        # 날짜 필터 (cycle_date 또는 date 컬럼 사용)
        for time_keyword, date_expr in ExaoneService.TIME_KEYWORDS.items():
            if time_keyword in query_lower:
                if table_name == "injection_cycle":
                    where_clauses.append(f"cycle_date = {date_expr}")
                elif table_name == "daily_production":
                    where_clauses.append(f"production_date = {date_expr}")
                elif table_name == "production_summary":
                    where_clauses.append(f"DATE(summary_datetime) = {date_expr}")
                elif table_name == "energy_usage":
                    where_clauses.append(f"usage_date = {date_expr}")
                break

        # 불량 유형 필터
        if "flash" in query_lower or "플래시" in query_lower:
            where_clauses.append("defect_type_id = 1")  # D001: Flash
        elif "void" in query_lower or "공동" in query_lower:
            where_clauses.append("defect_type_id = 2")  # D002: Void
        elif "weld" in query_lower or "용접" in query_lower:
            where_clauses.append("defect_type_id = 3")  # D003: Weld Line
        elif "jetting" in query_lower:
            where_clauses.append("defect_type_id = 4")  # D004: Jetting
        elif "flow" in query_lower or "흐름" in query_lower:
            where_clauses.append("defect_type_id = 5")  # D005: Flow Mark

        # 상태 필터 (성공/불량)
        if "양호" in query_lower or "정상" in query_lower or "성공" in query_lower:
            where_clauses.append("has_defect = FALSE")
        elif "불량" in query_lower or "결함" in query_lower:
            where_clauses.append("has_defect = TRUE")

        where_clause = ""
        if where_clauses:
            where_clause = "WHERE " + " AND ".join(where_clauses)

        # 4. GROUP BY 절 (그룹화가 필요한 경우)
        group_by_clause = ""
        if intent["has_groupby"]:
            group_by_clause = ExaoneService._build_group_by(
                query, table_name
            )

        # 5. ORDER BY 절 (날짜 역순 기본)
        if table_name == "injection_cycle":
            order_by_clause = "ORDER BY id DESC"
        elif table_name == "daily_production":
            order_by_clause = "ORDER BY production_date DESC"
        elif table_name == "production_summary":
            order_by_clause = "ORDER BY summary_datetime DESC"
        else:
            order_by_clause = "ORDER BY id DESC"

        # 6. LIMIT 절 (강제)
        limit_clause = "LIMIT 100"

        # SQL 조합
        sql_parts = [select_clause, from_clause]
        if where_clause:
            sql_parts.append(where_clause)
        if group_by_clause:
            sql_parts.append(group_by_clause)
        sql_parts.append(order_by_clause)
        sql_parts.append(limit_clause)

        sql = " ".join(sql_parts) + ";"

        return sql

    @staticmethod
    def _build_aggregate_select(query: str, table_name: str) -> str:
        """
        집계 함수를 포함한 SELECT 절 구성 (사출 성형)

        예:
        - "총 사이클 수" → COUNT(*)
        - "평균 무게" → AVG(product_weight_g)
        - "불량률" → SUM(CASE WHEN has_defect THEN 1 ELSE 0 END) / COUNT(*) * 100
        """
        query_lower = query.lower()

        # 사이클/생산량 관련 집계
        if any(kw in query_lower for kw in ["사이클", "생산", "생산량", "개수"]):
            if "일별" in query_lower or "시간별" in query_lower:
                return "SELECT COUNT(*) as total_cycles, SUM(CASE WHEN has_defect = 0 THEN 1 ELSE 0 END) as good_count"
            else:
                return "SELECT COUNT(*) as total_cycles, COUNT(DISTINCT cycle_date) as cycle_dates"

        # 불량 관련 집계
        elif any(kw in query_lower for kw in ["불량", "결함"]):
            if "율" in query_lower or "rate" in query_lower:
                return "SELECT COUNT(*) as total, SUM(CASE WHEN has_defect = 1 THEN 1 ELSE 0 END) as defect_count, ROUND(SUM(CASE WHEN has_defect = 1 THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 2) as defect_rate"
            else:
                return "SELECT SUM(CASE WHEN has_defect = 1 THEN 1 ELSE 0 END) as defect_count, COUNT(*) as total_cycles"

        # 무게 관련 집계
        elif any(kw in query_lower for kw in ["무게", "weight"]):
            if "평균" in query_lower:
                return "SELECT AVG(product_weight_g) as avg_weight, MIN(product_weight_g) as min_weight, MAX(product_weight_g) as max_weight, STDDEV(product_weight_g) as stddev_weight"
            else:
                return "SELECT AVG(product_weight_g) as avg_weight, COUNT(*) as total_cycles"

        # 온도 관련 집계
        elif any(kw in query_lower for kw in ["온도"]):
            return "SELECT AVG(temp_nh) as avg_nh, AVG(temp_h1) as avg_h1, AVG(temp_h2) as avg_h2, AVG(temp_h3) as avg_h3, AVG(temp_h4) as avg_h4"

        # 압력 관련 집계
        elif any(kw in query_lower for kw in ["압력"]):
            return "SELECT AVG(pressure_primary) as avg_primary, AVG(pressure_secondary) as avg_secondary, AVG(pressure_holding) as avg_holding"

        # 유지보수 관련 집계
        elif any(kw in query_lower for kw in ["유지", "점검", "정비"]):
            return "SELECT COUNT(*) as total_maintenance, MAX(maintenance_date) as last_maintenance, SUM(maintenance_hours) as total_hours"

        # 에너지 관련 집계
        elif any(kw in query_lower for kw in ["에너지", "전력"]):
            return "SELECT SUM(power_consumption_kwh) as total_kwh, AVG(power_consumption_kwh) as avg_kwh"

        # 기본값
        return "SELECT COUNT(*) as total_records"

    @staticmethod
    def _build_group_by(query: str, table_name: str) -> str:
        """
        GROUP BY 절 구성 (사출 성형)

        예:
        - "불량유형별 불량" → GROUP BY defect_type_id
        - "일별 생산" → GROUP BY cycle_date
        - "시간별 생산" → GROUP BY HOUR(cycle_datetime)
        """
        query_lower = query.lower()

        grouping_rules = [
            ("불량유형별", "defect_type_id"),
            ("불량유형별로", "defect_type_id"),
            ("불량별", "defect_type_id"),
            ("불량별로", "defect_type_id"),
            ("날짜별", "cycle_date"),
            ("날짜별로", "cycle_date"),
            ("일별", "cycle_date"),
            ("일별로", "cycle_date"),
            ("시간별", "HOUR(cycle_datetime)"),
            ("시간별로", "HOUR(cycle_datetime)"),
            ("금형별", "mold_id"),
            ("금형별로", "mold_id"),
            ("몰드별", "mold_id"),
            ("몰드별로", "mold_id"),
            ("재료별", "material_id"),
            ("재료별로", "material_id"),
        ]

        for keyword, column in grouping_rules:
            if keyword in query_lower:
                return f"GROUP BY {column}"

        # 기본값: 테이블에 따라
        if table_name == "injection_cycle":
            return "GROUP BY cycle_date"
        elif table_name == "daily_production":
            return "GROUP BY production_date"
        elif table_name == "production_summary":
            return "GROUP BY DATE(summary_datetime)"
        elif table_name == "equipment_maintenance":
            return "GROUP BY machine_id"

        return ""


# ============================================================================
# 실제 EXAONE API 연동 (Friendli.ai)
# ============================================================================

class ChatGPTService:
    """
    OpenAI ChatGPT API를 사용한 NL-to-SQL 변환 서비스
    """

    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
    OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4")
    OPENAI_API_BASE_URL = "https://api.openai.com/v1/chat/completions"

    @staticmethod
    def nl_to_sql(
        user_query: str,
        corrected_query: str,
        schema_info: Dict[str, Any],
        knowledge_base: Optional[List[str]] = None
    ) -> str:
        """
        ChatGPT API를 호출하여 SQL 생성

        Args:
            user_query: 원본 질문
            corrected_query: 보정된 질문
            schema_info: 스키마 메타데이터
            knowledge_base: 도메인 지식 리스트

        Returns:
            생성된 SQL 쿼리 문자열
        """
        if not ChatGPTService.OPENAI_API_KEY:
            raise ValueError("OPENAI_API_KEY가 설정되지 않았습니다")

        try:
            # 프롬프트 구성
            prompt = ChatGPTService._build_prompt(
                corrected_query, schema_info, knowledge_base
            )

            # ChatGPT API 호출
            payload = {
                "model": ChatGPTService.OPENAI_MODEL,
                "messages": [
                    {
                        "role": "system",
                        "content": """당신은 EXAONE 사출 성형 분석 에이전트입니다.

역할: 850톤 사출기의 생산 데이터 기반 SQL 쿼리 생성, 분석, 조언 제공

규칙:
1. SELECT 쿼리만 생성 (설명 없음)
2. 비교 질문("더 많다", "차이", "비교")이 있으면 두 기간의 데이터를 모두 조회
3. 날짜 필터: 오늘=CURDATE(), 어제=DATE_SUB(CURDATE(), INTERVAL 1 DAY), 그저께=DATE_SUB(CURDATE(), INTERVAL 2 DAY)
4. 집계함수(SUM, AVG, COUNT) 사용시 명확한 별칭 제공
5. GROUP BY 규칙:
   - "불량유형별" 키워드 → GROUP BY defect_type_id
   - "일별" 키워드 → GROUP BY cycle_date
   - "시간별" 키워드 → GROUP BY HOUR(cycle_datetime)
   - "금형별" 키워드 → GROUP BY mold_id
6. 예시:
   - "어제 불량률?" → SELECT COUNT(*) as total, SUM(CASE WHEN has_defect=1 THEN 1 ELSE 0 END) as defect_count, ROUND(SUM(CASE WHEN has_defect=1 THEN 1 ELSE 0 END)*100/COUNT(*), 2) as rate WHERE cycle_date=DATE_SUB(...)
   - "어제 불량유형별 불량?" → SELECT defect_type_id, COUNT(*) as count FROM injection_cycle WHERE cycle_date=DATE_SUB(...) AND has_defect=1 GROUP BY defect_type_id
7. SQL만 출력하세요.

🚨 중요: 이전 대화 컨텍스트가 포함되어 있다면 그것을 우선으로 사용하세요!
- 이전에 "어제"를 기준으로 했으면, 새로운 질문에서 날짜를 명시하지 않으면 **반드시 "어제"를 유지**하세요.
- 예) 이전: "어제 생산량?", 현재: "불량유형별?" → "어제 불량유형별 불량"으로 해석
- 날짜를 바꾸려면 사용자가 명시적으로 "오늘", "그저께" 등을 말해야 함""",
                    },
                    {
                        "role": "user",
                        "content": prompt,
                    },
                ],
                "temperature": 0.3,
                "max_tokens": 500,
            }

            response = requests.post(
                ChatGPTService.OPENAI_API_BASE_URL,
                headers={
                    "Authorization": f"Bearer {ChatGPTService.OPENAI_API_KEY}",
                    "Content-Type": "application/json",
                },
                json=payload,
                timeout=30,
            )

            # 응답 검증
            if response.status_code != 200:
                error_msg = response.text
                print(f"❌ ChatGPT API 오류 ({response.status_code}): {error_msg}")
                raise ValueError(f"ChatGPT API 호출 실패: {response.status_code}")

            # SQL 추출
            result = response.json()
            if "choices" not in result or not result["choices"]:
                raise ValueError("API 응답에 choices가 없습니다")

            generated_sql = result["choices"][0]["message"]["content"].strip()

            # SQL 정제
            generated_sql = ChatGPTService._clean_sql(generated_sql)

            print(f"✅ ChatGPT SQL 생성 성공")
            print(f"   생성된 SQL: {generated_sql[:100]}...")

            return generated_sql

        except requests.exceptions.Timeout:
            raise ValueError("ChatGPT 요청 타임아웃")
        except Exception as e:
            raise ValueError(f"ChatGPT SQL 생성 오류: {str(e)}")

    @staticmethod
    def _build_prompt(
        user_query: str,
        schema_info: Dict[str, Any],
        knowledge_base: Optional[List[str]] = None,
        context_info: str = ""
    ) -> str:
        """
        프롬프트 구성

        Args:
            user_query: 사용자 질문
            schema_info: 스키마 정보
            knowledge_base: 도메인 지식
            context_info: 이전 대화 컨텍스트 (시간 정보 등)
        """
        tables_info = ""
        if "tables" in schema_info:
            for table in schema_info["tables"]:
                tables_info += f"\n- {table['name']}: {table.get('description', 'N/A')}"
                for col in table.get("columns", []):
                    tables_info += f"\n  - {col['name']} ({col.get('type', 'unknown')})"

        if knowledge_base:
            knowledge_text = "\n".join([f"- {kb}" for kb in knowledge_base[:5]])
        else:
            knowledge_text = """- 생산량(사이클 수)는 COUNT(*)로 조회합니다
- 불량률은 SUM(CASE WHEN has_defect=1 THEN 1 ELSE 0 END)*100/COUNT(*) 로 계산합니다
- 불량은 has_defect=1, 양호는 has_defect=0으로 필터링합니다
- 불량 유형은 defect_type_id (1=Flash, 2=Void, 3=WeldLine, 등)
- 제품 무게는 product_weight_g (목표값: 252.5g ±2g)
- 온도: temp_nh, temp_h1, temp_h2, temp_h3, temp_h4
- 압력: pressure_primary, pressure_secondary, pressure_holding
- 오늘 = CURDATE(), 어제 = DATE_SUB(CURDATE(), INTERVAL 1 DAY)"""

        # 컨텍스트가 있으면 포함
        context_section = ""
        if context_info:
            context_section = f"""## 이전 대화 컨텍스트
{context_info}

주의: 사용자가 특별히 날짜를 명시하지 않았다면, 이전 대화에서 언급된 날짜를 기준으로 응답하세요.

"""

        prompt = f"""{context_section}## 데이터베이스 스키마 (850톤 사출기)
{tables_info}

## 도메인 지식
{knowledge_text}

## SQL 생성 규칙
1. MySQL 문법 사용
2. SELECT 쿼리만 생성 (INSERT, UPDATE, DELETE 금지)
3. 모든 쿼리에 LIMIT 100 추가
4. 집계 함수 사용 시 명확한 별칭 제공
5. 주석 제외
6. 비교 질문("더 많다", "차이", "비교")이 있으면 두 기간의 데이터를 모두 조회
7. 특별히 날짜를 명시하지 않으면 이전 대화의 컨텍스트를 따르세요

## 날짜 매핑
- 오늘: CURDATE()
- 어제: DATE_SUB(CURDATE(), INTERVAL 1 DAY)
- 그저께/재어제: DATE_SUB(CURDATE(), INTERVAL 2 DAY)

## 예제

예시 1) 단순 집계: "오늘 생산량은?"
SELECT SUM(actual_quantity) as total_quantity FROM production_data WHERE DATE(production_date) = CURDATE() LIMIT 100;

예시 2) 비교: "어제와 그저께 생산량을 비교해줘"
SELECT DATE(production_date) as date, SUM(actual_quantity) as total FROM production_data WHERE DATE(production_date) >= DATE_SUB(CURDATE(), INTERVAL 2 DAY) AND DATE(production_date) <= DATE_SUB(CURDATE(), INTERVAL 1 DAY) GROUP BY DATE(production_date) ORDER BY date DESC LIMIT 100;

예시 3) 라인별: "라인별 생산량은?"
SELECT line_id, SUM(actual_quantity) as quantity FROM production_data WHERE DATE(production_date) = CURDATE() GROUP BY line_id ORDER BY line_id LIMIT 100;

## 사용자 질문
"{user_query}"

SQL만 생성하고 다른 설명은 하지 마세요."""

        return prompt

    @staticmethod
    def generate_response(
        user_query: str,
        sql_result: Dict[str, Any]
    ) -> str:
        """
        SQL 실행 결과를 받아서 자연어 답변 생성

        Args:
            user_query: 원본 사용자 질문
            sql_result: {"columns": [...], "rows": [...], "row_count": ...} 형태의 SQL 결과

        Returns:
            자연스러운 한국어 답변 문자열
        """
        if not ChatGPTService.OPENAI_API_KEY:
            raise ValueError("OPENAI_API_KEY가 설정되지 않았습니다")

        try:
            # 결과를 읽기 쉬운 형식으로 포맷
            result_summary = ChatGPTService._format_result_for_llm(sql_result)

            prompt = f"""사용자의 질문에 대해 데이터베이스 조회 결과를 바탕으로 자연스러운 한국어 답변을 해주세요.

## 사용자 질문
{user_query}

## 조회 결과
{result_summary}

## 답변 규칙
1. 사람이 대답하는 것처럼 자연스럽게 답변하기
2. 숫자에는 천 단위 구분 기호(,) 포함
3. 날짜는 읽기 쉬운 형식으로 표현 (예: 2026년 1월 19일, 어제, 오늘)
4. 데이터가 없으면 그 이유를 자연스럽게 설명
5. 이모지나 특수 기호는 사용하지 않기
6. 2-3 문장으로 간결하게 답변

자연스러운 답변만 해주세요. 설명이나 주석은 불필요합니다."""

            # ChatGPT API 호출
            payload = {
                "model": ChatGPTService.OPENAI_MODEL,
                "messages": [
                    {
                        "role": "user",
                        "content": prompt,
                    },
                ],
                "temperature": 0.7,  # 자연스러운 문체를 위해 조금 높음
                "max_tokens": 300,
            }

            response = requests.post(
                ChatGPTService.OPENAI_API_BASE_URL,
                headers={
                    "Authorization": f"Bearer {ChatGPTService.OPENAI_API_KEY}",
                    "Content-Type": "application/json",
                },
                json=payload,
                timeout=30,
            )

            # 응답 검증
            if response.status_code != 200:
                error_msg = response.text
                print(f"❌ ChatGPT 응답 생성 오류 ({response.status_code}): {error_msg}")
                raise ValueError(f"ChatGPT 응답 생성 실패: {response.status_code}")

            result = response.json()
            if "choices" not in result or not result["choices"]:
                raise ValueError("API 응답에 choices가 없습니다")

            response_text = result["choices"][0]["message"]["content"].strip()

            print(f"✅ ChatGPT 응답 생성 성공")
            print(f"   생성된 답변: {response_text[:100]}...")

            return response_text

        except requests.exceptions.Timeout:
            raise ValueError("ChatGPT 응답 생성 타임아웃")
        except Exception as e:
            raise ValueError(f"ChatGPT 응답 생성 오류: {str(e)}")

    @staticmethod
    def generate_response_without_sql(user_query: str) -> str:
        """
        SQL이 필요 없는 일반 질문에 대한 자연어 응답 생성

        Args:
            user_query: 사용자 질문

        Returns:
            자연스러운 한국어 답변 문자열
        """
        if not ChatGPTService.OPENAI_API_KEY:
            raise ValueError("OPENAI_API_KEY가 설정되지 않았습니다")

        try:
            prompt = f"""당신은 EXAONE 사출 성형 분석 에이전트입니다. 850톤 사출기 생산 데이터 시스템의 영리한 어시스턴트입니다.

사용자의 질문에 대해 자연스러운 한국어 답변을 해주세요.

## 규칙
1. 친근하고 전문적인 톤으로 답변
2. 이모지나 특수 기호 사용 금지
3. 2-3 문장으로 간결하게 답변
4. 사출 성형 생산 데이터와 관련 있으면 그에 맞게 답변

## 사용자 질문
{user_query}

자연스러운 답변만 해주세요."""

            payload = {
                "model": ChatGPTService.OPENAI_MODEL,
                "messages": [
                    {
                        "role": "system",
                        "content": """당신은 EXAONE 사출 성형 분석 에이전트입니다.

역할:
- 850톤 사출기의 생산 데이터 기반 분석 및 조언
- 친근한 대화 상대
- 전문적이면서도 이해하기 쉬운 설명

특징:
- 정중하고 전문적
- 사출 성형/제조 도메인 전문 지식 활용
- 데이터 기반 인사이트 제공""",
                    },
                    {
                        "role": "user",
                        "content": prompt,
                    },
                ],
                "temperature": 0.7,
                "max_tokens": 300,
            }

            response = requests.post(
                ChatGPTService.OPENAI_API_BASE_URL,
                headers={
                    "Authorization": f"Bearer {ChatGPTService.OPENAI_API_KEY}",
                    "Content-Type": "application/json",
                },
                json=payload,
                timeout=30,
            )

            # 응답 검증
            if response.status_code != 200:
                error_msg = response.text
                print(f"❌ ChatGPT 응답 생성 오류 ({response.status_code}): {error_msg}")
                raise ValueError(f"ChatGPT 응답 생성 실패: {response.status_code}")

            result = response.json()
            if "choices" not in result or not result["choices"]:
                raise ValueError("API 응답에 choices가 없습니다")

            response_text = result["choices"][0]["message"]["content"].strip()

            print(f"✅ ChatGPT 일반 대화 응답 생성 성공")
            print(f"   생성된 답변: {response_text[:100]}...")

            return response_text

        except requests.exceptions.Timeout:
            raise ValueError("ChatGPT 응답 생성 타임아웃")
        except Exception as e:
            raise ValueError(f"ChatGPT 응답 생성 오류: {str(e)}")

    @staticmethod
    def _format_result_for_llm(sql_result: Dict[str, Any]) -> str:
        """
        SQL 결과를 LLM이 이해하기 쉬운 형식으로 포맷

        Args:
            sql_result: {"columns": [...], "rows": [...], "row_count": ...}

        Returns:
            포맷된 문자열
        """
        columns = sql_result.get("columns", [])
        rows = sql_result.get("rows", [])
        row_count = sql_result.get("row_count", 0)

        if row_count == 0:
            return "조회된 데이터가 없습니다."

        # 컬럼명 정렬
        result_lines = [f"조회 행 수: {row_count}개"]
        result_lines.append(f"컬럼: {', '.join(columns)}")
        result_lines.append("")

        # 결과 행들
        if row_count <= 10:  # 10개 이하면 모두 표시
            result_lines.append("데이터:")
            for i, row in enumerate(rows, 1):
                row_str = ", ".join([f"{col}: {row.get(col)}" for col in columns])
                result_lines.append(f"  행 {i}: {row_str}")
        else:  # 많으면 요약
            result_lines.append("데이터 (상위 5개만 표시):")
            for i, row in enumerate(rows[:5], 1):
                row_str = ", ".join([f"{col}: {row.get(col)}" for col in columns])
                result_lines.append(f"  행 {i}: {row_str}")
            result_lines.append(f"  ... 외 {row_count - 5}개 행")

        return "\n".join(result_lines)

    @staticmethod
    def _clean_sql(sql: str) -> str:
        """SQL 정제"""
        # <sql> 태그 제거
        if "<sql>" in sql:
            sql = sql.split("<sql>")[1].split("</sql>")[0]

        # ``` 마크다운 코드 블록 제거
        if "```sql" in sql:
            sql = sql.split("```sql")[1].split("```")[0]
        elif "```" in sql:
            sql = sql.split("```")[1].split("```")[0]

        sql = sql.strip()

        lines = []
        for line in sql.split("\n"):
            if "--" in line:
                line = line.split("--")[0]
            if "#" in line:
                line = line.split("#")[0]
            lines.append(line.strip())

        sql = " ".join([l for l in lines if l])

        select_pattern = r'SELECT\s+.*?(?:LIMIT\s+\d+)?'
        if "LIMIT" not in sql.upper():
            sql = sql.rstrip(";") + " LIMIT 100"

        if not sql.endswith(";"):
            sql += ";"

        return sql


class ExaoneAPIService:
    """
    실제 EXAONE API를 사용한 NL-to-SQL 변환 서비스

    Friendli.ai의 EXAONE 모델을 사용하여 자연어 질문을 SQL로 변환합니다.
    """

    EXAONE_API_BASE_URL = os.getenv(
        "EXAONE_API_BASE_URL",
        "https://api.friendli.ai/serverless/v1/chat/completions"
    )
    EXAONE_MODEL = os.getenv(
        "EXAONE_MODEL",
        "LGAI-EXAONE/K-EXAONE-236B-A23B"
    )
    EXAONE_TEMPERATURE = float(os.getenv("EXAONE_TEMPERATURE", "0.3"))
    EXAONE_MAX_TOKENS = int(os.getenv("EXAONE_MAX_TOKENS", "1000"))
    FRIENDLI_API_KEY = os.getenv("FRIENDLI_API_KEY")

    @staticmethod
    def nl_to_sql_api(
        user_query: str,
        corrected_query: str,
        schema_info: Dict[str, Any],
        knowledge_base: Optional[List[str]] = None
    ) -> str:
        """
        실제 EXAONE API를 호출하여 SQL 생성

        Args:
            user_query: 원본 질문 (예: "오늘 생산량은?")
            corrected_query: 보정된 질문 (용어 사전 적용)
            schema_info: 스키마 메타데이터
            knowledge_base: 도메인 지식 리스트

        Returns:
            생성된 SQL 쿼리 문자열

        Raises:
            ValueError: API 호출 실패 또는 SQL 파싱 오류
        """
        if not ExaoneAPIService.FRIENDLI_API_KEY:
            raise ValueError("FRIENDLI_API_KEY가 설정되지 않았습니다")

        try:
            # 1. 프롬프트 구성
            prompt = ExaoneAPIService._build_prompt(
                corrected_query, schema_info, knowledge_base
            )

            # 2. EXAONE API 호출
            payload = {
                "model": ExaoneAPIService.EXAONE_MODEL,
                "messages": [
                    {
                        "role": "system",
                        "content": """당신은 MySQL 사출 성형 데이터 전문가입니다. 사용자의 자연어 질문을 정확한 SQL로 변환합니다.

규칙:
1. SELECT 쿼리만 생성 (설명 없음)
2. 비교 질문("더 많다", "차이", "비교")이 있으면 두 기간의 데이터를 모두 조회
3. 날짜 필터: 오늘=CURDATE(), 어제=DATE_SUB(CURDATE(), INTERVAL 1 DAY)
4. 집계함수(SUM, AVG, COUNT) 사용시 명확한 별칭 제공
5. 불량은 has_defect 컬럼, defect_type_id 필드로 조회
6. SQL만 출력하세요.""",
                    },
                    {
                        "role": "user",
                        "content": prompt,
                    },
                ],
            }
            # max_tokens는 선택사항이지만, temperature는 서버에서 고정되어 있으므로 제거

            response = requests.post(
                ExaoneAPIService.EXAONE_API_BASE_URL,
                headers={
                    "Authorization": f"Bearer {ExaoneAPIService.FRIENDLI_API_KEY}",
                    "Content-Type": "application/json",
                },
                json=payload,
                timeout=30,
            )

            # 3. 응답 검증
            if response.status_code != 200:
                error_msg = response.text
                print(f"❌ EXAONE API 오류 ({response.status_code}): {error_msg}")
                raise ValueError(f"EXAONE API 호출 실패: {response.status_code}")

            # 4. SQL 추출
            result = response.json()
            if "choices" not in result or not result["choices"]:
                raise ValueError("API 응답에 choices가 없습니다")

            generated_sql = result["choices"][0]["message"]["content"].strip()

            # 5. SQL 정제 (마크다운 제거, 주석 제거)
            generated_sql = ExaoneAPIService._clean_sql(generated_sql)

            print(f"✅ EXAONE API 호출 성공")
            print(f"   원본 질문: {user_query}")
            print(f"   생성된 SQL: {generated_sql[:100]}...")

            return generated_sql

        except requests.exceptions.Timeout:
            raise ValueError("EXAONE API 타임아웃 (30초 초과)")
        except requests.exceptions.ConnectionError:
            raise ValueError("EXAONE API 연결 실패")
        except Exception as e:
            print(f"❌ SQL 생성 오류: {str(e)}")
            raise ValueError(f"SQL 생성 오류: {str(e)}")

    @staticmethod
    def _build_prompt(
        user_query: str,
        schema_info: Dict[str, Any],
        knowledge_base: Optional[List[str]] = None
    ) -> str:
        """
        EXAONE API를 위한 프롬프트 구성

        Few-shot 예제와 스키마 정보를 포함합니다.
        """
        # 스키마 정보 포맷팅
        tables_info = ""
        if "tables" in schema_info:
            for table in schema_info["tables"]:
                tables_info += f"\n- {table['name']}: {table.get('description', 'N/A')}"
                for col in table.get("columns", []):
                    tables_info += f"\n  - {col['name']} ({col.get('type', 'unknown')})"

        # 도메인 지식 포맷팅 (사출 성형)
        if knowledge_base:
            knowledge_text = "\n".join([f"- {kb}" for kb in knowledge_base[:5]])
        else:
            knowledge_text = """- 생산량(사이클 수)는 COUNT(*)로 조회합니다
- 불량률은 SUM(CASE WHEN has_defect=1 THEN 1 ELSE 0 END)*100/COUNT(*) 로 계산합니다
- 불량은 has_defect=1, 양호는 has_defect=0으로 필터링합니다
- 불량 유형은 defect_type_id (1=Flash, 2=Void, 3=WeldLine, 4=Jetting, 5=FlowMark, 등)
- 제품 무게는 product_weight_g (목표값: 252.5g ±2g)
- 온도: temp_nh, temp_h1, temp_h2, temp_h3, temp_h4, temp_mold_fixed, temp_mold_moving
- 압력: pressure_primary, pressure_secondary, pressure_holding
- 오늘 = CURDATE(), 어제 = DATE_SUB(CURDATE(), INTERVAL 1 DAY)"""

        prompt = f"""## 데이터베이스 스키마 (850톤 사출기)
다음은 사출 성형 생산 데이터베이스 스키마입니다:{tables_info}

## 도메인 지식
{knowledge_text}

## SQL 생성 규칙
1. MySQL 문법 사용
2. SELECT 쿼리만 생성 (INSERT, UPDATE, DELETE 금지)
3. 모든 쿼리에 LIMIT 100 추가
4. 집계 함수 사용 시 명확한 별칭 제공
5. ORDER BY는 반드시 SELECT된 컬럼만 사용
6. GROUP BY와 ORDER BY 함께 사용 시, ORDER BY 컬럼은 GROUP BY의 컬럼이거나 집계 함수여야 함
7. 한글 주석은 포함하지 않기

## Few-shot 예제 (사출 성형)

### 예제 1: 기본 사이클 수
질문: "오늘 생산량은?"
SQL: SELECT COUNT(*) as total_cycles FROM injection_cycle WHERE cycle_date = CURDATE() LIMIT 100;

### 예제 2: 불량유형별 불량 수 (GROUP BY)
질문: "어제 불량유형별 불량은?"
SQL: SELECT defect_type_id, COUNT(*) as count FROM injection_cycle WHERE cycle_date = DATE_SUB(CURDATE(), INTERVAL 1 DAY) AND has_defect = 1 GROUP BY defect_type_id ORDER BY count DESC LIMIT 100;

### 예제 3: 불량 필터
질문: "어제 불량은?"
SQL: SELECT COUNT(*) as defect_count FROM injection_cycle WHERE cycle_date = DATE_SUB(CURDATE(), INTERVAL 1 DAY) AND has_defect = 1 LIMIT 100;

### 예제 4: 불량률 계산
질문: "오늘 불량률은?"
SQL: SELECT COUNT(*) as total, SUM(CASE WHEN has_defect = 1 THEN 1 ELSE 0 END) as defect_count, ROUND(SUM(CASE WHEN has_defect = 1 THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 2) as defect_rate FROM injection_cycle WHERE cycle_date = CURDATE() LIMIT 100;

### 예제 5: 평균 무게
질문: "지난주 제품 무게 평균은?"
SQL: SELECT AVG(product_weight_g) as avg_weight, MIN(product_weight_g) as min_weight, MAX(product_weight_g) as max_weight FROM injection_cycle WHERE cycle_date >= DATE_SUB(CURDATE(), INTERVAL 7 DAY) LIMIT 100;

### 예제 6: 온도 범위
질문: "어제 노즐 온도 평균은?"
SQL: SELECT AVG(temp_nh) as nh, AVG(temp_h1) as h1, AVG(temp_h2) as h2, AVG(temp_h3) as h3, AVG(temp_h4) as h4 FROM injection_cycle WHERE cycle_date = DATE_SUB(CURDATE(), INTERVAL 1 DAY) LIMIT 100;

### 예제 7: 일별 통계
질문: "지난 3일 일별 생산량은?"
SQL: SELECT cycle_date, COUNT(*) as total_cycles, SUM(CASE WHEN has_defect = 0 THEN 1 ELSE 0 END) as good_count FROM injection_cycle WHERE cycle_date >= DATE_SUB(CURDATE(), INTERVAL 3 DAY) GROUP BY cycle_date ORDER BY cycle_date DESC LIMIT 100;

## 사용자 질문
"{user_query}"

위 질문을 SQL로 변환하세요. SQL만 출력하고 설명은 포함하지 마세요.
"""
        return prompt

    @staticmethod
    def _clean_sql(sql: str) -> str:
        """
        API 응답에서 SQL을 추출하고 정제합니다.

        - 마크다운 코드 블록 제거
        - 앞뒤 공백 제거
        - 주석 제거
        - 컬럼명 띄어쓰기 정규화
        - reasoning 텍스트 제거
        """
        # 마크다운 제거
        if "```sql" in sql:
            sql = sql.split("```sql")[1].split("```")[0]
        elif "```" in sql:
            sql = sql.split("```")[1].split("```")[0]

        # 앞뒤 공백 제거
        sql = sql.strip()

        # 한글 주석 제거 (-- 또는 #)
        lines = []
        for line in sql.split("\n"):
            # -- 주석 제거
            if "--" in line:
                line = line.split("--")[0]
            # # 주석 제거
            if "#" in line:
                line = line.split("#")[0]
            lines.append(line.strip())

        sql = " ".join([l for l in lines if l])

        # 컬럼명 띄어쓰기 정규화 (예: "production _date" → "production_date")
        sql = re.sub(r'\s+_', '_', sql)  # " _" → "_"
        sql = re.sub(r'_\s+', '_', sql)  # "_ " → "_"

        # 가장 강력한 방법: SELECT...LIMIT 패턴을 추출
        # SELECT 부터 LIMIT 숫자까지만 추출 (그 이후 텍스트 제거)
        # 패턴: SELECT ... FROM ... WHERE ... LIMIT number
        select_pattern = r'SELECT\s+.*?\s+LIMIT\s+\d+'
        match = re.search(select_pattern, sql, re.IGNORECASE | re.DOTALL)

        if match:
            sql = match.group(0)
            # 마지막에 세미콜론 추가 (없으면)
            if not sql.endswith(";"):
                sql += ";"
            return sql

        # 위 패턴이 없으면 다른 방법 시도: LIMIT가 있는 경우
        # LIMIT 절을 포함한 모든 텍스트 이후 제거
        limit_match = re.search(r'LIMIT\s+\d+\s*;?', sql, re.IGNORECASE)
        if limit_match:
            sql = sql[:limit_match.end()]
            if not sql.endswith(";"):
                sql += ";"
            return sql

        # LIMIT가 없으면 원본 반환 (안전장치)
        if not sql.endswith(";"):
            sql += ";"

        return sql


class GeminiService:
    """
    Google Gemini API를 사용한 NL-to-SQL 변환 서비스
    """

    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
    GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")
    GEMINI_API_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/models"

    @staticmethod
    def nl_to_sql(
        user_query: str,
        corrected_query: str,
        schema_info: Dict[str, Any],
        knowledge_base: Optional[List[str]] = None
    ) -> str:
        """
        Gemini API를 호출하여 SQL 생성

        Args:
            user_query: 원본 질문
            corrected_query: 보정된 질문
            schema_info: 스키마 메타데이터
            knowledge_base: 도메인 지식 리스트

        Returns:
            생성된 SQL 쿼리 문자열
        """
        if not GeminiService.GEMINI_API_KEY:
            raise ValueError("GEMINI_API_KEY가 설정되지 않았습니다")

        try:
            # 프롬프트 구성
            prompt = ChatGPTService._build_prompt(
                corrected_query, schema_info, knowledge_base
            )

            # Gemini API 호출
            url = f"{GeminiService.GEMINI_API_BASE_URL}/{GeminiService.GEMINI_MODEL}:generateContent?key={GeminiService.GEMINI_API_KEY}"

            payload = {
                "contents": [
                    {
                        "role": "user",
                        "parts": [
                            {
                                "text": f"""당신은 EXAONE 사출 성형 분석 에이전트입니다.

역할: 850톤 사출기의 생산 데이터 기반 SQL 쿼리 생성, 분석, 조언 제공

규칙:
1. SELECT 쿼리만 생성 (설명 없음)
2. 비교 질문("더 많다", "차이", "비교")이 있으면 두 기간의 데이터를 모두 조회
3. 날짜 필터:
   - 오늘=CURDATE()
   - 어제=DATE_SUB(CURDATE(), INTERVAL 1 DAY)
   - 그저께/재어제=DATE_SUB(CURDATE(), INTERVAL 2 DAY)
4. 집계함수(SUM, AVG, COUNT) 사용시 명확한 별칭 제공
5. GROUP BY 규칙:
   - "불량유형별" 키워드 → GROUP BY defect_type_id
   - "일별" 키워드 → GROUP BY cycle_date
   - "시간별" 키워드 → GROUP BY HOUR(cycle_datetime)
   - "불량률", "생산량" 같은 요약 지표 + "별" 없으면 COUNT 사용 (GROUP BY 없음)
6. 예시:
   - "어제 불량률?" → SELECT COUNT(*) as total, SUM(CASE WHEN has_defect=1 THEN 1 ELSE 0 END) as defect_count, ROUND(SUM(CASE WHEN has_defect=1 THEN 1 ELSE 0 END)*100/COUNT(*), 2) as rate WHERE cycle_date=DATE_SUB(...)
   - "어제 불량유형별 불량?" → SELECT defect_type_id, COUNT(*) as count FROM injection_cycle WHERE cycle_date=DATE_SUB(...) AND has_defect=1 GROUP BY defect_type_id
7. SQL만 출력하세요.

🚨 중요: 이전 대화 컨텍스트가 포함되어 있다면 그것을 우선으로 사용하세요!
- 이전에 "어제"를 기준으로 했으면, 새로운 질문에서 날짜를 명시하지 않으면 **반드시 "어제"를 유지**하세요.
- 예) 이전: "어제 생산량?", 현재: "불량유형별?" → "어제 불량유형별 불량"으로 해석
- 날짜를 바꾸려면 사용자가 명시적으로 "오늘", "그저께" 등을 말해야 함

{prompt}"""
                            }
                        ]
                    }
                ],
                "generationConfig": {
                    "temperature": 0.3,
                    "maxOutputTokens": 500,
                },
            }

            response = requests.post(
                url,
                json=payload,
                timeout=30,
            )

            # 응답 검증
            if response.status_code != 200:
                error_msg = response.text
                print(f"❌ Gemini API 오류 ({response.status_code}): {error_msg}")
                raise ValueError(f"Gemini API 호출 실패: {response.status_code}")

            # SQL 추출
            result = response.json()
            if "candidates" not in result or not result["candidates"]:
                raise ValueError("API 응답에 candidates가 없습니다")

            generated_sql = result["candidates"][0]["content"]["parts"][0]["text"].strip()

            # SQL 정제
            generated_sql = ChatGPTService._clean_sql(generated_sql)

            print(f"✅ Gemini SQL 생성 성공")
            print(f"   생성된 SQL: {generated_sql[:100]}...")

            return generated_sql

        except requests.exceptions.Timeout:
            raise ValueError("Gemini 요청 타임아웃")
        except Exception as e:
            raise ValueError(f"Gemini SQL 생성 오류: {str(e)}")

    @staticmethod
    def generate_response(
        user_query: str,
        sql_result: Dict[str, Any]
    ) -> str:
        """
        SQL 실행 결과를 받아서 자연어 답변 생성

        Args:
            user_query: 원본 사용자 질문
            sql_result: {"columns": [...], "rows": [...], "row_count": ...} 형태의 SQL 결과

        Returns:
            자연스러운 한국어 답변 문자열
        """
        if not GeminiService.GEMINI_API_KEY:
            raise ValueError("GEMINI_API_KEY가 설정되지 않았습니다")

        try:
            # 결과를 읽기 쉬운 형식으로 포맷
            result_summary = ChatGPTService._format_result_for_llm(sql_result)

            prompt = f"""사용자의 질문에 대해 데이터베이스 조회 결과를 바탕으로 자연스러운 한국어 답변을 해주세요.

## 사용자 질문
{user_query}

## 조회 결과
{result_summary}

## 답변 규칙
1. 사람이 대답하는 것처럼 자연스럽게 답변하기
2. 숫자에는 천 단위 구분 기호(,) 포함
3. 날짜는 읽기 쉬운 형식으로 표현 (예: 2026년 1월 19일, 어제, 오늘)
4. 데이터가 없으면 그 이유를 자연스럽게 설명
5. 이모지나 특수 기호는 사용하지 않기
6. 2-3 문장으로 간결하게 답변

자연스러운 답변만 해주세요. 설명이나 주석은 불필요합니다."""

            # Gemini API 호출
            url = f"{GeminiService.GEMINI_API_BASE_URL}/{GeminiService.GEMINI_MODEL}:generateContent?key={GeminiService.GEMINI_API_KEY}"

            payload = {
                "contents": [
                    {
                        "role": "user",
                        "parts": [
                            {
                                "text": prompt
                            }
                        ]
                    }
                ],
                "generationConfig": {
                    "temperature": 0.7,
                    "maxOutputTokens": 300,
                },
            }

            response = requests.post(
                url,
                json=payload,
                timeout=30,
            )

            # 응답 검증
            if response.status_code != 200:
                error_msg = response.text
                print(f"❌ Gemini 응답 생성 오류 ({response.status_code}): {error_msg}")
                raise ValueError(f"Gemini 응답 생성 실패: {response.status_code}")

            result = response.json()
            if "candidates" not in result or not result["candidates"]:
                raise ValueError("API 응답에 candidates가 없습니다")

            response_text = result["candidates"][0]["content"]["parts"][0]["text"].strip()

            print(f"✅ Gemini 응답 생성 성공")
            print(f"   생성된 답변: {response_text[:100]}...")

            return response_text

        except requests.exceptions.Timeout:
            raise ValueError("Gemini 응답 생성 타임아웃")
        except Exception as e:
            raise ValueError(f"Gemini 응답 생성 오류: {str(e)}")

    @staticmethod
    def generate_response_without_sql(user_query: str) -> str:
        """
        SQL이 필요 없는 일반 질문에 대한 자연어 응답 생성

        Args:
            user_query: 사용자 질문

        Returns:
            자연스러운 한국어 답변 문자열
        """
        if not GeminiService.GEMINI_API_KEY:
            raise ValueError("GEMINI_API_KEY가 설정되지 않았습니다")

        try:
            prompt = f"""당신은 EXAONE 사출 성형 분석 에이전트입니다. 850톤 사출기 생산 데이터 시스템의 영리한 어시스턴트입니다.

사용자의 질문에 대해 자연스러운 한국어 답변을 해주세요.

## 규칙
1. 친근하고 전문적인 톤으로 답변
2. 이모지나 특수 기호 사용 금지
3. 2-3 문장으로 간결하게 답변
4. 사출 성형 생산 데이터와 관련 있으면 그에 맞게 답변

## 사용자 질문
{user_query}

자연스러운 답변만 해주세요."""

            # Gemini API 호출
            url = f"{GeminiService.GEMINI_API_BASE_URL}/{GeminiService.GEMINI_MODEL}:generateContent?key={GeminiService.GEMINI_API_KEY}"

            payload = {
                "contents": [
                    {
                        "role": "user",
                        "parts": [
                            {
                                "text": prompt
                            }
                        ]
                    }
                ],
                "generationConfig": {
                    "temperature": 0.7,
                    "maxOutputTokens": 300,
                },
            }

            response = requests.post(
                url,
                json=payload,
                timeout=30,
            )

            if response.status_code != 200:
                error_msg = response.text
                print(f"❌ Gemini 일반 응답 생성 오류 ({response.status_code}): {error_msg}")
                raise ValueError(f"Gemini 일반 응답 생성 실패: {response.status_code}")

            result = response.json()
            if "candidates" not in result or not result["candidates"]:
                raise ValueError("API 응답에 candidates가 없습니다")

            response_text = result["candidates"][0]["content"]["parts"][0]["text"].strip()

            print(f"✅ Gemini 일반 응답 생성 성공")
            print(f"   생성된 답변: {response_text[:100]}...")

            return response_text

        except requests.exceptions.Timeout:
            raise ValueError("Gemini 일반 응답 생성 타임아웃")
        except Exception as e:
            raise ValueError(f"Gemini 일반 응답 생성 오류: {str(e)}")
