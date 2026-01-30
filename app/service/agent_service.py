"""
에이전트 서비스
수동 에이전트 루프로 EXAONE 호출 관리
"""

import json
import re
import logging
from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session

from app.schemas.agent import AgentAction, AgentResponse, AgentContext
from app.service.ollama_exaone_service import OllamaExaoneService
from app.models.admin import AdminEntity

logger = logging.getLogger(__name__)


class AgentService:
    """에이전트 서비스"""

    @staticmethod
    def get_agent_prompt(context: AgentContext) -> str:
        """
        EXAONE에게 전달할 에이전트 프롬프트 생성

        Args:
            context: 에이전트 컨텍스트

        Returns:
            프롬프트 문자열
        """
        # 사용 가능한 엔티티 정보 생성
        entities_info = "없음"
        if context.available_entities:
            entities_list = []
            for entity_type, values in context.available_entities.items():
                if values:
                    value_strs = [f"{v.get('id', v.get('name', v))}" for v in values]
                    entities_list.append(f"- {entity_type}: {', '.join(value_strs)}")
            if entities_list:
                entities_info = "\n".join(entities_list)

        previous_result_str = str(context.previous_result)[:200] if context.previous_result else "없음"
        extracted_info_str = json.dumps(context.extracted_info, ensure_ascii=False, indent=2)

        # 대화 히스토리 포맷팅
        conversation_context = ""
        if context.conversation_history:
            conversation_context = f"""이전 대화 기록:
{context.conversation_history}

"""

        return f"""제조 데이터 조회 에이전트. 다음 규칙으로 SQL을 생성하거나 답변을 제공해줘.

{conversation_context}질문: {context.user_message}
추출정보: {extracted_info_str}

📊 테이블 스키마:
- injection_cycle: cycle_date, machine_id, defect_description (예: "Flash (플래시)"), has_defect, product_weight_g
- production_summary: summary_date, summary_hour, machine_id, total_cycles, defect_cycles, defect_rate
- daily_summary: summary_date, machine_id, total_cycles, good_cycles, defect_cycles, defect_rate

컬럼 매핑:
- "생산량" → total_cycles | "양품" → good_cycles | "불량" → defect_cycles
- "불량 원인" → injection_cycle.defect_description | "불량율" → defect_rate (이미 계산됨)

현재: previous_result {previous_result_str[:50]} | 반복 {context.iteration}/{context.max_iterations}

액션 선택 규칙:
1. previous_result가 있으면 → return_answer (무조건!)
2. extracted_info가 비어있으면 → query_entities
3. else → query_production (처음 1회만)

SQL 규칙 (테이블명 항상 명시):
- 불량원인 (injection_cycle만 사용): SELECT injection_cycle.defect_description, COUNT(*) as count FROM injection_cycle WHERE injection_cycle.machine_id = 1 AND injection_cycle.cycle_date = '2026-01-28' AND injection_cycle.has_defect = 1 GROUP BY injection_cycle.defect_description ORDER BY count DESC
- 불량율 (production_summary 또는 daily_summary 사용): SELECT production_summary.defect_rate FROM production_summary WHERE production_summary.machine_id = 1 AND production_summary.summary_date = '2026-01-28'
- 비교쿼리 (CTE 사용): WITH period1 AS (SELECT ...), period2 AS (SELECT ...) SELECT ... FROM period1 JOIN period2. 모든 컬럼에 테이블/CTE 명시. FULL OUTER JOIN 금지

JSON 응답 형식:
{{
  "action": "query_entities|ask_clarification|query_production|return_answer",
  "reasoning": "액션 선택 이유 (1-2문장)",
  "sql": "query_production일 때만",
  "answer": "return_answer일 때만"
}}

JSON만 응답 (다른 텍스트 없음)"""

    @staticmethod
    def call_ollama_agent(context: AgentContext) -> AgentResponse:
        """
        EXAONE에 호출하여 다음 액션 결정

        Args:
            context: 에이전트 컨텍스트

        Returns:
            AgentResponse
        """
        try:
            prompt = AgentService.get_agent_prompt(context)

            # Ollama 호출
            response_text = OllamaExaoneService.generate(prompt)
            logger.debug(f"EXAONE 응답: {response_text[:200]}...")

            # JSON 파싱
            agent_response = AgentService.parse_agent_response(response_text)
            logger.info(f"에이전트 액션: {agent_response.action}")

            return agent_response

        except Exception as e:
            logger.error(f"에이전트 호출 오류: {str(e)}")
            raise

    @staticmethod
    def parse_agent_response(response_text: str) -> AgentResponse:
        """
        EXAONE 응답을 AgentResponse로 파싱

        Args:
            response_text: EXAONE 응답 텍스트

        Returns:
            AgentResponse

        Raises:
            ValueError: JSON 파싱 실패 시
        """
        try:
            # 마크다운 코드 블록 제거 (```json ... ```)
            # 1. 마크다운 블록 제거 (여러 라인)
            cleaned_text = re.sub(r'```(?:json)?\s*\n', '', response_text)
            cleaned_text = re.sub(r'\n?```\s*\n?', '', cleaned_text)

            # 2. 제어 문자 정리 (줄바꿈 등)
            cleaned_text = cleaned_text.strip()

            # 3. JSON 블록 추출 - 더 강건한 정규식
            # {로 시작해서 }로 끝나는 가장 긴 문자열 찾기
            json_match = re.search(r'\{[\s\S]*\}', cleaned_text)

            if not json_match:
                raise ValueError("JSON을 찾을 수 없음")

            json_str = json_match.group()

            # 4. JSON 문자열 정리 (백슬래시 문제 처리)
            # 이스케이프되지 않은 줄바꿈 제거
            json_str = re.sub(r'(?<!\\)\n', ' ', json_str)
            json_str = re.sub(r'(?<!\\)\r', '', json_str)

            data = json.loads(json_str)

            # 액션 검증
            action_str = data.get("action", "").lower()
            if action_str not in [a.value for a in AgentAction]:
                raise ValueError(f"유효하지 않은 action: {action_str}")

            # AgentResponse 생성
            return AgentResponse(
                action=AgentAction(action_str),
                reasoning=data.get("reasoning", ""),
                message=data.get("message"),
                sql=data.get("sql"),
                answer=data.get("answer"),
            )

        except json.JSONDecodeError as e:
            logger.error(f"JSON 파싱 오류: {str(e)}")
            raise ValueError(f"EXAONE 응답 JSON 파싱 실패: {str(e)}")
        except Exception as e:
            logger.error(f"응답 파싱 오류: {str(e)}")
            raise

    @staticmethod
    def get_available_entities(db_postgres: Session, db_mysql: Session) -> Dict[str, List[Dict[str, Any]]]:
        """
        동적으로 모든 엔티티 메타데이터 로드 및 조회

        Args:
            db_postgres: PostgreSQL 세션 (메타데이터)
            db_mysql: MySQL 세션 (실제 데이터)

        Returns:
            {entity_name: [{id, name}, ...], ...}
        """
        try:
            result = {}

            # AdminEntity에서 모든 엔티티 정의 로드
            entities_config = db_postgres.query(AdminEntity).filter(
                AdminEntity.deleted_at.is_(None)
            ).all()

            for config in entities_config:
                try:
                    # 메타데이터에서 정의한 쿼리 실행
                    # db_type에 따라 다른 세션 사용
                    if config.db_type == "mysql":
                        db = db_mysql
                    else:
                        db = db_postgres

                    from sqlalchemy import text
                    rows = db.execute(text(config.query)).fetchall()

                    # 결과를 딕셔너리 리스트로 변환
                    result[config.entity_name] = [dict(row) for row in rows]

                    logger.debug(f"엔티티 조회 완료: {config.entity_name} ({len(rows)}개)")

                except Exception as e:
                    logger.warning(f"엔티티 조회 실패 ({config.entity_name}): {str(e)}")
                    result[config.entity_name] = []

            logger.info(f"사용 가능한 엔티티: {list(result.keys())}")
            return result

        except Exception as e:
            logger.error(f"엔티티 메타데이터 로드 오류: {str(e)}")
            return {}
