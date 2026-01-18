"""
RAG (Retrieval-Augmented Generation) 서비스

TF-IDF 기반 문서 유사도 검색으로 대화 컨텍스트를 활용합니다.

기능:
1. 메시지 벡터화 (TF-IDF)
2. 벡터 저장 (PostgreSQL JSON)
3. 유사 메시지 검색 (코사인 유사도)
4. 컨텍스트 조합 (이전 대화 + 현재 질문)
"""

import json
import logging
from typing import List, Dict, Any, Optional, Tuple
from scipy.sparse import csr_matrix
from scipy.spatial.distance import cosine
from sklearn.feature_extraction.text import TfidfVectorizer
from sqlalchemy.orm import Session
from sqlalchemy import text
import numpy as np

logger = logging.getLogger(__name__)


class RAGService:
    """TF-IDF 기반 RAG 서비스"""

    # 싱글톤 TfidfVectorizer
    _vectorizer: Optional[TfidfVectorizer] = None
    _fitted = False

    @classmethod
    def get_vectorizer(cls) -> TfidfVectorizer:
        """TfidfVectorizer 싱글톤 반환"""
        if cls._vectorizer is None:
            cls._vectorizer = TfidfVectorizer(
                analyzer="char",  # 문자 단위 분석 (한글 처리 최적)
                ngram_range=(2, 3),  # 바이그램, 트라이그램
                lowercase=False,  # 한글은 case 무관
                stop_words=None,  # 한글 불용어 없음
                max_features=1000,  # 최대 1000개 특성
            )
            logger.info("✅ TfidfVectorizer 초기화 완료")
        return cls._vectorizer

    @staticmethod
    def vectorize_text(text: str) -> np.ndarray:
        """
        텍스트를 TF-IDF 벡터로 변환

        Args:
            text: 입력 텍스트

        Returns:
            TF-IDF 벡터 (밀집 배열)
        """
        try:
            vectorizer = RAGService.get_vectorizer()

            # 첫 번째 호출인 경우 fit_transform
            if not RAGService._fitted:
                # 간단한 초기 학습을 위해 기본 문장들 사용
                sample_texts = [
                    "생산량",
                    "불량률",
                    "설비",
                    "라인",
                    "어제",
                    "오늘",
                    "비교",
                    "증가",
                    "감소",
                ]
                vectorizer.fit(sample_texts)
                RAGService._fitted = True
                logger.info("✅ TfidfVectorizer 학습 완료")

            # 텍스트 벡터화 (dense array로 변환)
            vector = vectorizer.transform([text]).toarray()[0]
            return vector

        except Exception as e:
            logger.error(f"벡터화 오류: {str(e)}")
            raise

    @staticmethod
    def store_embedding(
        db: Session,
        thread_id: int,
        message: str,
        result_data: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        메시지 벡터를 DB에 저장

        Args:
            db: PostgreSQL 세션
            thread_id: 쓰레드 ID
            message: 메시지 텍스트
            result_data: 쿼리 실행 결과 (선택)
        """
        try:
            # 벡터화
            vector = RAGService.vectorize_text(message)

            # 벡터를 JSON으로 직렬화 (db에 저장하기 위해)
            vector_json = json.dumps(vector.tolist())
            result_data_json = json.dumps(result_data) if result_data else None

            # 저장 (pgvector 대신 JSONB에 저장)
            insert_sql = """
            INSERT INTO message_embeddings (thread_id, message, embedding, result_data, created_at)
            VALUES (:thread_id, :message, :embedding, :result_data, CURRENT_TIMESTAMP)
            """

            db.execute(
                text(insert_sql),
                {
                    "thread_id": thread_id,
                    "message": message,
                    "embedding": vector_json,  # JSON 배열로 저장
                    "result_data": result_data_json,
                },
            )
            db.commit()
            logger.info(f"✅ RAG 벡터 저장: thread_id={thread_id}")

        except Exception as e:
            db.rollback()
            logger.error(f"벡터 저장 오류: {str(e)}")

    @staticmethod
    def retrieve_context(
        db: Session, thread_id: int, query: str, top_k: int = 3
    ) -> List[Dict[str, Any]]:
        """
        쿼리와 유사한 이전 메시지 검색

        Args:
            db: PostgreSQL 세션
            thread_id: 쓰레드 ID
            query: 현재 질문
            top_k: 반환할 메시지 개수

        Returns:
            유사한 메시지 리스트 (유사도 순)
        """
        try:
            # 쿼리 벡터화
            query_vector = RAGService.vectorize_text(query)

            # DB에서 같은 스레드의 모든 메시지 벡터 조회
            fetch_sql = """
            SELECT id, message, embedding, result_data
            FROM message_embeddings
            WHERE thread_id = :thread_id
            ORDER BY created_at DESC
            LIMIT 100
            """

            results = db.execute(
                text(fetch_sql), {"thread_id": thread_id}
            ).fetchall()

            if not results:
                logger.info(f"⚠️ 검색할 메시지 없음: thread_id={thread_id}")
                return []

            # 유사도 계산
            similarities = []
            for row in results:
                msg_id, message_text, embedding_json, result_data_json = row

                try:
                    # JSON 벡터 로드
                    stored_vector = np.array(json.loads(embedding_json))

                    # 코사인 유사도 계산
                    similarity = 1 - cosine(query_vector, stored_vector)

                    similarities.append(
                        {
                            "id": msg_id,
                            "message": message_text,
                            "result_data": (
                                json.loads(result_data_json)
                                if result_data_json
                                else None
                            ),
                            "similarity": similarity,
                        }
                    )
                except Exception as e:
                    logger.warning(f"벡터 유사도 계산 오류: {str(e)}")
                    continue

            # 유사도 상위 top_k 선택
            similarities.sort(key=lambda x: x["similarity"], reverse=True)
            top_results = similarities[:top_k]

            logger.info(f"✅ RAG 컨텍스트 검색: {len(top_results)} 개 메시지")
            return top_results

        except Exception as e:
            logger.error(f"컨텍스트 검색 오류: {str(e)}")
            return []

    @staticmethod
    def format_rag_context(
        context: List[Dict[str, Any]], max_chars: int = 2000
    ) -> str:
        """
        검색된 컨텍스트를 프롬프트 포맷으로 변환

        Args:
            context: 검색된 메시지 리스트
            max_chars: 최대 문자 길이

        Returns:
            포맷된 컨텍스트 문자열
        """
        if not context:
            return ""

        formatted = "=== 이전 대화 컨텍스트 ===\n"
        current_length = len(formatted)

        for i, item in enumerate(context, 1):
            message = item["message"]
            result = item.get("result_data", {})
            similarity = item.get("similarity", 0)

            # 결과 요약
            result_summary = ""
            if result:
                if isinstance(result, dict):
                    row_count = result.get("row_count", 0)
                    result_summary = f" (결과: {row_count}행)"
                else:
                    result_summary = f" (결과: {str(result)[:100]})"

            # 문자 길이 제한 확인
            line = f"{i}. Q: {message}{result_summary}\n"
            if current_length + len(line) > max_chars:
                break

            formatted += line
            current_length += len(line)

        formatted += "======================\n\n"
        return formatted

    @staticmethod
    def build_rag_prompt(
        user_query: str,
        context: List[Dict[str, Any]],
        schema_info: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        RAG 컨텍스트를 포함한 프롬프트 구성

        Args:
            user_query: 현재 사용자 질문
            context: 검색된 이전 대화
            schema_info: 스키마 정보 (선택)

        Returns:
            컨텍스트가 포함된 프롬프트
        """
        prompt = ""

        # 이전 컨텍스트 추가
        if context:
            prompt += RAGService.format_rag_context(context)

        # 현재 질문
        prompt += f"현재 질문: {user_query}\n\n"

        # 스키마 정보 (선택)
        if schema_info:
            prompt += "이용 가능한 테이블:\n"
            for table in schema_info.get("tables", []):
                prompt += f"- {table['name']}: {table.get('description', '')}\n"

        return prompt
