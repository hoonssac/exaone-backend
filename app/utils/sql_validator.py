"""
SQL 안전성 검증 모듈

목적:
- SQL Injection 방지
- 위험한 쿼리 블로킹 (INSERT, UPDATE, DELETE, DROP 등)
- LIMIT 강제 추가 (대량 데이터 전송 방지)

검증 규칙:
1. SELECT만 허용 (읽기 전용)
2. 위험한 키워드 차단
3. 주석 제거
4. 세미콜론 검사 (다중 쿼리 방지)
5. LIMIT 자동 추가
"""

import re
from typing import Tuple
import sqlparse
from sqlparse.sql import IdentifierList, Identifier, Where, Function
from sqlparse.tokens import Keyword, DML


class SQLValidator:
    """SQL 쿼리 안전성 검증 클래스"""

    # 차단할 위험한 키워드 (대소문자 무시)
    DANGEROUS_KEYWORDS = [
        "INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "CREATE",
        "TRUNCATE", "EXEC", "EXECUTE", "SLEEP", "LOAD_FILE",
        "INTO OUTFILE", "INTO DUMPFILE", "UNION", "WITH",
        "PRAGMA", "ATTACH", "DETACH", "REPLACE", "RENAME",
    ]

    # 차단할 위험한 함수
    DANGEROUS_FUNCTIONS = [
        "SLEEP", "BENCHMARK", "LOAD_FILE", "OUTFILE",
        "SYSTEM", "SHELL_EXEC", "EVAL", "EXEC",
    ]

    # 신뢰할 수 있는 함수
    SAFE_FUNCTIONS = [
        "SUM", "COUNT", "AVG", "MIN", "MAX", "ROUND",
        "CONCAT", "SUBSTR", "LENGTH", "UPPER", "LOWER",
        "CAST", "COALESCE", "DATE", "DATE_ADD", "DATE_SUB",
        "YEAR", "MONTH", "DAY", "HOUR", "MINUTE", "SECOND",
        "NOW", "CURDATE", "CURTIME", "ABS", "SQRT", "POWER",
        "MOD", "FLOOR", "CEIL", "DATE_TRUNC", "EXTRACT",
    ]

    @staticmethod
    def validate(sql: str) -> Tuple[bool, str]:
        """
        SQL 쿼리 안전성 검증

        Args:
            sql: 검증할 SQL 쿼리

        Returns:
            (is_valid, error_message)
            - is_valid: True이면 안전, False이면 위험
            - error_message: 검증 실패 이유
        """
        if not sql or not sql.strip():
            return False, "빈 쿼리입니다"

        # 1. 주석 제거
        sql_clean = SQLValidator.remove_comments(sql)

        # 2. 공백 정규화
        sql_clean = " ".join(sql_clean.split())

        # 3. 세미콜론 검사 (다중 쿼리 방지)
        # 마지막 세미콜론은 허용
        sql_trimmed = sql_clean.rstrip(";")
        if ";" in sql_trimmed:
            return False, "다중 쿼리는 허용되지 않습니다"

        # 4. SELECT 쿼리만 허용
        sql_upper = sql_clean.upper().strip()
        if not sql_upper.startswith("SELECT"):
            return False, "SELECT 쿼리만 허용됩니다"

        # 5. 위험한 키워드 검사
        for keyword in SQLValidator.DANGEROUS_KEYWORDS:
            # 정확한 단어 매칭 (예: UPDATE는 차단하지만 UPDATES는 허용)
            if re.search(rf'\b{re.escape(keyword)}\b', sql_clean, re.IGNORECASE):
                return False, f"허용되지 않는 키워드: {keyword}"

        # 6. 위험한 함수 검사
        for func in SQLValidator.DANGEROUS_FUNCTIONS:
            if re.search(rf'{re.escape(func)}\s*\(', sql_clean, re.IGNORECASE):
                return False, f"허용되지 않는 함수: {func}"

        # 7. 위험한 패턴 검사
        dangerous_patterns = [
            r"--\s*.*",  # SQL 주석 (혹시 모르니)
            r"/\*.*?\*/",  # 블록 주석 (혹시 모르니)
            r"xp_",  # SQL Server 확장 프로시저
            r"sp_",  # SQL Server 시스템 프로시저
            r"@@",  # SQL Server 글로벌 변수
            r"0x[0-9a-f]+",  # 16진수 인코딩 (바이너리 데이터)
        ]

        for pattern in dangerous_patterns:
            if re.search(pattern, sql_clean, re.IGNORECASE):
                return False, f"위험한 패턴이 감지되었습니다: {pattern}"

        # 8. 테이블 이름 검증 (필요시)
        # 테이블은 알파벳, 숫자, 언더스코어만 허용
        tables = SQLValidator.extract_tables(sql_clean)
        for table in tables:
            if not re.match(r'^[a-zA-Z0-9_]+$', table):
                return False, f"잘못된 테이블 이름: {table}"

        return True, ""

    @staticmethod
    def add_limit(sql: str, limit: int = 100) -> str:
        """
        LIMIT 절 자동 추가

        이미 LIMIT이 있으면 그대로 두고,
        없으면 지정된 LIMIT 값을 추가합니다.

        Args:
            sql: SQL 쿼리
            limit: LIMIT 값 (기본값: 100)

        Returns:
            LIMIT이 추가된 SQL
        """
        if not sql:
            return sql

        sql_upper = sql.upper()

        # 이미 LIMIT이 있으면 그대로 반환
        if "LIMIT" in sql_upper:
            return sql

        # LIMIT 추가
        sql = sql.rstrip(";").strip()
        return f"{sql} LIMIT {limit};"

    @staticmethod
    def remove_comments(sql: str) -> str:
        """
        SQL 주석 제거

        제거 대상:
        - 한 줄 주석: -- 또는 #
        - 블록 주석: /* ... */
        - MySQL 주석: ;!50000...*/

        Args:
            sql: 원본 SQL

        Returns:
            주석이 제거된 SQL
        """
        # 블록 주석 제거: /* ... */
        sql = re.sub(r'/\*.*?\*/', '', sql, flags=re.DOTALL)

        # 한 줄 주석 제거: -- ... 또는 # ...
        sql = re.sub(r'--[^\n]*', '', sql)
        sql = re.sub(r'#[^\n]*', '', sql)

        return sql

    @staticmethod
    def extract_tables(sql: str) -> list:
        """
        SQL에서 테이블명 추출

        FROM 또는 JOIN 뒤의 테이블명을 추출합니다.

        Args:
            sql: SQL 쿼리

        Returns:
            테이블 이름 리스트
        """
        tables = []

        try:
            parsed = sqlparse.parse(sql)[0]

            # FROM 키워드 찾기
            from_seen = False
            for token in parsed.tokens:
                # FROM 키워드 감지
                if token.ttype is Keyword and token.value.upper() == 'FROM':
                    from_seen = True
                    continue

                # FROM 뒤의 첫 번째 식별자가 테이블
                if from_seen:
                    if isinstance(token, IdentifierList):
                        # 여러 테이블 (콤마로 구분)
                        for identifier in token.get_identifiers():
                            table_name = str(identifier).split()[0]
                            tables.append(table_name)
                        from_seen = False
                    elif isinstance(token, Identifier):
                        table_name = token.get_real_name()
                        if table_name:
                            tables.append(table_name)
                        from_seen = False
                    elif token.ttype is Keyword:
                        # WHERE 등 다른 키워드를 만나면 종료
                        if token.value.upper() in ['WHERE', 'GROUP', 'ORDER', 'LIMIT']:
                            from_seen = False

        except Exception:
            # 파싱 실패 시 정규표현식으로 대체
            pattern = r'FROM\s+([a-zA-Z0-9_]+)'
            matches = re.findall(pattern, sql, re.IGNORECASE)
            tables.extend(matches)

        return list(set(tables))  # 중복 제거

    @staticmethod
    def sanitize(sql: str, limit: int = 100) -> str:
        """
        SQL 쿼리 완전 정제

        다음을 순서대로 수행:
        1. 주석 제거
        2. 공백 정규화
        3. LIMIT 추가

        Args:
            sql: 원본 SQL
            limit: LIMIT 값

        Returns:
            정제된 SQL
        """
        # 1. 주석 제거
        sql = SQLValidator.remove_comments(sql)

        # 2. 공백 정규화
        sql = " ".join(sql.split())

        # 3. LIMIT 추가
        sql = SQLValidator.add_limit(sql, limit)

        return sql

    @staticmethod
    def explain_validation_error(error_msg: str) -> str:
        """
        검증 에러 메시지를 사용자 친화적으로 변환

        Args:
            error_msg: 기술적 에러 메시지

        Returns:
            사용자 친화적 메시지
        """
        error_explanations = {
            "빈 쿼리입니다": "검색 쿼리를 입력해주세요.",
            "SELECT 쿼리만 허용됩니다": "데이터 조회(SELECT) 쿼리만 사용 가능합니다.",
            "다중 쿼리는 허용되지 않습니다": "한 번에 하나의 쿼리만 실행 가능합니다.",
            "허용되지 않는 키워드": "사용할 수 없는 SQL 키워드가 포함되어 있습니다.",
            "허용되지 않는 함수": "사용할 수 없는 함수가 포함되어 있습니다.",
            "위험한 패턴이 감지되었습니다": "보안상 문제가 있는 쿼리입니다.",
            "잘못된 테이블 이름": "테이블 이름이 올바르지 않습니다.",
        }

        for key, value in error_explanations.items():
            if key in error_msg:
                return value

        return "쿼리가 검증 규칙을 위반했습니다."


# ============================================================================
# 테스트 및 예제
# ============================================================================

def test_sql_validator():
    """SQL Validator 테스트"""
    test_cases = [
        # (sql, should_pass, description)
        ("SELECT * FROM production_data LIMIT 10;", True, "정상 SELECT"),
        ("SELECT SUM(actual_quantity) FROM production_data WHERE production_date = CURDATE();", True, "집계 함수"),
        ("INSERT INTO production_data VALUES (...);", False, "INSERT 차단"),
        ("DELETE FROM production_data;", False, "DELETE 차단"),
        ("SELECT * FROM production_data; DROP TABLE users;", False, "다중 쿼리 차단"),
        ("SELECT * FROM production_data -- comment", True, "주석 제거 후 허용"),
        ("SELECT * FROM production_data /*comment*/;", True, "블록 주석 제거"),
        ("SELECT * FROM production_data WHERE id = 1 UNION SELECT * FROM users;", False, "UNION 차단"),
        ("SELECT SLEEP(5) FROM production_data;", False, "위험한 함수 차단"),
        ("SELECT * FROM production_data WHERE id = 0x31;", False, "16진수 인코딩 차단"),
    ]

    print("=" * 60)
    print("SQL Validator 테스트")
    print("=" * 60)

    passed = 0
    failed = 0

    for sql, should_pass, description in test_cases:
        is_valid, error = SQLValidator.validate(sql)

        if is_valid == should_pass:
            status = "✅ PASS"
            passed += 1
        else:
            status = "❌ FAIL"
            failed += 1

        print(f"\n{status} - {description}")
        print(f"  SQL: {sql[:60]}...")
        print(f"  Expected: {should_pass}, Got: {is_valid}")
        if error:
            print(f"  Error: {error}")

    print("\n" + "=" * 60)
    print(f"결과: {passed} 통과, {failed} 실패")
    print("=" * 60)


if __name__ == "__main__":
    # 테스트 실행
    test_sql_validator()

    # 예제 1: LIMIT 추가
    print("\n📝 예제 1: LIMIT 자동 추가")
    sql = "SELECT * FROM production_data WHERE production_date = CURDATE()"
    sanitized = SQLValidator.sanitize(sql)
    print(f"  원본:     {sql}")
    print(f"  정제됨:   {sanitized}")

    # 예제 2: 주석 제거
    print("\n📝 예제 2: 주석 제거")
    sql_with_comments = "SELECT * FROM production_data -- 생산 데이터 조회\nWHERE production_date = CURDATE();"
    cleaned = SQLValidator.remove_comments(sql_with_comments)
    print(f"  원본:     {repr(sql_with_comments)}")
    print(f"  정제됨:   {repr(cleaned)}")

    # 예제 3: 테이블 추출
    print("\n📝 예제 3: 테이블명 추출")
    sql = "SELECT * FROM production_data JOIN equipment_data ON production_data.line_id = equipment_data.line_id"
    tables = SQLValidator.extract_tables(sql)
    print(f"  SQL:      {sql}")
    print(f"  테이블:   {tables}")
