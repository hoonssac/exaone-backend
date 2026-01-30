"""
관리자 API 라우트

용어 사전, 도메인 지식, 필드 설명, 필터 규칙을 관리하는 API입니다.

엔드포인트:
- GET /api/v1/admin/terms: 모든 용어 조회
- POST /api/v1/admin/terms: 새 용어 추가
- PUT /api/v1/admin/terms/{id}: 용어 수정
- DELETE /api/v1/admin/terms/{id}: 용어 삭제
- GET /api/v1/admin/knowledge: 모든 도메인 지식 조회
- POST /api/v1/admin/knowledge: 새 지식 추가
- PUT /api/v1/admin/knowledge/{id}: 지식 수정
- DELETE /api/v1/admin/knowledge/{id}: 지식 삭제
- GET /api/v1/admin/schema: 모든 필드 설명 조회
- PUT /api/v1/admin/schema/{id}: 필드 설명 수정
- GET /api/v1/admin/filters: 모든 필터 규칙 조회
- POST /api/v1/admin/filters: 새 필터 규칙 추가
- GET /api/v1/admin/filters/{id}: 특정 필터 규칙 조회
- PUT /api/v1/admin/filters/{id}: 필터 규칙 수정
- DELETE /api/v1/admin/filters/{id}: 필터 규칙 삭제
"""

from fastapi import APIRouter, Depends, HTTPException, status, Header
from sqlalchemy.orm import Session
from typing import Optional, List
from datetime import datetime
import os

from app.db.database import get_postgres_db
from app.schemas.auth import ErrorResponse
from app.schemas.admin import (
    FilterableFieldCreate, FilterableFieldUpdate,
    FilterableFieldResponse, FilterableFieldListResponse
)
from app.service.admin_service import AdminService
from app.config.security import verify_token

router = APIRouter(prefix="/api/v1/admin", tags=["Admin Management"])

# 개발 환경에서는 인증 스킵
SKIP_AUTH = os.getenv("SKIP_AUTH", "false").lower() == "true"


def get_current_user_id(authorization: Optional[str] = Header(None)) -> int:
    """
    현재 사용자 ID 추출
    Authorization 헤더에서 Bearer 토큰을 받아 사용자 ID를 반환합니다.
    개발 환경(SKIP_AUTH=true)에서는 토큰 검증을 건너뜁니다.
    """
    if SKIP_AUTH:
        return 0  # 개발 환경에서는 더미 사용자 ID 반환

    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="인증 토큰이 없습니다",
        )

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
            detail="토큰에서 사용자 ID를 찾을 수 없습니다",
        )

    return user_id


# ============= 용어 사전 (Terms) =============

@router.get("/terms", tags=["Terms"])
def get_all_terms(
    db: Session = Depends(get_postgres_db),
    current_user_id: int = Depends(get_current_user_id),
):
    """
    모든 용어 조회
    """
    try:
        from app.models.admin import Term as TermModel

        terms = db.query(TermModel).filter(
            TermModel.deleted_at.is_(None)
        ).all()

        return {
            "success": True,
            "data": [
                {
                    "id": term.id,
                    "user_expression": term.user_expression,
                    "standard_term": term.standard_term,
                    "created_at": term.created_at.isoformat(),
                    "updated_at": term.updated_at.isoformat() if term.updated_at else None,
                }
                for term in terms
            ]
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"용어 조회 오류: {str(e)}"
        )


@router.post("/terms", tags=["Terms"])
def create_term(
    user_expression: str,
    standard_term: str,
    db: Session = Depends(get_postgres_db),
    current_user_id: int = Depends(get_current_user_id),
):
    """
    새 용어 추가
    """
    try:
        from app.models.admin import Term as TermModel

        if not user_expression.strip() or not standard_term.strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="user_expression과 standard_term 모두 필수입니다"
            )

        new_term = TermModel(
            user_expression=user_expression,
            standard_term=standard_term,
            created_at=datetime.utcnow(),
        )
        db.add(new_term)
        db.commit()
        db.refresh(new_term)

        return {
            "success": True,
            "data": {
                "id": new_term.id,
                "user_expression": new_term.user_expression,
                "standard_term": new_term.standard_term,
                "created_at": new_term.created_at.isoformat(),
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"용어 생성 오류: {str(e)}"
        )


@router.put("/terms/{term_id}", tags=["Terms"])
def update_term(
    term_id: int,
    user_expression: str,
    standard_term: str,
    db: Session = Depends(get_postgres_db),
    current_user_id: int = Depends(get_current_user_id),
):
    """
    용어 수정
    """
    try:
        from app.models.admin import Term as TermModel

        term = db.query(TermModel).filter(
            TermModel.id == term_id,
            TermModel.deleted_at.is_(None)
        ).first()

        if not term:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="용어를 찾을 수 없습니다"
            )

        term.user_expression = user_expression
        term.standard_term = standard_term
        term.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(term)

        return {
            "success": True,
            "data": {
                "id": term.id,
                "user_expression": term.user_expression,
                "standard_term": term.standard_term,
                "created_at": term.created_at.isoformat(),
                "updated_at": term.updated_at.isoformat(),
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"용어 수정 오류: {str(e)}"
        )


@router.delete("/terms/{term_id}", tags=["Terms"])
def delete_term(
    term_id: int,
    db: Session = Depends(get_postgres_db),
    current_user_id: int = Depends(get_current_user_id),
):
    """
    용어 삭제 (소프트 삭제)
    """
    try:
        from app.models.admin import Term as TermModel

        term = db.query(TermModel).filter(
            TermModel.id == term_id,
            TermModel.deleted_at.is_(None)
        ).first()

        if not term:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="용어를 찾을 수 없습니다"
            )

        term.deleted_at = datetime.utcnow()
        db.commit()

        return {"success": True, "message": "용어가 삭제되었습니다"}
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"용어 삭제 오류: {str(e)}"
        )


# ============= 도메인 지식 (Knowledge) =============

@router.get("/knowledge", tags=["Knowledge"])
def get_all_knowledge(
    db: Session = Depends(get_postgres_db),
    current_user_id: int = Depends(get_current_user_id),
):
    """
    모든 도메인 지식 조회
    """
    try:
        from app.models.admin import Knowledge as KnowledgeModel

        knowledge = db.query(KnowledgeModel).filter(
            KnowledgeModel.deleted_at.is_(None)
        ).all()

        return {
            "success": True,
            "data": [
                {
                    "id": k.id,
                    "category": k.category,
                    "content": k.content,
                    "created_at": k.created_at.isoformat(),
                    "updated_at": k.updated_at.isoformat() if k.updated_at else None,
                }
                for k in knowledge
            ]
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"지식 조회 오류: {str(e)}"
        )


@router.post("/knowledge", tags=["Knowledge"])
def create_knowledge(
    category: str,
    content: str,
    db: Session = Depends(get_postgres_db),
    current_user_id: int = Depends(get_current_user_id),
):
    """
    새 도메인 지식 추가
    """
    try:
        from app.models.admin import Knowledge as KnowledgeModel

        if not category.strip() or not content.strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="category와 content 모두 필수입니다"
            )

        new_knowledge = KnowledgeModel(
            category=category,
            content=content,
            created_at=datetime.utcnow(),
        )
        db.add(new_knowledge)
        db.commit()
        db.refresh(new_knowledge)

        return {
            "success": True,
            "data": {
                "id": new_knowledge.id,
                "category": new_knowledge.category,
                "content": new_knowledge.content,
                "created_at": new_knowledge.created_at.isoformat(),
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"지식 생성 오류: {str(e)}"
        )


@router.put("/knowledge/{knowledge_id}", tags=["Knowledge"])
def update_knowledge(
    knowledge_id: int,
    category: str,
    content: str,
    db: Session = Depends(get_postgres_db),
    current_user_id: int = Depends(get_current_user_id),
):
    """
    도메인 지식 수정
    """
    try:
        from app.models.admin import Knowledge as KnowledgeModel

        knowledge = db.query(KnowledgeModel).filter(
            KnowledgeModel.id == knowledge_id,
            KnowledgeModel.deleted_at.is_(None)
        ).first()

        if not knowledge:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="지식을 찾을 수 없습니다"
            )

        knowledge.category = category
        knowledge.content = content
        knowledge.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(knowledge)

        return {
            "success": True,
            "data": {
                "id": knowledge.id,
                "category": knowledge.category,
                "content": knowledge.content,
                "created_at": knowledge.created_at.isoformat(),
                "updated_at": knowledge.updated_at.isoformat(),
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"지식 수정 오류: {str(e)}"
        )


@router.delete("/knowledge/{knowledge_id}", tags=["Knowledge"])
def delete_knowledge(
    knowledge_id: int,
    db: Session = Depends(get_postgres_db),
    current_user_id: int = Depends(get_current_user_id),
):
    """
    도메인 지식 삭제 (소프트 삭제)
    """
    try:
        from app.models.admin import Knowledge as KnowledgeModel

        knowledge = db.query(KnowledgeModel).filter(
            KnowledgeModel.id == knowledge_id,
            KnowledgeModel.deleted_at.is_(None)
        ).first()

        if not knowledge:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="지식을 찾을 수 없습니다"
            )

        knowledge.deleted_at = datetime.utcnow()
        db.commit()

        return {"success": True, "message": "지식이 삭제되었습니다"}
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"지식 삭제 오류: {str(e)}"
        )


# ============= 필드 설명 (Schema) =============

@router.get("/schema", tags=["Schema"])
def get_all_schema_fields(
    db: Session = Depends(get_postgres_db),
    current_user_id: int = Depends(get_current_user_id),
):
    """
    모든 필드 설명 조회
    """
    try:
        from app.models.admin import SchemaField as SchemaFieldModel

        fields = db.query(SchemaFieldModel).filter(
            SchemaFieldModel.deleted_at.is_(None)
        ).all()

        return {
            "success": True,
            "data": [
                {
                    "id": field.id,
                    "table_name": field.table_name,
                    "field_name": field.field_name,
                    "data_type": field.data_type,
                    "description": field.description,
                    "is_core": field.is_core,
                    "created_at": field.created_at.isoformat(),
                    "updated_at": field.updated_at.isoformat() if field.updated_at else None,
                }
                for field in fields
            ]
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"필드 조회 오류: {str(e)}"
        )


@router.put("/schema/{schema_field_id}", tags=["Schema"])
def update_schema_field(
    schema_field_id: int,
    description: str,
    db: Session = Depends(get_postgres_db),
    current_user_id: int = Depends(get_current_user_id),
):
    """
    필드 설명 수정 (핵심 필드 제외)
    """
    try:
        from app.models.admin import SchemaField as SchemaFieldModel

        field = db.query(SchemaFieldModel).filter(
            SchemaFieldModel.id == schema_field_id,
            SchemaFieldModel.deleted_at.is_(None)
        ).first()

        if not field:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="필드를 찾을 수 없습니다"
            )

        if field.is_core:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="핵심 필드는 수정할 수 없습니다"
            )

        field.description = description
        field.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(field)

        return {
            "success": True,
            "data": {
                "id": field.id,
                "table_name": field.table_name,
                "field_name": field.field_name,
                "data_type": field.data_type,
                "description": field.description,
                "is_core": field.is_core,
                "created_at": field.created_at.isoformat(),
                "updated_at": field.updated_at.isoformat(),
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"필드 수정 오류: {str(e)}"
        )


# ============= 필터 규칙 (FilterableField) =============

@router.get("/filters", tags=["Filters"])
def get_all_filters(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_postgres_db),
    current_user_id: int = Depends(get_current_user_id),
):
    """
    모든 필터 규칙 조회
    """
    try:
        fields, total = AdminService.get_all_filterable_fields(db, skip=skip, limit=limit)
        
        return {
            "success": True,
            "total": total,
            "data": [
                {
                    "id": field.id,
                    "field_name": field.field_name,
                    "display_name": field.display_name,
                    "description": field.description,
                    "field_type": field.field_type,
                    "extraction_pattern": field.extraction_pattern,
                    "extraction_keywords": field.extraction_keywords,
                    "value_mapping": field.value_mapping,
                    "is_optional": field.is_optional,
                    "multiple_allowed": field.multiple_allowed,
                    "valid_values": field.valid_values,
                    "validation_type": field.validation_type,
                }
                for field in fields
            ]
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"필터 조회 오류: {str(e)}"
        )


@router.get("/filters/{filter_id}", tags=["Filters"])
def get_filter(
    filter_id: int,
    db: Session = Depends(get_postgres_db),
    current_user_id: int = Depends(get_current_user_id),
):
    """
    특정 필터 규칙 조회
    """
    try:
        field = AdminService.get_filterable_field_by_id(db, filter_id)
        
        if not field:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="필터를 찾을 수 없습니다"
            )
        
        return {
            "success": True,
            "data": {
                "id": field.id,
                "field_name": field.field_name,
                "display_name": field.display_name,
                "description": field.description,
                "field_type": field.field_type,
                "extraction_pattern": field.extraction_pattern,
                "extraction_keywords": field.extraction_keywords,
                "value_mapping": field.value_mapping,
                "is_optional": field.is_optional,
                "multiple_allowed": field.multiple_allowed,
                "valid_values": field.valid_values,
                "validation_type": field.validation_type,
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"필터 조회 오류: {str(e)}"
        )


@router.post("/filters", tags=["Filters"])
def create_filter(
    payload: FilterableFieldCreate,
    db: Session = Depends(get_postgres_db),
    current_user_id: int = Depends(get_current_user_id),
):
    """
    새 필터 규칙 추가
    """
    try:
        # 데이터 검증
        is_valid, error_msg = AdminService.validate_filterable_field(
            payload.field_type,
            payload.extraction_pattern,
            payload.extraction_keywords
        )
        
        if not is_valid:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=error_msg
            )
        
        # 필터 생성
        field = AdminService.create_filterable_field(
            db=db,
            field_name=payload.field_name,
            display_name=payload.display_name,
            field_type=payload.field_type,
            extraction_pattern=payload.extraction_pattern,
            extraction_keywords=payload.extraction_keywords,
            value_mapping=payload.value_mapping,
            description=payload.description,
            is_optional=payload.is_optional,
            multiple_allowed=payload.multiple_allowed
        )
        
        return {
            "success": True,
            "data": {
                "id": field.id,
                "field_name": field.field_name,
                "display_name": field.display_name,
                "description": field.description,
                "field_type": field.field_type,
                "extraction_pattern": field.extraction_pattern,
                "extraction_keywords": field.extraction_keywords,
                "value_mapping": field.value_mapping,
                "is_optional": field.is_optional,
                "multiple_allowed": field.multiple_allowed,
                "valid_values": field.valid_values,
                "validation_type": field.validation_type,
            }
        }
    except HTTPException:
        raise
    except ValueError as ve:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(ve)
        )
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"필터 생성 오류: {str(e)}"
        )


@router.put("/filters/{filter_id}", tags=["Filters"])
def update_filter(
    filter_id: int,
    payload: FilterableFieldUpdate,
    db: Session = Depends(get_postgres_db),
    current_user_id: int = Depends(get_current_user_id),
):
    """
    필터 규칙 수정
    """
    try:
        # 필드 타입이 변경되는 경우 검증
        if payload.field_type:
            is_valid, error_msg = AdminService.validate_filterable_field(
                payload.field_type,
                payload.extraction_pattern,
                payload.extraction_keywords
            )
            
            if not is_valid:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=error_msg
                )
        
        # 업데이트할 필드들만 추출
        update_data = {}
        for key, value in payload.dict(exclude_unset=True).items():
            update_data[key] = value
        
        # 필터 업데이트
        field = AdminService.update_filterable_field(db, filter_id, **update_data)
        
        return {
            "success": True,
            "data": {
                "id": field.id,
                "field_name": field.field_name,
                "display_name": field.display_name,
                "description": field.description,
                "field_type": field.field_type,
                "extraction_pattern": field.extraction_pattern,
                "extraction_keywords": field.extraction_keywords,
                "value_mapping": field.value_mapping,
                "is_optional": field.is_optional,
                "multiple_allowed": field.multiple_allowed,
                "valid_values": field.valid_values,
                "validation_type": field.validation_type,
            }
        }
    except HTTPException:
        raise
    except ValueError as ve:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(ve)
        )
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"필터 수정 오류: {str(e)}"
        )


@router.delete("/filters/{filter_id}", tags=["Filters"])
def delete_filter(
    filter_id: int,
    db: Session = Depends(get_postgres_db),
    current_user_id: int = Depends(get_current_user_id),
):
    """
    필터 규칙 삭제
    """
    try:
        field = AdminService.get_filterable_field_by_id(db, filter_id)
        
        if not field:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="필터를 찾을 수 없습니다"
            )
        
        AdminService.delete_filterable_field(db, filter_id)
        
        return {"success": True, "message": "필터가 삭제되었습니다"}
    except HTTPException:
        raise
    except ValueError as ve:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(ve)
        )
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"필터 삭제 오류: {str(e)}"
        )
