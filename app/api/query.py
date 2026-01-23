"""
쿼리 처리 API 라우트

자연어 질문을 SQL로 변환하고 제조 데이터를 조회하는 API입니다.

엔드포인트:
- POST /api/v1/query: 질문 처리
- GET /api/v1/query/threads: 사용자의 모든 쓰레드 조회
- GET /api/v1/query/threads/{thread_id}/messages: 특정 쓰레드의 메시지 조회
"""

from fastapi import APIRouter, Depends, HTTPException, status, Header, UploadFile, File
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from typing import Optional, List
import time
import io

from app.db.database import get_postgres_db, get_mysql_db
from app.schemas.query import (
    QueryRequest,
    QueryResponse,
    ChatThreadResponse,
    ChatMessageResponse,
    QueryErrorResponse,
    TTSRequest,
    TTSResponse,
)
from app.service.query_service import QueryService
from app.service.clova_speech_service import ClovaSpeechService
from app.service.supertonic_service import SupertonicService
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
        "message": "어제 불량유형별 불량은?",
        "context_tag": "@현장",
        "thread_id": null
    }
    ```

    ### 응답 예시

    ```json
    {
        "thread_id": 1,
        "message_id": 1,
        "original_message": "어제 불량유형별 불량은?",
        "corrected_message": "DATE_SUB(CURDATE(), INTERVAL 1 DAY) 불량유형별 불량은?",
        "generated_sql": "SELECT defect_type_id, COUNT(*) as count FROM injection_cycle WHERE cycle_date = DATE_SUB(CURDATE(), INTERVAL 1 DAY) AND has_defect = 1 GROUP BY defect_type_id LIMIT 100;",
        "result_data": {
            "columns": ["defect_type_id", "count"],
            "rows": [
                {"defect_type_id": 1, "count": 45},
                {"defect_type_id": 3, "count": 28}
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
            "message": "사출 사이클 데이터 조회 결과",
            "corrected_msg": "CURDATE() 생산량은?",
            "gen_sql": "SELECT COUNT(*) as total_cycles FROM injection_cycle WHERE cycle_date = CURDATE() LIMIT 100;",
            "result_data": {
                "columns": ["total_cycles"],
                "rows": [{"total_cycles": 1603}],
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


@router.post(
    "/voice",
    response_model=QueryResponse,
    responses={
        400: {"model": QueryErrorResponse, "description": "잘못된 요청"},
        401: {"model": QueryErrorResponse, "description": "인증 오류"},
        500: {"model": QueryErrorResponse, "description": "서버 오류"},
    },
)
async def process_voice_query(
    file: UploadFile = File(...),
    context_tag: Optional[str] = None,
    thread_id: Optional[int] = None,
    language: str = "Kor",
    db_postgres: Session = Depends(get_postgres_db),
    db_mysql: Session = Depends(get_mysql_db),
    user_id: int = Depends(get_current_user_id),
):
    """
    음성 질문을 텍스트로 변환 후 처리

    Naver Clova Speech를 사용하여 음성 파일을 텍스트로 변환하고,
    일반 텍스트 쿼리와 동일하게 처리합니다.

    ### 요청

    **multipart/form-data로 전송**

    - **file** (필수): 음성 파일 (MP3, AAC, AC3, OGG, FLAC, WAV)
    - **language** (선택): 언어 코드 (Kor, Eng, Jpn, Chn) - 기본값: Kor
    - **context_tag** (선택): 컨텍스트 태그 (@현장, @회의실, @일반 등)
    - **thread_id** (선택): 기존 쓰레드 ID (없으면 새 쓰레드 생성)

    ### 응답

    일반 쿼리 API와 동일한 QueryResponse를 반환합니다.

    ```json
    {
        "thread_id": 1,
        "message_id": 1,
        "original_message": "오늘 생산량은?",
        "corrected_message": "CURDATE() 생산량은?",
        "generated_sql": "SELECT COUNT(*) as total_cycles FROM injection_cycle WHERE cycle_date = CURDATE() LIMIT 100;",
        "result_data": {...},
        "execution_time": 45.2,
        "natural_response": "오늘 총 생산 사이클은 1,603개입니다.",
        "created_at": "2026-01-21T10:30:00"
    }
    ```

    ### 인증

    요청 헤더에 Bearer 토큰을 포함해야 합니다:
    ```
    Authorization: Bearer <access_token>
    ```

    ### 지원 언어

    - **Kor**: 한국어 (기본값)
    - **Eng**: 영어
    - **Jpn**: 일본어
    - **Chn**: 중국어(간체)

    ### 지원 오디오 포맷

    - MP3, AAC, AC3, OGG, FLAC, WAV (최대 60초, ~200KB)

    ### 처리 흐름

    1. **음성 파일 검증**: 포맷, 크기 확인
    2. **STT (Speech-to-Text)**: Naver Clova Speech로 음성 → 텍스트 변환
    3. **쿼리 처리**: 일반 쿼리 API와 동일하게 처리
    4. **결과 반환**: SQL 실행 결과 및 자연어 응답 반환

    ### 에러 처리

    - `400 Bad Request`: 오디오 파일 검증 실패, STT 변환 실패
    - `401 Unauthorized`: 인증 실패 또는 토큰 만료
    - `500 Internal Server Error`: 서버 오류
    """
    try:
        # 1. 음성 파일 읽기
        audio_data = await file.read()

        print(f"🎤 음성 파일 처리 시작: {file.filename} ({len(audio_data)} bytes)")

        # 2. 음성 파일 검증
        try:
            ClovaSpeechService.validate_audio_file(audio_data, file.filename)
            print(f"✅ 음성 파일 검증 완료")
        except ValueError as e:
            print(f"❌ 음성 파일 검증 실패: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"음성 파일 검증 실패: {str(e)}",
            )

        # 3. STT: 음성 → 텍스트 변환
        try:
            recognized_text = ClovaSpeechService.recognize_speech(
                audio_data=audio_data,
                language=language,
                audio_format=file.filename.split(".")[-1].lower()
            )

            if not recognized_text:
                print(f"❌ STT 변환 결과 없음")
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="음성에서 텍스트를 인식하지 못했습니다",
                )

            print(f"✅ STT 변환 완료: '{recognized_text}'")

        except Exception as e:
            print(f"❌ STT 변환 오류: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"음성 인식 중 오류가 발생했습니다: {str(e)}",
            )

        # 4. 쿼리 처리 (일반 텍스트 쿼리와 동일)
        query_request = QueryRequest(
            message=recognized_text,
            context_tag=context_tag,
            thread_id=thread_id
        )

        response = QueryService.process_query(
            db_postgres,
            db_mysql,
            user_id,
            query_request
        )

        print(f"✅ 음성 쿼리 처리 완료")

        return response

    except HTTPException:
        # HTTPException은 그대로 던지기
        raise

    except ValueError as e:
        error_msg = str(e)
        print(f"❌ 입력 검증 오류: {error_msg}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error_msg,
        )

    except Exception as e:
        print(f"❌ 음성 쿼리 처리 오류: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="음성 쿼리 처리 중 오류가 발생했습니다",
        )


@router.delete(
    "/threads/{thread_id}",
    responses={
        200: {
            "description": "쓰레드 삭제 성공",
        },
        401: {"model": QueryErrorResponse, "description": "인증 오류"},
        403: {"model": QueryErrorResponse, "description": "권한 없음"},
        404: {"model": QueryErrorResponse, "description": "쓰레드 없음"},
        500: {"model": QueryErrorResponse, "description": "서버 오류"},
    },
)
async def delete_thread(
    thread_id: int,
    db: Session = Depends(get_postgres_db),
    user_id: int = Depends(get_current_user_id),
):
    """
    특정 대화 쓰레드 삭제 (Soft Delete)

    지정된 쓰레드와 해당 쓰레드의 모든 메시지를 삭제합니다.
    (물리적 삭제가 아닌 soft delete로 구현되어 나중에 복구 가능)

    ### 경로 매개변수

    - **thread_id**: 삭제할 쓰레드 ID

    ### 응답

    ```json
    {
        "thread_id": 1,
        "deleted_messages_count": 5,
        "deleted_at": "2026-01-22T10:30:00+00:00"
    }
    ```

    ### 인증

    요청 헤더에 Bearer 토큰을 포함해야 합니다:
    ```
    Authorization: Bearer <access_token>
    ```

    ### 권한

    사용자는 자신의 쓰레드만 삭제할 수 있습니다.

    ### 에러 처리

    - `401 Unauthorized`: 인증 실패 또는 토큰 만료
    - `403 Forbidden`: 삭제 권한 없음
    - `404 Not Found`: 쓰레드 없음 또는 이미 삭제됨
    - `500 Internal Server Error`: 서버 오류
    """
    try:
        result = QueryService.delete_thread(db, thread_id, user_id)

        print(f"✅ 쓰레드 삭제 완료: {result}")

        return result

    except ValueError as e:
        error_msg = str(e)
        print(f"❌ 쓰레드 삭제 오류: {error_msg}")

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
        print(f"❌ 쓰레드 삭제 오류: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="쓰레드 삭제 중 오류가 발생했습니다",
        )


@router.post(
    "/tts",
    responses={
        200: {
            "content": {"audio/wav": {}},
            "description": "WAV 파일 (오디오)",
        },
        400: {"model": QueryErrorResponse, "description": "검증 실패"},
        401: {"model": QueryErrorResponse, "description": "인증 오류"},
        500: {"model": QueryErrorResponse, "description": "서버 오류"},
    },
)
async def text_to_speech(
    request: TTSRequest,
    user_id: int = Depends(get_current_user_id),
):
    """
    텍스트를 음성(WAV 파일)으로 변환

    Supertonic TTS를 사용하여 텍스트를 고품질의 음성으로 변환합니다.

    ### 요청

    ```json
    {
        "text": "오늘 총 생산량은 15,280개입니다.",
        "language": "ko",
        "speaker": "M1"
    }
    ```

    ### 응답

    - Content-Type: `audio/wav`
    - 바이너리 WAV 파일 데이터
    - 헤더에 메타데이터 포함:
      - `X-Execution-Time`: 실행 시간 (초)
      - `X-Audio-Size`: 오디오 파일 크기 (바이트)
      - `X-Language`: 사용된 언어
      - `X-Speaker`: 사용된 화자

    ### 인증

    요청 헤더에 Bearer 토큰을 포함해야 합니다:
    ```
    Authorization: Bearer <access_token>
    ```

    ### 지원 언어

    - **ko**: 한국어 (기본값)
    - **en**: 영어
    - **es**: 스페인어
    - **pt**: 포르투갈어
    - **fr**: 프랑스어

    ### 지원 화자

    - **M1-M5**: 남성 화자
    - **F1-F5**: 여성 화자
    - 기본값: M1

    ### 제약사항

    - 최대 텍스트 길이: 500자
    - 응답 시간: 일반적으로 0.5-2초

    ### 에러 처리

    - `400 Bad Request`: 입력 검증 실패 (빈 텍스트, 너무 긴 텍스트, 잘못된 언어)
    - `401 Unauthorized`: 인증 실패 또는 토큰 만료
    - `500 Internal Server Error`: TTS 변환 오류
    """
    try:
        start_time = time.time()

        # 입력 검증
        try:
            SupertonicService.validate_text(request.text)
            print(f"🎤 TTS 요청: '{request.text[:50]}...' (언어: {request.language}, 화자: {request.speaker})")
        except ValueError as e:
            print(f"❌ 입력 검증 실패: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"입력 검증 실패: {str(e)}",
            )

        # TTS 변환
        try:
            audio_bytes = SupertonicService.text_to_speech(
                text=request.text,
                language=request.language,
                speaker=request.speaker
            )

            execution_time = time.time() - start_time
            print(f"✅ TTS 변환 완료 (실행 시간: {execution_time:.2f}초, 파일 크기: {len(audio_bytes)} bytes)")

        except ValueError as e:
            print(f"❌ TTS 검증 오류: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"TTS 변환 검증 실패: {str(e)}",
            )
        except Exception as e:
            print(f"❌ TTS 변환 오류: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"텍스트 음성 변환 중 오류가 발생했습니다: {str(e)}",
            )

        # WAV 파일을 스트리밍으로 반환
        audio_stream = io.BytesIO(audio_bytes)

        return StreamingResponse(
            iter([audio_bytes]),
            media_type="audio/wav",
            headers={
                "Content-Disposition": f'attachment; filename="tts_{int(time.time())}.wav"',
                "X-Execution-Time": str(execution_time),
                "X-Audio-Size": str(len(audio_bytes)),
                "X-Language": request.language,
                "X-Speaker": request.speaker or SupertonicService.DEFAULT_SPEAKER,
            }
        )

    except HTTPException:
        # HTTPException은 그대로 던지기
        raise

    except Exception as e:
        print(f"❌ TTS 처리 오류: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="TTS 처리 중 오류가 발생했습니다",
        )
