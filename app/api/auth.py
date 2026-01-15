"""
인증 API 라우트
"""
from fastapi import APIRouter, Depends, HTTPException, status, Header
from sqlalchemy.orm import Session
from typing import Optional

from app.db.database import get_postgres_db
from app.schemas.auth import (
    LoginRequest,
    LoginResponse,
    SignupRequest,
    ChangePasswordRequest,
    UserResponse,
    ErrorResponse,
)
from app.service.auth_service import AuthService
from app.config.security import verify_token

router = APIRouter(prefix="/api/v1/auth", tags=["Authentication"])


def get_current_user_id(authorization: Optional[str] = Header(None)) -> int:
    """
    현재 사용자 ID 추출
    Authorization 헤더에서 Bearer 토큰을 받아 사용자 ID를 반환
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
    "/login",
    response_model=LoginResponse,
    responses={
        401: {"model": ErrorResponse, "description": "이메일 또는 비밀번호 오류"},
        400: {"model": ErrorResponse, "description": "요청 데이터 오류"},
    },
)
async def login(
    request: LoginRequest,
    db: Session = Depends(get_postgres_db),
):
    """
    사용자 로그인

    - **email**: 사용자 이메일
    - **password**: 사용자 비밀번호

    반환:
    - access_token: JWT 액세스 토큰
    - refresh_token: JWT 리프레시 토큰
    - user: 사용자 정보
    """
    try:
        response = AuthService.login(db, request)
        return response
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
        )
    except Exception as e:
        print(f"❌ 로그인 오류: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="로그인 중 오류가 발생했습니다",
        )


@router.post(
    "/signup",
    response_model=LoginResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        409: {"model": ErrorResponse, "description": "이메일 또는 사원ID 중복"},
        400: {"model": ErrorResponse, "description": "요청 데이터 오류"},
    },
)
async def signup(
    request: SignupRequest,
    db: Session = Depends(get_postgres_db),
):
    """
    새로운 사용자 회원가입

    - **email**: 사용자 이메일 (유니크)
    - **password**: 비밀번호 (영문+숫자+특수문자 8자 이상)
    - **name**: 사용자 이름
    - **employee_id**: 사원ID (8자리 숫자, 유니크)
    - **dept_name**: 부서명
    - **position**: 직급

    반환:
    - access_token: JWT 액세스 토큰
    - refresh_token: JWT 리프레시 토큰
    - user: 사용자 정보
    """
    try:
        response = AuthService.signup(db, request)
        return response
    except ValueError as e:
        error_msg = str(e)
        # 이메일 중복 또는 사원ID 중복의 경우 409 Conflict
        if "이미 존재하는" in error_msg:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=error_msg,
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=error_msg,
            )
    except Exception as e:
        print(f"❌ 회원가입 오류: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="회원가입 중 오류가 발생했습니다",
        )


@router.post(
    "/change-password",
    response_model=dict,
    responses={
        401: {"model": ErrorResponse, "description": "인증 오류"},
        400: {"model": ErrorResponse, "description": "비밀번호 오류"},
    },
)
async def change_password(
    request: ChangePasswordRequest,
    db: Session = Depends(get_postgres_db),
    user_id: int = Depends(get_current_user_id),
):
    """
    사용자 비밀번호 변경

    Header:
    - **Authorization**: "Bearer <access_token>"

    Body:
    - **current_password**: 현재 비밀번호
    - **new_password**: 새로운 비밀번호 (영문+숫자+특수문자 8자 이상)

    반환:
    - message: 성공 메시지
    """
    try:
        # 비밀번호 변경
        response = AuthService.change_password(db, user_id, request)
        return response
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        print(f"❌ 비밀번호 변경 오류: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="비밀번호 변경 중 오류가 발생했습니다",
        )


@router.get(
    "/me",
    response_model=UserResponse,
    responses={
        401: {"model": ErrorResponse, "description": "인증 오류"},
    },
)
async def get_me(
    db: Session = Depends(get_postgres_db),
    user_id: int = Depends(get_current_user_id),
):
    """
    현재 사용자 정보 조회

    Header:
    - **Authorization**: "Bearer <access_token>"

    반환:
    - 현재 사용자 정보
    """
    try:
        user_info = AuthService.get_current_user(db, user_id)
        return user_info
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    except Exception as e:
        print(f"❌ 사용자 정보 조회 오류: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="사용자 정보 조회 중 오류가 발생했습니다",
        )
