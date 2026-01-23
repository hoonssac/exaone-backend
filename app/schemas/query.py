"""
쿼리 API 요청/응답 스키마

쿼리 처리 API의 입출력 데이터 구조를 정의합니다.
"""

from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime


class QueryRequest(BaseModel):
    """
    쿼리 API 요청 스키마

    자연어 질문을 SQL로 변환하여 제조 데이터를 조회하는 요청입니다.
    """
    message: str = Field(
        ...,
        description="자연어 질문 (예: '오늘 생산량은?')",
        example="오늘 생산량은?"
    )
    context_tag: Optional[str] = Field(
        None,
        description="컨텍스트 태그 (@현장, @회의실, @일반 등)",
        example="@현장"
    )
    thread_id: Optional[int] = Field(
        None,
        description="기존 대화 쓰레드 ID (없으면 새로운 쓰레드 생성)",
        example=1
    )

    class Config:
        json_schema_extra = {
            "example": {
                "message": "오늘 라인별 생산량은?",
                "context_tag": "@현장",
                "thread_id": None
            }
        }


class QueryResultData(BaseModel):
    """
    쿼리 실행 결과
    """
    columns: List[str] = Field(
        ...,
        description="조회된 컬럼명 목록",
        example=["line_id", "total_production"]
    )
    rows: List[Dict[str, Any]] = Field(
        ...,
        description="조회된 데이터 행",
        example=[
            {"line_id": "LINE-01", "total_production": 7900},
            {"line_id": "LINE-02", "total_production": 6295}
        ]
    )
    row_count: int = Field(
        ...,
        description="반환된 행의 개수",
        example=2
    )

    class Config:
        json_schema_extra = {
            "example": {
                "columns": ["line_id", "total_production"],
                "rows": [
                    {"line_id": "LINE-01", "total_production": 7900},
                    {"line_id": "LINE-02", "total_production": 6295}
                ],
                "row_count": 2
            }
        }


class QueryResponse(BaseModel):
    """
    쿼리 API 응답 스키마

    자연어를 SQL로 변환하고 실행한 결과를 반환합니다.
    """
    thread_id: int = Field(
        ...,
        description="대화 쓰레드 ID",
        example=1
    )
    message_id: int = Field(
        ...,
        description="메시지 ID",
        example=1
    )
    original_message: str = Field(
        ...,
        description="사용자가 입력한 원본 질문",
        example="오늘 생산량은?"
    )
    corrected_message: str = Field(
        ...,
        description="용어 사전으로 보정된 질문",
        example="CURDATE() 생산량은?"
    )
    generated_sql: str = Field(
        ...,
        description="생성된 SQL 쿼리",
        example="SELECT SUM(actual_quantity) as total FROM production_data WHERE production_date = CURDATE() LIMIT 100;"
    )
    result_data: QueryResultData = Field(
        ...,
        description="SQL 실행 결과"
    )
    execution_time: float = Field(
        ...,
        description="쿼리 실행 시간 (밀리초)",
        example=45.2
    )
    natural_response: str = Field(
        ...,
        description="ChatGPT가 생성한 자연어 응답",
        example="오늘 총 생산량은 15,280개입니다."
    )
    created_at: datetime = Field(
        ...,
        description="응답 생성 시간",
        example="2026-01-14T10:30:00"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "thread_id": 1,
                "message_id": 1,
                "original_message": "오늘 생산량은?",
                "corrected_message": "CURDATE() 생산량은?",
                "generated_sql": "SELECT SUM(actual_quantity) as total FROM production_data WHERE production_date = CURDATE() LIMIT 100;",
                "result_data": {
                    "columns": ["total"],
                    "rows": [{"total": 15280}],
                    "row_count": 1
                },
                "execution_time": 45.2,
                "natural_response": "오늘 총 생산량은 15,280개입니다.",
                "created_at": "2026-01-14T10:30:00"
            }
        }


class ChatThreadResponse(BaseModel):
    """
    대화 쓰레드 응답

    사용자의 대화 쓰레드 조회 시 반환됩니다.
    """
    id: int = Field(
        ...,
        description="쓰레드 ID",
        example=1
    )
    title: str = Field(
        ...,
        description="쓰레드 제목",
        example="오늘 생산량 조회"
    )
    message_count: int = Field(
        ...,
        description="쓰레드의 메시지 개수",
        example=5
    )
    created_at: datetime = Field(
        ...,
        description="쓰레드 생성 시간",
        example="2026-01-14T10:30:00"
    )
    updated_at: Optional[datetime] = Field(
        None,
        description="쓰레드 마지막 업데이트 시간",
        example="2026-01-14T11:45:00"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "id": 1,
                "title": "오늘 생산량 조회",
                "message_count": 5,
                "created_at": "2026-01-14T10:30:00",
                "updated_at": "2026-01-14T11:45:00"
            }
        }


class ChatMessageResponse(BaseModel):
    """
    대화 메시지 응답

    쓰레드의 메시지 조회 시 반환됩니다.
    """
    id: int = Field(
        ...,
        description="메시지 ID",
        example=1
    )
    thread_id: int = Field(
        ...,
        description="쓰레드 ID",
        example=1
    )
    role: str = Field(
        ...,
        description="메시지 역할 (user/assistant)",
        example="user"
    )
    message: str = Field(
        ...,
        description="메시지 내용",
        example="오늘 생산량은?"
    )
    corrected_msg: Optional[str] = Field(
        None,
        description="보정된 메시지 (assistant 메시지일 때)",
        example="CURDATE() 생산량은?"
    )
    gen_sql: Optional[str] = Field(
        None,
        description="생성된 SQL (assistant 메시지일 때)",
        example="SELECT SUM(actual_quantity) as total FROM production_data WHERE production_date = CURDATE() LIMIT 100;"
    )
    result_data: Optional[Dict[str, Any]] = Field(
        None,
        description="SQL 실행 결과 (assistant 메시지일 때)",
        example={
            "columns": ["total"],
            "rows": [{"total": 15280}],
            "row_count": 1
        }
    )
    context_tag: Optional[str] = Field(
        None,
        description="컨텍스트 태그",
        example="@현장"
    )
    created_at: datetime = Field(
        ...,
        description="메시지 생성 시간",
        example="2026-01-14T10:30:00"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "id": 1,
                "thread_id": 1,
                "role": "user",
                "message": "오늘 생산량은?",
                "corrected_msg": "CURDATE() 생산량은?",
                "gen_sql": "SELECT SUM(actual_quantity) as total FROM production_data WHERE production_date = CURDATE() LIMIT 100;",
                "result_data": {
                    "columns": ["total"],
                    "rows": [{"total": 15280}],
                    "row_count": 1
                },
                "context_tag": "@현장",
                "created_at": "2026-01-14T10:30:00"
            }
        }


class QueryErrorResponse(BaseModel):
    """
    쿼리 API 에러 응답
    """
    error_code: str = Field(
        ...,
        description="에러 코드",
        example="SQL_VALIDATION_FAILED"
    )
    message: str = Field(
        ...,
        description="에러 메시지",
        example="쿼리 검증에 실패했습니다"
    )
    details: Optional[str] = Field(
        None,
        description="추가 상세 정보",
        example="허용되지 않는 키워드: DELETE"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "error_code": "SQL_VALIDATION_FAILED",
                "message": "쿼리 검증에 실패했습니다",
                "details": "허용되지 않는 키워드: DELETE"
            }
        }


class TTSRequest(BaseModel):
    """
    TTS (Text-to-Speech) API 요청 스키마

    텍스트를 음성(WAV 파일)으로 변환하는 요청입니다.
    """
    text: str = Field(
        ...,
        description="변환할 텍스트 (최대 500자)",
        example="오늘 총 생산량은 15,280개입니다.",
        max_length=500,
        min_length=1
    )
    language: str = Field(
        default="ko",
        description="언어 코드 (ko, en, es, pt, fr)",
        example="ko"
    )
    speaker: Optional[str] = Field(
        None,
        description="화자 코드 (M1-M5: 남성, F1-F5: 여성), 기본값은 M1",
        example="M1"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "text": "오늘 총 생산량은 15,280개입니다.",
                "language": "ko",
                "speaker": "M1"
            }
        }


class TTSResponse(BaseModel):
    """
    TTS API 응답 스키마

    WAV 파일 바이너리와 메타데이터를 반환합니다.
    실제 응답은 audio/wav Content-Type으로 바이너리 스트림입니다.
    """
    text: str = Field(
        ...,
        description="변환된 텍스트",
        example="오늘 총 생산량은 15,280개입니다."
    )
    language: str = Field(
        ...,
        description="사용된 언어",
        example="ko"
    )
    speaker: str = Field(
        ...,
        description="사용된 화자",
        example="M1"
    )
    audio_size_bytes: int = Field(
        ...,
        description="생성된 WAV 파일 크기 (바이트)",
        example=96000
    )
    execution_time: float = Field(
        ...,
        description="TTS 변환 실행 시간 (초)",
        example=0.5
    )

    class Config:
        json_schema_extra = {
            "example": {
                "text": "오늘 총 생산량은 15,280개입니다.",
                "language": "ko",
                "speaker": "M1",
                "audio_size_bytes": 96000,
                "execution_time": 0.5
            }
        }
