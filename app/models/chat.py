from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, BigInteger, JSON
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.db.database import Base


class ChatThread(Base):
    """
    채팅 쓰레드 테이블
    하나의 대화 세션을 나타냄
    """
    __tablename__ = "chat_thread"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    title = Column(String(255), nullable=True)  # AI가 자동 생성하는 요약
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # 관계
    messages = relationship("ChatMessage", back_populates="thread", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<ChatThread(id={self.id}, user_id={self.user_id}, title={self.title})>"


class ChatMessage(Base):
    """
    채팅 메시지 테이블
    사용자 질문, AI 응답, 생성된 SQL, 결과 등을 저장
    """
    __tablename__ = "chat_message"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    thread_id = Column(BigInteger, ForeignKey("chat_thread.id"), nullable=False, index=True)
    role = Column(String(10), nullable=False)  # "user", "assistant", "system"
    context_tag = Column(String(20), nullable=True)  # "@현장", "@회의실", "@일반"
    message = Column(Text, nullable=True)  # 원문 질문 (사용자)
    corrected_msg = Column(Text, nullable=True)  # 보정된 질문
    gen_sql = Column(Text, nullable=True)  # 생성된 SQL
    result_data = Column(JSON, nullable=True)  # 쿼리 실행 결과 (JSON)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # 관계
    thread = relationship("ChatThread", back_populates="messages")

    def __repr__(self):
        return f"<ChatMessage(id={self.id}, thread_id={self.thread_id}, role={self.role})>"
