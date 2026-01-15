"""
쿼리 처리 API 라우트

자연어 질문을 SQL로 변환하고 제조 데이터를 조회하는 API입니다.

엔드포인트:
- POST /api/v1/query: 질문 처리
- GET /api/v1/query/threads: 사용자의 모든 쓰레드 조회
- GET /api/v1/query/threads/{thread_id}/messages: 특정 쓰레드의 메시지 조회
"""

from fastapi import APIRouter, Depends, HTTPException, status, Header
from sqlalchemy.orm import Session
from typing import Optional, List

from app.db.database import get_postgres_db, get_mysql_db
from app.schemas.query import (
    QueryRequest,
    QueryResponse,
    ChatThreadResponse,
    ChatMessageResponse,
    QueryErrorResponse,
)
from app.service.query_service import QueryService
from app.config.security import verify_token

router = APIRouter(prefix="/api/v1/query", tags=["Query"])


def get_current_user_id(authorization: Optional[str] = Header(None)) -> int:
    """
    현재 사용자 ID 추출

    Authorization 헤더에서 Bearer 토큰을 받아 사용자 ID를 반환합니다.
    """
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="인증 토큰이 없습니다",
        )

    # "Bearer <token>" 형식에서 토큰 추출
    if authorization.startswith("Bearer "):
        token = authorization[7:]
    else:
        token = authorization

    payload = verify_token(token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="유효하지 않은 토큰입니다",
        )

    user_id = payload.get("id")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="토큰에서 사용자 정보를 찾을 수 없습니다",
        )

    return user_id


@router.post(
    "/",
    response_model=QueryResponse,
    responses={
        400: {"model": QueryErrorResponse, "description": "검증 실패"},
        401: {"model": QueryErrorResponse, "description": "인증 오류"},
        500: {"model": QueryErrorResponse, "description": "서버 오류"},
    },
)
async def process_query(
    request: QueryRequest,
    db_postgres: Session = Depends(get_postgres_db),
    db_mysql: Session = Depends(get_mysql_db),
    user_id: int = Depends(get_current_user_id),
):
    """
    자연어 질문을 SQL로 변환하고 실행

    이 엔드포인트는 사용자의 자연어 질문을 다음과 같이 처리합니다:

    1. **질문 보정**: 용어 사전을 이용하여 질문의 한글 용어를 표준화합니다
    2. **SQL 생성**: EXAONE AI를 이용하여 자연어를 SQL로 변환합니다
    3. **SQL 검증**: SQL Injection 방지를 위해 엄격하게 검증합니다
    4. **쿼리 실행**: MySQL에서 쿼리를 실행합니다
    5. **결과 저장**: 대화 이력을 PostgreSQL에 저장합니다

    ### 요청 예시

    ```json
    {
        "message": "오늘 라인별 생산량은?",
        "context_tag": "@현장",
        "thread_id": null
    }
    ```

    ### 응답 예시

    ```json
    {
        "thread_id": 1,
        "message_id": 1,
        "original_message": "오늘 라인별 생산량은?",
        "corrected_message": "CURDATE() 라인별 생산량은?",
        "generated_sql": "SELECT line_id, SUM(actual_quantity) as total FROM production_data WHERE production_date = CURDATE() GROUP BY line_id LIMIT 100;",
        "result_data": {
            "columns": ["line_id", "total"],
            "rows": [
                {"line_id": "LINE-01", "total": 7900},
                {"line_id": "LINE-02", "total": 6295}
            ],
            "row_count": 2
        },
        "execution_time": 45.2,
        "created_at": "2026-01-14T10:30:00"
    }
    ```

    ### 인증

    요청 헤더에 Bearer 토큰을 포함해야 합니다:
    ```
    Authorization: Bearer <access_token>
    ```

    ### 매개변수

    - **message** (필수): 자연어 질문
    - **context_tag** (선택): 컨텍스트 태그 (@현장, @회의실, @일반 등)
    - **thread_id** (선택): 기존 쓰레드 ID (없으면 새 쓰레드 생성)

    ### 에러 처리

    - `400 Bad Request`: SQL 검증 실패, 잘못된 요청
    - `401 Unauthorized`: 인증 실패 또는 토큰 만료
    - `500 Internal Server Error`: 서버 오류
    """
    try:
        # 쿼리 처리
        response = QueryService.process_query(
            db_postgres,
            db_mysql,
            user_id,
            request
        )

        return response

    except ValueError as e:
        error_msg = str(e)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error_msg,
        )
    except Exception as e:
        print(f"❌ 쿼리 처리 오류: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="쿼리 처리 중 오류가 발생했습니다",
        )


@router.get(
    "/threads",
    response_model=List[ChatThreadResponse],
    responses={
        401: {"model": QueryErrorResponse, "description": "인증 오류"},
        500: {"model": QueryErrorResponse, "description": "서버 오류"},
    },
)
async def get_user_threads(
    db: Session = Depends(get_postgres_db),
    user_id: int = Depends(get_current_user_id),
):
    """
    사용자의 모든 대화 쓰레드 조회

    현재 로그인한 사용자의 대화 쓰레드 목록을 최신순으로 반환합니다.

    ### 응답 예시

    ```json
    [
        {
            "id": 1,
            "title": "오늘 생산량 조회",
            "message_count": 5,
            "created_at": "2026-01-14T10:30:00",
            "updated_at": "2026-01-14T11:45:00"
        },
        {
            "id": 2,
            "title": "설비 가동 상태 확인",
            "message_count": 3,
            "created_at": "2026-01-13T14:20:00",
            "updated_at": "2026-01-13T15:00:00"
        }
    ]
    ```

    ### 인증

    요청 헤더에 Bearer 토큰을 포함해야 합니다:
    ```
    Authorization: Bearer <access_token>
    ```
    """
    try:
        threads = QueryService.get_user_threads(db, user_id)

        # Response 모델로 변환
        return [ChatThreadResponse(**thread) for thread in threads]

    except Exception as e:
        print(f"❌ 쓰레드 조회 오류: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="쓰레드 조회 중 오류가 발생했습니다",
        )


@router.get(
    "/threads/{thread_id}/messages",
    response_model=List[ChatMessageResponse],
    responses={
        401: {"model": QueryErrorResponse, "description": "인증 오류"},
        403: {"model": QueryErrorResponse, "description": "권한 없음"},
        404: {"model": QueryErrorResponse, "description": "쓰레드 없음"},
        500: {"model": QueryErrorResponse, "description": "서버 오류"},
    },
)
async def get_thread_messages(
    thread_id: int,
    db: Session = Depends(get_postgres_db),
    user_id: int = Depends(get_current_user_id),
):
    """
    특정 대화 쓰레드의 메시지 조회

    지정된 쓰레드의 모든 메시지를 시간순으로 반환합니다.

    ### 경로 매개변수

    - **thread_id**: 조회할 쓰레드 ID

    ### 응답 예시

    ```json
    [
        {
            "id": 1,
            "thread_id": 1,
            "role": "user",
            "message": "오늘 생산량은?",
            "corrected_msg": null,
            "gen_sql": null,
            "result_data": null,
            "context_tag": "@현장",
            "created_at": "2026-01-14T10:30:00"
        },
        {
            "id": 2,
            "thread_id": 1,
            "role": "assistant",
            "message": "생산 데이터 조회 결과 3행 반환",
            "corrected_msg": "CURDATE() 생산량은?",
            "gen_sql": "SELECT SUM(actual_quantity) as total FROM production_data WHERE production_date = CURDATE() LIMIT 100;",
            "result_data": {
                "columns": ["total"],
                "rows": [{"total": 15280}],
                "row_count": 1
            },
            "context_tag": "@현장",
            "created_at": "2026-01-14T10:30:05"
        }
    ]
    ```

    ### 인증

    요청 헤더에 Bearer 토큰을 포함해야 합니다:
    ```
    Authorization: Bearer <access_token>
    ```

    ### 권한

    사용자는 자신의 쓰레드만 조회할 수 있습니다.
    """
    try:
        messages = QueryService.get_thread_messages(db, thread_id, user_id)

        # Response 모델로 변환
        return [ChatMessageResponse(**msg) for msg in messages]

    except ValueError as e:
        error_msg = str(e)
        if "권한" in error_msg:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=error_msg,
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=error_msg,
            )
    except Exception as e:
        print(f"❌ 메시지 조회 오류: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="메시지 조회 중 오류가 발생했습니다",
        )
