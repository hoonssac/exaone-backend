from sqlalchemy import Column, Integer, String, Text, BigInteger, ForeignKey
from sqlalchemy.orm import relationship
from app.db.database import Base


class PromptTable(Base):
    """
    AI 프롬프트 지식 베이스: 테이블 정보
    데이터베이스의 테이블 메타데이터를 저장
    """
    __tablename__ = "prompt_table"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False)  # 물리 테이블명
    description = Column(String(255), nullable=False)  # 테이블 설명

    # 관계
    columns = relationship("PromptColumn", back_populates="table", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<PromptTable(id={self.id}, name={self.name})>"


class PromptColumn(Base):
    """
    AI 프롬프트 지식 베이스: 컬럼 정보
    각 테이블의 컬럼 메타데이터를 저장
    """
    __tablename__ = "prompt_column"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    table_id = Column(BigInteger, ForeignKey("prompt_table.id"), nullable=False)
    name = Column(String(100), nullable=False)  # 물리 컬럼명
    description = Column(String(255), nullable=False)  # 컬럼 설명 (의미/단위)
    data_type = Column(String(50), nullable=False)  # 데이터 타입

    # 관계
    table = relationship("PromptTable", back_populates="columns")

    def __repr__(self):
        return f"<PromptColumn(id={self.id}, name={self.name}, type={self.data_type})>"


class PromptDict(Base):
    """
    AI 프롬프트 지식 베이스: 용어 사전
    현장 용어를 표준 DB 용어로 매핑
    예: Loading → 로딩기, Unloader → 언로더
    """
    __tablename__ = "prompt_dict"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    key = Column(String(50), nullable=False, unique=True)  # 현장 용어 / 약어
    value = Column(String(255), nullable=False)  # 표준 DB 용어

    def __repr__(self):
        return f"<PromptDict(key={self.key}, value={self.value})>"


class PromptKnowledge(Base):
    """
    AI 프롬프트 지식 베이스: 도메인 지식
    비정형 도메인 지식 저장
    예: 제조 프로세스 설명, 산업별 용어, 비즈니스 규칙
    """
    __tablename__ = "prompt_know"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    content = Column(Text, nullable=False)  # 도메인 지식 본문

    def __repr__(self):
        return f"<PromptKnowledge(id={self.id})>"
