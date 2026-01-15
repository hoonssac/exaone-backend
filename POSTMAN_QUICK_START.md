# Postman 빠른 시작 가이드 (5분 안에 시작하기)

## 📦 사전 준비

- ✅ Postman 설치됨
- ✅ FastAPI 서버 실행 중 (http://localhost:8080)
- ✅ 컬렉션 파일: `EXAONE_API_Postman_Collection.json`

---

## 🚀 5분 안에 시작하기

### 1️⃣ Postman에서 컬렉션 가져오기 (30초)

```
Postman 열기
  → File
  → Import
  → EXAONE_API_Postman_Collection.json 선택
  → Import 클릭
```

**확인**: 왼쪽 패널에 "EXAONE Query Processing API" 폴더 표시

---

### 2️⃣ 환경(Environment) 설정 (30초)

```
우측 상단 ⚙️ 클릭
  → Environments
  → Create New Environment
  → 이름: "EXAONE Local"
  → Variables 탭에서:
     - access_token = (공백)
     - refresh_token = (공백)
     - user_id = (공백)
     - thread_id = (공백)
     - message_id = (공백)
  → Save
```

**확인**: 우측 상단에 "EXAONE Local" 선택됨

---

### 3️⃣ 회원가입 (20초)

```
좌측에서:
  1. Authentication
     → 회원가입 (Sign Up) 선택
  → Send 클릭
```

**확인**: Status 201 Created 표시

---

### 4️⃣ 로그인 (30초)

```
좌측에서:
  1. Authentication
     → 로그인 (Login) - 토큰 획득 선택
  → Send 클릭
```

**확인**:
- ✅ Status 200 OK
- ✅ Console에 "✅ 토큰 획득 성공" 표시
- ✅ access_token이 자동으로 저장됨

---

### 5️⃣ 첫 번째 쿼리 실행 (20초)

```
좌측에서:
  2. Query Processing
     → 기본 생산량 조회 선택
  → Send 클릭
```

**예상 결과**:
```
Status: 200 OK

Body:
{
  "thread_id": 1,
  "message_id": 1,
  "original_message": "오늘 생산량은?",
  "generated_sql": "SELECT * FROM production_data...",
  "result_data": {
    "row_count": 9
  },
  "execution_time": 48.71
}
```

---

### ✅ 완료!

이제 모든 API를 테스트할 수 있습니다! 🎉

---

## 다음 테스트할 요청들

### 🔍 추가 쿼리 테스트 (각 20초)

```
1. 라인별 생산량 조회
   → 예상: line_id별로 그룹화된 데이터

2. 어제 불량 조회
   → 예상: 어제 날짜 필터링된 데이터

3. 설비 가동 상태 조회
   → 예상: equipment_data 테이블 조회

4. 쓰레드 목록 조회
   → 예상: 사용자의 모든 대화 쓰레드
```

### 📊 대화 히스토리 조회

```
1. 사용자 쓰레드 목록 조회
   → 쓰레드 ID 확인

2. 특정 쓰레드의 메시지 조회
   → thread_id로 메시지 상세 확인
```

---

## 📝 응답 확인 방법

### Status 코드 확인
- **200** = 성공 ✅
- **201** = 생성 성공 ✅
- **400** = 입력 오류 ❌
- **401** = 인증 오류 ❌
- **500** = 서버 오류 ❌

### Body 확인
- **Response** 탭에서 JSON 확인
- **Pretty** 버튼으로 보기 좋게 정렬

### Headers 확인
- **Headers** 탭에서 응답 헤더 확인
- `Content-Type: application/json` 확인

### Console 확인
- **Console** 버튼 (왼쪽 하단)
- 자동으로 실행된 스크립트 로그 확인

---

## 🆘 빠른 문제 해결

### ❌ "인증 토큰이 없습니다"
```
→ 로그인 단계를 다시 실행
→ Console에서 "✅ 토큰 획득 성공" 확인
→ 환경 변수에서 access_token 값 확인
```

### ❌ "테이블을 찾을 수 없습니다"
```
→ 서버 로그 확인
→ MySQL 컨테이너 재시작
→ 헬스 체크 실행
```

### ❌ "500 Internal Server Error"
```
→ 헬스 체크 실행
→ 서버 로그 확인: docker logs exaone_fastapi
→ 데이터베이스 연결 확인
```

---

## 💡 유용한 팁

### 팁 1: 변수 참조
모든 필드에서 `{{변수명}}` 사용 가능:
```
{{access_token}}   # 토큰
{{thread_id}}      # 쓰레드 ID
{{user_id}}        # 사용자 ID
```

### 팁 2: 요청 복제
자주 쓰는 요청은 복제해서 다른 이름으로 저장:
```
요청 우클릭 → Duplicate → 이름 변경
```

### 팁 3: 설명 보기
각 요청에 마우스 올리면 설명 표시:
```
"기본 생산량 조회" → 설명 팝업
```

### 팁 4: 원본 요청 보기
Send 전에 URL과 Body 다시 확인:
```
Body 탭 → 요청 데이터 확인
```

---

## 🔄 테스트 흐름

```
회원가입 (201)
    ↓
로그인 (200) ← 토큰 자동 저장
    ↓
사용자 정보 조회 (200)
    ↓
기본 쿼리 (200) ← thread_id 자동 저장
    ↓
라인별 쿼리 (200)
    ↓
어제 불량 조회 (200)
    ↓
설비 상태 조회 (200)
    ↓
쓰레드 목록 조회 (200)
    ↓
메시지 상세 조회 (200)
    ↓
헬스 체크 (200)
```

**전체 테스트 시간**: 약 5-10분

---

## 🎯 확인 체크리스트

테스트하면서 다음을 확인하세요:

### 인증 (Authentication)
- [ ] 회원가입 성공
- [ ] 로그인 성공 및 토큰 획득
- [ ] 토큰이 자동으로 저장됨
- [ ] 사용자 정보 조회 성공

### 쿼리 처리 (Query Processing)
- [ ] 기본 쿼리 실행 성공
- [ ] SQL이 생성됨
- [ ] 결과가 반환됨
- [ ] thread_id와 message_id가 저장됨
- [ ] 라인별 쿼리 실행 성공
- [ ] 어제 불량 조회 성공
- [ ] 설비 상태 조회 성공

### 대화 히스토리 (Conversation History)
- [ ] 쓰레드 목록 조회 성공
- [ ] 메시지 상세 조회 성공
- [ ] 사용자 질문과 AI 응답 확인

### 시스템 (System)
- [ ] 헬스 체크 성공
- [ ] PostgreSQL 연결됨
- [ ] MySQL 연결됨

---

## 📞 추가 도움

**전체 가이드**: [POSTMAN_GUIDE.md](./POSTMAN_GUIDE.md)

**테스트 결과**: [TEST_RESULTS.md](./TEST_RESULTS.md)

**API 구현 완료**: [IMPLEMENTATION_SUMMARY.md](./IMPLEMENTATION_SUMMARY.md)

---

## 🎉 성공!

모든 API를 성공적으로 테스트했다면:

✅ **FastAPI 서버 정상 작동**
✅ **데이터베이스 연결 완료**
✅ **쿼리 처리 API 작동**
✅ **대화 히스토리 저장 확인**

다음 단계: 실제 EXAONE API 연동 (Phase 2) 시작!

---

**시간**: 5분
**난이도**: ⭐ (매우 쉬움)
**필수 조건**: Postman + 실행 중인 FastAPI 서버
