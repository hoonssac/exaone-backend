"""
마이그레이션: valid_values와 validation_type 컬럼 추가

admin_filterable_fields 테이블에 다음 컬럼을 추가:
- valid_values (JSON): 유효한 값 목록
- validation_type (String): 검증 타입 (none, exact, range)
"""

from sqlalchemy import text
from app.db.database import PostgresSessionLocal


def migrate_up():
    """마이그레이션 업그레이드"""
    db = PostgresSessionLocal()
    try:
        print("🔄 마이그레이션 시작: valid_values와 validation_type 컬럼 추가...")

        # 1. valid_values 컬럼 추가
        db.execute(text("""
            ALTER TABLE admin_filterable_fields
            ADD COLUMN IF NOT EXISTS valid_values JSONB DEFAULT NULL;
        """))
        print("✅ valid_values 컬럼 추가 완료")

        # 2. validation_type 컬럼 추가
        db.execute(text("""
            ALTER TABLE admin_filterable_fields
            ADD COLUMN IF NOT EXISTS validation_type VARCHAR(50) DEFAULT 'none';
        """))
        print("✅ validation_type 컬럼 추가 완료")

        db.commit()
        print("✅ 마이그레이션 완료")

    except Exception as e:
        db.rollback()
        print(f"❌ 마이그레이션 실패: {str(e)}")
        raise
    finally:
        db.close()


def migrate_down():
    """마이그레이션 롤백"""
    db = PostgresSessionLocal()
    try:
        print("🔄 마이그레이션 롤백 시작...")

        # 컬럼 제거
        db.execute(text("""
            ALTER TABLE admin_filterable_fields
            DROP COLUMN IF EXISTS valid_values,
            DROP COLUMN IF EXISTS validation_type;
        """))

        db.commit()
        print("✅ 마이그레이션 롤백 완료")

    except Exception as e:
        db.rollback()
        print(f"❌ 마이그레이션 롤백 실패: {str(e)}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "down":
        migrate_down()
    else:
        migrate_up()
