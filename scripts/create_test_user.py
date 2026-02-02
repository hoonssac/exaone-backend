"""
테스트 사용자 생성 스크립트
"""
import sys
from pathlib import Path

# 상위 디렉토리를 Python 경로에 추가
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.db.database import PostgresSessionLocal
from app.models.user import User
from app.config.security import hash_password

def create_test_user():
    """테스트 사용자 생성"""
    db = PostgresSessionLocal()
    
    try:
        # 기존 테스트 사용자 확인
        existing_user = db.query(User).filter(User.email == "test@example.com").first()
        
        if existing_user:
            print("✅ 테스트 사용자가 이미 존재합니다")
            print(f"   이메일: {existing_user.email}")
            print(f"   이름: {existing_user.name}")
            print(f"   사원ID: {existing_user.employee_id}")
            return
        
        # 테스트 사용자 생성
        test_user = User(
            email="test@example.com",
            password=hash_password("Test1234!"),
            name="테스트 사용자",
            employee_id="12345678",
            dept_name="개발팀",
            position="사원",
            is_active=True
        )
        
        db.add(test_user)
        db.commit()
        db.refresh(test_user)
        
        print("✅ 테스트 사용자 생성 완료")
        print(f"   이메일: {test_user.email}")
        print(f"   비밀번호: Test1234!")
        print(f"   이름: {test_user.name}")
        print(f"   사원ID: {test_user.employee_id}")
        
    except Exception as e:
        db.rollback()
        print(f"❌ 테스트 사용자 생성 실패: {str(e)}")
    finally:
        db.close()

if __name__ == "__main__":
    create_test_user()
