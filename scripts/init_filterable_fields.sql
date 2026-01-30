-- FilterableField 초기 데이터 등록
-- 사출 성형 공장의 기본 필터 항목

-- 1. 사출기 (machine_id)
INSERT INTO admin_filterable_fields
(field_name, display_name, description, field_type, extraction_pattern, extraction_keywords, value_mapping, is_optional, multiple_allowed)
VALUES
('machine_id', '사출기', '사출 기계 ID', 'numeric', '\d+',
 '["1번", "1호", "1호기", "사출기 1", "기계 1", "2번", "2호", "2호기", "사출기 2", "기계 2", "3번", "3호", "3호기", "사출기 3", "기계 3", "4번", "4호", "4호기", "사출기 4", "기계 4", "5번", "5호", "5호기", "사출기 5", "기계 5"]',
 NULL, true, false)
ON CONFLICT DO NOTHING;

-- 2. 날짜 (cycle_date)
INSERT INTO admin_filterable_fields
(field_name, display_name, description, field_type, extraction_pattern, extraction_keywords, value_mapping, is_optional, multiple_allowed)
VALUES
('cycle_date', '날짜', '사이클 실행 날짜', 'date', '\d{4}-\d{2}-\d{2}|\d{4}년\s*\d{1,2}월\s*\d{1,2}일',
 '["오늘", "어제", "내일", "지난주", "이번주", "지난달", "이번달", "모레", "그저께"]',
 '{"오늘": "CURDATE()", "어제": "DATE_SUB(CURDATE(), INTERVAL 1 DAY)", "내일": "DATE_ADD(CURDATE(), INTERVAL 1 DAY)", "지난주": "DATE_SUB(CURDATE(), INTERVAL 7 DAY)", "이번주": "DATE_FORMAT(CURDATE(), ''%Y-%m-01'')", "지난달": "DATE_SUB(CURDATE(), INTERVAL 1 MONTH)", "이번달": "DATE_FORMAT(CURDATE(), ''%Y-%m-01'')", "모레": "DATE_ADD(CURDATE(), INTERVAL 1 DAY)", "그저께": "DATE_SUB(CURDATE(), INTERVAL 2 DAY)"}',
 true, false)
ON CONFLICT DO NOTHING;

-- 3. 금형 (mold_id)
INSERT INTO admin_filterable_fields
(field_name, display_name, description, field_type, extraction_pattern, extraction_keywords, value_mapping, is_optional, multiple_allowed)
VALUES
('mold_id', '금형', '사용된 금형 ID', 'numeric', '\d+',
 '["금형", "DC", "DC1", "DC2"]',
 NULL, true, true)
ON CONFLICT DO NOTHING;

-- 4. 재료 (material_id)
INSERT INTO admin_filterable_fields
(field_name, display_name, description, field_type, extraction_pattern, extraction_keywords, value_mapping, is_optional, multiple_allowed)
VALUES
('material_id', '재료', '원재료 ID', 'numeric', '\d+',
 '["HIPS", "PP", "재료"]',
 NULL, true, true)
ON CONFLICT DO NOTHING;
