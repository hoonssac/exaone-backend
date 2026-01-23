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
                    "num_predict": 100,
                },
                timeout=300,
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
        except requests.exceptions.Timeout as e:
            print(f"❌ Ollama 타임아웃: {str(e)}")
            raise ValueError(f"Ollama 요청 타임아웃 (설정된 시간 초과): {str(e)}")
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

        # 도메인 지식 (사출 성형)
        if knowledge_base:
            knowledge_text = "\n".join([f"- {kb}" for kb in knowledge_base[:5]])
        else:
            knowledge_text = """- 생산량(사이클 수)는 COUNT(*)로 조회합니다
- 불량률은 SUM(CASE WHEN has_defect=1 THEN 1 ELSE 0 END)*100/COUNT(*) 로 계산합니다
- 불량은 has_defect=1, 양호는 has_defect=0으로 필터링합니다
- 불량 유형은 defect_type_id (1=Flash, 2=Void, 3=WeldLine, 4=Jetting, 5=FlowMark)
- 제품 무게는 product_weight_g (목표값: 252.5g ±2g)
- 오늘 = CURDATE(), 어제 = DATE_SUB(CURDATE(), INTERVAL 1 DAY)"""

        prompt = f"""당신은 MySQL 사출 성형 데이터 전문가입니다. 사용자의 자연어 질문을 정확한 SQL 쿼리로 변환하세요.

## 데이터베이스 스키마 (850톤 사출기)
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

## 예제 (사출 성형)

질문: "오늘 생산량은?"
SQL: SELECT COUNT(*) as total_cycles FROM injection_cycle WHERE cycle_date = CURDATE() LIMIT 100;

질문: "어제 불량유형별 불량은?"
SQL: SELECT defect_type_id, COUNT(*) as count FROM injection_cycle WHERE cycle_date = DATE_SUB(CURDATE(), INTERVAL 1 DAY) AND has_defect = 1 GROUP BY defect_type_id ORDER BY count DESC LIMIT 100;

질문: "어제 불량은?"
SQL: SELECT COUNT(*) as defect_count FROM injection_cycle WHERE cycle_date = DATE_SUB(CURDATE(), INTERVAL 1 DAY) AND has_defect = 1 LIMIT 100;

질문: "오늘 불량률은?"
SQL: SELECT COUNT(*) as total, SUM(CASE WHEN has_defect = 1 THEN 1 ELSE 0 END) as defect_count, ROUND(SUM(CASE WHEN has_defect = 1 THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 2) as defect_rate FROM injection_cycle WHERE cycle_date = CURDATE() LIMIT 100;

질문: "지난주 제품 무게 평균은?"
SQL: SELECT AVG(product_weight_g) as avg_weight, MIN(product_weight_g) as min_weight, MAX(product_weight_g) as max_weight FROM injection_cycle WHERE cycle_date >= DATE_SUB(CURDATE(), INTERVAL 7 DAY) LIMIT 100;

질문: "어제와 오늘 생산량을 비교해줘"
SQL: SELECT cycle_date, COUNT(*) as total_cycles FROM injection_cycle WHERE cycle_date >= DATE_SUB(CURDATE(), INTERVAL 1 DAY) GROUP BY cycle_date ORDER BY cycle_date DESC LIMIT 100;

## 사용자 질문
"{user_query}"

이 질문을 SQL로 변환하세요. SQL만 출력하고 설명은 포함하지 마세요."""

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

    @staticmethod
    def _format_result_for_llm(sql_result: Dict[str, Any]) -> str:
        """SQL 결과를 LLM이 이해하기 쉬운 형식으로 포맷"""
        if not sql_result.get("rows"):
            return "결과 데이터 없음"

        columns = sql_result.get("columns", [])
        rows = sql_result.get("rows", [])
        row_count = sql_result.get("row_count", 0)

        result_text = f"총 {row_count}개 행\n\n"
        result_text += "| " + " | ".join(columns) + " |\n"
        result_text += "| " + " | ".join(["---"] * len(columns)) + " |\n"

        for row in rows[:10]:  # 최대 10행만
            values = [str(row.get(col, "")) for col in columns]
            result_text += "| " + " | ".join(values) + " |\n"

        if row_count > 10:
            result_text += f"\n... 외 {row_count - 10}개 행"

        return result_text

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
        try:
            # 결과를 읽기 쉬운 형식으로 포맷
            result_summary = OllamaExaoneService._format_result_for_llm(sql_result)

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

            print(f"🔄 Ollama EXAONE 응답 생성 중... (모델: {OllamaExaoneService.OLLAMA_MODEL})")

            response = requests.post(
                f"{OllamaExaoneService.OLLAMA_BASE_URL}/api/generate",
                json={
                    "model": OllamaExaoneService.OLLAMA_MODEL,
                    "prompt": prompt,
                    "temperature": 0.7,
                    "stream": False,
                    "num_predict": 300,
                },
                timeout=300,
            )

            if response.status_code != 200:
                raise ValueError(f"Ollama API 오류: {response.status_code}")

            result = response.json()
            response_text = result.get("response", "").strip()

            if not response_text:
                raise ValueError("Ollama가 응답을 생성하지 못했습니다")

            print(f"✅ Ollama EXAONE 응답 생성 성공")
            print(f"   생성된 답변: {response_text[:100]}...")

            return response_text

        except requests.exceptions.ConnectionError:
            raise ValueError(
                f"Ollama 서버에 연결할 수 없습니다. ({OllamaExaoneService.OLLAMA_BASE_URL})"
            )
        except requests.exceptions.Timeout:
            raise ValueError("Ollama 응답 생성 타임아웃")
        except Exception as e:
            raise ValueError(f"Ollama 응답 생성 오류: {str(e)}")

    @staticmethod
    def generate_response_without_sql(user_query: str) -> str:
        """
        SQL이 필요 없는 일반 질문에 대한 자연어 응답 생성

        Args:
            user_query: 사용자 질문

        Returns:
            자연스러운 한국어 답변 문자열
        """
        try:
            prompt = f"""당신은 EXAONE 제조 에이전트입니다. 생산 데이터 시스템의 영리한 어시스턴트입니다.

사용자의 질문에 대해 자연스러운 한국어 답변을 해주세요.

## 규칙
1. 친근하고 전문적인 톤으로 답변
2. 이모지나 특수 기호 사용 금지
3. 2-3 문장으로 간결하게 답변
4. 생산 데이터 시스템과 관련 있으면 그에 맞게 답변

## 사용자 질문
{user_query}

자연스러운 답변만 해주세요."""

            print(f"🔄 Ollama EXAONE 일반 응답 생성 중... (모델: {OllamaExaoneService.OLLAMA_MODEL})")

            response = requests.post(
                f"{OllamaExaoneService.OLLAMA_BASE_URL}/api/generate",
                json={
                    "model": OllamaExaoneService.OLLAMA_MODEL,
                    "prompt": prompt,
                    "temperature": 0.7,
                    "stream": False,
                    "num_predict": 300,
                },
                timeout=300,
            )

            if response.status_code != 200:
                raise ValueError(f"Ollama API 오류: {response.status_code}")

            result = response.json()
            response_text = result.get("response", "").strip()

            if not response_text:
                raise ValueError("Ollama가 응답을 생성하지 못했습니다")

            print(f"✅ Ollama EXAONE 일반 응답 생성 성공")
            print(f"   생성된 답변: {response_text[:100]}...")

            return response_text

        except requests.exceptions.ConnectionError:
            raise ValueError(
                f"Ollama 서버에 연결할 수 없습니다. ({OllamaExaoneService.OLLAMA_BASE_URL})"
            )
        except requests.exceptions.Timeout:
            raise ValueError("Ollama 일반 응답 생성 타임아웃")
        except Exception as e:
            raise ValueError(f"Ollama 일반 응답 생성 오류: {str(e)}")

    @staticmethod
    def _ask_yes_no(prompt: str) -> str:
        """
        Ollama에 yes/no 질문을 하고 답변을 받습니다.

        대화 흐름 분석 등 간단한 yes/no 판단이 필요할 때 사용합니다.

        Args:
            prompt: yes/no 질문을 포함한 프롬프트

        Returns:
            "yes" 또는 "no"
        """
        try:
            response = requests.post(
                f"{OllamaExaoneService.OLLAMA_BASE_URL}/api/generate",
                json={
                    "model": OllamaExaoneService.OLLAMA_MODEL,
                    "prompt": prompt,
                    "temperature": 0.1,  # 낮은 온도 (결정적인 답변)
                    "stream": False,
                    "num_predict": 10,  # 매우 짧은 응답만
                },
                timeout=30,
            )

            if response.status_code != 200:
                raise ValueError(f"Ollama API 오류: {response.status_code}")

            result = response.json()
            response_text = result.get("response", "").strip().lower()

            # yes/no 추출
            if "yes" in response_text:
                return "yes"
            elif "no" in response_text:
                return "no"
            else:
                # 기본값: yes (새로운 조회 필요로 안전하게 판단)
                print(f"⚠️ yes/no 추출 실패, 응답: {response_text}")
                return "yes"

        except Exception as e:
            print(f"⚠️ yes/no 판단 오류: {str(e)}")
            # 오류 시 yes로 (새로운 조회 필요)
            return "yes"
