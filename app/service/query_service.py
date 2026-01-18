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
from datetime import datetime
from decimal import Decimal
from typing import Optional, Dict, List, Any
from sqlalchemy.orm import Session
from sqlalchemy import text, func

from app.schemas.query import QueryRequest, QueryResponse, QueryResultData
from app.models.chat import ChatThread, ChatMessage
from app.models.prompt import PromptDict, PromptKnowledge, PromptTable, PromptColumn
from app.service.exaone_service import ExaoneService, ExaoneAPIService
from app.service.ollama_exaone_service import OllamaExaoneService
from app.service.rag_service import RAGService
from app.service.schema_rag_service import SchemaRAGService
from app.utils.sql_validator import SQLValidator


class QueryService:
    """쿼리 처리 서비스 클래스"""

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

            # 2. 질문 보정 (용어 사전)
            corrected_message = QueryService.correct_message(
                request.message,
                db_postgres
            )

            # 3. 스키마 정보 조회
            schema_info = QueryService.get_schema_info(db_postgres, db_mysql)

            # 4. 프롬프트 지식 베이스 조회
            knowledge_base = QueryService.get_knowledge_base(db_postgres)

            # 5. RAG 컨텍스트 검색 (2가지: Conversation RAG + Schema RAG)
            rag_context = []
            schema_hint = ""

            try:
                # Conversation RAG: 이전 대화 검색
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

            try:
                # Schema RAG: 스키마 기반 검색 (테이블/컬럼 자동 매핑)
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

            # 6. EXAONE AI 호출 (SQL 생성)
            # 우선 순서: Ollama 로컬 EXAONE → Mock 폴백
            generated_sql = None
            try:
                print(f"🔄 Ollama 로컬 EXAONE 호출 중...")

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

                # Schema RAG 힌트 추가
                if schema_hint:
                    if api_query == request.message:
                        api_query = schema_hint + "\n질문: " + request.message
                    else:
                        api_query = schema_hint + "\n" + api_query

                generated_sql = OllamaExaoneService.nl_to_sql(
                    user_query=api_query,
                    corrected_query=corrected_message,
                    schema_info=schema_info,
                    knowledge_base=knowledge_base
                )
                print(f"✅ Ollama 로컬 EXAONE 사용")
            except Exception as ollama_error:
                print(f"⚠️ Ollama 오류 ({str(ollama_error)}), Mock으로 폴백...")
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

            # 7. SQL 검증
            is_valid, error_msg = SQLValidator.validate(generated_sql)
            if not is_valid:
                raise ValueError(f"SQL 검증 실패: {error_msg}")

            # SQL 정제 (LIMIT 추가 등)
            sanitized_sql = SQLValidator.sanitize(generated_sql)

            # 8. MySQL에서 쿼리 실행
            result_data = QueryService.execute_query(db_mysql, sanitized_sql)

            # 9. 대화 기록 저장
            message = ChatMessage(
                thread_id=thread.id,
                role="user",
                message=request.message,
                context_tag=request.context_tag,
            )
            db_postgres.add(message)
            db_postgres.flush()  # message.id를 얻기 위해
            message_id = message.id

            # Assistant 응답 메시지 저장
            result_data_dict = {
                "columns": result_data.columns,
                "rows": result_data.rows,
                "row_count": result_data.row_count
            }

            assistant_message = ChatMessage(
                thread_id=thread.id,
                role="assistant",
                message=f"생산 데이터 조회 결과 {result_data.row_count}행 반환",
                corrected_msg=corrected_message,
                gen_sql=sanitized_sql,
                result_data=result_data_dict
            )
            db_postgres.add(assistant_message)
            db_postgres.commit()

            # 10. RAG 임베딩 저장 (비동기)
            try:
                # 사용자 메시지 임베딩
                RAGService.store_embedding(
                    db_postgres,
                    thread_id=thread.id,
                    message=request.message
                )

                # Assistant 응답 임베딩
                RAGService.store_embedding(
                    db_postgres,
                    thread_id=thread.id,
                    message=f"생산 데이터 조회 결과 {result_data.row_count}행 반환",
                    result_data=result_data_dict
                )
                print(f"✅ RAG 임베딩 저장 완료")
            except Exception as embedding_error:
                print(f"⚠️ RAG 임베딩 저장 실패: {str(embedding_error)}")
                # 임베딩 저장 실패해도 쿼리 결과는 반환

            # 11. 응답 구성
            execution_time = (time.time() - start_time) * 1000  # 밀리초

            response = QueryResponse(
                thread_id=thread.id,
                message_id=message_id,
                original_message=request.message,
                corrected_message=corrected_message,
                generated_sql=sanitized_sql,
                result_data=result_data,
                execution_time=execution_time,
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
        스키마 메타데이터 조회

        Returns:
            {
                "tables": [
                    {
                        "name": "production_data",
                        "description": "생산 데이터",
                        "columns": [
                            {"name": "id", "type": "BIGINT", "description": "..."},
                            ...
                        ]
                    },
                    ...
                ],
                "available_columns": ["production_date", "line_id", ...]
            }
        """
        try:
            # 프롬프트 테이블 메타데이터 조회
            tables = db_postgres.query(PromptTable).all()

            schema_info = {
                "tables": [],
                "available_columns": []
            }

            for table in tables:
                # 각 테이블의 컬럼 조회
                columns = db_postgres.query(PromptColumn).filter(
                    PromptColumn.table_id == table.id
                ).all()

                table_info = {
                    "name": table.name,
                    "description": table.description,
                    "columns": [
                        {
                            "name": col.name,
                            "type": col.data_type,
                            "description": col.description
                        }
                        for col in columns
                    ]
                }

                schema_info["tables"].append(table_info)

                # 모든 컬럼 이름 수집
                schema_info["available_columns"].extend([col.name for col in columns])

            # MySQL 테이블 검증 (실제 존재하는지 확인)
            try:
                for table in tables:
                    db_mysql.execute(text(f"SELECT 1 FROM {table.name} LIMIT 1"))
            except Exception as e:
                print(f"⚠️ MySQL 테이블 검증 오류: {str(e)}")

            return schema_info

        except Exception as e:
            print(f"❌ 스키마 정보 조회 오류: {str(e)}")
            # 기본값 반환
            return {
                "tables": [],
                "available_columns": ["production_date", "line_id", "actual_quantity"]
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
        사용자의 모든 쓰레드 조회

        Args:
            db: PostgreSQL 세션
            user_id: 사용자 ID
            limit: 조회할 최대 개수

        Returns:
            쓰레드 정보 리스트
        """
        try:
            threads = db.query(ChatThread).filter(
                ChatThread.user_id == user_id
            ).order_by(ChatThread.created_at.desc()).limit(limit).all()

            result = []
            for thread in threads:
                # 각 쓰레드의 메시지 개수 조회
                message_count = db.query(func.count(ChatMessage.id)).filter(
                    ChatMessage.thread_id == thread.id
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
        특정 쓰레드의 메시지 조회

        Args:
            db: PostgreSQL 세션
            thread_id: 쓰레드 ID
            user_id: 사용자 ID (권한 확인용)

        Returns:
            메시지 리스트

        Raises:
            ValueError: 권한 없음
        """
        try:
            # 권한 확인
            thread = db.query(ChatThread).filter(
                ChatThread.id == thread_id,
                ChatThread.user_id == user_id
            ).first()

            if not thread:
                raise ValueError("쓰레드에 접근할 권한이 없습니다")

            # 메시지 조회
            messages = db.query(ChatMessage).filter(
                ChatMessage.thread_id == thread_id
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
