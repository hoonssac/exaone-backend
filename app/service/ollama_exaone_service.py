"""
Ollama 로컬 EXAONE 기반 NL-to-SQL 변환 서비스
"""

import os
import requests
import re
from typing import Optional, Dict, List, Any
from dotenv import load_dotenv

load_dotenv()


class OllamaExaoneService:
    """Ollama 로컬 EXAONE을 사용한 NL-to-SQL 변환"""

    OLLAMA_BASE_URL = os.getenv(
        "OLLAMA_BASE_URL",
        "http://localhost:11434"
    )
    OLLAMA_MODEL = os.getenv(
        "OLLAMA_MODEL",
        "exaone3.5:2.4b"
    )

    @staticmethod
    def nl_to_sql(
        user_query: str,
        corrected_query: str,
        schema_info: Dict[str, Any],
        knowledge_base: Optional[List[str]] = None
    ) -> str:
        """
        Ollama 로컬 EXAONE으로 SQL 생성

        Args:
            user_query: 원본 질문 (예: "오늘 생산량은?")
            corrected_query: 보정된 질문
            schema_info: 스키마 메타데이터
            knowledge_base: 도메인 지식

        Returns:
            생성된 SQL 쿼리

        Raises:
            ValueError: Ollama 연결 실패 또는 SQL 생성 오류
        """
        try:
            # 프롬프트 구성
            prompt = OllamaExaoneService._build_prompt(
                corrected_query, schema_info, knowledge_base
            )

            print(f"🔄 Ollama EXAONE 호출 중... (모델: {OllamaExaoneService.OLLAMA_MODEL})")

            # Ollama API 호출
            response = requests.post(
                f"{OllamaExaoneService.OLLAMA_BASE_URL}/api/generate",
                json={
                    "model": OllamaExaoneService.OLLAMA_MODEL,
                    "prompt": prompt,
                    "temperature": 0.3,
                    "stream": False,
                    "num_predict": 500,
                },
                timeout=60,
            )

            if response.status_code != 200:
                raise ValueError(f"Ollama API 오류: {response.status_code}")

            result = response.json()
            generated_sql = result.get("response", "").strip()

            if not generated_sql:
                raise ValueError("Ollama가 응답을 생성하지 못했습니다")

            # SQL 정제
            generated_sql = OllamaExaoneService._clean_sql(generated_sql)

            print(f"✅ Ollama EXAONE 호출 성공")
            print(f"   생성된 SQL: {generated_sql[:100]}...")

            return generated_sql

        except requests.exceptions.ConnectionError:
            raise ValueError(
                f"Ollama 서버에 연결할 수 없습니다. ({OllamaExaoneService.OLLAMA_BASE_URL})\n"
                "실행: ollama serve"
            )
        except requests.exceptions.Timeout:
            raise ValueError("Ollama 요청 타임아웃 (60초 초과)")
        except Exception as e:
            raise ValueError(f"SQL 생성 오류: {str(e)}")

    @staticmethod
    def _build_prompt(
        user_query: str,
        schema_info: Dict[str, Any],
        knowledge_base: Optional[List[str]] = None
    ) -> str:
        """프롬프트 구성"""
        # 스키마 정보
        tables_info = ""
        if "tables" in schema_info:
            for table in schema_info["tables"]:
                tables_info += f"\n- {table['name']}: {table.get('description', 'N/A')}"
                for col in table.get("columns", []):
                    tables_info += f"\n  - {col['name']} ({col.get('type', 'unknown')})"

        # 도메인 지식
        if knowledge_base:
            knowledge_text = "\n".join([f"- {kb}" for kb in knowledge_base[:5]])
        else:
            knowledge_text = """- 생산량은 actual_quantity로 조회합니다
- 불량률은 defect_quantity / actual_quantity * 100 으로 계산합니다
- 오늘 = CURDATE(), 어제 = DATE_SUB(CURDATE(), INTERVAL 1 DAY)"""

        prompt = f"""You are a MySQL expert. Convert the user's natural language question into a valid SQL query.

## Database Schema
{tables_info}

## Domain Knowledge
{knowledge_text}

## SQL Generation Rules
1. Use MySQL syntax
2. Generate only SELECT queries (no INSERT, UPDATE, DELETE)
3. Add LIMIT 100 to all queries
4. Provide clear aliases for aggregate functions
5. Do not include comments

## Few-shot Examples

Question: "오늘 생산량은?"
SQL: SELECT SUM(actual_quantity) as total_production FROM production_data WHERE production_date = CURDATE() LIMIT 100;

Question: "라인별 생산량은?"
SQL: SELECT line_id, SUM(actual_quantity) as total FROM production_data GROUP BY line_id ORDER BY line_id LIMIT 100;

Question: "어제 불량은?"
SQL: SELECT SUM(defect_quantity) as total_defect FROM production_data WHERE production_date = DATE_SUB(CURDATE(), INTERVAL 1 DAY) LIMIT 100;

## User Question
"{user_query}"

Convert this question to SQL. Output only the SQL, no explanation."""

        return prompt

    @staticmethod
    def _clean_sql(sql: str) -> str:
        """SQL 정제"""
        # 마크다운 제거
        if "```sql" in sql:
            sql = sql.split("```sql")[1].split("```")[0]
        elif "```" in sql:
            sql = sql.split("```")[1].split("```")[0]

        sql = sql.strip()

        # 주석 제거
        lines = []
        for line in sql.split("\n"):
            if "--" in line:
                line = line.split("--")[0]
            if "#" in line:
                line = line.split("#")[0]
            lines.append(line.strip())

        sql = " ".join([l for l in lines if l])

        # SELECT ... LIMIT 패턴 추출
        select_pattern = r'SELECT\s+.*?\s+LIMIT\s+\d+'
        match = re.search(select_pattern, sql, re.IGNORECASE | re.DOTALL)

        if match:
            sql = match.group(0)
            if not sql.endswith(";"):
                sql += ";"
            return sql

        if not sql.endswith(";"):
            sql += ";"

        return sql
