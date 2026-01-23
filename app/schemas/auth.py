"""
인증 관련 요청/응답 스키마
"""
from pydantic import BaseModel, EmailStr, field_validator
from typing import Optional


class LoginRequest(BaseModel):
    """로그인 요청"""
    email: EmailStr
    password: str

    class Config:
        json_schema_extra = {
            "example": {
                "email": "user@example.com",
                "password": "Password123!"
            }
        }


class UserResponse(BaseModel):
    """사용자 정보 응답"""
    id: int
    email: str
    name: str
    employee_id: str
    dept_name: str
    position: str

    class Config:
        from_attributes = True


class LoginResponse(BaseModel):
    """로그인 응답"""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: UserResponse

    class Config:
        json_schema_extra = {
            "example": {
                "access_token": "eyJhbGciOiJIUzI1NiIs...",
                "refresh_token": "eyJhbGciOiJIUzI1NiIs...",
                "token_type": "bearer",
                "user": {
                    "id": 1,
                    "email": "user@example.com",
                    "name": "John Doe",
                    "employee_id": "12345678",
                    "dept_name": "제조",
                    "position": "과장"
                }
            }
        }


class SignupRequest(BaseModel):
    """회원가입 요청"""
    email: EmailStr
    password: str
    name: str
    employee_id: str
    dept_name: str
    position: str

    @field_validator('password')
    @classmethod
    def validate_password(cls, v):
        """비밀번호 유효성 검증: 영문+숫자 8자 이상 (특수문자 선택)"""
        if len(v) < 8:
            raise ValueError('비밀번호는 최소 8자 이상이어야 합니다')

        has_letter = any(c.isalpha() for c in v)
        has_digit = any(c.isdigit() for c in v)

        if not (has_letter and has_digit):
            raise ValueError('비밀번호는 영문과 숫자를 포함해야 합니다')

        return v

    @field_validator('employee_id')
    @classmethod
    def validate_employee_id(cls, v):
        """사원ID 유효성 검증: 8자리 숫자"""
        if not v.isdigit() or len(v) != 8:
            raise ValueError('사원ID는 8자리 숫자여야 합니다')
        return v

    class Config:
        json_schema_extra = {
            "example": {
                "email": "newuser@example.com",
                "password": "NewPass123!",
                "name": "Jane Doe",
                "employee_id": "12345678",
                "dept_name": "제조",
                "position": "대리"
            }
        }


class ChangePasswordRequest(BaseModel):
    """비밀번호 변경 요청"""
    current_password: str
    new_password: str

    @field_validator('new_password')
    @classmethod
    def validate_password(cls, v):
        """비밀번호 유효성 검증: 영문+숫자 8자 이상 (특수문자 선택)"""
        if len(v) < 8:
            raise ValueError('비밀번호는 최소 8자 이상이어야 합니다')

        has_letter = any(c.isalpha() for c in v)
        has_digit = any(c.isdigit() for c in v)

        if not (has_letter and has_digit):
            raise ValueError('비밀번호는 영문과 숫자를 포함해야 합니다')

        return v

    class Config:
        json_schema_extra = {
            "example": {
                "current_password": "OldPass123!",
                "new_password": "NewPass456!"
            }
        }


class ErrorResponse(BaseModel):
    """에러 응답"""
    detail: str
    status_code: int

    class Config:
        json_schema_extra = {
            "example": {
                "detail": "이메일 또는 비밀번호가 잘못되었습니다",
                "status_code": 401
            }
        }
