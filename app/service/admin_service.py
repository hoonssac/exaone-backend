"""
관리자(Admin) 서비스
FilterableField 관리 기능
"""

import logging
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.models.admin import FilterableField

logger = logging.getLogger(__name__)


class AdminService:
    """관리자 서비스"""

    @staticmethod
    def get_all_filterable_fields(db: Session, skip: int = 0, limit: int = 100) -> tuple[List[FilterableField], int]:
        """
        모든 FilterableField 조회

        Args:
            db: PostgreSQL 세션
            skip: 스킵할 개수
            limit: 조회 제한 개수

        Returns:
            (필터 목록, 전체 개수)
        """
        try:
            total = db.query(func.count(FilterableField.id)).scalar()
            fields = db.query(FilterableField).offset(skip).limit(limit).all()
            logger.info(f"FilterableField 조회 완료: {len(fields)}개")
            return fields, total
        except Exception as e:
            logger.error(f"FilterableField 조회 실패: {str(e)}")
            raise

    @staticmethod
    def get_filterable_field_by_id(db: Session, field_id: int) -> Optional[FilterableField]:
        """
        특정 ID의 FilterableField 조회

        Args:
            db: PostgreSQL 세션
            field_id: 필터 ID

        Returns:
            FilterableField 객체 또는 None
        """
        try:
            field = db.query(FilterableField).filter(FilterableField.id == field_id).first()
            if field:
                logger.debug(f"FilterableField 조회: {field.field_name}")
            return field
        except Exception as e:
            logger.error(f"FilterableField 조회 실패 (ID: {field_id}): {str(e)}")
            raise

    @staticmethod
    def get_filterable_field_by_name(db: Session, field_name: str) -> Optional[FilterableField]:
        """
        필드명으로 FilterableField 조회

        Args:
            db: PostgreSQL 세션
            field_name: 필드명

        Returns:
            FilterableField 객체 또는 None
        """
        try:
            field = db.query(FilterableField).filter(
                FilterableField.field_name == field_name
            ).first()
            return field
        except Exception as e:
            logger.error(f"FilterableField 조회 실패 (field_name: {field_name}): {str(e)}")
            raise

    @staticmethod
    def create_filterable_field(
        db: Session,
        field_name: str,
        display_name: str,
        field_type: str,
        extraction_pattern: Optional[str] = None,
        extraction_keywords: Optional[List[str]] = None,
        value_mapping: Optional[Dict[str, str]] = None,
        description: Optional[str] = None,
        is_optional: bool = True,
        multiple_allowed: bool = False,
        valid_values: Optional[List[Any]] = None,
        validation_type: str = "none"
    ) -> FilterableField:
        """
        새로운 FilterableField 생성

        Args:
            db: PostgreSQL 세션
            field_name: 필터 필드명
            display_name: 화면 표시 이름
            field_type: 필드 타입
            extraction_pattern: 정규표현식 패턴
            extraction_keywords: 추출 키워드 목록
            value_mapping: 키워드→값 매핑
            description: 설명
            is_optional: 선택적 여부
            multiple_allowed: 다중값 허용 여부
            valid_values: 유효한 값 목록
            validation_type: 검증 타입 (none, exact, range)

        Returns:
            생성된 FilterableField 객체
        """
        try:
            # 중복 확인
            existing = AdminService.get_filterable_field_by_name(db, field_name)
            if existing:
                raise ValueError(f"필드명 '{field_name}'은 이미 존재합니다")

            # 생성
            new_field = FilterableField(
                field_name=field_name,
                display_name=display_name,
                description=description,
                field_type=field_type,
                extraction_pattern=extraction_pattern,
                extraction_keywords=extraction_keywords or [],
                value_mapping=value_mapping or {},
                is_optional=is_optional,
                multiple_allowed=multiple_allowed,
                valid_values=valid_values,
                validation_type=validation_type
            )

            db.add(new_field)
            db.commit()
            db.refresh(new_field)

            logger.info(f"FilterableField 생성: {field_name}")
            return new_field

        except ValueError as ve:
            db.rollback()
            logger.warning(f"FilterableField 생성 실패: {str(ve)}")
            raise
        except Exception as e:
            db.rollback()
            logger.error(f"FilterableField 생성 오류: {str(e)}")
            raise

    @staticmethod
    def update_filterable_field(
        db: Session,
        field_id: int,
        **kwargs
    ) -> FilterableField:
        """
        FilterableField 업데이트

        Args:
            db: PostgreSQL 세션
            field_id: 필터 ID
            **kwargs: 업데이트할 필드들

        Returns:
            업데이트된 FilterableField 객체
        """
        try:
            field = AdminService.get_filterable_field_by_id(db, field_id)
            if not field:
                raise ValueError(f"필터 ID {field_id}를 찾을 수 없습니다")

            # 업데이트 가능한 필드
            updatable_fields = {
                'display_name', 'description', 'field_type',
                'extraction_pattern', 'extraction_keywords',
                'value_mapping', 'is_optional', 'multiple_allowed',
                'valid_values', 'validation_type'
            }

            for key, value in kwargs.items():
                if key in updatable_fields and value is not None:
                    setattr(field, key, value)

            db.commit()
            db.refresh(field)

            logger.info(f"FilterableField 업데이트: {field.field_name}")
            return field

        except ValueError as ve:
            db.rollback()
            logger.warning(f"FilterableField 업데이트 실패: {str(ve)}")
            raise
        except Exception as e:
            db.rollback()
            logger.error(f"FilterableField 업데이트 오류: {str(e)}")
            raise

    @staticmethod
    def delete_filterable_field(db: Session, field_id: int) -> bool:
        """
        FilterableField 삭제

        Args:
            db: PostgreSQL 세션
            field_id: 필터 ID

        Returns:
            성공 여부
        """
        try:
            field = AdminService.get_filterable_field_by_id(db, field_id)
            if not field:
                raise ValueError(f"필터 ID {field_id}를 찾을 수 없습니다")

            field_name = field.field_name
            db.delete(field)
            db.commit()

            logger.info(f"FilterableField 삭제: {field_name}")
            return True

        except ValueError as ve:
            db.rollback()
            logger.warning(f"FilterableField 삭제 실패: {str(ve)}")
            raise
        except Exception as e:
            db.rollback()
            logger.error(f"FilterableField 삭제 오류: {str(e)}")
            raise

    @staticmethod
    def validate_filterable_field(
        field_type: str,
        extraction_pattern: Optional[str] = None,
        extraction_keywords: Optional[List[str]] = None
    ) -> tuple[bool, Optional[str]]:
        """
        FilterableField 데이터 검증

        Args:
            field_type: 필드 타입
            extraction_pattern: 정규표현식 패턴
            extraction_keywords: 추출 키워드 목록

        Returns:
            (유효성, 에러 메시지)
        """
        # 필드 타입 검증
        valid_types = ['numeric', 'date', 'string', 'boolean']
        if field_type not in valid_types:
            return False, f"invalid field_type: {field_type} (allowed: {valid_types})"

        # 정규표현식 검증
        if extraction_pattern:
            try:
                import re
                re.compile(extraction_pattern)
            except Exception as e:
                return False, f"invalid extraction_pattern: {str(e)}"

        # 키워드 검증
        if extraction_keywords:
            if not isinstance(extraction_keywords, list):
                return False, "extraction_keywords must be a list"
            if len(extraction_keywords) == 0:
                return False, "extraction_keywords cannot be empty"

        return True, None
