"""
엔티티 추출 서비스

FilterableField 규칙을 기반으로 사용자 메시지에서
필터 조건(엔티티)을 추출합니다.

예:
  message: "1호 사출기 오늘 생산량은?"
  entities: {"machine_id": "1", "cycle_date": "CURDATE()"}
  where_clause: "machine_id = '1' AND cycle_date = CURDATE()"
"""

import re
import logging
from typing import Dict, Any, Optional, List
from sqlalchemy.orm import Session

from app.models.admin import FilterableField

logger = logging.getLogger(__name__)


class EntityExtractionService:
    """엔티티 추출 서비스"""

    @staticmethod
    def extract_entities(message: str, db: Session) -> Dict[str, Any]:
        """
        정규화된 메시지에서 엔티티를 추출합니다.

        Args:
            message: 정규화된 사용자 메시지
            db: PostgreSQL 세션

        Returns:
            추출된 엔티티 딕셔너리
            예: {"machine_id": "1", "cycle_date": "CURDATE()"}
        """
        entities = {}

        try:
            # FilterableField 규칙 로드
            filterable_fields = db.query(FilterableField).all()

            for field in filterable_fields:
                # 각 필터에 대해 엔티티 추출 시도
                extracted_value = EntityExtractionService._extract_single_entity(
                    message, field
                )

                if extracted_value is not None:
                    if field.multiple_allowed:
                        # 여러 값 허용: 리스트로 저장
                        if field.field_name not in entities:
                            entities[field.field_name] = []
                        entities[field.field_name].append(extracted_value)
                    else:
                        # 단일 값: 첫 번째만 저장
                        entities[field.field_name] = extracted_value

            logger.info(f"✅ 엔티티 추출 완료: {entities}")
            return entities

        except Exception as e:
            logger.error(f"❌ 엔티티 추출 오류: {str(e)}")
            return {}

    @staticmethod
    def _extract_single_entity(message: str, field: FilterableField) -> Optional[str]:
        """
        단일 필드에 대한 엔티티를 추출합니다.

        Args:
            message: 정규화된 메시지
            field: FilterableField 객체

        Returns:
            추출된 값, 없으면 None
        """
        value = None

        # 1단계: 키워드로 먼저 추출 (더 정확함)
        if field.extraction_keywords:
            for keyword in field.extraction_keywords:
                if keyword in message:
                    # 값 매핑 적용 (있으면)
                    if field.value_mapping and keyword in field.value_mapping:
                        value = field.value_mapping[keyword]
                    else:
                        value = keyword
                        # 키워드에서 숫자만 추출 (예: "1번" → "1")
                        digits = re.findall(r'\d+', keyword)
                        if digits:
                            value = digits[0]

                    # 검증 (있으면)
                    if not EntityExtractionService._validate_value(value, field):
                        logger.debug(
                            f"   [keyword-rejected] {field.field_name}: '{value}' "
                            f"(유효하지 않은 값)"
                        )
                        continue

                    logger.debug(
                        f"   [keyword] {field.field_name}: '{value}' "
                        f"(keyword: '{keyword}')"
                    )
                    return value

        # 2단계: 키워드가 없으면 정규표현식으로 추출
        if field.extraction_pattern:
            try:
                match = re.search(field.extraction_pattern, message)
                if match:
                    # 모든 그룹 중 첫 번째 유효한 값 사용
                    value = None
                    if match.groups():
                        # 여러 그룹이 있을 경우 None이 아닌 첫 번째 값 사용
                        for group_value in match.groups():
                            if group_value is not None:
                                value = group_value
                                break
                    if value is None:
                        # 그룹이 없으면 전체 match 사용
                        value = match.group(0)

                    # 검증 (있으면)
                    if not EntityExtractionService._validate_value(value, field):
                        logger.debug(
                            f"   [regex-rejected] {field.field_name}: '{value}' "
                            f"(유효하지 않은 값)"
                        )
                        return None

                    logger.debug(
                        f"   [regex] {field.field_name}: '{value}' "
                        f"(pattern: {field.extraction_pattern})"
                    )
                    return value
            except Exception as e:
                logger.warning(
                    f"   정규표현식 오류 ({field.field_name}): {str(e)}"
                )

        return None

    @staticmethod
    def _validate_value(value: str, field: FilterableField) -> bool:
        """
        추출된 값이 FilterableField의 valid_values 범위에 있는지 검증합니다.

        Args:
            value: 추출된 값
            field: FilterableField 객체

        Returns:
            유효하면 True, 아니면 False
        """
        # 검증이 설정되지 않았으면 모든 값 허용
        if not field.validation_type or field.validation_type == "none":
            return True

        # 검증 타입에 따라 처리
        if field.validation_type == "exact":
            # 정확한 값 일치
            if field.valid_values:
                valid_values_str = [str(v) for v in field.valid_values]
                return str(value) in valid_values_str
            return True

        elif field.validation_type == "range":
            # 숫자 범위
            if field.valid_values and len(field.valid_values) >= 2:
                try:
                    min_val = float(field.valid_values[0])
                    max_val = float(field.valid_values[1])
                    val = float(value)
                    return min_val <= val <= max_val
                except (ValueError, TypeError):
                    return True
            return True

        return True

    @staticmethod
    def build_where_clause(entities: Dict[str, Any]) -> str:
        """
        추출된 엔티티로 WHERE 절을 생성합니다.

        Args:
            entities: 추출된 엔티티 딕셔너리

        Returns:
            WHERE 절 문자열
            예: "machine_id = '1' AND cycle_date = CURDATE()"
        """
        if not entities:
            return ""

        conditions = []

        for field_name, value in entities.items():
            if isinstance(value, list):
                # 여러 값: IN 절
                values_str = ", ".join(f"'{v}'" for v in value)
                condition = f"{field_name} IN ({values_str})"
                conditions.append(condition)
            else:
                # 단일 값
                # CURDATE() 같은 SQL 함수는 따옴표 없음
                # 함수 판정: 괄호가 있거나, DATE_, INTERVAL, NOW, CURDATE 등이 포함된 경우
                is_sql_function = (
                    value and (
                        "(" in str(value) and ")" in str(value)  # 괄호가 있으면 함수
                        or "CURDATE" in str(value).upper()
                        or "DATE_" in str(value).upper()
                        or "NOW()" in str(value).upper()
                        or "INTERVAL" in str(value).upper()
                    )
                )

                if is_sql_function:
                    condition = f"{field_name} = {value}"  # 따옴표 없음
                else:
                    condition = f"{field_name} = '{value}'"  # 따옴표 포함
                conditions.append(condition)

        where_clause = " AND ".join(conditions)
        logger.info(f"📌 WHERE 절 생성: {where_clause}")
        return where_clause

    @staticmethod
    def merge_entities(
        current_entities: Dict[str, Any],
        previous_entities: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        현재 엔티티와 이전 엔티티를 병합합니다.

        현재 엔티티가 우선순위가 높습니다 (명시된 것).

        Args:
            current_entities: 현재 메시지에서 추출한 엔티티
            previous_entities: 이전 메시지에서 추출한 엔티티

        Returns:
            병합된 엔티티 딕셔너리
        """
        if not previous_entities:
            return current_entities

        # 이전 엔티티를 기본값으로 시작
        merged = previous_entities.copy()

        # 현재 엔티티로 덮어쓰기 (명시된 것)
        merged.update(current_entities)

        logger.info(f"🔀 엔티티 병합: {merged}")
        return merged
