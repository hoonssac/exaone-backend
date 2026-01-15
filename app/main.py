from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import os
from dotenv import load_dotenv

# 모델 import (테이블 생성을 위해 필요)
from app.models.user import User
from app.models.chat import ChatThread, ChatMessage
from app.models.prompt import PromptTable, PromptColumn, PromptDict, PromptKnowledge
from app.db.database import create_all_tables, test_postgres_connection, test_mysql_connection

# 환경변수 로드
load_dotenv()

# FastAPI 앱 생성
app = FastAPI(
    title="EXAONE API",
    description="EXAONE AI 기반 제조 데이터 조회 API",
    version="1.0.0"
)

# CORS 설정
CORS_ORIGINS = [
    "http://localhost:8080",
    "http://10.0.2.2:8080",  # Android 에뮬레이터
    "http://localhost:3000",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 애플리케이션 시작 시 테이블 생성
@app.on_event("startup")
async def startup_event():
    """애플리케이션 시작 시 실행"""
    print("🚀 EXAONE API 서버 시작...")

    # 데이터베이스 연결 테스트
    postgres_ok = test_postgres_connection()
    mysql_ok = test_mysql_connection()

    if postgres_ok:
        # 테이블 생성
        create_all_tables()
        print("✅ 모든 시작 절차 완료")
    else:
        print("❌ PostgreSQL 연결 실패 - 테이블을 생성할 수 없습니다")

# 헬스체크 엔드포인트
@app.get("/health")
async def health_check():
    """헬스체크 엔드포인트"""
    postgres_ok = test_postgres_connection()
    mysql_ok = test_mysql_connection()

    return {
        "status": "healthy" if (postgres_ok and mysql_ok) else "degraded",
        "postgresql": "connected" if postgres_ok else "disconnected",
        "mysql": "connected" if mysql_ok else "disconnected"
    }

# 메인 엔드포인트
@app.get("/")
async def root():
    """API 루트 엔드포인트"""
    return {
        "message": "EXAONE API Server",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/health"
    }

# API 라우트
from app.api import auth, query
app.include_router(auth.router)
app.include_router(query.router)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8080,
        reload=True
    )
