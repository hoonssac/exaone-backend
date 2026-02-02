"""
쿼리 처리 서비스

사용자의 자연어 질문을 다음 단계로 처리합니다:
1. 용어 사전으로 질문 보정
2. 프롬프트 지식 베이스 조회
3. EXAONE API 호출하여 SQL 생성
4. SQL 안전성 검증
5. MySQL에서 쿼리 실행
6. PostgreSQL에 대화 기록 저장
7. 결과 반환
"""

import time
import json
import re
import requests
from datetime import datetime
from decimal import Decimal
from typing import Optional, Dict, List, Any
from sqlalchemy.orm import Session
from sqlalchemy import text, func

from app.schemas.query import QueryRequest, QueryResponse, QueryResultData
from app.schemas.agent import AgentAction, AgentContext, AgentResponse
from app.models.chat import ChatThread, ChatMessage
from app.models.prompt import PromptDict, PromptKnowledge, PromptTable, PromptColumn
from app.models.injection_molding import InjectionMoldingMachine
from app.service.exaone_service import ExaoneService, ExaoneAPIService, ChatGPTService, GeminiService
from app.service.ollama_exaone_service import OllamaExaoneService
from app.service.rag_service import RAGService
from app.service.schema_rag_service import SchemaRAGService
from app.service.entity_extraction_service import EntityExtractionService
from app.service.agent_service import AgentService
from app.utils.sql_validator import SQLValidator


class QueryService:
    """쿼리 처리 서비스 클래스"""

    # STT 오류 교정 맵 (발음 유사성으로 인한 오류 교정)
    STT_CORRECTION_MAP = {
        "일본": "1번",           # 1번 → 일본
        "이본": "1번",           # 1번 → 이본
        "일불": "불량",         # 불량 → 일불
        "양품": "양품",          # 양품 (정확함)
        "지난주": "지난주",      # 지난주 (정확함)
        "이번주": "이번주",      # 이번주 (정확함)
    }

    # 극도로 주제 벗어난 키워드 (거절 대상)
    OUT_OF_SCOPE_KEYWORDS = [
        "의료", "진료", "질병", "약", "치료", "수술",
        "법률", "소송", "판사", "변호사", "계약서",
        "금융", "주식", "투자", "대출", "암호화폐",
        "군사", "폭탄", "무기", "전쟁",
        "정치", "선거", "대통령", "국회",
    ]

    # 특수 질문 키워드 (대화 응답)
    SPECIAL_KEYWORDS = {
        "누구야?": "special_intro",
        "자기소개": "special_intro",
        "역할": "special_intro",
        "뭐할 수 있어?": "special_help",
        "도움말": "special_help",
        "뭔가?": "special_intro",
        "기능": "special_help",
        "help": "special_help",
    }

    # 데이터 조회 관련 키워드 (사출 성형)
    DATA_KEYWORDS = [
        "생산", "생산량", "사이클", "주기", "불량", "데이터",
        "조회", "통계", "현황", "어제", "오늘", "내일", "그저께", "재어제", "모레",
        "비교", "지난", "이번", "지만", "많다", "적다", "증가", "감소", "변화",
        "최고", "최저", "평균", "합계", "개수", "차이",
        "온도", "압력", "무게", "설비", "금형", "몰드", "불량유형", "결함",
    ]

    @staticmethod
    def needs_sql(query: str) -> bool:
        """
        질문이 SQL을 필요로 하는지 판단 (키워드 기반)

        Args:
            query: 사용자 질문

        Returns:
            True: SQL 필요, False: SQL 불필요
        """
        lower_query = query.lower()

        # 데이터 관련 키워드가 있으면 SQL 필요
        for keyword in QueryService.DATA_KEYWORDS:
            if keyword in lower_query:
                return True

        # 키워드 없으면 일반 대화
        return False

    @staticmethod
    def needs_sql_based_on_context(
        current_query: str,
        previous_query: Optional[str] = None,
        previous_result: Optional[Dict] = None
    ) -> bool:
        """
        이전 대화 컨텍스트를 고려하여 SQL이 필요한지 판단

        AI가 현재 질문의 의도를 분석해서 새로운 데이터 조회가 필요한지 판단합니다.

        Args:
            current_query: 현재 사용자 질문
            previous_query: 이전 질문 (있으면 컨텍스트 고려)
            previous_result: 이전 조회 결과

        Returns:
            True: 새로운 SQL 필요, False: 이전 결과 기반 답변
        """
        try:
            # 1단계: 키워드로 빠르게 판단 (성능)
            if QueryService.needs_sql(current_query):
                return True

            # 2단계: 이전 대화가 없으면 SQL 필요 없음
            if not previous_query or not previous_result:
                return False

            # 3단계: 이전 대화가 있으면 AI에게 의도 판단 요청
            print(f"🤔 대화 흐름 분석 중...")

            # 결과 데이터를 읽기 좋은 형태로 포맷
            result_summary = ""
            if isinstance(previous_result, dict):
                rows = previous_result.get("rows", [])
                if rows:
                    result_summary = "조회 결과: " + str(rows[:3])  # 처음 3행만

            prompt = f"""당신은 데이터 분석 전문가입니다. 대화 흐름을 파악하세요.

이전 질문: "{previous_query}"
이전 결과 샘플: {result_summary}

현재 질문: "{current_query}"

질문: 현재 질문이 새로운 데이터를 조회해야 합니까?

판단 기준:
- "새로운 데이터 조회 필요" (새로운 정보가 필요함) → yes
  예) "오늘은?" "어제와 비교해줘" "다른 유형은?" "온도는?" "불량률은?" "평균은?" "합계는?"
  ※ 중요: 불량률, 평균, 합계, 최고/최저 등 집계 메트릭은 항상 새로운 조회가 필요합니다!
  ※ 이전 결과를 기반으로 계산할 수는 있지만, 일반적으로 정확한 DB 조회가 필요합니다

- "새로운 조회 불필요" (이전 결과로 판단/비교하면 됨) → no
  예) "높은거야?" "많은거야?" "정상이야?" "맞아?" "어때?" "그래서?"

반드시 'yes' 또는 'no'만 답변하세요."""

            response = OllamaExaoneService._ask_yes_no(prompt)

            if response.lower() == "yes":
                print(f"✅ 새로운 데이터 조회 필요")
                return True
            else:
                print(f"✅ 이전 결과 기반 판단")
                return False

        except Exception as e:
            print(f"⚠️ 대화 흐름 분석 오류: {str(e)}")
            # 오류 시 안전하게 SQL 필요로 판단
            return True

    @staticmethod
    def is_out_of_scope(query: str) -> bool:
        """
        질문이 극도로 주제를 벗어났는지 판단 (의료, 법률, 금융 등)

        Args:
            query: 사용자 질문

        Returns:
            True: 주제 벗어남, False: 범위 내
        """
        lower_query = query.lower()

        # 1. 키워드 기반 필터링
        for keyword in QueryService.OUT_OF_SCOPE_KEYWORDS:
            if keyword in lower_query:
                return True

        return False

    @staticmethod
    def get_special_response(query: str) -> Optional[str]:
        """
        특수 질문(자기소개, 도움말 등)에 대한 응답 생성

        Args:
            query: 사용자 질문

        Returns:
            응답 문자열, 또는 None (일반 질문)
        """
        lower_query = query.lower()

        # 자기소개 질문
        if any(keyword in lower_query for keyword in ["누구야", "자기소개", "역할", "뭔가"]):
            return """안녕하세요! 저는 EXAONE 제조 에이전트입니다.

저는 생산 데이터를 기반으로:
- 생산량, 불량률, 라인별 현황 등 데이터 조회 및 분석
- 생산 추세 분석 및 인사이트 제공
- 제조 관련 질문에 대한 답변 및 조언

을 제공합니다.

무엇을 도와드릴까요?"""

        # 도움말/기능 질문
        if any(keyword in lower_query for keyword in ["뭐할 수 있어", "도움말", "기능", "help", "할 수 있는"]):
            return """저는 다음과 같은 작업을 할 수 있습니다:

1. 데이터 조회
   - 오늘/어제 생산량
   - 라인별 생산 현황
   - 불량률 조회

2. 데이터 분석
   - 생산량 비교 (어제 vs 오늘)
   - 추세 분석
   - 라인별 효율성 분석

3. 일반 대화
   - 인사말, 감사 인사
   - 제조 관련 조언
   - 데이터 해석 및 설명

예시:
- "오늘 생산량은?"
- "라인별 생산 현황 보여줄래?"
- "어제와 오늘 비교해줘"
- "가장 효율이 좋은 라인은?"

무엇을 도와드릴까요?"""

        return None

    @staticmethod
    def get_conversation_history(db_postgres: Session, thread_id: int, max_messages: int = 10) -> str:
        """
        스레드의 대화 히스토리를 문자열로 반환

        Args:
            db_postgres: PostgreSQL 세션
            thread_id: 스레드 ID
            max_messages: 포함할 최대 메시지 수 (최근부터)

        Returns:
            포맷된 대화 히스토리 문자열
        """
        try:
            # 최근 메시지부터 조회 (생성 시간 역순)
            messages = db_postgres.query(ChatMessage).filter(
                ChatMessage.thread_id == thread_id
            ).order_by(ChatMessage.created_at.desc()).limit(max_messages).all()

            # 시간순으로 정렬 (오래된 것부터)
            messages = list(reversed(messages))

            if not messages:
                return ""

            # 대화 히스토리 포맷팅
            history = ""
            for msg in messages:
                role = "사용자" if msg.role == "user" else "챗봇"
                history += f"{role}: {msg.message}\n"

            return history.strip()
        except Exception as e:
            print(f"⚠️ 대화 히스토리 조회 오류: {str(e)}")
            return ""

    @staticmethod
    def process_query_agentic(
        db_postgres: Session,
        db_mysql: Session,
        user_id: int,
        request: QueryRequest
    ) -> QueryResponse:
        """
        에이전트 루프로 쿼리 처리

        EXAONE에게 반복적으로 다음 액션을 결정하도록 함:
        1. query_machines: 사용 가능한 기계 조회
        2. query_production: SQL 실행
        3. ask_clarification: 사용자에게 재질문
        4. return_answer: 최종 답변

        Args:
            db_postgres: PostgreSQL 세션
            db_mysql: MySQL 세션
            user_id: 사용자 ID
            request: 쿼리 요청

        Returns:
            QueryResponse
        """
        start_time = time.time()

        try:
            # 쓰레드 생성/조회
            if request.thread_id:
                thread = db_postgres.query(ChatThread).filter(
                    ChatThread.id == request.thread_id,
                    ChatThread.user_id == user_id
                ).first()
                if not thread:
                    raise ValueError("스레드를 찾을 수 없습니다")
            else:
                thread = QueryService._get_or_create_thread(
                    db_postgres, user_id, request.message
                )

            print(f"🤖 에이전트 루프 시작: {request.message[:50]}...")

            # 대화 히스토리 조회 (맥락 이해용)
            conversation_history = QueryService.get_conversation_history(
                db_postgres,
                thread_id=thread.id,
                max_messages=10
            )
            if conversation_history:
                print(f"🔗 대화 히스토리 조회 완료")
                print(f"   최근 대화:\n{conversation_history[:200]}...")

            # 사용자 메시지에서 엔티티 추출 (FilterableFields 적용)
            extracted_entities = EntityExtractionService.extract_entities(
                request.message,
                db_postgres
            )
            print(f"📋 추출된 엔티티: {extracted_entities}")

            # 현재 질문에서 필터가 부족하면 이전 대화에서 찾기
            if conversation_history:
                missing_filters = []
                if "machine_id" not in extracted_entities or not extracted_entities["machine_id"]:
                    missing_filters.append("machine_id")
                if "cycle_date" not in extracted_entities or not extracted_entities["cycle_date"]:
                    missing_filters.append("cycle_date")

                # 이전 대화에서 필터 정보 추출
                if missing_filters:
                    previous_entities = EntityExtractionService.extract_entities(
                        conversation_history,  # 이전 대화에서도 추출
                        db_postgres
                    )
                    print(f"📍 이전 대화에서 추출된 엔티티: {previous_entities}")

                    # 현재 질문에 없는 필터를 이전 대화에서 채우기
                    for filter_key in missing_filters:
                        if filter_key in previous_entities and previous_entities[filter_key]:
                            extracted_entities[filter_key] = previous_entities[filter_key]
                            print(f"  ✅ {filter_key}: 이전 대화에서 보충 = {previous_entities[filter_key]}")

            print(f"📋 최종 엔티티 (대화맥락 적용): {extracted_entities}")

            # 에이전트 컨텍스트 초기화
            context = AgentContext(
                user_message=request.message,
                extracted_info=extracted_entities,
                available_entities={},
                previous_result=None,
                iteration=0,
                max_iterations=3,  # 최대 반복 횟수 감소 (5 → 3)
                conversation_history=conversation_history,
            )

            # 에이전트 루프 (타임아웃 적용)
            AGENT_TIMEOUT = 30  # 30초 타임아웃
            loop_start_time = time.time()

            while context.iteration < context.max_iterations:
                # 타임아웃 확인
                elapsed_time = time.time() - loop_start_time
                if elapsed_time > AGENT_TIMEOUT:
                    print(f"⏱️ 에이전트 루프 타임아웃 ({elapsed_time:.1f}초 초과)")
                    # 이전 결과가 있으면 반환, 없으면 에러
                    if context.previous_result and context.previous_result.get("row_count", 0) > 0:
                        print(f"→ 타임아웃되었지만 이미 조회 결과가 있으므로 반환")
                        answer_text = QueryService._generate_answer_from_result(
                            context.user_message,
                            context.previous_result,
                            context.extracted_info
                        )
                    else:
                        print(f"→ 타임아웃되고 조회 결과 없음")
                        answer_text = "처리 시간이 초과되었습니다. 질문을 단순화하거나 다시 시도해주세요."

                    # 메시지 저장 후 반환
                    user_msg = ChatMessage(
                        thread_id=thread.id,
                        role="user",
                        message=request.message,
                        context_tag=request.context_tag,
                    )
                    db_postgres.add(user_msg)
                    db_postgres.flush()

                    assistant_msg = ChatMessage(
                        thread_id=thread.id,
                        role="assistant",
                        message=answer_text,
                    )
                    db_postgres.add(assistant_msg)
                    db_postgres.commit()

                    execution_time = (time.time() - start_time) * 1000
                    response = QueryResponse(
                        thread_id=thread.id,
                        message_id=None,
                        original_message=request.message,
                        corrected_message=request.message,
                        generated_sql=None,
                        result_data=context.previous_result if context.previous_result else None,
                        execution_time=execution_time,
                        natural_response=answer_text,
                        created_at=datetime.now()
                    )
                    return response

                context.iteration += 1
                print(f"\n[에이전트 반복 {context.iteration}/{context.max_iterations}] (경과 시간: {elapsed_time:.1f}초)")

                # 2번째 반복 이상이고 이미 결과가 있으면 answer 반환 (쿼리 반복 방지)
                if context.iteration >= 2 and context.previous_result and context.previous_result.get("row_count", 0) > 0:
                    print(f"→ 이미 조회 완료 (2번째 반복 + 결과 있음) → answer 생성")

                    # 쿼리 결과를 기반으로 답변 생성
                    answer_text = QueryService._generate_answer_from_result(
                        context.user_message,
                        context.previous_result,
                        context.extracted_info
                    )

                    agent_response = AgentResponse(
                        action=AgentAction.RETURN_ANSWER,
                        reasoning="이미 조회 결과가 있으므로 답변 제공",
                        answer=answer_text
                    )
                else:
                    # EXAONE 호출하여 다음 액션 결정
                    agent_response = AgentService.call_ollama_agent(context)

                # 액션별 처리
                if agent_response.action == AgentAction.QUERY_ENTITIES:
                    print(f"→ 엔티티 조회 중: {agent_response.entities_to_query}")

                    # 모든 가능한 엔티티 로드 (첫 번째는 전체 로드, 이후는 특정 엔티티만)
                    if not context.available_entities:
                        context.available_entities = AgentService.get_available_entities(db_postgres, db_mysql)

                    # 필요한 엔티티만 기록
                    queried_entities = {}
                    if agent_response.entities_to_query:
                        for entity_type in agent_response.entities_to_query:
                            if entity_type in context.available_entities:
                                queried_entities[entity_type] = context.available_entities[entity_type]

                    context.history.append({
                        "step": context.iteration,
                        "action": "query_entities",
                        "entities": agent_response.entities_to_query,
                        "result": queried_entities
                    })
                    print(f"✅ 엔티티 조회 완료: {list(queried_entities.keys())}")
                    continue

                elif agent_response.action == AgentAction.QUERY_PRODUCTION:
                    print(f"→ SQL 실행 중: {agent_response.sql[:100]}...")
                    try:
                        result = db_mysql.execute(text(agent_response.sql))
                        rows = result.fetchall()

                        # 컬럼명과 데이터 추출
                        if rows:
                            columns = list(rows[0]._mapping.keys())
                            rows_dict = [dict(row._mapping) for row in rows]
                        else:
                            columns = []
                            rows_dict = []

                        context.previous_result = {
                            "columns": columns,
                            "rows": rows_dict,
                            "row_count": len(rows_dict)
                        }
                        context.history.append({
                            "step": context.iteration,
                            "action": "query_production",
                            "sql": agent_response.sql,
                            "result": context.previous_result
                        })
                        print(f"✅ SQL 실행 완료: {len(rows)}개 행")
                    except Exception as e:
                        print(f"❌ SQL 실행 오류: {str(e)}")
                        # 오류 후 루프 탈출 (무한 반복 방지)
                        error_msg = f"쿼리 실행 중 오류가 발생했습니다: {str(e)[:100]}"

                        user_msg = ChatMessage(
                            thread_id=thread.id,
                            role="user",
                            message=request.message,
                            context_tag=request.context_tag,
                        )
                        db_postgres.add(user_msg)
                        db_postgres.flush()

                        assistant_msg = ChatMessage(
                            thread_id=thread.id,
                            role="assistant",
                            message=error_msg,
                        )
                        db_postgres.add(assistant_msg)
                        db_postgres.commit()

                        execution_time = (time.time() - start_time) * 1000
                        response = QueryResponse(
                            thread_id=thread.id,
                            message_id=None,
                            original_message=request.message,
                            corrected_message=request.message,
                            generated_sql=agent_response.sql,
                            result_data=None,
                            execution_time=execution_time,
                            natural_response=error_msg,
                            created_at=datetime.now()
                        )
                        return response

                elif agent_response.action == AgentAction.ASK_CLARIFICATION:
                    print(f"→ 사용자에게 재질문")
                    # 사용자 메시지 저장
                    user_msg = ChatMessage(
                        thread_id=thread.id,
                        role="user",
                        message=request.message,
                        context_tag=request.context_tag,
                    )
                    db_postgres.add(user_msg)
                    db_postgres.flush()

                    # 챗봇 질문 저장
                    assistant_msg = ChatMessage(
                        thread_id=thread.id,
                        role="assistant",
                        message=agent_response.message,
                    )
                    db_postgres.add(assistant_msg)
                    db_postgres.commit()

                    execution_time = (time.time() - start_time) * 1000
                    response = QueryResponse(
                        thread_id=thread.id,
                        message_id=None,
                        original_message=request.message,
                        corrected_message=request.message,
                        generated_sql=None,
                        result_data=None,
                        execution_time=execution_time,
                        natural_response=agent_response.message,
                        created_at=datetime.now()
                    )
                    print(f"✅ 에이전트 루프 완료 (clarification)")
                    return response

                elif agent_response.action == AgentAction.RETURN_ANSWER:
                    print(f"→ 최종 답변 반환")

                    # 템플릿 답변의 플레이스홀더를 실제 데이터로 교체
                    final_answer = QueryService._fix_template_answer(
                        agent_response.answer,
                        context.previous_result,
                        context.user_message,
                        context.extracted_info
                    )

                    # 사용자 메시지 저장
                    user_msg = ChatMessage(
                        thread_id=thread.id,
                        role="user",
                        message=request.message,
                        context_tag=request.context_tag,
                    )
                    db_postgres.add(user_msg)
                    db_postgres.flush()

                    # 챗봇 답변 저장
                    assistant_msg = ChatMessage(
                        thread_id=thread.id,
                        role="assistant",
                        message=final_answer,
                    )
                    db_postgres.add(assistant_msg)
                    db_postgres.commit()

                    execution_time = (time.time() - start_time) * 1000

                    # result_data 구성
                    result_data = None
                    if context.previous_result and "error" not in context.previous_result:
                        result_data = QueryResultData(
                            columns=context.previous_result.get("columns", []),
                            rows=context.previous_result.get("rows", []),
                            row_count=context.previous_result.get("row_count", 0)
                        )

                    response = QueryResponse(
                        thread_id=thread.id,
                        message_id=user_msg.id,
                        original_message=request.message,
                        corrected_message=request.message,
                        generated_sql=context.history[-1]["sql"] if context.history and context.history[-1].get("sql") else None,
                        result_data=result_data,
                        execution_time=execution_time,
                        natural_response=final_answer,
                        created_at=datetime.now()
                    )
                    print(f"✅ 에이전트 루프 완료 (answer)")
                    return response

            # 최대 반복 초과
            error_msg = "에이전트가 결정을 내리지 못했습니다"
            print(f"❌ {error_msg}")
            raise ValueError(error_msg)

        except Exception as e:
            print(f"❌ 에이전트 처리 오류: {str(e)}")
            error_response = f"쿼리 처리 중 오류: {str(e)}"

            try:
                if 'thread' in locals():
                    user_msg = ChatMessage(
                        thread_id=thread.id,
                        role="user",
                        message=request.message,
                        context_tag=request.context_tag,
                    )
                    db_postgres.add(user_msg)

                    assistant_msg = ChatMessage(
                        thread_id=thread.id,
                        role="assistant",
                        message=error_response,
                    )
                    db_postgres.add(assistant_msg)
                    db_postgres.commit()
            except:
                pass

            execution_time = (time.time() - start_time) * 1000
            return QueryResponse(
                thread_id=thread.id if 'thread' in locals() else None,
                message_id=None,
                original_message=request.message,
                corrected_message=request.message,
                generated_sql=None,
                result_data=None,
                execution_time=execution_time,
                natural_response=error_response,
                created_at=datetime.now()
            )

    @staticmethod
    def process_query(
        db_postgres: Session,
        db_mysql: Session,
        user_id: int,
        request: QueryRequest
    ) -> QueryResponse:
        """
        사용자 질문을 처리하고 SQL을 생성하여 실행

        단계:
        1. 쓰레드 생성/조회
        2. 질문 보정 (용어 사전)
        3. 스키마 정보 조회
        4. 프롬프트 지식 베이스 조회
        5. EXAONE API 호출 (SQL 생성)
        6. SQL 검증
        7. MySQL에서 쿼리 실행
        8. 대화 기록 저장
        9. 응답 반환

        Args:
            db_postgres: PostgreSQL 세션
            db_mysql: MySQL 세션
            user_id: 사용자 ID
            request: 쿼리 요청 객체

        Returns:
            QueryResponse: 쿼리 처리 결과

        Raises:
            ValueError: 검증 실패 시
            Exception: 쿼리 실행 오류 시
        """
        start_time = time.time()

        try:
            # 1. 쓰레드 생성 또는 조회
            if request.thread_id:
                # 기존 쓰레드 조회 (권한 확인)
                thread = db_postgres.query(ChatThread).filter(
                    ChatThread.id == request.thread_id,
                    ChatThread.user_id == user_id
                ).first()
                if not thread:
                    raise ValueError("스레드를 찾을 수 없습니다")
                print(f"✅ 기존 스레드 사용: {request.thread_id}")
            else:
                # 새 쓰레드 생성
                thread = QueryService._get_or_create_thread(
                    db_postgres,
                    user_id,
                    request.message
                )
                print(f"✅ 새 스레드 생성: {thread.id}")

            # 2. 범위 체크 (극도로 주제 벗어난 질문인지 확인)
            print(f"🔍 범위 체크 중: '{request.message[:50]}...'")
            if QueryService.is_out_of_scope(request.message):
                print(f"❌ 범위 외 질문 거절")
                rejection_response = "죄송합니다. 그 주제는 제 역할 범위 밖입니다. 생산 데이터나 일상적인 대화를 나누겠습니다."

                # 사용자 메시지 저장
                message = ChatMessage(
                    thread_id=thread.id,
                    role="user",
                    message=request.message,
                    context_tag=request.context_tag,
                )
                db_postgres.add(message)
                db_postgres.flush()
                message_id = message.id

                # 거절 응답 메시지 저장
                assistant_message = ChatMessage(
                    thread_id=thread.id,
                    role="assistant",
                    message=rejection_response,
                )
                db_postgres.add(assistant_message)
                db_postgres.commit()

                # 응답 구성
                execution_time = (time.time() - start_time) * 1000
                response = QueryResponse(
                    thread_id=thread.id,
                    message_id=message_id,
                    original_message=request.message,
                    corrected_message=request.message,
                    generated_sql="",
                    result_data=QueryResultData(columns=[], rows=[], row_count=0),
                    execution_time=execution_time,
                    natural_response=rejection_response,
                    created_at=datetime.now()
                )
                return response

            # 3. 특수 질문 체크 (자기소개, 도움말 등)
            print(f"🔍 특수 질문 체크 중")
            special_response = QueryService.get_special_response(request.message)
            if special_response:
                print(f"✅ 특수 질문 감지: 직접 응답")

                # 사용자 메시지 저장
                message = ChatMessage(
                    thread_id=thread.id,
                    role="user",
                    message=request.message,
                    context_tag=request.context_tag,
                )
                db_postgres.add(message)
                db_postgres.flush()
                message_id = message.id

                # 특수 응답 메시지 저장
                assistant_message = ChatMessage(
                    thread_id=thread.id,
                    role="assistant",
                    message=special_response,
                )
                db_postgres.add(assistant_message)
                db_postgres.commit()

                # 응답 구성
                execution_time = (time.time() - start_time) * 1000
                response = QueryResponse(
                    thread_id=thread.id,
                    message_id=message_id,
                    original_message=request.message,
                    corrected_message=request.message,
                    generated_sql="",
                    result_data=QueryResultData(columns=[], rows=[], row_count=0),
                    execution_time=execution_time,
                    natural_response=special_response,
                    created_at=datetime.now()
                )
                return response

            # 4. 이전 질문/결과 가져오기 (대화 흐름 분석용)
            previous_query = None
            previous_result = None
            try:
                # 현재 스레드의 마지막 메시지(사용자 질문) 조회
                last_user_message = db_postgres.query(ChatMessage).filter(
                    ChatMessage.thread_id == thread.id,
                    ChatMessage.role == "user"
                ).order_by(ChatMessage.created_at.desc()).first()

                if last_user_message:
                    previous_query = last_user_message.message

                    # 마지막 사용자 메시지 바로 다음의 AI 응답 찾기
                    last_assistant_message = db_postgres.query(ChatMessage).filter(
                        ChatMessage.thread_id == thread.id,
                        ChatMessage.role == "assistant",
                        ChatMessage.created_at > last_user_message.created_at
                    ).order_by(ChatMessage.created_at.asc()).first()

                    if last_assistant_message and last_assistant_message.result_data:
                        try:
                            previous_result = json.loads(last_assistant_message.result_data)
                        except:
                            previous_result = None
            except Exception as e:
                print(f"⚠️ 이전 메시지 조회 오류: {str(e)}")

            # 5. SQL 필요 여부 체크 (대화 흐름 고려)
            print(f"🔍 SQL 필요 여부 판단 중: '{request.message[:50]}...'")
            needs_sql = QueryService.needs_sql_based_on_context(
                current_query=request.message,
                previous_query=previous_query,
                previous_result=previous_result
            )

            if not needs_sql:
                print(f"✅ SQL 불필요 - 이전 결과 기반 판단 응답")

                try:
                    # 사용자 메시지 저장
                    message = ChatMessage(
                        thread_id=thread.id,
                        role="user",
                        message=request.message,
                        context_tag=request.context_tag,
                    )
                    db_postgres.add(message)
                    db_postgres.flush()
                    message_id = message.id

                    # Ollama EXAONE으로 일반 대화 응답 생성
                    # 이전 질문과 결과가 있으면 컨텍스트로 전달
                    context_for_response = ""
                    if previous_query and previous_result:
                        context_for_response = f"""이전 질문: {previous_query}
이전 결과: {str(previous_result.get('rows', [])[:5])}

"""

                    full_prompt = context_for_response + request.message
                    conversation_response = OllamaExaoneService.generate_response_without_sql(
                        user_query=full_prompt
                    )

                    # 응답 메시지 저장
                    assistant_message = ChatMessage(
                        thread_id=thread.id,
                        role="assistant",
                        message=conversation_response,
                    )
                    db_postgres.add(assistant_message)
                    db_postgres.commit()

                    # 응답 구성
                    execution_time = (time.time() - start_time) * 1000
                    response = QueryResponse(
                        thread_id=thread.id,
                        message_id=message_id,
                        original_message=request.message,
                        corrected_message=request.message,
                        generated_sql="",
                        result_data=QueryResultData(columns=[], rows=[], row_count=0),
                        execution_time=execution_time,
                        natural_response=conversation_response,
                        created_at=datetime.now()
                    )
                    return response

                except Exception as conv_error:
                    print(f"⚠️ 일반 대화 응답 생성 실패: {str(conv_error)}")
                    # 실패 시 기본 응답
                    basic_response = "죄송하지만 응답을 생성하는데 문제가 발생했습니다. 다시 시도해주세요."

                    message = ChatMessage(
                        thread_id=thread.id,
                        role="user",
                        message=request.message,
                        context_tag=request.context_tag,
                    )
                    db_postgres.add(message)
                    db_postgres.flush()
                    message_id = message.id

                    assistant_message = ChatMessage(
                        thread_id=thread.id,
                        role="assistant",
                        message=basic_response,
                    )
                    db_postgres.add(assistant_message)
                    db_postgres.commit()

                    execution_time = (time.time() - start_time) * 1000
                    response = QueryResponse(
                        thread_id=thread.id,
                        message_id=message_id,
                        original_message=request.message,
                        corrected_message=request.message,
                        generated_sql="",
                        result_data=QueryResultData(columns=[], rows=[], row_count=0),
                        execution_time=execution_time,
                        natural_response=basic_response,
                        created_at=datetime.now()
                    )
                    return response

            print(f"✅ SQL 필요 질문 확인")

            # 5. 대화 히스토리 조회 (전체 맥락 파악용)
            conversation_history = QueryService.get_conversation_history(
                db_postgres,
                thread_id=thread.id,
                max_messages=10
            )
            if conversation_history:
                print(f"🔗 대화 히스토리 조회 완료 (10개 메시지)")

            # 6. 엔티티 추출 (FilterableField 규칙 기반) - 원본 메시지 사용
            # ⚠️ 정규화 전 원본 메시지에서 추출해야 숫자나 키워드가 손실되지 않음
            entities = EntityExtractionService.extract_entities(
                request.message,
                db_postgres
            )
            where_clause_hint = EntityExtractionService.build_where_clause(entities)
            if where_clause_hint:
                print(f"📌 추출된 WHERE 절: {where_clause_hint}")

            # 6.2. 필수 필터 조건 확인 (machine_id 필수)
            # machine_id가 없으면 대화 히스토리에서 가장 최근의 machine_id 찾기
            if "machine_id" not in entities or not entities.get("machine_id"):
                # 대화 히스토리에서 마지막 machine_id 추출
                if conversation_history:
                    # 대화에서 숫자 + "번" 패턴 찾기 (예: "1번 사출기")
                    import re
                    machine_pattern = r'(\d+)번\s*(?:사출기|라인)'
                    matches = re.findall(machine_pattern, conversation_history)
                    if matches:
                        last_machine_id = matches[-1]  # 가장 최근 것 사용
                        entities["machine_id"] = last_machine_id
                        print(f"✅ 대화 히스토리에서 machine_id 복구: {last_machine_id}번")

            # machine_id 재확인 (여전히 없으면 사용자에게 물어보기)
            if "machine_id" not in entities or not entities.get("machine_id"):
                print(f"❓ 필수 필터 누락: machine_id 없음 - 사용자에게 질문 중...")
                natural_response = "어느 번호의 사출기를 조회하고 싶으신가요? (예: 1번, 2번, 3번...)"

                # 사용자 메시지 저장
                message = ChatMessage(
                    thread_id=thread.id,
                    role="user",
                    message=request.message,
                    context_tag=request.context_tag,
                )
                db_postgres.add(message)
                db_postgres.flush()
                message_id = message.id

                # 챗봇 질문 저장
                assistant_message = ChatMessage(
                    thread_id=thread.id,
                    role="assistant",
                    message=natural_response
                )
                db_postgres.add(assistant_message)
                db_postgres.commit()

                # 응답 반환
                execution_time = (time.time() - start_time) * 1000
                response = QueryResponse(
                    thread_id=thread.id,
                    message_id=message_id,
                    original_message=request.message,
                    corrected_message=None,
                    generated_sql=None,
                    result_data=None,
                    execution_time=execution_time,
                    natural_response=natural_response,
                    created_at=datetime.now()
                )
                return response

            # 6.5. 질문 정규화 (용어 사전) - 원본 메시지 기반
            normalized_message = QueryService.normalize_message(
                request.message,  # 원본 메시지 정규화
                db_postgres
            )

            # 7. 스키마 정보 조회
            schema_info = QueryService.get_schema_info(db_postgres, db_mysql)

            # 8. 프롬프트 지식 베이스 조회
            knowledge_base = QueryService.get_knowledge_base(db_postgres)

            # 9. RAG 컨텍스트 검색 (2가지: Conversation RAG + Schema RAG)
            rag_context = []
            schema_hint = ""

            # 9-1. Conversation RAG: 이전 대화 검색 - 원본 메시지 사용
            try:
                rag_context = RAGService.retrieve_context(
                    db_postgres,
                    thread_id=thread.id,
                    query=request.message,  # 원본 메시지 사용
                    top_k=3
                )
                if rag_context:
                    print(f"✅ Conversation RAG: {len(rag_context)} 개 메시지 검색됨")
            except Exception as rag_error:
                print(f"⚠️ Conversation RAG 검색 실패: {str(rag_error)}")
                rag_context = []

            # 9-2. Schema RAG: 스키마 기반 검색 (테이블/컬럼 자동 매핑) - 원본 메시지 사용
            try:
                schema_results = SchemaRAGService.search_similar_schema(
                    db_postgres,
                    query=request.message,  # 원본 메시지 사용
                    top_k=5
                )
                if schema_results:
                    schema_hint = SchemaRAGService.format_schema_hint(schema_results)
                    print(f"✅ Schema RAG: {len(schema_results)} 개 스키마 검색됨")
                    print(f"   스키마 힌트:\n{schema_hint}")
            except Exception as schema_rag_error:
                print(f"⚠️ Schema RAG 검색 실패: {str(schema_rag_error)}")
                schema_hint = ""

            # 10. SQL 생성 (Ollama EXAONE → Mock 폴백)
            # 우선 순서: Ollama EXAONE → Mock 폴백
            generated_sql = None
            try:
                print(f"🔄 [1단계] Ollama EXAONE SQL 생성 중...")

                # 통합 프롬프트 구성: 대화 히스토리 + Schema RAG
                api_query = request.message  # 원본 질문 사용

                # 대화 히스토리 포함 (전체 맥락 이해)
                if conversation_history:
                    api_query = f"""대화 기록:
{conversation_history}

새로운 질문: {request.message}"""
                    print(f"💬 대화 히스토리 포함 (전체 맥락 이해)")

                # Schema RAG 힌트 추가
                if schema_hint:
                    if conversation_history:
                        api_query = api_query + "\n\n" + schema_hint
                    else:
                        api_query = schema_hint + "\n질문: " + request.message
                    print(f"🗂️ 스키마 힌트 추가됨")

                print(f"📤 Ollama EXAONE에 전달할 질문:\n{api_query[:200]}...")
                generated_sql = OllamaExaoneService.nl_to_sql(
                    user_query=api_query,
                    corrected_query=normalized_message,
                    schema_info=schema_info,
                    knowledge_base=knowledge_base,
                    where_clause_hint=where_clause_hint
                )

                print(f"✅ Ollama EXAONE SQL 생성 성공")
            except Exception as ollama_error:
                print(f"⚠️ Ollama EXAONE 오류 ({str(ollama_error)}), Mock으로 폴백...")
                try:
                    generated_sql = ExaoneService.nl_to_sql(
                        user_query=request.message,  # 원본 메시지 사용
                        corrected_query=normalized_message,
                        schema_info=schema_info,
                        knowledge_base=knowledge_base,
                        where_clause_hint=where_clause_hint
                    )
                    print(f"✅ Mock 방식 사용")
                except Exception as mock_error:
                    raise ValueError(f"SQL 생성 실패 (Ollama: {ollama_error}, Mock: {mock_error})")

            # 11. 생성된 결과가 SQL인지 질문인지 판단
            is_sql = "SELECT" in generated_sql.upper().strip()

            if not is_sql:
                # SQL이 아니라 사용자에게 하는 질문 (필터 조건 부족)
                print(f"❓ 필터 조건 부족 - 사용자에게 질문 중: {generated_sql[:100]}...")
                natural_response = generated_sql  # 직접 질문을 응답으로 사용
                result_data_dict = None
                sanitized_sql = None
            else:
                # SQL 검증
                is_valid, error_msg = SQLValidator.validate(generated_sql)
                if not is_valid:
                    raise ValueError(f"SQL 검증 실패: {error_msg}")

                # SQL 정제 (LIMIT 추가 등)
                sanitized_sql = SQLValidator.sanitize(generated_sql)

                # 12. MySQL에서 쿼리 실행
                result_data = QueryService.execute_query(db_mysql, sanitized_sql)

            # SQL일 때만 자연어 응답 생성
            if is_sql:
                # 13. [2단계] 자연어 응답 생성
                print(f"🔄 [2단계] Ollama EXAONE 자연어 응답 생성 중...")
                try:
                    result_data_for_llm = {
                        "columns": result_data.columns,
                        "rows": result_data.rows,
                        "row_count": result_data.row_count
                    }
                    natural_response = OllamaExaoneService.generate_response(
                        user_query=request.message,
                        sql_result=result_data_for_llm
                    )
                    print(f"✅ Ollama EXAONE 자연어 응답 생성 성공")
                except Exception as response_error:
                    print(f"⚠️ 자연어 응답 생성 실패: {str(response_error)}")
                    # 응답 생성 실패 시 기본 응답 사용
                    natural_response = f"데이터 조회 완료: {result_data.row_count}행 반환되었습니다."
            else:
                # SQL이 아닐 때는 이미 natural_response가 설정됨
                print(f"💬 사용자 입력 필요 응답 준비 완료")

            # 14. 대화 기록 저장
            message = ChatMessage(
                thread_id=thread.id,
                role="user",
                message=request.message,
                context_tag=request.context_tag,
            )
            db_postgres.add(message)
            db_postgres.flush()  # message.id를 얻기 위해
            message_id = message.id

            # Assistant 응답 메시지 저장 (자연어 응답)
            if is_sql:
                # SQL 실행 결과 저장
                result_data_dict = {
                    "columns": result_data.columns,
                    "rows": result_data.rows,
                    "row_count": result_data.row_count
                }
            else:
                # 사용자 질문 (SQL 없음)
                result_data_dict = None

            assistant_message = ChatMessage(
                thread_id=thread.id,
                role="assistant",
                message=natural_response,  # AI가 생성한 자연어 응답
                corrected_msg=normalized_message if is_sql else None,
                gen_sql=sanitized_sql if is_sql else None,
                result_data=result_data_dict
            )
            db_postgres.add(assistant_message)
            db_postgres.commit()

            # 15. RAG 임베딩 저장 (비동기)
            try:
                # 사용자 메시지 임베딩
                RAGService.store_embedding(
                    db_postgres,
                    thread_id=thread.id,
                    message=request.message
                )

                # Assistant 응답 임베딩 (자연어 응답)
                if is_sql:
                    RAGService.store_embedding(
                        db_postgres,
                        thread_id=thread.id,
                        message=natural_response,
                        result_data=result_data_dict
                    )
                else:
                    # 사용자 질문일 때는 result_data 없이 저장
                    RAGService.store_embedding(
                        db_postgres,
                        thread_id=thread.id,
                        message=natural_response
                    )
                print(f"✅ RAG 임베딩 저장 완료")
            except Exception as embedding_error:
                print(f"⚠️ RAG 임베딩 저장 실패: {str(embedding_error)}")
                # 임베딩 저장 실패해도 쿼리 결과는 반환

            # 16. 응답 구성
            execution_time = (time.time() - start_time) * 1000  # 밀리초

            # SQL일 때만 result_data 포함
            if is_sql:
                result_data_response = result_data
            else:
                result_data_response = None

            response = QueryResponse(
                thread_id=thread.id,
                message_id=message_id,
                original_message=request.message,
                corrected_message=normalized_message if is_sql else None,
                generated_sql=sanitized_sql if is_sql else None,
                result_data=result_data_response,
                execution_time=execution_time,
                natural_response=natural_response,
                created_at=datetime.now()
            )

            return response

        except ValueError as e:
            db_postgres.rollback()
            raise ValueError(str(e))
        except Exception as e:
            db_postgres.rollback()
            raise Exception(f"쿼리 처리 중 오류: {str(e)}")

    @staticmethod
    def normalize_message(message: str, db: Session) -> str:
        """
        용어 사전을 이용하여 질문 정규화

        사용자의 다양한 표현을 정규화된 용어로 통일합니다.
        SQL 함수나 조건은 생성하지 않습니다.

        예:
        - "1번" → "사출기"
        - "1호기" → "사출기"
        - "생산" → "생산량"
        - "불량" → "불량률"

        Args:
            message: 원본 질문
            db: PostgreSQL 세션

        Returns:
            정규화된 질문
        """
        normalized = message

        try:
            # 용어 사전 조회
            term_dicts = db.query(PromptDict).all()

            for term_dict in term_dicts:
                # 대소문자 무시하고 단어 전체 매칭
                pattern = rf'\b{re.escape(term_dict.key)}\b'
                normalized = re.sub(
                    pattern,
                    term_dict.value,
                    normalized,
                    flags=re.IGNORECASE
                )

        except Exception as e:
            print(f"⚠️ 정규화 오류: {str(e)}")
            # 정규화 실패 시 원본 반환
            return message

        return normalized

    @staticmethod
    def correct_message(message: str, db: Session) -> str:
        """
        용어 사전을 이용하여 질문 보정 (레거시)

        NOTE: normalize_message()로 교체될 예정입니다.
        현재는 호환성 유지를 위해 남겨둡니다.

        Args:
            message: 원본 질문
            db: PostgreSQL 세션

        Returns:
            보정된 질문
        """
        # normalize_message()와 동일하게 동작
        return QueryService.normalize_message(message, db)

    @staticmethod
    def get_schema_info(db_postgres: Session, db_mysql: Session) -> Dict[str, Any]:
        """
        스키마 메타데이터 조회 (사출 성형 스키마)

        Returns:
            {
                "tables": [
                    {
                        "name": "injection_cycle",
                        "description": "사출 사이클 데이터",
                        "columns": [
                            {"name": "id", "type": "BIGINT", "description": "..."},
                            ...
                        ]
                    },
                    ...
                ],
                "available_columns": ["cycle_date", "has_defect", ...]
            }
        """
        try:
            # SchemaRAGService에서 hardcoded 스키마 가져오기
            from app.service.schema_rag_service import SchemaRAGService

            schema_dict = SchemaRAGService.INJECTION_MOLDING_SCHEMA

            schema_info = {
                "tables": [],
                "available_columns": []
            }

            for table_data in schema_dict.get("tables", []):
                table_info = {
                    "name": table_data["name"],
                    "description": table_data.get("description", ""),
                    "columns": [
                        {
                            "name": col["name"],
                            "type": col.get("type", "UNKNOWN"),
                            "description": col.get("description", "")
                        }
                        for col in table_data.get("columns", [])
                    ]
                }

                schema_info["tables"].append(table_info)

                # 모든 컬럼 이름 수집
                schema_info["available_columns"].extend([col["name"] for col in table_data.get("columns", [])])

            # MySQL 테이블 검증 (실제 존재하는지 확인)
            try:
                for table_data in schema_dict.get("tables", []):
                    table_name = table_data["name"]
                    db_mysql.execute(text(f"SELECT 1 FROM {table_name} LIMIT 1"))
                    print(f"✅ MySQL 테이블 확인: {table_name}")
            except Exception as e:
                print(f"⚠️ MySQL 테이블 검증 오류: {str(e)}")

            return schema_info

        except Exception as e:
            print(f"❌ 스키마 정보 조회 오류: {str(e)}")
            # 기본값 반환 (사출 성형 스키마)
            return {
                "tables": [],
                "available_columns": ["cycle_date", "has_defect", "product_weight_g", "defect_type_id", "temp_nh", "pressure_primary"]
            }

    @staticmethod
    def get_knowledge_base(db: Session) -> List[str]:
        """
        도메인 지식 베이스 조회

        Returns:
            도메인 지식 문장 리스트
        """
        try:
            knowledge_list = db.query(PromptKnowledge).all()
            return [k.content for k in knowledge_list]
        except Exception as e:
            print(f"⚠️ 지식 베이스 조회 오류: {str(e)}")
            return []

    @staticmethod
    def execute_query(db: Session, sql: str) -> QueryResultData:
        """
        MySQL에서 SQL 쿼리 실행

        Args:
            db: MySQL 세션
            sql: 실행할 SQL 쿼리

        Returns:
            QueryResultData: 쿼리 실행 결과

        Raises:
            Exception: 쿼리 실행 오류
        """
        try:
            # 쿼리 실행
            result = db.execute(text(sql))

            # 컬럼명 조회
            columns = list(result.keys())

            # 행 데이터 조회
            rows = []
            for row in result.fetchall():
                row_dict = {}
                for i, col in enumerate(columns):
                    value = row[i]
                    # 날짜/타임스탬프 객체는 ISO 형식 문자열로 변환
                    if hasattr(value, 'isoformat'):
                        value = value.isoformat()
                    # Decimal 타입은 float로 변환 (JSON 직렬화 가능)
                    elif isinstance(value, Decimal):
                        value = float(value)
                    row_dict[col] = value
                rows.append(row_dict)

            # 결과 데이터 구성
            result_data = QueryResultData(
                columns=columns,
                rows=rows,
                row_count=len(rows)
            )

            return result_data

        except Exception as e:
            raise Exception(f"쿼리 실행 오류: {str(e)}")

    @staticmethod
    def _get_or_create_thread(
        db: Session,
        user_id: int,
        first_message: str
    ) -> ChatThread:
        """
        쓰레드 생성 또는 기존 쓰레드 반환

        Args:
            db: PostgreSQL 세션
            user_id: 사용자 ID
            first_message: 첫 번째 메시지

        Returns:
            ChatThread: 쓰레드 객체
        """
        try:
            # 새로운 쓰레드 생성
            # 제목은 첫 메시지의 처음 50자로 설정
            title = first_message[:50]

            thread = ChatThread(
                user_id=user_id,
                title=title
            )

            db.add(thread)
            db.flush()  # thread.id를 얻기 위해

            return thread

        except Exception as e:
            db.rollback()
            raise Exception(f"쓰레드 생성 오류: {str(e)}")

    @staticmethod
    def get_user_threads(
        db: Session,
        user_id: int,
        limit: int = 20
    ) -> List[Dict[str, Any]]:
        """
        사용자의 모든 쓰레드 조회 (삭제되지 않은 쓰레드만)

        Args:
            db: PostgreSQL 세션
            user_id: 사용자 ID
            limit: 조회할 최대 개수

        Returns:
            쓰레드 정보 리스트
        """
        try:
            threads = db.query(ChatThread).filter(
                ChatThread.user_id == user_id,
                ChatThread.deleted_at.is_(None)  # Soft delete 제외
            ).order_by(ChatThread.created_at.desc()).limit(limit).all()

            result = []
            for thread in threads:
                # 각 쓰레드의 메시지 개수 조회 (삭제되지 않은 메시지만)
                message_count = db.query(func.count(ChatMessage.id)).filter(
                    ChatMessage.thread_id == thread.id,
                    ChatMessage.deleted_at.is_(None)  # Soft delete 제외
                ).scalar()

                result.append({
                    "id": thread.id,
                    "title": thread.title,
                    "message_count": message_count,
                    "created_at": thread.created_at,
                    "updated_at": thread.updated_at
                })

            return result

        except Exception as e:
            raise Exception(f"쓰레드 조회 오류: {str(e)}")

    @staticmethod
    def get_thread_messages(
        db: Session,
        thread_id: int,
        user_id: int
    ) -> List[Dict[str, Any]]:
        """
        특정 쓰레드의 메시지 조회 (삭제되지 않은 메시지만)

        Args:
            db: PostgreSQL 세션
            thread_id: 쓰레드 ID
            user_id: 사용자 ID (권한 확인용)

        Returns:
            메시지 리스트

        Raises:
            ValueError: 권한 없음 또는 쓰레드 없음
        """
        try:
            # 권한 확인 (삭제되지 않은 쓰레드만)
            thread = db.query(ChatThread).filter(
                ChatThread.id == thread_id,
                ChatThread.user_id == user_id,
                ChatThread.deleted_at.is_(None)  # Soft delete 제외
            ).first()

            if not thread:
                raise ValueError("쓰레드에 접근할 권한이 없거나 삭제된 쓰레드입니다")

            # 메시지 조회 (삭제되지 않은 메시지만)
            messages = db.query(ChatMessage).filter(
                ChatMessage.thread_id == thread_id,
                ChatMessage.deleted_at.is_(None)  # Soft delete 제외
            ).order_by(ChatMessage.created_at.asc()).all()

            result = []
            for msg in messages:
                result.append({
                    "id": msg.id,
                    "thread_id": msg.thread_id,
                    "role": msg.role,
                    "message": msg.message,
                    "corrected_msg": msg.corrected_msg,
                    "gen_sql": msg.gen_sql,
                    "result_data": msg.result_data,
                    "context_tag": msg.context_tag,
                    "created_at": msg.created_at
                })

            return result

        except ValueError:
            raise
        except Exception as e:
            raise Exception(f"메시지 조회 오류: {str(e)}")

    @staticmethod
    def delete_thread(
        db: Session,
        thread_id: int,
        user_id: int
    ) -> Dict[str, Any]:
        """
        특정 쓰레드를 soft delete (쓰레드와 메시지 모두 삭제)

        Args:
            db: PostgreSQL 세션
            thread_id: 쓰레드 ID
            user_id: 사용자 ID (권한 확인용)

        Returns:
            삭제 결과

        Raises:
            ValueError: 권한 없음 또는 쓰레드 없음
        """
        try:
            # 권한 확인 (삭제되지 않은 쓰레드만)
            thread = db.query(ChatThread).filter(
                ChatThread.id == thread_id,
                ChatThread.user_id == user_id,
                ChatThread.deleted_at.is_(None)  # 이미 삭제된 쓰레드는 제외
            ).first()

            if not thread:
                raise ValueError("쓰레드에 접근할 권한이 없거나 이미 삭제된 쓰레드입니다")

            # 쓰레드 내 모든 메시지 soft delete
            deleted_messages_count = db.query(ChatMessage).filter(
                ChatMessage.thread_id == thread_id,
                ChatMessage.deleted_at.is_(None)  # 아직 삭제되지 않은 메시지만
            ).update(
                {ChatMessage.deleted_at: datetime.utcnow()},
                synchronize_session=False
            )

            # 쓰레드 soft delete
            thread.deleted_at = datetime.utcnow()
            db.commit()

            print(f"✅ 쓰레드 삭제 완료 (ID: {thread_id}, 메시지 {deleted_messages_count}개 삭제됨)")

            return {
                "thread_id": thread_id,
                "deleted_messages_count": deleted_messages_count,
                "deleted_at": thread.deleted_at
            }

        except ValueError:
            raise
        except Exception as e:
            db.rollback()
            raise Exception(f"쓰레드 삭제 오류: {str(e)}")

    @staticmethod
    def _correct_stt_result(text: str) -> str:
        """
        STT 결과를 도메인 어휘로 교정합니다.

        발음 유사성으로 인한 오류를 자동으로 교정합니다.
        예: "일본" → "1번", "이본" → "2번", "삼본" → "3번", "사본" → "4번"

        Args:
            text: STT 인식 결과 텍스트

        Returns:
            교정된 텍스트
        """
        corrected_text = text

        # 한글 숫자를 아라비아 숫자로 변환 (본/번 패턴)
        korean_to_arabic = {
            "일본": "1번",   # 일 → 1, 본 → 번
            "이본": "2번",   # 이 → 2, 본 → 번
            "삼본": "3번",   # 삼 → 3, 본 → 번
            "사본": "4번",   # 사 → 4, 본 → 번
            "오본": "5번",   # 오 → 5, 본 → 번
            "육본": "6번",   # 육 → 6, 본 → 번
            "칠본": "7번",   # 칠 → 7, 본 → 번
            "팔본": "8번",   # 팔 → 8, 본 → 번
            "구본": "9번",   # 구 → 9, 본 → 번
        }

        # 본 → 번 교정 (일반적인 패턴)
        for korean, arabic in korean_to_arabic.items():
            if korean in corrected_text:
                corrected_text = corrected_text.replace(korean, arabic)
                print(f"🔧 STT 교정: '{korean}' → '{arabic}'")

        # 추가 교정: "본"으로 끝나는데 숫자로 시작하는 경우
        # 예: "사본" → "4번" (위에서 처리됨)

        # 기타 일반적인 오류
        other_corrections = [
            ("일불", "불량"),         # 불량 인식 오류
            ("일불품", "불량품"),     # 불량품 인식 오류
        ]

        for wrong, correct in other_corrections:
            if wrong in corrected_text:
                corrected_text = corrected_text.replace(wrong, correct)
                print(f"🔧 STT 교정: '{wrong}' → '{correct}'")

        return corrected_text

    @staticmethod
    def _fix_template_answer(answer: str, previous_result: Dict[str, Any], user_message: str, extracted_info: Dict[str, Any]) -> str:
        """
        Agent가 생성한 템플릿 답변의 플레이스홀더를 실제 데이터로 교체

        Args:
            answer: Agent가 생성한 답변 (플레이스홀더 포함 가능)
            previous_result: SQL 실행 결과
            user_message: 사용자의 원본 메시지
            extracted_info: 추출된 엔티티 정보

        Returns:
            플레이스홀더가 실제 값으로 교체된 답변
        """
        # 플레이스홀더가 없으면 그대로 반환
        if not any(placeholder in answer for placeholder in ['[', ']', '(', ')']):
            return answer

        try:
            if not previous_result or previous_result.get("error") or not previous_result.get("rows"):
                # 결과가 없으면 원본 답변 반환
                return answer

            # 첫 번째 행의 데이터 추출
            row_data = previous_result["rows"][0]

            # 값 추출
            value = None
            for col_name, col_value in row_data.items():
                if col_value is not None:
                    try:
                        value = float(col_value)
                        break
                    except (ValueError, TypeError):
                        continue

            if value is None:
                return answer

            # 값 포매팅
            value_int = int(value)
            value_formatted = f"{value_int:,}"

            # 플레이스홀더 교체
            fixed_answer = answer

            # 일반적인 플레이스홀더 패턴 교체
            fixed_answer = fixed_answer.replace('[불량 개수]', f'{value_int}개')
            fixed_answer = fixed_answer.replace('[불량]', f'{value_int}개')
            fixed_answer = fixed_answer.replace('[양품 개수]', f'{value_int}개')
            fixed_answer = fixed_answer.replace('[양품]', f'{value_int}개')
            fixed_answer = fixed_answer.replace('[생산량]', f'{value_formatted}개')
            fixed_answer = fixed_answer.replace('[개수]', f'{value_int}개')

            # 괄호 형태의 플레이스홀더도 처리
            fixed_answer = fixed_answer.replace('(불량 개수)', f'{value_int}개')
            fixed_answer = fixed_answer.replace('(개수)', f'{value_int}개')

            # 말줄임표와 함께 있는 경우 정리
            fixed_answer = fixed_answer.replace('....', '.')
            fixed_answer = fixed_answer.rstrip('.')  + '.'

            return fixed_answer

        except Exception as e:
            print(f"⚠️ 템플릿 답변 교정 오류: {str(e)}")
            return answer

    @staticmethod
    def _generate_answer_from_result(
        user_message: str,
        previous_result: Dict[str, Any],
        extracted_info: Dict[str, Any]
    ) -> str:
        """
        쿼리 결과를 기반으로 자연스러운 한국어 답변을 생성합니다.

        Args:
            user_message: 사용자의 원본 메시지
            previous_result: SQL 실행 결과 (columns, rows, row_count)
            extracted_info: 추출된 엔티티 정보

        Returns:
            생성된 답변 문자열
        """
        try:
            # 오류가 있으면 빈 답변 반환
            if previous_result.get("error"):
                return "조회 중 오류가 발생했습니다."

            if not previous_result.get("rows"):
                return "조회 결과가 없습니다."

            # 첫 번째 행의 데이터 추출
            row_data = previous_result["rows"][0]

            # 사용자 메시지에서 측정 대상 파악
            if "불량율" in user_message or "불량률" in user_message or "불량비" in user_message:
                metric = "불량율"
                unit = "%"
                is_rate_query = True
            elif "양품" in user_message or "좋은" in user_message:
                metric = "양품"
                unit = "개"
                is_rate_query = False
            elif "불량" in user_message or "불량품" in user_message:
                metric = "불량품"
                unit = "개"
                is_rate_query = False
            else:
                metric = "생산량"
                unit = "개"
                is_rate_query = False

            # 시간 표현 파악
            if "__PERIOD__:past_week" in str(extracted_info.get("cycle_date", "")):
                time_expr = "지난주"
            elif "__PERIOD__:this_week" in str(extracted_info.get("cycle_date", "")):
                time_expr = "이번주"
            elif "__PERIOD__:past_month" in str(extracted_info.get("cycle_date", "")):
                time_expr = "지난달"
            elif "__PERIOD__:this_month" in str(extracted_info.get("cycle_date", "")):
                time_expr = "이번달"
            elif "어제" in user_message or "DATE_SUB" in str(extracted_info.get("cycle_date", "")):
                time_expr = "어제"
            elif "오늘" in user_message or "CURDATE" in str(extracted_info.get("cycle_date", "")):
                time_expr = "오늘"
            else:
                time_expr = ""

            # 쿼리 유형 판단: 숫자 조회 vs 텍스트 조회 (불량 원인 등)
            is_text_query = (
                "원인" in user_message or
                "이유" in user_message or
                "종류" in user_message
            )

            # 첫 번째 행의 데이터 추출
            row_data = previous_result["rows"][0]

            # 1. 텍스트 조회 (불량 원인 등)
            if is_text_query:
                rows = previous_result.get("rows", [])
                if not rows:
                    return "조회 결과가 없습니다."

                # 기계 정보 추가
                machine_id = extracted_info.get("machine_id", "")
                machine_str = f"{machine_id}번 사출기의" if machine_id else "사출기의"

                # 불량 원인별 개수가 있는지 확인
                has_count = False
                defect_counts = []

                for row in rows:
                    # defect_description과 count를 찾기
                    defect_desc = None
                    count = None

                    for col_name, col_value in row.items():
                        if col_name.lower() in ['defect_description', 'defect_desc']:
                            defect_desc = col_value
                        elif col_name.lower() == 'count':
                            try:
                                count = int(col_value)
                                has_count = True
                            except (ValueError, TypeError):
                                pass

                    if defect_desc:
                        if has_count and count:
                            defect_counts.append((defect_desc, count))
                        else:
                            defect_counts.append((defect_desc, None))

                if not defect_counts:
                    return "조회 결과가 없습니다."

                # 괄호 안의 한글 부분만 추출 (예: "Flash (플래시)" → "플래시")
                def extract_korean_name(desc):
                    match = re.search(r'\(([^)]+)\)', desc)
                    return match.group(1) if match else desc

                # 텍스트 답변 구성
                if has_count and all(count is not None for _, count in defect_counts):
                    # 개수가 있는 경우: "플래시 3건, 보이드 2건"
                    defect_details = []
                    total_defects = sum(count for _, count in defect_counts)

                    for desc, count in defect_counts:
                        korean_name = extract_korean_name(desc)
                        defect_details.append(f"{korean_name} {count}건")

                    details_str = ", ".join(defect_details)
                    answer = f"{time_expr} {machine_str} 불량 원인은 {details_str}이고, 총 {total_defects}건입니다."
                else:
                    # 개수가 없는 경우: "플래시, 보이드 등"
                    unique_descs = [extract_korean_name(desc) for desc, _ in defect_counts]
                    if len(unique_descs) == 1:
                        answer = f"{time_expr} {machine_str} 불량 원인은 {unique_descs[0]}입니다."
                    else:
                        values_str = ", ".join(unique_descs)
                        answer = f"{time_expr} {machine_str} 불량 원인은 {values_str} 등입니다."

                return answer

            # 2. 불량율 쿼리 (특별 처리)
            if is_rate_query:
                # 먼저 CTE 결과로 계산된 비교율이 있는지 확인 (yesterday_defects, yesterday_production, today_defects, today_production 등)
                period_data = {}
                for col_name, col_value in row_data.items():
                    col_lower = col_name.lower()
                    if col_value is not None:
                        try:
                            # yesterday_defects, yesterday_production, today_defects, today_production 등
                            if 'yesterday' in col_lower and 'defect' in col_lower:
                                if 'yesterday' not in period_data:
                                    period_data['yesterday'] = {}
                                period_data['yesterday']['defects'] = float(col_value)
                            elif 'yesterday' in col_lower and ('production' in col_lower or 'cycle' in col_lower):
                                if 'yesterday' not in period_data:
                                    period_data['yesterday'] = {}
                                period_data['yesterday']['production'] = float(col_value)
                            elif 'today' in col_lower and 'defect' in col_lower:
                                if 'today' not in period_data:
                                    period_data['today'] = {}
                                period_data['today']['defects'] = float(col_value)
                            elif 'today' in col_lower and ('production' in col_lower or 'cycle' in col_lower):
                                if 'today' not in period_data:
                                    period_data['today'] = {}
                                period_data['today']['production'] = float(col_value)
                            # 지난주, 이번주, 지난달, 이번달도 동일하게 처리
                            elif 'past_week' in col_lower or 'pastweek' in col_lower:
                                if 'past_week' not in period_data:
                                    period_data['past_week'] = {}
                                if 'defect' in col_lower:
                                    period_data['past_week']['defects'] = float(col_value)
                                else:
                                    period_data['past_week']['production'] = float(col_value)
                            elif 'this_week' in col_lower or 'thisweek' in col_lower:
                                if 'this_week' not in period_data:
                                    period_data['this_week'] = {}
                                if 'defect' in col_lower:
                                    period_data['this_week']['defects'] = float(col_value)
                                else:
                                    period_data['this_week']['production'] = float(col_value)
                            elif 'past_month' in col_lower or 'pastmonth' in col_lower:
                                if 'past_month' not in period_data:
                                    period_data['past_month'] = {}
                                if 'defect' in col_lower:
                                    period_data['past_month']['defects'] = float(col_value)
                                else:
                                    period_data['past_month']['production'] = float(col_value)
                            elif 'this_month' in col_lower or 'thismonth' in col_lower:
                                if 'this_month' not in period_data:
                                    period_data['this_month'] = {}
                                if 'defect' in col_lower:
                                    period_data['this_month']['defects'] = float(col_value)
                                else:
                                    period_data['this_month']['production'] = float(col_value)
                        except (ValueError, TypeError):
                            pass

                # CTE 결과 사용 (비교 쿼리) - 두 기간의 불량율 계산
                period_pairs = [
                    ('yesterday', '어제', 'today', '오늘'),
                    ('past_week', '지난주', 'this_week', '이번주'),
                    ('past_month', '지난달', 'this_month', '이번달'),
                ]

                for first_key, first_label, second_key, second_label in period_pairs:
                    if (first_key in period_data and second_key in period_data and
                        'defects' in period_data[first_key] and 'production' in period_data[first_key] and
                        'defects' in period_data[second_key] and 'production' in period_data[second_key]):

                        # 불량율 계산
                        first_prod = period_data[first_key]['production']
                        second_prod = period_data[second_key]['production']

                        if first_prod > 0 and second_prod > 0:
                            first_rate = (period_data[first_key]['defects'] / first_prod) * 100
                            second_rate = (period_data[second_key]['defects'] / second_prod) * 100
                            diff = second_rate - first_rate

                            if diff > 0:
                                change_str = f"({diff:.2f}%포인트 증가)"
                            elif diff < 0:
                                change_str = f"({abs(diff):.2f}%포인트 감소)"
                            else:
                                change_str = "(변화 없음)"

                            answer = f"{first_label} 불량율은 {first_rate:.2f}%, {second_label} 불량율은 {second_rate:.2f}% {change_str}입니다."
                            return answer

                # CTE 결과 없으면 기존 로직 사용
                total_defects = None
                total_production = None

                for col_name, col_value in row_data.items():
                    col_lower = col_name.lower()
                    if col_value is not None:
                        try:
                            if 'defect' in col_lower:
                                total_defects = float(col_value)
                            elif 'production' in col_lower or 'cycle' in col_lower:
                                total_production = float(col_value)
                        except (ValueError, TypeError):
                            pass

                if total_defects is None or total_production is None or total_production == 0:
                    return "조회 결과를 처리할 수 없습니다."

                # 불량율 계산
                defect_rate = (total_defects / total_production) * 100

                # 비교 쿼리인지 확인 (여러 행이 있는 경우 - UNION ALL 결과)
                rows = previous_result.get("rows", [])
                if len(rows) > 1:
                    # 비교 쿼리: 모든 행의 불량율 계산
                    rates = []
                    period_labels = []

                    # 사용자 메시지에서 기간 추출
                    if "지난주" in user_message and "이번주" in user_message:
                        period_labels = ["지난주", "이번주"]
                    elif "지난달" in user_message and "이번달" in user_message:
                        period_labels = ["지난달", "이번달"]
                    elif "어제" in user_message and "오늘" in user_message:
                        period_labels = ["어제", "오늘"]

                    for row in rows:
                        defects = None
                        prod = None

                        for col_name, col_value in row.items():
                            col_lower = col_name.lower()
                            if col_value is not None:
                                if 'defect' in col_lower:
                                    try:
                                        defects = float(col_value)
                                    except (ValueError, TypeError):
                                        pass
                                elif 'production' in col_lower or 'cycle' in col_lower:
                                    try:
                                        prod = float(col_value)
                                    except (ValueError, TypeError):
                                        pass

                        if defects is not None and prod is not None and prod > 0:
                            rate = (defects / prod) * 100
                            rates.append(rate)

                    if len(rates) == 2 and len(period_labels) == 2:
                        # 두 기간 비교
                        first_rate = rates[0]
                        second_rate = rates[1]
                        diff = second_rate - first_rate

                        if diff > 0:
                            change_str = f"({diff:.2f}%포인트 증가)"
                        elif diff < 0:
                            change_str = f"({abs(diff):.2f}%포인트 감소)"
                        else:
                            change_str = "(변화 없음)"

                        answer = f"{period_labels[0]} 불량율은 {first_rate:.2f}%, {period_labels[1]} 불량율은 {second_rate:.2f}% {change_str}입니다."
                        return answer
                    elif rates:
                        # 기간 레이블 없이 그냥 출력
                        details_str = ", ".join(f"{rate:.2f}%" for rate in rates)
                        answer = f"{details_str}입니다."
                        return answer

                # 단일 기간 쿼리
                answer = f"{time_expr} 불량율은 {defect_rate:.2f}%입니다."
                return answer

            # 3. 숫자 조회 (생산량, 불량 개수 등)
            value = None
            for col_name, col_value in row_data.items():
                if col_value is not None:
                    try:
                        # Decimal, int, float, numpy.int64 등 모든 숫자 타입 처리
                        value = float(col_value)
                        break
                    except (ValueError, TypeError):
                        continue

            if value is None:
                return "조회 결과를 처리할 수 없습니다."

            # 숫자 포매팅 (천 단위 구분)
            value_formatted = f"{int(value):,}"

            # 답변 구성
            if "__PERIOD__" in str(extracted_info.get("cycle_date", "")):
                # 범위 쿼리 (총 키워드 포함)
                answer = f"{time_expr} {metric}은 총 {value_formatted}{unit}입니다."
            else:
                # 단일 날짜 쿼리
                answer = f"{time_expr} {metric}은 {value_formatted}{unit}입니다."

            return answer

        except Exception as e:
            print(f"⚠️ 답변 생성 오류: {str(e)}")
            return "답변을 생성할 수 없습니다."
