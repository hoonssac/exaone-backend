"""
Schema-based RAG (Retrieval-Augmented Generation)

데이터베이스 스키마(테이블, 컬럼)의 의미론적 검색으로
사용자 질문에서 올바른 테이블/컬럼을 자동으로 찾습니다.

예시:
- 사용자: "물량이 얼마나?" (생산량과 다른 표현)
- RAG: actual_quantity (생산 수량) 자동 검색
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
    """스키마 기반 RAG 서비스"""

    _vectorizer: Optional[TfidfVectorizer] = None
    _fitted = False

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

    @staticmethod
    def initialize_schema_embeddings(db: Session) -> None:
        """
        prompt_table과 prompt_column의 description을 벡터화하여 저장

        처음 한 번만 실행 (또는 스키마 변경 시)
        """
        try:
            # 기존 데이터 삭제
            db.execute(text("DELETE FROM schema_embeddings"))

            # prompt_table에서 description 벡터화
            tables_sql = """
            SELECT id, name, description FROM prompt_table
            """
            tables = db.execute(text(tables_sql)).fetchall()

            vectorizer = SchemaRAGService.get_vectorizer()

            # 초기 학습
            if not SchemaRAGService._fitted:
                sample_texts = [
                    "생산",
                    "불량",
                    "설비",
                    "생산량",
                    "수량",
                    "속도",
                    "시간",
                    "횟수",
                ]
                vectorizer.fit(sample_texts)
                SchemaRAGService._fitted = True
                logger.info("SchemaRAG: Vectorizer 학습 완료")

            # 테이블 저장
            for table_id, table_name, description in tables:
                if not description:
                    description = table_name

                vector = vectorizer.transform([description]).toarray()[0]
                vector_json = json.dumps(vector.tolist())

                insert_sql = """
                INSERT INTO schema_embeddings (schema_type, table_id, name, description, embedding)
                VALUES (:schema_type, :table_id, :name, :description, :embedding)
                """
                db.execute(
                    text(insert_sql),
                    {
                        "schema_type": "table",
                        "table_id": table_id,
                        "name": table_name,
                        "description": description,
                        "embedding": vector_json,
                    },
                )

            # prompt_column에서 description 벡터화
            columns_sql = """
            SELECT pc.id, pc.table_id, pc.name, pc.description
            FROM prompt_column pc
            """
            columns = db.execute(text(columns_sql)).fetchall()

            for col_id, table_id, col_name, description in columns:
                if not description:
                    description = col_name

                vector = vectorizer.transform([description]).toarray()[0]
                vector_json = json.dumps(vector.tolist())

                insert_sql = """
                INSERT INTO schema_embeddings (schema_type, table_id, column_id, name, description, embedding)
                VALUES (:schema_type, :table_id, :column_id, :name, :description, :embedding)
                """
                db.execute(
                    text(insert_sql),
                    {
                        "schema_type": "column",
                        "table_id": table_id,
                        "column_id": col_id,
                        "name": col_name,
                        "description": description,
                        "embedding": vector_json,
                    },
                )

            db.commit()
            logger.info(
                f"SchemaRAG: {len(tables)} 테이블 + {len(columns)} 컬럼 임베딩 저장 완료"
            )

        except Exception as e:
            db.rollback()
            logger.error(f"SchemaRAG 초기화 오류: {str(e)}")

    @staticmethod
    def search_similar_schema(
        db: Session, query: str, top_k: int = 5
    ) -> List[Dict[str, Any]]:
        """
        질문과 유사한 스키마(테이블/컬럼) 검색

        Args:
            db: PostgreSQL 세션
            query: 사용자 질문
            top_k: 반환할 최대 개수

        Returns:
            유사한 스키마 정보 리스트 (유사도 순)
        """
        try:
            # 질문 벡터화
            vectorizer = SchemaRAGService.get_vectorizer()
            query_vector = vectorizer.transform([query]).toarray()[0]

            # DB에서 모든 스키마 임베딩 조회
            fetch_sql = """
            SELECT id, schema_type, table_id, column_id, name, description, embedding
            FROM schema_embeddings
            ORDER BY schema_type DESC, name
            """
            results = db.execute(text(fetch_sql)).fetchall()

            if not results:
                logger.warning("SchemaRAG: 저장된 스키마 임베딩 없음")
                return []

            # 유사도 계산
            similarities = []
            for row in results:
                schema_id, schema_type, table_id, col_id, name, desc, embedding_json = (
                    row
                )

                try:
                    stored_vector = np.array(json.loads(embedding_json))
                    similarity = 1 - cosine(query_vector, stored_vector)

                    similarities.append(
                        {
                            "id": schema_id,
                            "schema_type": schema_type,
                            "table_id": table_id,
                            "column_id": col_id,
                            "name": name,
                            "description": desc,
                            "similarity": float(similarity),
                        }
                    )
                except Exception as e:
                    logger.warning(f"SchemaRAG 유사도 계산 오류: {str(e)}")
                    continue

            # 유사도 상위 top_k
            similarities.sort(key=lambda x: x["similarity"], reverse=True)
            top_results = similarities[:top_k]

            logger.info(f"SchemaRAG: {len(top_results)} 개 스키마 검색됨")
            return top_results

        except Exception as e:
            logger.error(f"SchemaRAG 검색 오류: {str(e)}")
            return []

    @staticmethod
    def format_schema_hint(schema_results: List[Dict[str, Any]]) -> str:
        """
        검색된 스키마 정보를 EXAONE 프롬프트용 힌트로 포맷

        Args:
            schema_results: 검색된 스키마 리스트

        Returns:
            포맷된 힌트 문자열
        """
        if not schema_results:
            return ""

        hint = "\n=== 스키마 힌트 ===\n"

        # 테이블 정보
        tables = [r for r in schema_results if r["schema_type"] == "table"]
        if tables:
            hint += "테이블:\n"
            for item in tables[:3]:
                hint += f"  - {item['name']}: {item['description']} (유사도: {item['similarity']:.2f})\n"

        # 컬럼 정보
        columns = [r for r in schema_results if r["schema_type"] == "column"]
        if columns:
            hint += "컬럼:\n"
            for item in columns[:5]:
                hint += f"  - {item['name']}: {item['description']} (유사도: {item['similarity']:.2f})\n"

        hint += "==================\n"
        return hint

    @staticmethod
    def get_relevant_table_names(schema_results: List[Dict[str, Any]]) -> List[str]:
        """
        검색된 스키마에서 관련 테이블 이름 추출

        Args:
            schema_results: 검색된 스키마 리스트

        Returns:
            테이블 이름 리스트
        """
        tables = set()
        for item in schema_results:
            if item["schema_type"] == "table":
                tables.add(item["name"])
            elif item["schema_type"] == "column" and item["table_id"]:
                # 컬럼의 테이블 ID로 테이블 이름 찾기
                # (실제로는 조인으로 가져와야 하지만 여기서는 단순화)
                pass

        return list(tables)
