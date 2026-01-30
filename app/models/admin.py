"""
관리자 모듈 테이블
PostgreSQL에 저장됨
"""
from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, JSON
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


class FilterableField(Base):
    """
    필터 가능 필드 테이블
    엔티티 추출 규칙을 저장합니다
    """
    __tablename__ = "admin_filterable_fields"

    id = Column(Integer, primary_key=True, autoincrement=True)
    field_name = Column(String(100), nullable=False, index=True)      # "machine_id"
    display_name = Column(String(100), nullable=False)                # "사출기"
    description = Column(Text)                                         # "사출 기계"
    field_type = Column(String(50), nullable=False)                   # "numeric", "date", "text"
    extraction_pattern = Column(String(200))                          # regex: "\\d+"
    extraction_keywords = Column(JSON)                                # ["사출기", "호기", "호"]
    value_mapping = Column(JSON)                                      # {"오늘": "CURDATE()"}
    is_optional = Column(Boolean, default=True)                       # 필수 여부
    multiple_allowed = Column(Boolean, default=False)                 # 여러 값 허용
    valid_values = Column(JSON, nullable=True)                        # ["1", "2", "3", "4", "5"] - 유효한 값들
    validation_type = Column(String(50), default="none")              # "none", "exact", "range" - 검증 타입
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    deleted_at = Column(DateTime(timezone=True), nullable=True)

    def __repr__(self):
        return f"<FilterableField(id={self.id}, field_name={self.field_name}, display_name={self.display_name})>"


class AdminEntity(Base):
    """
    엔티티 정의 테이블
    동적으로 조회할 수 있는 엔티티(기계, 재료, 금형 등) 메타데이터
    """
    __tablename__ = "admin_entities"

    id = Column(Integer, primary_key=True, autoincrement=True)
    entity_name = Column(String(100), nullable=False, unique=True, index=True)  # "machines", "materials", "molds"
    display_name = Column(String(100), nullable=False)                          # "사출기", "재료", "금형"
    description = Column(Text)                                                  # "사용 가능한 사출기 목록"
    db_type = Column(String(20), default="mysql")                               # "mysql", "postgres"
    table_name = Column(String(100), nullable=False)                            # "injection_molding_machine", "material_spec"
    id_column = Column(String(100), nullable=False, default="id")              # "id", "material_id"
    name_column = Column(String(100), nullable=True)                            # "equipment_name", "material_type" (선택)
    query = Column(Text, nullable=False)                                        # SELECT id, name FROM table
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    deleted_at = Column(DateTime(timezone=True), nullable=True)

    def __repr__(self):
        return f"<AdminEntity(id={self.id}, entity_name={self.entity_name}, display_name={self.display_name})>"
