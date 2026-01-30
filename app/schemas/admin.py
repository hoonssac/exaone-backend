"""
관리자(Admin) API 응답 스키마
"""

from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


class FilterableFieldBase(BaseModel):
    """FilterableField 기본 정보"""
    field_name: str = Field(..., description="필터 필드명 (예: machine_id)")
    display_name: str = Field(..., description="화면에 표시할 이름 (예: 사출기)")
    description: Optional[str] = Field(None, description="필드 설명")
    field_type: str = Field(..., description="필드 타입 (numeric, date, string 등)")
    extraction_pattern: Optional[str] = Field(None, description="정규표현식 패턴")
    extraction_keywords: List[str] = Field(default_factory=list, description="추출 키워드 목록")
    value_mapping: Optional[Dict[str, str]] = Field(default=None, description="키워드→값 매핑")
    is_optional: bool = Field(default=True, description="선택적 필터 여부")
    multiple_allowed: bool = Field(default=False, description="다중값 허용 여부")
    valid_values: Optional[List[Any]] = Field(default=None, description="유효한 값 목록 (예: ['1', '2', '3'])")
    validation_type: str = Field(default="none", description="검증 타입 (none, exact, range)")


class FilterableFieldCreate(FilterableFieldBase):
    """FilterableField 생성 요청"""
    pass


class FilterableFieldUpdate(BaseModel):
    """FilterableField 업데이트 요청"""
    display_name: Optional[str] = None
    description: Optional[str] = None
    field_type: Optional[str] = None
    extraction_pattern: Optional[str] = None
    extraction_keywords: Optional[List[str]] = None
    value_mapping: Optional[Dict[str, str]] = None
    is_optional: Optional[bool] = None
    multiple_allowed: Optional[bool] = None
    valid_values: Optional[List[Any]] = None
    validation_type: Optional[str] = None


class FilterableFieldResponse(FilterableFieldBase):
    """FilterableField 응답"""
    id: int = Field(..., description="필터 ID")

    class Config:
        from_attributes = True


class FilterableFieldListResponse(BaseModel):
    """FilterableField 목록 응답"""
    total: int = Field(..., description="전체 필터 개수")
    filters: List[FilterableFieldResponse] = Field(..., description="필터 목록")

    class Config:
        from_attributes = True


class FilterableFieldDetailResponse(FilterableFieldResponse):
    """FilterableField 상세 응답"""
    created_at: Optional[str] = Field(None, description="생성 시간")
    updated_at: Optional[str] = Field(None, description="수정 시간")


class AdminMessage(BaseModel):
    """관리자 메시지 응답"""
    message: str
    status: str = Field(default="success", description="success, error, warning")


class AdminError(BaseModel):
    """관리자 에러 응답"""
    message: str
    detail: Optional[str] = None
    status: str = Field(default="error", description="error")
