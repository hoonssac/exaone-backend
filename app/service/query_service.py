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
import requests
from datetime import datetime
from decimal import Decimal
from typing import Optional, Dict, List, Any
from sqlalchemy.orm import Session
from sqlalchemy import text, func

from app.schemas.query import QueryRequest, QueryResponse, QueryResultData
from app.models.chat import ChatThread, ChatMessage
from app.models.prompt import PromptDict, PromptKnowledge, PromptTable, PromptColumn
from app.service.exaone_service import ExaoneService, ExaoneAPIService, ChatGPTService, GeminiService
from app.service.ollama_exaone_service import OllamaExaoneService
from app.service.rag_service import RAGService
from app.service.schema_rag_service import SchemaRAGService
from app.utils.sql_validator import SQLValidator


class QueryService:
    """쿼리 처리 서비스 클래스"""

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
  예) "오늘은?" "어제와 비교해줘" "다른 유형은?" "온도는?"

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
        if any(keyword in lower_query for keyword in ["누구야", "자기소개", "역할", "뭔가", "뭐야"]):
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

            # 5. 질문 보정 (용어 사전)
            corrected_message = QueryService.correct_message(
                request.message,
                db_postgres
            )

            # 4. 스키마 정보 조회
            schema_info = QueryService.get_schema_info(db_postgres, db_mysql)

            # 5. 프롬프트 지식 베이스 조회
            knowledge_base = QueryService.get_knowledge_base(db_postgres)

            # 6. RAG 컨텍스트 검색 (2가지: Conversation RAG + Schema RAG)
            rag_context = []
            schema_hint = ""

            # 5-1. Conversation RAG: 이전 대화 검색
            try:
                rag_context = RAGService.retrieve_context(
                    db_postgres,
                    thread_id=thread.id,
                    query=request.message,
                    top_k=3
                )
                if rag_context:
                    print(f"✅ Conversation RAG: {len(rag_context)} 개 메시지 검색됨")
            except Exception as rag_error:
                print(f"⚠️ Conversation RAG 검색 실패: {str(rag_error)}")
                rag_context = []

            # 5-2. Schema RAG: 스키마 기반 검색 (테이블/컬럼 자동 매핑)
            try:
                schema_results = SchemaRAGService.search_similar_schema(
                    db_postgres,
                    query=request.message,
                    top_k=5
                )
                if schema_results:
                    schema_hint = SchemaRAGService.format_schema_hint(schema_results)
                    print(f"✅ Schema RAG: {len(schema_results)} 개 스키마 검색됨")
                    print(f"   스키마 힌트:\n{schema_hint}")
            except Exception as schema_rag_error:
                print(f"⚠️ Schema RAG 검색 실패: {str(schema_rag_error)}")
                schema_hint = ""

            # 7. SQL 생성 (Ollama EXAONE → Mock 폴백)
            # 우선 순서: Ollama EXAONE → Mock 폴백
            generated_sql = None
            try:
                print(f"🔄 [1단계] Ollama EXAONE SQL 생성 중...")

                # 통합 프롬프트 구성: Conversation RAG + Schema RAG
                api_query = request.message

                # Conversation RAG 컨텍스트 추가
                if rag_context:
                    rag_prompt = RAGService.build_rag_prompt(
                        user_query=request.message,
                        context=rag_context,
                        schema_info=schema_info
                    )
                    api_query = rag_prompt
                    print(f"💬 이전 대화 컨텍스트 추가됨")

                # Schema RAG 힌트 추가
                if schema_hint:
                    if api_query == request.message:
                        api_query = schema_hint + "\n질문: " + request.message
                    else:
                        api_query = schema_hint + "\n" + api_query
                    print(f"🗂️ 스키마 힌트 추가됨")

                print(f"📤 Ollama EXAONE에 전달할 질문:\n{api_query[:200]}...")
                generated_sql = OllamaExaoneService.nl_to_sql(
                    user_query=api_query,
                    corrected_query=corrected_message,
                    schema_info=schema_info,
                    knowledge_base=knowledge_base
                )

                print(f"✅ Ollama EXAONE SQL 생성 성공")
            except Exception as ollama_error:
                print(f"⚠️ Ollama EXAONE 오류 ({str(ollama_error)}), Mock으로 폴백...")
                try:
                    generated_sql = ExaoneService.nl_to_sql(
                        user_query=request.message,
                        corrected_query=corrected_message,
                        schema_info=schema_info,
                        knowledge_base=knowledge_base
                    )
                    print(f"✅ Mock 방식 사용")
                except Exception as mock_error:
                    raise ValueError(f"SQL 생성 실패 (Ollama: {ollama_error}, Mock: {mock_error})")

            # 8. SQL 검증
            is_valid, error_msg = SQLValidator.validate(generated_sql)
            if not is_valid:
                raise ValueError(f"SQL 검증 실패: {error_msg}")

            # SQL 정제 (LIMIT 추가 등)
            sanitized_sql = SQLValidator.sanitize(generated_sql)

            # 9. MySQL에서 쿼리 실행
            result_data = QueryService.execute_query(db_mysql, sanitized_sql)

            # 10. [2단계] 자연어 응답 생성
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

            # 11. 대화 기록 저장
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
            result_data_dict = {
                "columns": result_data.columns,
                "rows": result_data.rows,
                "row_count": result_data.row_count
            }

            assistant_message = ChatMessage(
                thread_id=thread.id,
                role="assistant",
                message=natural_response,  # AI가 생성한 자연어 응답
                corrected_msg=corrected_message,
                gen_sql=sanitized_sql,
                result_data=result_data_dict
            )
            db_postgres.add(assistant_message)
            db_postgres.commit()

            # 12. RAG 임베딩 저장 (비동기)
            try:
                # 사용자 메시지 임베딩
                RAGService.store_embedding(
                    db_postgres,
                    thread_id=thread.id,
                    message=request.message
                )

                # Assistant 응답 임베딩 (자연어 응답)
                RAGService.store_embedding(
                    db_postgres,
                    thread_id=thread.id,
                    message=natural_response,
                    result_data=result_data_dict
                )
                print(f"✅ RAG 임베딩 저장 완료")
            except Exception as embedding_error:
                print(f"⚠️ RAG 임베딩 저장 실패: {str(embedding_error)}")
                # 임베딩 저장 실패해도 쿼리 결과는 반환

            # 13. 응답 구성
            execution_time = (time.time() - start_time) * 1000  # 밀리초

            response = QueryResponse(
                thread_id=thread.id,
                message_id=message_id,
                original_message=request.message,
                corrected_message=corrected_message,
                generated_sql=sanitized_sql,
                result_data=result_data,
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
    def correct_message(message: str, db: Session) -> str:
        """
        용어 사전을 이용하여 질문 보정

        예:
        - "오늘" → "CURDATE()"
        - "어제" → "DATE_SUB(CURDATE(), INTERVAL 1 DAY)"
        - "Loading" → "로딩기"

        Args:
            message: 원본 질문
            db: PostgreSQL 세션

        Returns:
            보정된 질문
        """
        corrected = message

        try:
            # 용어 사전 조회
            term_dicts = db.query(PromptDict).all()

            for term_dict in term_dicts:
                # 대소문자 무시하고 단어 전체 매칭
                import re
                pattern = rf'\b{re.escape(term_dict.key)}\b'
                corrected = re.sub(
                    pattern,
                    term_dict.value,
                    corrected,
                    flags=re.IGNORECASE
                )

        except Exception as e:
            print(f"⚠️ 용어 사전 보정 오류: {str(e)}")
            # 보정 실패 시 원본 반환
            return message

        return corrected

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
