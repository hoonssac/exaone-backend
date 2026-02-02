"""
마이그레이션: admin_entities 테이블 추가

엔티티 메타데이터를 저장하는 테이블
엔티티가 추가되어도 코드 수정 없이 DB에만 등록하면 됨
"""

from sqlalchemy import text
from app.db.database import PostgresSessionLocal


def migrate_up():
    """마이그레이션 업그레이드"""
    db = None
    try:
        db = PostgresSessionLocal()
        print("🔄 마이그레이션 002 시작: admin_entities 테이블 추가...")

        # admin_entities 테이블 생성
        try:
            db.execute(text("""
                CREATE TABLE IF NOT EXISTS admin_entities (
                    id SERIAL PRIMARY KEY,
                    entity_name VARCHAR(100) NOT NULL UNIQUE,
                    display_name VARCHAR(100) NOT NULL,
                    description TEXT,
                    db_type VARCHAR(20) DEFAULT 'mysql',
                    table_name VARCHAR(100) NOT NULL,
                    id_column VARCHAR(100) NOT NULL DEFAULT 'id',
                    name_column VARCHAR(100),
                    query TEXT NOT NULL,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                    updated_at TIMESTAMP WITH TIME ZONE,
                    deleted_at TIMESTAMP WITH TIME ZONE
                )
            """))
            print("✅ admin_entities 테이블 생성 완료")
        except Exception as e:
            print(f"ℹ️ admin_entities 테이블 생성 스킵 (이미 존재): {str(e)[:50]}")

        # 인덱스 생성
        try:
            db.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_admin_entities_entity_name
                ON admin_entities(entity_name)
            """))
            print("✅ 인덱스 생성 완료")
        except Exception as e:
            print(f"ℹ️ 인덱스 생성 스킵: {str(e)[:50]}")

        db.commit()
        print("✅ 마이그레이션 002 완료")

    except Exception as e:
        if db:
            db.rollback()
        print(f"⚠️ 마이그레이션 002 실패 (무시함): {str(e)[:100]}")
    finally:
        if db:
            db.close()


def migrate_down():
    """마이그레이션 롤백"""
    db = PostgresSessionLocal()
    try:
        print("🔄 마이그레이션 롤백 시작...")

        db.execute(text("""
            DROP TABLE IF EXISTS admin_entities CASCADE
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
