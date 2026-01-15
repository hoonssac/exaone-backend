"""
인증 비즈니스 로직
"""
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from app.models.user import User
from app.config.security import (
    hash_password,
    verify_password,
    create_access_token,
    create_refresh_token,
)
from app.schemas.auth import (
    LoginRequest,
    SignupRequest,
    LoginResponse,
    UserResponse,
    ChangePasswordRequest,
)


class AuthService:
    """인증 서비스"""

    @staticmethod
    def login(db: Session, request: LoginRequest) -> LoginResponse:
        """
        사용자 로그인

        Args:
            db: PostgreSQL 데이터베이스 세션
            request: 로그인 요청

        Returns:
            LoginResponse: 액세스 토큰, 리프레시 토큰, 사용자 정보

        Raises:
            ValueError: 이메일이 없거나 비밀번호가 잘못된 경우
        """
        # 이메일로 사용자 조회
        user = db.query(User).filter(User.email == request.email).first()

        if not user:
            raise ValueError("이메일 또는 비밀번호가 잘못되었습니다")

        # 비밀번호 검증
        if not verify_password(request.password, user.password):
            raise ValueError("이메일 또는 비밀번호가 잘못되었습니다")

        if not user.is_active:
            raise ValueError("비활성화된 계정입니다")

        # 토큰 생성
        access_token = create_access_token({"sub": user.email, "id": user.id})
        refresh_token = create_refresh_token({"sub": user.email, "id": user.id})

        user_response = UserResponse.model_validate(user)

        return LoginResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            user=user_response,
        )

    @staticmethod
    def signup(db: Session, request: SignupRequest) -> LoginResponse:
        """
        새로운 사용자 생성

        Args:
            db: PostgreSQL 데이터베이스 세션
            request: 회원가입 요청

        Returns:
            LoginResponse: 액세스 토큰, 리프레시 토큰, 사용자 정보

        Raises:
            ValueError: 이메일 또는 사원ID가 이미 존재하는 경우
        """
        try:
            # 해시된 비밀번호 생성
            hashed_password = hash_password(request.password)

            # 새로운 사용자 생성
            user = User(
                email=request.email,
                password=hashed_password,
                name=request.name,
                employee_id=request.employee_id,
                dept_name=request.dept_name,
                position=request.position,
                is_active=True,
            )

            db.add(user)
            db.commit()
            db.refresh(user)

        except IntegrityError as e:
            db.rollback()
            if "email" in str(e):
                raise ValueError("이미 존재하는 이메일입니다")
            elif "employee_id" in str(e):
                raise ValueError("이미 존재하는 사원ID입니다")
            else:
                raise ValueError("회원가입 중 오류가 발생했습니다")
        except Exception as e:
            db.rollback()
            raise ValueError(f"회원가입 중 오류가 발생했습니다: {str(e)}")

        # 토큰 생성
        access_token = create_access_token({"sub": user.email, "id": user.id})
        refresh_token = create_refresh_token({"sub": user.email, "id": user.id})

        user_response = UserResponse.model_validate(user)

        return LoginResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            user=user_response,
        )

    @staticmethod
    def change_password(
        db: Session, user_id: int, request: ChangePasswordRequest
    ) -> dict:
        """
        사용자 비밀번호 변경

        Args:
            db: PostgreSQL 데이터베이스 세션
            user_id: 사용자 ID
            request: 비밀번호 변경 요청

        Returns:
            dict: 성공 메시지

        Raises:
            ValueError: 사용자를 찾을 수 없거나 현재 비밀번호가 잘못된 경우
        """
        # 사용자 조회
        user = db.query(User).filter(User.id == user_id).first()

        if not user:
            raise ValueError("사용자를 찾을 수 없습니다")

        # 현재 비밀번호 검증
        if not verify_password(request.current_password, user.password):
            raise ValueError("현재 비밀번호가 잘못되었습니다")

        # 새로운 비밀번호와 현재 비밀번호가 같은지 확인
        if verify_password(request.new_password, user.password):
            raise ValueError("새로운 비밀번호는 현재 비밀번호와 달라야 합니다")

        # 비밀번호 업데이트
        try:
            user.password = hash_password(request.new_password)
            db.commit()
            return {"message": "비밀번호가 변경되었습니다"}
        except Exception as e:
            db.rollback()
            raise ValueError(f"비밀번호 변경 중 오류가 발생했습니다: {str(e)}")

    @staticmethod
    def get_current_user(db: Session, user_id: int) -> UserResponse:
        """
        현재 사용자 정보 조회

        Args:
            db: PostgreSQL 데이터베이스 세션
            user_id: 사용자 ID

        Returns:
            UserResponse: 사용자 정보

        Raises:
            ValueError: 사용자를 찾을 수 없는 경우
        """
        user = db.query(User).filter(User.id == user_id).first()

        if not user:
            raise ValueError("사용자를 찾을 수 없습니다")

        return UserResponse.model_validate(user)
