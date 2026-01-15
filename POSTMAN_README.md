# Postman 테스트 가이드

EXAONE API를 Postman으로 테스트하는 방법에 대한 완전한 가이드입니다.

---

## 📚 문서 구성

### 1. **POSTMAN_QUICK_START.md** (추천! 먼저 읽기)
**5분 안에 시작하기**

```
✅ 가장 빠른 방법
✅ 필수 단계만 포함
✅ 초보자 친화적
✅ 단계별 체크리스트

시간: 5분
```

👉 **[빠른 시작 가이드 읽기](./POSTMAN_QUICK_START.md)**

---

### 2. **POSTMAN_GUIDE.md** (상세 가이드)
**완전한 API 테스트 방법**

```
✅ 모든 엔드포인트 설명
✅ 요청/응답 예시
✅ 문제 해결 방법
✅ 팁과 트릭

시간: 15-20분
```

👉 **[상세 가이드 읽기](./POSTMAN_GUIDE.md)**

---

### 3. **EXAONE_API_Postman_Collection.json**
**Postman 컬렉션 파일**

```
✅ 모든 API 요청 포함
✅ 자동 토큰 저장 스크립트
✅ 변수 관리
✅ 그룹화된 카테고리

파일: EXAONE_API_Postman_Collection.json
```

---

## 🎯 사용 시나리오

### 시나리오 1: 빠르게 테스트하고 싶을 때
```
1. POSTMAN_QUICK_START.md 읽기 (5분)
2. Postman에서 컬렉션 가져오기
3. 회원가입 → 로그인 → 쿼리 실행
4. Done! 🎉
```

### 시나리오 2: 체계적으로 배우고 싶을 때
```
1. POSTMAN_GUIDE.md 읽기 (20분)
2. 각 섹션별로 요청 시도
3. 응답 확인하면서 이해
4. 모든 엔드포인트 학습
```

### 시나리오 3: 팀원과 공유하고 싶을 때
```
1. EXAONE_API_Postman_Collection.json 공유
2. POSTMAN_QUICK_START.md 링크 전송
3. 팀원들이 독립적으로 테스트
```

---

## 📦 설치 단계

### Step 1: Postman 설치
```bash
# 다운로드
https://www.postman.com/downloads/

# 또는 Homebrew (Mac)
brew install --cask postman

# 또는 Chocolatey (Windows)
choco install postman
```

### Step 2: 컬렉션 임포트
```
Postman 실행
→ File → Import
→ EXAONE_API_Postman_Collection.json 선택
→ Import 클릭
```

### Step 3: 환경 설정
```
우측 상단 ⚙️ 클릭
→ Environments → Create New
→ 이름: "EXAONE Local"
→ 변수 추가:
   - access_token
   - refresh_token
   - user_id
   - thread_id
   - message_id
→ Save
```

### Step 4: 서버 확인
```bash
# FastAPI 서버가 실행 중인지 확인
curl http://localhost:8080/health

# 응답 확인
{
  "status": "healthy",
  "postgresql": "connected",
  "mysql": "connected"
}
```

---

## 🚀 첫 번째 요청 실행

### 1단계: 회원가입
```
좌측: 1. Authentication → 회원가입 (Sign Up)
Send 클릭
예상 응답: 201 Created
```

### 2단계: 로그인
```
좌측: 1. Authentication → 로그인 (Login)
Send 클릭
예상 응답: 200 OK
토큰이 자동으로 저장됨 ✅
```

### 3단계: 쿼리 실행
```
좌측: 2. Query Processing → 기본 생산량 조회
Send 클릭
예상 응답: 200 OK
생성된 SQL과 결과 확인 ✅
```

---

## 📊 컬렉션 구조

```
EXAONE Query Processing API/
├── 1. Authentication
│   ├── 회원가입 (Sign Up)
│   ├── 로그인 (Login) - 토큰 획득 ⭐
│   └── 현재 사용자 정보 조회 (Get Me)
│
├── 2. Query Processing
│   ├── 기본 생산량 조회 ⭐
│   ├── 라인별 생산량 조회
│   ├── 어제 불량 조회
│   ├── 설비 가동 상태 조회
│   ├── 최근 7일 생산량
│   └── 평균 불량률 조회
│
├── 3. Conversation History
│   ├── 사용자 쓰레드 목록 조회
│   └── 특정 쓰레드의 메시지 조회
│
└── 4. System
    ├── 헬스 체크
    └── API 루트
```

⭐ = 가장 중요한 엔드포인트

---

## ✨ 주요 기능

### 자동 토큰 저장
로그인 후 `access_token`이 자동으로 저장되어 다음 요청에 사용됩니다.

```javascript
// Tests 탭의 자동 스크립트
if (pm.response.code === 200) {
    var jsonData = pm.response.json();
    pm.environment.set('access_token', jsonData.access_token);
    pm.environment.set('user_id', jsonData.user.id);
}
```

### 변수 참조
모든 요청에서 저장된 변수를 사용할 수 있습니다:
```
{{access_token}}   # JWT 토큰
{{user_id}}        # 사용자 ID
{{thread_id}}      # 쓰레드 ID
{{message_id}}     # 메시지 ID
```

### 자동 로깅
각 요청의 결과가 Console에 자동으로 기록됩니다:
```
✅ 토큰 획득 성공
✅ 쿼리 실행 성공
✅ 데이터 조회 완료
```

---

## 🔍 응답 확인 방법

### Response 탭
```
[Status]    Status Code 확인 (200, 201, 400 등)
[Body]      JSON 응답 확인 (Pretty 모드 권장)
[Headers]   Content-Type 등 헤더 확인
```

### Console 탭 (왼쪽 하단)
```
자동으로 실행된 스크립트 로그 확인
에러 메시지 확인
변수 저장 확인
```

### Tests 탭
```
각 요청의 검증 로직 확인
자동 실행 스크립트 수정 가능
```

---

## 🆘 문제 해결

### 문제 1: "인증 토큰이 없습니다"
```
해결:
1. 로그인 요청 다시 실행
2. Console에서 "✅ 토큰 획득 성공" 확인
3. 환경에서 access_token 값 확인
```

### 문제 2: 401 Unauthorized
```
해결:
1. 로그인 재실행
2. Authorization 헤더 확인
3. 토큰 복사/붙여넣기 다시 확인
```

### 문제 3: 500 Internal Server Error
```
해결:
1. 헬스 체크 실행 (System > 헬스 체크)
2. 서버 로그 확인
3. 데이터베이스 연결 상태 확인
```

### 문제 4: "테이블을 찾을 수 없습니다"
```
해결:
1. MySQL 테이블 생성 확인
2. 서버 재시작
3. 초기화 스크립트 실행
```

---

## 💡 팁과 트릭

### 팁 1: 요청 복제
```
요청 우클릭 → Duplicate
변수만 다르게 해서 여러 버전 만들기
```

### 팁 2: 환경 전환
```
우측 상단 [Environment 드롭다운]
다양한 환경 (개발/테스트/프로덕션) 관리
```

### 팁 3: Runner 사용
```
Collection 우클릭 → Run
모든 요청을 순차적으로 실행
자동으로 결과 리포트 생성
```

### 팁 4: 예약된 요청
```
요청을 스케줄로 실행
정기적인 API 모니터링 가능
```

---

## 🎓 학습 순서 추천

### 1주차
```
☐ 인증 (Authentication) 이해
☐ 회원가입/로그인 테스트
☐ 토큰 관리 방법 학습
```

### 2주차
```
☐ 기본 쿼리 실행
☐ 다양한 질문으로 쿼리 생성 확인
☐ SQL 검증 방법 이해
```

### 3주차
```
☐ 대화 히스토리 조회
☐ 쓰레드 관리
☐ 메시지 상세 확인
```

### 4주차
```
☐ 성능 테스트
☐ 에러 케이스 테스트
☐ 엣지 케이스 확인
```

---

## 📈 다음 단계

### API 검증
```
✅ 모든 엔드포인트 테스트 완료
✅ 응답 형식 확인
✅ 에러 처리 확인
```

### 성능 평가
```
✅ 응답 시간 측정
✅ 최대 부하 테스트
✅ 동시 요청 테스트
```

### 실제 통합
```
✅ Android 앱과 연동
✅ 실제 데이터로 테스트
✅ 모니터링 설정
```

---

## 📞 지원

### 문제가 있을 때
1. POSTMAN_GUIDE.md 의 "문제 해결" 섹션 확인
2. 서버 로그 확인: `docker logs exaone_fastapi`
3. 헬스 체크 실행: System > 헬스 체크
4. 데이터베이스 상태 확인

### API 문서
- **Swagger UI**: http://localhost:8080/docs
- **ReDoc**: http://localhost:8080/redoc
- **구현 요약**: IMPLEMENTATION_SUMMARY.md

### 관련 문서
- [빠른 시작 가이드](./POSTMAN_QUICK_START.md)
- [상세 가이드](./POSTMAN_GUIDE.md)
- [테스트 결과](./TEST_RESULTS.md)
- [구현 완료 문서](./IMPLEMENTATION_SUMMARY.md)

---

## 🎉 축하합니다!

이제 EXAONE API를 완벽하게 테스트할 수 있습니다!

**다음 단계**:
1. ✅ Postman에서 모든 API 테스트
2. ⬜ Android 앱 개발 계속
3. ⬜ 실제 EXAONE API 연동 (Phase 2)

---

**작성일**: 2026-01-14
**버전**: 1.0.0
**대상**: 초보자 ~ 중급자
