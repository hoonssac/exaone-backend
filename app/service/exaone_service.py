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

    # 제조 도메인 관련 키워드 패턴
    PRODUCTION_KEYWORDS = [
        "생산량", "생산", "생산된", "산출", "출산",
        "계획", "목표", "예정", "계획량",
        "불량", "결함", "에러", "오류", "불량율", "불량률",
        "달성률", "달성", "목표달성", "품질",
    ]

    EQUIPMENT_KEYWORDS = [
        "설비", "기계", "장비", "라인", "라인1", "라인2", "라인3",
        "프레스", "용접", "조립", "검사", "포장",
        "가동", "정지", "점검", "유지보수", "다운타임",
        "운영시간", "정지시간", "운영",
    ]

    TIME_KEYWORDS = {
        "오늘": "CURDATE()",
        "어제": "DATE_SUB(CURDATE(), INTERVAL 1 DAY)",
        "내일": "DATE_ADD(CURDATE(), INTERVAL 1 DAY)",
        "지난주": "DATE_SUB(CURDATE(), INTERVAL 7 DAY)",
        "지난달": "DATE_SUB(CURDATE(), INTERVAL 30 DAY)",
        "이번달": "DATE_TRUNC('month', CURDATE())",
        "이번주": "DATE_TRUNC('week', CURDATE())",
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
        if any(keyword in query_lower for keyword in ["합계", "총", "평균", "최대", "최소", "몇개", "몇"]):
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
        질문에 필요한 테이블 결정

        Returns:
            {
                "table_name": str,
                "columns": List[str],
                "join_tables": List[str]
            }
        """
        query_lower = query.lower()
        table_name = "production_data"
        columns = ["*"]
        join_tables = []

        # 설비 관련 질문
        if any(keyword in query_lower for keyword in ExaoneService.EQUIPMENT_KEYWORDS):
            table_name = "equipment_data"
            columns = ["*"]

        # 불량 관련 질문
        elif any(keyword in query_lower for keyword in ["불량", "결함", "에러"]):
            table_name = "defect_data"
            columns = ["*"]
            join_tables = ["production_data"]

        # 통계 관련 질문
        elif "일별" in query_lower:
            table_name = "daily_production_summary"
            columns = ["*"]
        elif "시간별" in query_lower:
            table_name = "hourly_production_summary"
            columns = ["*"]

        # 기본값: production_data
        else:
            table_name = "production_data"
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
        의도와 테이블 정보를 바탕으로 SQL 생성

        Rules:
        1. 집계(sum/count/avg)가 필요하면 SELECT SUM/COUNT/AVG
        2. 날짜 필터가 있으면 WHERE production_date = ...
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

        # 3. WHERE 절 구성 (날짜, 라인, 제품 등)
        where_clauses = []

        # 날짜 필터
        for time_keyword, date_expr in ExaoneService.TIME_KEYWORDS.items():
            if time_keyword in query_lower:
                if "production_date" in schema_info.get("available_columns", []):
                    where_clauses.append(f"production_date = {date_expr}")
                elif "recorded_date" in schema_info.get("available_columns", []):
                    where_clauses.append(f"recorded_date = {date_expr}")
                break

        # 라인 필터
        if "라인-01" in query or "라인1" in query:
            where_clauses.append("line_id = 'LINE-01'")
        elif "라인-02" in query or "라인2" in query:
            where_clauses.append("line_id = 'LINE-02'")
        elif "라인-03" in query or "라인3" in query:
            where_clauses.append("line_id = 'LINE-03'")

        # 상태 필터 (설비)
        if "가동" in query_lower and "정지" not in query_lower:
            where_clauses.append("status = '가동'")
        elif "정지" in query_lower:
            where_clauses.append("status = '정지'")

        where_clause = ""
        if where_clauses:
            where_clause = "WHERE " + " AND ".join(where_clauses)

        # 4. GROUP BY 절 (그룹화가 필요한 경우)
        group_by_clause = ""
        if intent["has_groupby"]:
            group_by_clause = ExaoneService._build_group_by(
                query, table_name
            )

        # 5. ORDER BY 절 (최근순 기본)
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
        집계 함수를 포함한 SELECT 절 구성

        예:
        - "총 생산량" → SUM(actual_quantity)
        - "평균 불량율" → AVG(defect_rate)
        - "최대 다운타임" → MAX(downtime)
        """
        query_lower = query.lower()

        # 생산 관련 집계
        if any(kw in query_lower for kw in ["생산량", "생산"]):
            if "계획" in query_lower:
                return "SELECT SUM(planned_quantity) as total_planned, COUNT(*) as count"
            else:
                return "SELECT SUM(actual_quantity) as total_production, COUNT(*) as count"

        # 불량 관련 집계
        elif any(kw in query_lower for kw in ["불량", "결함"]):
            if "율" in query_lower or "rate" in query_lower.lower():
                return "SELECT AVG(defect_rate) as avg_defect_rate, SUM(defect_quantity) as total_defect"
            else:
                return "SELECT SUM(defect_quantity) as total_defect, COUNT(*) as count"

        # 설비 관련 집계
        elif any(kw in query_lower for kw in ["다운타임", "정지시간"]):
            return "SELECT SUM(downtime) as total_downtime, AVG(downtime) as avg_downtime"
        elif any(kw in query_lower for kw in ["가동", "운영"]):
            return "SELECT SUM(operation_time) as total_operation_time, AVG(operation_time) as avg_operation_time"

        # 기본값
        return "SELECT COUNT(*) as total_count, AVG(actual_quantity) as avg_quantity"

    @staticmethod
    def _build_group_by(query: str, table_name: str) -> str:
        """
        GROUP BY 절 구성

        예:
        - "라인별 생산량" → GROUP BY line_id
        - "제품별 불량" → GROUP BY product_code
        - "시간별 생산" → GROUP BY production_hour
        """
        query_lower = query.lower()

        grouping_rules = [
            ("라인별", "line_id"),
            ("라인별로", "line_id"),
            ("제품별", "product_code"),
            ("제품별로", "product_code"),
            ("시간별", "production_hour"),
            ("시간별로", "production_hour"),
            ("일별", "production_date"),
            ("일별로", "production_date"),
            ("근무조별", "shift"),
            ("근무조별로", "shift"),
            ("불량유형별", "defect_type"),
            ("상태별", "status"),
        ]

        for keyword, column in grouping_rules:
            if keyword in query_lower:
                return f"GROUP BY {column}"

        # 기본값: 라인별
        if table_name == "production_data":
            return "GROUP BY line_id"
        elif table_name == "equipment_data":
            return "GROUP BY equipment_id"
        elif table_name == "defect_data":
            return "GROUP BY defect_type"

        return ""


# ============================================================================
# 실제 EXAONE API 연동 (Friendli.ai)
# ============================================================================

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
                        "content": "당신은 MySQL 전문가입니다. 사용자의 자연어 질문을 정확한 SQL로 변환합니다. SELECT 쿼리만 생성하고, SQL만 출력하세요. 설명은 포함하지 마세요.",
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

        # 도메인 지식 포맷팅
        if knowledge_base:
            knowledge_text = "\n".join([f"- {kb}" for kb in knowledge_base[:5]])
        else:
            knowledge_text = """- 생산량은 actual_quantity로 조회합니다
- 불량률은 defect_quantity / actual_quantity * 100 으로 계산합니다
- 오늘 = CURDATE(), 어제 = DATE_SUB(CURDATE(), INTERVAL 1 DAY)"""

        prompt = f"""## 데이터베이스 스키마
다음은 제조 데이터베이스 스키마입니다:{tables_info}

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

## Few-shot 예제

### 예제 1: 기본 집계
질문: "오늘 생산량은?"
SQL: SELECT SUM(actual_quantity) as total_production FROM production_data WHERE production_date = CURDATE() LIMIT 100;

### 예제 2: 그룹화 (GROUP BY + ORDER BY)
질문: "라인별 생산량은?"
SQL: SELECT line_id, SUM(actual_quantity) as total FROM production_data GROUP BY line_id ORDER BY line_id LIMIT 100;
참고: ORDER BY는 SELECT된 컬럼(line_id)이나 집계 함수(SUM) 사용

### 예제 3: 조건 필터
질문: "어제 불량은?"
SQL: SELECT SUM(defect_quantity) as total_defect FROM production_data WHERE production_date = DATE_SUB(CURDATE(), INTERVAL 1 DAY) LIMIT 100;

### 예제 4: 다중 조건
질문: "라인1의 평균 불량률은?"
SQL: SELECT AVG(defect_quantity / actual_quantity * 100) as avg_defect_rate FROM production_data WHERE line_id = 'LINE-01' LIMIT 100;

### 예제 5: 날짜 범위
질문: "지난주 생산량은?"
SQL: SELECT SUM(actual_quantity) as total FROM production_data WHERE production_date >= DATE_SUB(CURDATE(), INTERVAL 7 DAY) LIMIT 100;

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
