from sqlalchemy import Column, Integer, String, DateTime, Boolean
from sqlalchemy.sql import func
from app.db.database import Base


class User(Base):
    """
    사용자 정보 테이블
    PostgreSQL에 저장됨
    """
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    email = Column(String(100), unique=True, nullable=False, index=True)
    password = Column(String(255), nullable=False)  # bcrypt 해시
    name = Column(String(50), nullable=False)
    employee_id = Column(String(20), unique=True, nullable=False, index=True)
    dept_name = Column(String(50), nullable=False)  # 부서명
    position = Column(String(50), nullable=False)  # 직급
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    def __repr__(self):
        return f"<User(id={self.id}, email={self.email}, name={self.name})>"
