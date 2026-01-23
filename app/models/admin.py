"""
관리자 모듈 테이블
PostgreSQL에 저장됨
"""
from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean
from sqlalchemy.sql import func
from app.db.database import Base


class Term(Base):
    """
    용어 사전 테이블
    사용자 표현과 표준 용어를 매핑합니다
    """
    __tablename__ = "admin_terms"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_expression = Column(String(255), nullable=False, index=True)
    standard_term = Column(String(255), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    deleted_at = Column(DateTime(timezone=True), nullable=True)

    def __repr__(self):
        return f"<Term(id={self.id}, user_expression={self.user_expression}, standard_term={self.standard_term})>"


class Knowledge(Base):
    """
    도메인 지식 테이블
    업계 규칙, 표준, 참고값을 저장합니다
    """
    __tablename__ = "admin_knowledge"

    id = Column(Integer, primary_key=True, autoincrement=True)
    category = Column(String(100), nullable=False, index=True)
    content = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    deleted_at = Column(DateTime(timezone=True), nullable=True)

    def __repr__(self):
        return f"<Knowledge(id={self.id}, category={self.category})>"


class SchemaField(Base):
    """
    필드 설명 테이블
    데이터베이스 필드에 대한 설명 메타데이터
    """
    __tablename__ = "admin_schema_fields"

    id = Column(Integer, primary_key=True, autoincrement=True)
    table_name = Column(String(100), nullable=False, index=True)
    field_name = Column(String(100), nullable=False)
    data_type = Column(String(50), nullable=False)
    description = Column(Text, nullable=False)
    is_core = Column(Boolean, default=True)  # 핵심 필드 (수정 불가)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    deleted_at = Column(DateTime(timezone=True), nullable=True)

    def __repr__(self):
        return f"<SchemaField(id={self.id}, table_name={self.table_name}, field_name={self.field_name})>"
