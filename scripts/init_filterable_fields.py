"""
FilterableField 초기 데이터 등록 스크립트
데이터베이스에서 실행: python scripts/init_filterable_fields.py
"""

import sys
from pathlib import Path

# 프로젝트 루트 디렉토리 추가
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.db.database import PostgresSessionLocal
from app.models.admin import FilterableField


def init_filterable_fields():
    """FilterableField 초기 데이터 등록"""

    db = PostgresSessionLocal()

    try:
        # 1. 기존 데이터 확인
        existing = db.query(FilterableField).filter(
            FilterableField.field_name == "machine_id"
        ).first()

        if existing:
            print("✅ FilterableField 데이터가 이미 존재합니다")
            return

        # 2. 사출기 필터
        machine_filter = FilterableField(
            field_name="machine_id",
            display_name="사출기",
            description="사출 기계 ID",
            field_type="numeric",
            extraction_pattern=r"\d+",
            extraction_keywords=[
                "1번", "1호", "1호기", "사출기 1", "기계 1",
                "2번", "2호", "2호기", "사출기 2", "기계 2",
                "3번", "3호", "3호기", "사출기 3", "기계 3",
                "4번", "4호", "4호기", "사출기 4", "기계 4",
                "5번", "5호", "5호기", "사출기 5", "기계 5"
            ],
            value_mapping=None,
            is_optional=True,
            multiple_allowed=False
        )
        db.add(machine_filter)

        # 3. 날짜 필터
        date_filter = FilterableField(
            field_name="cycle_date",
            display_name="날짜",
            description="사이클 실행 날짜",
            field_type="date",
            extraction_pattern=r"\d{4}-\d{2}-\d{2}|\d{4}년\s*\d{1,2}월\s*\d{1,2}일",
            extraction_keywords=[
                "오늘", "어제", "내일", "지난주", "이번주",
                "지난달", "이번달", "모레", "그저께"
            ],
            value_mapping={
                "오늘": "CURDATE()",
                "어제": "DATE_SUB(CURDATE(), INTERVAL 1 DAY)",
                "내일": "DATE_ADD(CURDATE(), INTERVAL 1 DAY)",
                "지난주": "DATE_SUB(CURDATE(), INTERVAL 7 DAY)",
                "이번주": "DATE_FORMAT(CURDATE(), '%Y-%m-01')",
                "지난달": "DATE_SUB(CURDATE(), INTERVAL 1 MONTH)",
                "이번달": "DATE_FORMAT(CURDATE(), '%Y-%m-01')",
                "모레": "DATE_ADD(CURDATE(), INTERVAL 1 DAY)",
                "그저께": "DATE_SUB(CURDATE(), INTERVAL 2 DAY)"
            },
            is_optional=True,
            multiple_allowed=False
        )
        db.add(date_filter)

        # 4. 금형 필터
        mold_filter = FilterableField(
            field_name="mold_id",
            display_name="금형",
            description="사용된 금형 ID",
            field_type="numeric",
            extraction_pattern=r"\d+",
            extraction_keywords=["금형", "DC", "DC1", "DC2"],
            value_mapping=None,
            is_optional=True,
            multiple_allowed=True
        )
        db.add(mold_filter)

        # 5. 재료 필터
        material_filter = FilterableField(
            field_name="material_id",
            display_name="재료",
            description="원재료 ID",
            field_type="numeric",
            extraction_pattern=r"\d+",
            extraction_keywords=["HIPS", "PP", "재료"],
            value_mapping=None,
            is_optional=True,
            multiple_allowed=True
        )
        db.add(material_filter)

        # 6. 저장
        db.commit()
        print("✅ FilterableField 초기 데이터 등록 완료")
        print(f"   - 사출기 필터")
        print(f"   - 날짜 필터")
        print(f"   - 금형 필터")
        print(f"   - 재료 필터")

    except Exception as e:
        print(f"❌ 오류: {str(e)}")
        db.rollback()
        raise

    finally:
        db.close()


if __name__ == "__main__":
    init_filterable_fields()
