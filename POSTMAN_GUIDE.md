# Postman을 이용한 EXAONE API 테스트 가이드

## 📋 목차
1. [Postman 설치 및 컬렉션 가져오기](#설치-및-가져오기)
2. [환경 변수 설정](#환경-변수-설정)
3. [단계별 테스트 방법](#단계별-테스트-방법)
4. [API 엔드포인트 상세](#api-엔드포인트-상세)
5. [테스트 시나리오](#테스트-시나리오)
6. [문제 해결](#문제-해결)

---

## 설치 및 가져오기

### Step 1: Postman 다운로드 및 설치

1. [Postman 공식 웹사이트](https://www.postman.com/downloads/)에서 다운로드
2. OS에 맞게 설치 (Windows/Mac/Linux)
3. 계정 생성 또는 로그인 (선택사항이지만 권장)

### Step 2: 컬렉션 가져오기

#### 방법 1: 파일로 가져오기 (권장)

1. Postman 실행
2. **File** → **Import** 클릭
3. **EXAONE_API_Postman_Collection.json** 파일 선택
4. **Import** 클릭

#### 방법 2: URL로 가져오기

1. Postman 실행
2. **File** → **Import from link** 클릭
3. 다음 URL 입력:
   ```
   https://raw.githubusercontent.com/yourrepo/EXAONE_API_Postman_Collection.json
   ```
4. **Import** 클릭

### Step 3: 환경(Environment) 생성

1. Postman 오른쪽 상단 **⚙️ 설정** 클릭
2. **Environments** → **Create New** 클릭
3. 이름: `EXAONE Local` 입력
4. 다음 변수 추가:
   ```
   access_token    | 공백
   refresh_token   | 공백
   user_id         | 공백
   thread_id       | 공백
   message_id      | 공백
   ```
5. **Save** 클릭

---

## 환경 변수 설정

### 로컬 환경 설정

**Postman 오른쪽 상단에서 환경 선택**:

```
[No Environment ▼] → [EXAONE Local ▼]
```

### 변수 자동 할당

로그인 후 다음 변수가 자동으로 설정됩니다:
- `{{access_token}}` - JWT 액세스 토큰
- `{{refresh_token}}` - JWT 리프레시 토큰
- `{{user_id}}` - 사용자 ID
- `{{thread_id}}` - 쓰레드 ID (쿼리 실행 후 설정)
- `{{message_id}}` - 메시지 ID (쿼리 실행 후 설정)

---

## 단계별 테스트 방법

### 📍 단계 1: 회원가입

**요청 선택**: `1. Authentication` → `회원가입 (Sign Up)`

**요청 본문 (Body)**:
```json
{
  "email": "postman@example.com",
  "password": "PostmanTest123!",
  "name": "Postman 테스트 사용자",
  "employee_id": "20240099",
  "dept_name": "테스트부",
  "position": "테스터"
}
```

**예상 응답** (201 Created):
```json
{
  "access_token": "eyJhbGc...",
  "refresh_token": "eyJhbGc...",
  "token_type": "bearer",
  "user": {
    "id": 5,
    "email": "postman@example.com",
    "name": "Postman 테스트 사용자",
    ...
  }
}
```

**확인 사항**:
- ✅ Status Code: 201 Created
- ✅ access_token 값 확인

---

### 📍 단계 2: 로그인

**요청 선택**: `1. Authentication` → `로그인 (Login) - 토큰 획득`

**요청 본문 (Body)**:
```json
{
  "email": "postman@example.com",
  "password": "PostmanTest123!"
}
```

**예상 응답** (200 OK):
```json
{
  "access_token": "eyJhbGc...",
  "refresh_token": "eyJhbGc...",
  "token_type": "bearer",
  "user": {
    "id": 5,
    "email": "postman@example.com",
    ...
  }
}
```

**자동 처리**:
- ✅ `access_token` 자동 저장 (Tests 탭의 스크립트)
- ✅ `refresh_token` 자동 저장
- ✅ `user_id` 자동 저장
- ✅ 환경 변수에 자동 할당

**확인 방법**:
1. 요청 Send 클릭
2. **Console** 확인 (왼쪽 하단)
   ```
   ✅ 토큰 획득 성공
   Access Token: eyJhbGc...
   ```

---

### 📍 단계 3: 사용자 정보 조회

**요청 선택**: `1. Authentication` → `현재 사용자 정보 조회 (Get Me)`

**인증**: Authorization 헤더에 자동 포함 (`Bearer {{access_token}}`)

**예상 응답** (200 OK):
```json
{
  "id": 5,
  "email": "postman@example.com",
  "name": "Postman 테스트 사용자",
  "employee_id": "20240099",
  "dept_name": "테스트부",
  "position": "테스터",
  "is_active": true,
  "created_at": "2026-01-14T04:53:00"
}
```

---

### 📍 단계 4: 기본 쿼리 실행

**요청 선택**: `2. Query Processing` → `기본 생산량 조회`

**요청 본문 (Body)**:
```json
{
  "message": "오늘 생산량은?",
  "context_tag": "@현장"
}
```

**예상 응답** (200 OK):
```json
{
  "thread_id": 1,
  "message_id": 1,
  "original_message": "오늘 생산량은?",
  "corrected_message": "CURDATE() 생산량은?",
  "generated_sql": "SELECT * FROM production_data ORDER BY id DESC LIMIT 100;",
  "result_data": {
    "columns": ["id", "line_id", "product_code", ...],
    "rows": [
      {"id": 9, "line_id": "LINE-03", ...},
      {"id": 8, "line_id": "LINE-02", ...},
      ...
    ],
    "row_count": 9
  },
  "execution_time": 48.71,
  "created_at": "2026-01-14T04:53:30"
}
```

**응답 확인**:
- ✅ Status Code: 200 OK
- ✅ `generated_sql` 필드에 생성된 SQL 확인
- ✅ `result_data.row_count` 확인
- ✅ `execution_time` 확인

**자동 처리**:
- ✅ `thread_id` 자동 저장
- ✅ `message_id` 자동 저장

---

### 📍 단계 5: 라인별 생산량 조회

**요청 선택**: `2. Query Processing` → `라인별 생산량 조회`

**요청 본문 (Body)**:
```json
{
  "message": "라인별 생산량은?",
  "context_tag": "@현장"
}
```

**기대 효과**:
- GROUP BY line_id가 포함된 SQL 생성
- 라인별 데이터 반환

---

### 📍 단계 6: 어제 불량 조회

**요청 선택**: `2. Query Processing` → `어제 불량 조회`

**요청 본문 (Body)**:
```json
{
  "message": "어제 불량은?"
}
```

**기대 효과**:
- WHERE production_date = DATE_SUB(CURDATE(), INTERVAL 1 DAY) 포함
- 어제 데이터 필터링

---

### 📍 단계 7: 설비 상태 조회

**요청 선택**: `2. Query Processing` → `설비 가동 상태 조회`

**요청 본문 (Body)**:
```json
{
  "message": "설비 상태는?"
}
```

**기대 효과**:
- equipment_data 테이블에서 조회
- 가동/정지/점검 상태 반환

---

### 📍 단계 8: 쓰레드 목록 조회

**요청 선택**: `3. Conversation History` → `사용자 쓰레드 목록 조회`

**HTTP Method**: GET

**인증**: Authorization 헤더에 자동 포함

**예상 응답** (200 OK):
```json
[
  {
    "id": 1,
    "title": "오늘 생산량은?",
    "message_count": 2,
    "created_at": "2026-01-14T04:41:47.142547",
    "updated_at": null
  },
  {
    "id": 2,
    "title": "라인별 생산량은?",
    "message_count": 2,
    "created_at": "2026-01-14T04:41:47.313276",
    "updated_at": null
  },
  ...
]
```

**확인 사항**:
- ✅ Status Code: 200 OK
- ✅ 쓰레드 개수 확인
- ✅ 각 쓰레드의 메시지 개수 확인

---

### 📍 단계 9: 메시지 상세 조회

**요청 선택**: `3. Conversation History` → `특정 쓰레드의 메시지 조회`

**URL Path**: `/threads/{{thread_id}}/messages`

**자동 설정**: 위 단계에서 얻은 `thread_id` 자동 사용

**예상 응답** (200 OK):
```json
[
  {
    "id": 1,
    "thread_id": 1,
    "role": "user",
    "message": "오늘 생산량은?",
    "corrected_msg": null,
    "gen_sql": null,
    "result_data": null,
    "context_tag": "@현장",
    "created_at": "2026-01-14T04:41:47.142547"
  },
  {
    "id": 2,
    "thread_id": 1,
    "role": "assistant",
    "message": "생산 데이터 조회 결과 9행 반환",
    "corrected_msg": "CURDATE() 생산량은?",
    "gen_sql": "SELECT * FROM production_data ORDER BY id DESC LIMIT 100;",
    "result_data": {
      "columns": ["id", "line_id", ...],
      "rows": [...],
      "row_count": 9
    },
    "context_tag": "@현장",
    "created_at": "2026-01-14T04:41:47.200000"
  }
]
```

---

### 📍 단계 10: 헬스 체크

**요청 선택**: `4. System` → `헬스 체크`

**HTTP Method**: GET

**인증**: 불필요

**예상 응답** (200 OK):
```json
{
  "status": "healthy",
  "postgresql": "connected",
  "mysql": "connected"
}
```

**확인 사항**:
- ✅ Status: healthy
- ✅ PostgreSQL: connected
- ✅ MySQL: connected

---

## API 엔드포인트 상세

### 인증 API

#### 회원가입
```
POST /api/v1/auth/signup
Content-Type: application/json

Body:
{
  "email": "user@example.com",
  "password": "SecurePass123!",
  "name": "사용자 이름",
  "employee_id": "20240001",
  "dept_name": "부서명",
  "position": "직급"
}

Response: 201 Created
{
  "access_token": "string",
  "refresh_token": "string",
  "user": {...}
}
```

#### 로그인
```
POST /api/v1/auth/login
Content-Type: application/json

Body:
{
  "email": "user@example.com",
  "password": "SecurePass123!"
}

Response: 200 OK
{
  "access_token": "string",
  "refresh_token": "string",
  "user": {...}
}
```

#### 현재 사용자 정보
```
GET /api/v1/auth/me
Authorization: Bearer {{access_token}}

Response: 200 OK
{
  "id": 1,
  "email": "user@example.com",
  "name": "사용자 이름",
  ...
}
```

---

### 쿼리 처리 API

#### 쿼리 실행
```
POST /api/v1/query
Authorization: Bearer {{access_token}}
Content-Type: application/json

Body:
{
  "message": "자연어 질문",
  "context_tag": "@현장 (선택)",
  "thread_id": 1 (선택)
}

Response: 200 OK
{
  "thread_id": 1,
  "message_id": 1,
  "original_message": "string",
  "corrected_message": "string",
  "generated_sql": "string",
  "result_data": {
    "columns": ["col1", "col2"],
    "rows": [{...}, {...}],
    "row_count": 9
  },
  "execution_time": 48.71,
  "created_at": "2026-01-14T..."
}
```

#### 사용자 쓰레드 목록
```
GET /api/v1/query/threads
Authorization: Bearer {{access_token}}

Response: 200 OK
[
  {
    "id": 1,
    "title": "string",
    "message_count": 2,
    "created_at": "2026-01-14T...",
    "updated_at": null
  }
]
```

#### 쓰레드 메시지
```
GET /api/v1/query/threads/{thread_id}/messages
Authorization: Bearer {{access_token}}

Response: 200 OK
[
  {
    "id": 1,
    "thread_id": 1,
    "role": "user",
    "message": "string",
    ...
  }
]
```

---

## 테스트 시나리오

### 시나리오 1: 전체 플로우

1. ✅ 회원가입
2. ✅ 로그인 (토큰 획득)
3. ✅ 사용자 정보 확인
4. ✅ 기본 쿼리 실행
5. ✅ 라인별 쿼리 실행
6. ✅ 쓰레드 목록 조회
7. ✅ 메시지 상세 조회
8. ✅ 헬스 체크

**예상 시간**: 2-3분

---

### 시나리오 2: 다양한 쿼리 테스트

```
요청들:
1. "오늘 생산량은?"
2. "라인별 생산량은?"
3. "어제 불량은?"
4. "설비 상태는?"
5. "지난주 생산량은?"
6. "불량률은?"

각 요청마다:
- 생성된 SQL 확인
- 결과 행 수 확인
- 실행 시간 확인
```

---

### 시나리오 3: 대화 히스토리

```
1. 3개 이상의 다른 질문 실행
2. /threads 엔드포인트로 쓰레드 목록 확인
3. 각 thread_id로 /messages 엔드포인트 확인
4. 사용자 질문과 AI 응답이 저장되었는지 확인
```

---

## 응답 해석 방법

### Response 탭에서 확인할 항목

1. **Status Code**
   - 200 OK: 성공
   - 201 Created: 생성 성공
   - 400 Bad Request: 입력 오류
   - 401 Unauthorized: 인증 실패
   - 500 Internal Server Error: 서버 오류

2. **Body**
   - JSON 형식 확인
   - 필수 필드 존재 여부

3. **Headers**
   - Content-Type: application/json 확인

### Console 탭에서 확인

- 자동 실행된 스크립트 로그
- 토큰 저장 확인
- 변수 할당 확인

---

## Pretty vs Raw 표시

### Pretty 탭 (권장)
```
보기 좋은 JSON 포맷
{
  "key": "value",
  ...
}
```

### Raw 탭
```
한 줄로 표시된 JSON
{"key":"value",...}
```

---

## 문제 해결

### Q1: "인증 토큰이 없습니다" 오류

**원인**: Authorization 헤더가 누락됨

**해결책**:
1. 로그인 단계 재실행
2. 환경 변수에서 `access_token` 확인
3. Header에 `Authorization: Bearer {{access_token}}` 추가

### Q2: "쓰레드를 찾을 수 없습니다" 오류

**원인**: thread_id가 잘못되었거나 권한이 없음

**해결책**:
1. 쿼리 실행 후 응답에서 `thread_id` 확인
2. `/threads` 엔드포인트로 올바른 thread_id 확인
3. 환경 변수에서 `{{thread_id}}` 확인

### Q3: "테이블을 찾을 수 없습니다" 오류

**원인**: MySQL 테이블이 생성되지 않음

**해결책**:
```bash
# MySQL 테이블 생성 확인
docker exec exaone_mysql mysql -u exaone_user -pexaone_password manufacturing -e "SHOW TABLES;"
```

### Q4: Status 500 Internal Server Error

**확인 사항**:
1. 서버 로그 확인
   ```bash
   docker logs exaone_fastapi | tail -50
   ```
2. 데이터베이스 연결 확인
   ```bash
   docker logs exaone_fastapi | grep -E "PostgreSQL|MySQL"
   ```
3. 헬스 체크 실행

---

## 팁과 트릭

### 팁 1: 변수 사용

URL에 변수 사용:
```
{{access_token}}    # 토큰
{{thread_id}}       # 쓰레드 ID
{{user_id}}         # 사용자 ID
```

### 팁 2: Pre-request Script

요청 전에 자동으로 실행되는 스크립트 추가:
```javascript
pm.environment.set("timestamp", Date.now());
```

### 팁 3: Tests 탭

응답 검증 및 변수 저장:
```javascript
pm.test("Status code is 200", function () {
    pm.response.to.have.status(200);
});

pm.environment.set("access_token", pm.response.json().access_token);
```

### 팁 4: 요청 복제

자주 사용하는 요청은:
1. 요청 오른쪽 클릭
2. Duplicate 선택
3. 이름 변경

---

## 컬렉션 공유

### 팀원과 공유

1. **Postman 계정 필요**
2. **File** → **Share** 클릭
3. 팀원 이메일 입력
4. 권한 설정

---

## 자주 묻는 질문

**Q: 컬렉션이 최신 상태인가요?**
A: 컬렉션은 API 변경 시 수동으로 업데이트해야 합니다.

**Q: 여러 환경을 사용할 수 있나요?**
A: 네, 개발/테스트/프로덕션 환경을 각각 생성할 수 있습니다.

**Q: 대량 요청을 보낼 수 있나요?**
A: Collection Runner를 사용하면 여러 요청을 순차적으로 실행 가능합니다.

---

## 추가 리소스

- [Postman 공식 문서](https://learning.postman.com/)
- [API 문서](http://localhost:8080/docs)
- [테스트 결과 보고서](./TEST_RESULTS.md)

---

**문서 작성**: 2026-01-14
**Postman 버전**: 11.0 이상 권장
