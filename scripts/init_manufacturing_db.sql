-- ============================================================================
-- EXAONE Manufacturing Database Initialization
-- ============================================================================

USE manufacturing;

-- ============================================================================
-- 1. production_data 테이블 (생산 데이터)
-- ============================================================================

CREATE TABLE production_data (
    id BIGINT PRIMARY KEY AUTO_INCREMENT COMMENT '생산 ID',
    line_id VARCHAR(50) NOT NULL COMMENT '라인 ID',
    product_code VARCHAR(50) NOT NULL COMMENT '제품 코드',
    product_name VARCHAR(100) NOT NULL COMMENT '제품명',
    planned_quantity INT NOT NULL COMMENT '계획 생산량',
    actual_quantity INT NOT NULL COMMENT '실제 생산량',
    defect_quantity INT NOT NULL DEFAULT 0 COMMENT '불량 수량',
    production_date DATE NOT NULL COMMENT '생산 일자',
    production_hour TINYINT NOT NULL COMMENT '생산 시간 (0-23)',
    shift VARCHAR(10) COMMENT '근무 조 (주간/야간)',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '등록 일시',
    INDEX idx_date (production_date),
    INDEX idx_line (line_id),
    INDEX idx_product (product_code)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT '생산 실적 데이터';

-- ============================================================================
-- 2. defect_data 테이블 (불량 데이터)
-- ============================================================================

CREATE TABLE defect_data (
    id BIGINT PRIMARY KEY AUTO_INCREMENT COMMENT '불량 ID',
    production_id BIGINT NOT NULL COMMENT 'production_data 외래키',
    defect_code VARCHAR(50) NOT NULL COMMENT '불량 코드',
    defect_name VARCHAR(100) NOT NULL COMMENT '불량명',
    defect_quantity INT NOT NULL COMMENT '불량 수량',
    defect_rate DECIMAL(5,2) COMMENT '불량률 (%)',
    defect_type VARCHAR(50) COMMENT '불량 유형 (외관/기능/치수)',
    detected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '감지 일시',
    FOREIGN KEY (production_id) REFERENCES production_data(id) ON DELETE CASCADE,
    INDEX idx_code (defect_code),
    INDEX idx_type (defect_type)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT '불량 데이터';

-- ============================================================================
-- 3. equipment_data 테이블 (설비 데이터)
-- ============================================================================

CREATE TABLE equipment_data (
    id BIGINT PRIMARY KEY AUTO_INCREMENT COMMENT '설비 데이터 ID',
    equipment_id VARCHAR(50) NOT NULL COMMENT '설비 ID',
    equipment_name VARCHAR(100) NOT NULL COMMENT '설비명',
    line_id VARCHAR(50) NOT NULL COMMENT '라인 ID',
    status VARCHAR(20) NOT NULL COMMENT '가동 상태 (가동/정지/점검)',
    operation_time INT COMMENT '가동 시간 (분)',
    downtime INT COMMENT '정지 시간 (분)',
    downtime_reason VARCHAR(255) COMMENT '정지 사유',
    recorded_date DATE NOT NULL COMMENT '기록 일자',
    recorded_hour TINYINT COMMENT '기록 시간 (0-23)',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '등록 일시',
    INDEX idx_equipment (equipment_id),
    INDEX idx_status (status),
    INDEX idx_date (recorded_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT '설비 가동 데이터';

-- ============================================================================
-- 4. VIEW: 일별 생산 통계
-- ============================================================================

CREATE VIEW daily_production_summary AS
SELECT
    production_date,
    line_id,
    product_code,
    product_name,
    SUM(planned_quantity) as total_planned,
    SUM(actual_quantity) as total_actual,
    SUM(defect_quantity) as total_defect,
    ROUND(SUM(actual_quantity) / SUM(planned_quantity) * 100, 2) as achievement_rate,
    ROUND(SUM(defect_quantity) / SUM(actual_quantity) * 100, 2) as defect_rate
FROM production_data
GROUP BY production_date, line_id, product_code, product_name;

-- ============================================================================
-- 5. VIEW: 시간별 생산 통계
-- ============================================================================

CREATE VIEW hourly_production_summary AS
SELECT
    production_date,
    production_hour,
    line_id,
    SUM(actual_quantity) as hourly_quantity,
    SUM(defect_quantity) as hourly_defect,
    ROUND(AVG(defect_quantity * 100.0 / actual_quantity), 2) as hourly_defect_rate
FROM production_data
WHERE actual_quantity > 0
GROUP BY production_date, production_hour, line_id;

-- ============================================================================
-- 6. 샘플 데이터 생성 (최근 7일치)
-- ============================================================================

-- 현재 날짜 기준 생산 데이터 (150행)
INSERT INTO production_data
(line_id, product_code, product_name, planned_quantity, actual_quantity, defect_quantity, production_date, production_hour, shift)
VALUES
-- 2026-01-14 (오늘)
('LINE-01', 'P001', '제품A', 1000, 980, 15, '2026-01-14', 8, '주간'),
('LINE-01', 'P001', '제품A', 1000, 950, 25, '2026-01-14', 9, '주간'),
('LINE-01', 'P001', '제품A', 1000, 990, 10, '2026-01-14', 10, '주간'),
('LINE-01', 'P001', '제품A', 1000, 1000, 8, '2026-01-14', 11, '주간'),
('LINE-01', 'P001', '제품A', 1000, 970, 20, '2026-01-14', 12, '주간'),
('LINE-01', 'P001', '제품A', 1000, 985, 12, '2026-01-14', 13, '주간'),
('LINE-01', 'P001', '제품A', 1000, 995, 5, '2026-01-14', 14, '주간'),
('LINE-01', 'P001', '제품A', 1000, 1000, 6, '2026-01-14', 15, '주간'),
('LINE-02', 'P002', '제품B', 800, 780, 20, '2026-01-14', 8, '주간'),
('LINE-02', 'P002', '제품B', 800, 750, 35, '2026-01-14', 9, '주간'),
('LINE-02', 'P002', '제품B', 800, 790, 15, '2026-01-14', 10, '주간'),
('LINE-02', 'P002', '제품B', 800, 800, 10, '2026-01-14', 11, '주간'),
('LINE-02', 'P002', '제품B', 800, 770, 25, '2026-01-14', 12, '주간'),
('LINE-02', 'P002', '제품B', 800, 785, 18, '2026-01-14', 13, '주간'),
('LINE-02', 'P002', '제품B', 800, 795, 12, '2026-01-14', 14, '주간'),
('LINE-02', 'P002', '제품B', 800, 800, 8, '2026-01-14', 15, '주간'),
('LINE-03', 'P003', '제품C', 600, 580, 18, '2026-01-14', 8, '주간'),
('LINE-03', 'P003', '제품C', 600, 560, 30, '2026-01-14', 9, '주간'),
('LINE-03', 'P003', '제품C', 600, 590, 12, '2026-01-14', 10, '주간'),
('LINE-03', 'P003', '제품C', 600, 600, 8, '2026-01-14', 11, '주간'),

-- 2026-01-13 (어제)
('LINE-01', 'P001', '제품A', 1000, 960, 30, '2026-01-13', 8, '주간'),
('LINE-01', 'P001', '제품A', 1000, 940, 40, '2026-01-13', 9, '주간'),
('LINE-01', 'P001', '제품A', 1000, 980, 15, '2026-01-13', 10, '주간'),
('LINE-01', 'P001', '제품A', 1000, 990, 12, '2026-01-13', 11, '주간'),
('LINE-01', 'P001', '제품A', 1000, 950, 35, '2026-01-13', 12, '주간'),
('LINE-02', 'P002', '제품B', 800, 760, 30, '2026-01-13', 8, '주간'),
('LINE-02', 'P002', '제품B', 800, 740, 45, '2026-01-13', 9, '주간'),
('LINE-02', 'P002', '제품B', 800, 780, 20, '2026-01-13', 10, '주간'),
('LINE-02', 'P002', '제품B', 800, 790, 18, '2026-01-13', 11, '주간'),
('LINE-03', 'P003', '제품C', 600, 570, 25, '2026-01-13', 8, '주간'),

-- 2026-01-12 (2일 전)
('LINE-01', 'P001', '제품A', 1000, 970, 20, '2026-01-12', 8, '주간'),
('LINE-01', 'P001', '제품A', 1000, 950, 35, '2026-01-12', 9, '주간'),
('LINE-01', 'P001', '제품A', 1000, 980, 15, '2026-01-12', 10, '주간'),
('LINE-02', 'P002', '제품B', 800, 770, 25, '2026-01-12', 8, '주간'),
('LINE-02', 'P002', '제품B', 800, 750, 40, '2026-01-12', 9, '주간'),
('LINE-03', 'P003', '제품C', 600, 580, 20, '2026-01-12', 8, '주간'),

-- 2026-01-11 (3일 전)
('LINE-01', 'P001', '제품A', 1000, 980, 18, '2026-01-11', 8, '주간'),
('LINE-02', 'P002', '제품B', 800, 780, 22, '2026-01-11', 8, '주간'),
('LINE-03', 'P003', '제품C', 600, 590, 15, '2026-01-11', 8, '주간'),

-- 2026-01-10 (4일 전)
('LINE-01', 'P001', '제품A', 1000, 960, 28, '2026-01-10', 8, '주간'),
('LINE-02', 'P002', '제품B', 800, 760, 32, '2026-01-10', 8, '주간'),
('LINE-03', 'P003', '제품C', 600, 570, 28, '2026-01-10', 8, '주간'),

-- 2026-01-09 (5일 전)
('LINE-01', 'P001', '제품A', 1000, 975, 22, '2026-01-09', 8, '주간'),
('LINE-02', 'P002', '제품B', 800, 775, 28, '2026-01-09', 8, '주간'),
('LINE-03', 'P003', '제품C', 600, 585, 18, '2026-01-09', 8, '주간'),

-- 2026-01-08 (6일 전)
('LINE-01', 'P001', '제품A', 1000, 970, 25, '2026-01-08', 8, '주간'),
('LINE-02', 'P002', '제품B', 800, 770, 30, '2026-01-08', 8, '주간'),
('LINE-03', 'P003', '제품C', 600, 575, 22, '2026-01-08', 8, '주간');

-- ============================================================================
-- 7. 불량 데이터 샘플
-- ============================================================================

INSERT INTO defect_data
(production_id, defect_code, defect_name, defect_quantity, defect_rate, defect_type)
SELECT
    id, 'D001', '스크래치', defect_quantity * 0.5, ROUND(defect_quantity * 100.0 / actual_quantity, 2), '외관'
FROM production_data
WHERE defect_quantity > 0 AND MOD(id, 2) = 0
LIMIT 30;

-- ============================================================================
-- 8. 설비 데이터 샘플
-- ============================================================================

INSERT INTO equipment_data
(equipment_id, equipment_name, line_id, status, operation_time, downtime, downtime_reason, recorded_date, recorded_hour)
VALUES
('EQ-01-001', '프레스 기계', 'LINE-01', '가동', 480, 0, NULL, '2026-01-14', 8),
('EQ-01-002', '용접 기계', 'LINE-01', '가동', 480, 0, NULL, '2026-01-14', 8),
('EQ-02-001', '조립 라인', 'LINE-02', '정지', 420, 60, '부품 수급 지연', '2026-01-14', 8),
('EQ-02-002', '검사 기계', 'LINE-02', '가동', 480, 0, NULL, '2026-01-14', 8),
('EQ-03-001', '포장 기계', 'LINE-03', '가동', 450, 30, '청소', '2026-01-14', 8),
('EQ-01-001', '프레스 기계', 'LINE-01', '가동', 480, 0, NULL, '2026-01-13', 8),
('EQ-01-002', '용접 기계', 'LINE-01', '정지', 360, 120, '메인터넌스', '2026-01-13', 8),
('EQ-02-001', '조립 라인', 'LINE-02', '가동', 480, 0, NULL, '2026-01-13', 8),
('EQ-02-002', '검사 기계', 'LINE-02', '가동', 480, 0, NULL, '2026-01-13', 8),
('EQ-03-001', '포장 기계', 'LINE-03', '가동', 480, 0, NULL, '2026-01-13', 8);

-- ============================================================================
-- 9. 데이터 확인
-- ============================================================================

SELECT 'Production Data Created:' as Status;
SELECT COUNT(*) as row_count FROM production_data;

SELECT 'Defect Data Created:' as Status;
SELECT COUNT(*) as row_count FROM defect_data;

SELECT 'Equipment Data Created:' as Status;
SELECT COUNT(*) as row_count FROM equipment_data;

SELECT 'Daily Summary Sample:' as Status;
SELECT * FROM daily_production_summary LIMIT 5;

SELECT 'Hourly Summary Sample:' as Status;
SELECT * FROM hourly_production_summary LIMIT 5;

-- ============================================================================
-- 10. product_pricing 테이블 (제품 가격/원가)
-- ============================================================================

CREATE TABLE product_pricing (
    id BIGINT PRIMARY KEY AUTO_INCREMENT COMMENT '가격 ID',
    product_code VARCHAR(50) NOT NULL UNIQUE COMMENT '제품 코드',
    product_name VARCHAR(100) NOT NULL COMMENT '제품명',
    unit_price DECIMAL(10,2) NOT NULL COMMENT '판매 단가',
    material_cost DECIMAL(10,2) NOT NULL COMMENT '자재비',
    labor_cost DECIMAL(10,2) NOT NULL COMMENT '노무비',
    manufacturing_cost DECIMAL(10,2) NOT NULL COMMENT '제조비',
    profit_margin DECIMAL(5,2) COMMENT '이익률 (%)',
    effective_date DATE NOT NULL COMMENT '적용 시작일',
    end_date DATE COMMENT '적용 종료일',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_product (product_code)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT '제품 가격/원가';

-- ============================================================================
-- 11. worker_info 테이블 (작업자 정보)
-- ============================================================================

CREATE TABLE worker_info (
    id INT PRIMARY KEY AUTO_INCREMENT COMMENT '작업자 ID',
    worker_id VARCHAR(50) NOT NULL UNIQUE COMMENT '작업자 사번',
    worker_name VARCHAR(50) NOT NULL COMMENT '작업자명',
    line_id VARCHAR(50) NOT NULL COMMENT '라인 ID',
    position VARCHAR(50) COMMENT '직급 (기능사/숙련공/반장)',
    skill_level INT COMMENT '숙련도 레벨 (1-5)',
    hire_date DATE NOT NULL COMMENT '입사 일자',
    is_active BOOLEAN DEFAULT TRUE COMMENT '활동 여부',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_line (line_id),
    INDEX idx_active (is_active)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT '작업자 정보';

-- ============================================================================
-- 12. material_inventory 테이블 (자재 재고)
-- ============================================================================

CREATE TABLE material_inventory (
    id BIGINT PRIMARY KEY AUTO_INCREMENT COMMENT '재고 ID',
    material_code VARCHAR(50) NOT NULL COMMENT '자재 코드',
    material_name VARCHAR(100) NOT NULL COMMENT '자재명',
    current_quantity INT NOT NULL COMMENT '현재 재고량',
    reorder_point INT NOT NULL COMMENT '재주문 포인트',
    reorder_quantity INT NOT NULL COMMENT '재주문 수량',
    unit_price DECIMAL(10,2) NOT NULL COMMENT '단가',
    warehouse_location VARCHAR(50) COMMENT '보관 위치',
    last_update_date DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '마지막 업데이트',
    INDEX idx_code (material_code),
    INDEX idx_quantity (current_quantity)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT '자재 재고';

-- ============================================================================
-- 13. process_step 테이블 (공정 단계별 진행)
-- ============================================================================

CREATE TABLE process_step (
    id BIGINT PRIMARY KEY AUTO_INCREMENT COMMENT '공정 ID',
    production_id BIGINT NOT NULL COMMENT 'production_data 외래키',
    product_code VARCHAR(50) NOT NULL COMMENT '제품 코드',
    process_sequence INT NOT NULL COMMENT '공정 순서 (1,2,3...)',
    process_name VARCHAR(100) NOT NULL COMMENT '공정명',
    equipment_id VARCHAR(50) COMMENT '설비 ID',
    start_time DATETIME NOT NULL COMMENT '공정 시작 시간',
    end_time DATETIME COMMENT '공정 완료 시간',
    duration_minutes INT COMMENT '소요 시간 (분)',
    process_status VARCHAR(20) COMMENT '공정 상태 (진행중/완료/대기)',
    worker_id VARCHAR(50) COMMENT '담당 작업자',
    FOREIGN KEY (production_id) REFERENCES production_data(id) ON DELETE CASCADE,
    INDEX idx_product (product_code),
    INDEX idx_status (process_status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT '공정 단계별 진행';

-- ============================================================================
-- 14. quality_inspection 테이블 (품질 검사 상세)
-- ============================================================================

CREATE TABLE quality_inspection (
    id BIGINT PRIMARY KEY AUTO_INCREMENT COMMENT '검사 ID',
    production_id BIGINT NOT NULL COMMENT 'production_data 외래키',
    inspection_date DATE NOT NULL COMMENT '검사 일자',
    inspection_time TIME COMMENT '검사 시간',
    inspector_name VARCHAR(50) COMMENT '검사자명',
    item_code VARCHAR(50) NOT NULL COMMENT '검사 항목 코드',
    item_name VARCHAR(100) NOT NULL COMMENT '검사 항목명',
    specification VARCHAR(50) COMMENT '규격',
    measurement_value DECIMAL(10,2) COMMENT '측정값',
    pass_fail VARCHAR(10) COMMENT '합격/부적격',
    remark TEXT COMMENT '비고',
    FOREIGN KEY (production_id) REFERENCES production_data(id) ON DELETE CASCADE,
    INDEX idx_date (inspection_date),
    INDEX idx_result (pass_fail)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT '품질 검사 상세';

-- ============================================================================
-- 15. energy_consumption 테이블 (에너지 사용량)
-- ============================================================================

CREATE TABLE energy_consumption (
    id BIGINT PRIMARY KEY AUTO_INCREMENT COMMENT 'ID',
    line_id VARCHAR(50) NOT NULL COMMENT '라인 ID',
    energy_type VARCHAR(20) NOT NULL COMMENT '에너지 유형 (전력/가스/수도)',
    consumption_date DATE NOT NULL COMMENT '사용 일자',
    consumption_hour TINYINT COMMENT '사용 시간 (0-23)',
    consumption_value DECIMAL(12,2) NOT NULL COMMENT '사용량',
    unit VARCHAR(10) COMMENT '단위 (kWh/m³)',
    cost DECIMAL(10,2) COMMENT '비용',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_line (line_id),
    INDEX idx_date (consumption_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT '에너지 사용량';

-- ============================================================================
-- 16. maintenance_schedule 테이블 (설비 유지보수)
-- ============================================================================

CREATE TABLE maintenance_schedule (
    id BIGINT PRIMARY KEY AUTO_INCREMENT COMMENT '유지보수 ID',
    equipment_id VARCHAR(50) NOT NULL COMMENT '설비 ID',
    equipment_name VARCHAR(100) NOT NULL COMMENT '설비명',
    maintenance_type VARCHAR(50) COMMENT '유지보수 유형 (정기/수리/개선)',
    scheduled_date DATE NOT NULL COMMENT '예정 일자',
    actual_date DATE COMMENT '실제 시공 일자',
    technician_name VARCHAR(50) COMMENT '담당 기술자',
    description TEXT COMMENT '작업 내용',
    cost DECIMAL(10,2) COMMENT '작업 비용',
    maintenance_status VARCHAR(20) COMMENT '상태 (예정/진행중/완료)',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_equipment (equipment_id),
    INDEX idx_status (maintenance_status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT '설비 유지보수';

-- ============================================================================
-- 17. 샘플 데이터: product_pricing
-- ============================================================================

INSERT INTO product_pricing
(product_code, product_name, unit_price, material_cost, labor_cost, manufacturing_cost, profit_margin, effective_date)
VALUES
('P001', '제품A', 50000, 15000, 8000, 10000, 27, '2026-01-01'),
('P002', '제품B', 35000, 10000, 6000, 7000, 31, '2026-01-01'),
('P003', '제품C', 45000, 12000, 7500, 9000, 30, '2026-01-01');

-- ============================================================================
-- 18. 샘플 데이터: worker_info
-- ============================================================================

INSERT INTO worker_info
(worker_id, worker_name, line_id, position, skill_level, hire_date, is_active)
VALUES
('W001', '김철수', 'LINE-01', '반장', 5, '2018-03-15', TRUE),
('W002', '이영희', 'LINE-01', '숙련공', 4, '2019-06-10', TRUE),
('W003', '박민준', 'LINE-01', '기능사', 2, '2023-01-20', TRUE),
('W004', '최지원', 'LINE-02', '반장', 5, '2017-09-01', TRUE),
('W005', '정민석', 'LINE-02', '숙련공', 3, '2020-05-15', TRUE),
('W006', '손예은', 'LINE-03', '반장', 4, '2019-02-10', TRUE),
('W007', '윤지호', 'LINE-03', '기능사', 2, '2023-08-01', TRUE);

-- ============================================================================
-- 19. 샘플 데이터: material_inventory
-- ============================================================================

INSERT INTO material_inventory
(material_code, material_name, current_quantity, reorder_point, reorder_quantity, unit_price, warehouse_location)
VALUES
('M001', '부품A (금속)', 5000, 1000, 2000, 500, 'A-01-01'),
('M002', '부품B (플라스틱)', 3500, 800, 1500, 300, 'A-01-02'),
('M003', '부품C (고무)', 2800, 500, 1000, 150, 'A-01-03'),
('M004', '접착제', 1200, 300, 500, 5000, 'A-02-01'),
('M005', '윤활유', 800, 200, 300, 8000, 'A-02-02'),
('M006', '포장재', 15000, 2000, 5000, 100, 'A-03-01');

-- ============================================================================
-- 20. 샘플 데이터: process_step
-- ============================================================================

INSERT INTO process_step
(production_id, product_code, process_sequence, process_name, equipment_id, start_time, end_time, duration_minutes, process_status, worker_id)
SELECT
    id, product_code, 1, '재단', 'EQ-01-001',
    CONCAT(production_date, ' ', LPAD(production_hour, 2, '0'), ':00:00'),
    CONCAT(production_date, ' ', LPAD(production_hour+1, 2, '0'), ':30:00'),
    90, '완료', 'W001'
FROM production_data
WHERE production_date = '2026-01-14'
LIMIT 10;

INSERT INTO process_step
(production_id, product_code, process_sequence, process_name, equipment_id, start_time, process_status, worker_id)
SELECT
    id, product_code, 2, '검사', 'EQ-02-001',
    CONCAT(production_date, ' ', LPAD(production_hour+2, 2, '0'), ':00:00'),
    '진행중', 'W004'
FROM production_data
WHERE production_date = '2026-01-14'
LIMIT 10;

-- ============================================================================
-- 21. 샘플 데이터: quality_inspection
-- ============================================================================

INSERT INTO quality_inspection
(production_id, inspection_date, inspector_name, item_code, item_name, specification, measurement_value, pass_fail, remark)
SELECT
    id, production_date, '김철수', 'Q001', '길이 검사', '±0.5mm', 100.2, '합격', '정상'
FROM production_data
WHERE production_date = '2026-01-14'
LIMIT 8;

INSERT INTO quality_inspection
(production_id, inspection_date, inspector_name, item_code, item_name, specification, measurement_value, pass_fail, remark)
SELECT
    id, production_date, '김철수', 'Q002', '외관 검사', '흠집 없음', NULL, IF(defect_quantity > 20, '부적격', '합격'), IF(defect_quantity > 20, '흠집 발견', '정상')
FROM production_data
WHERE production_date = '2026-01-14' AND defect_quantity > 0
LIMIT 5;

-- ============================================================================
-- 22. 샘플 데이터: energy_consumption
-- ============================================================================

INSERT INTO energy_consumption
(line_id, energy_type, consumption_date, consumption_hour, consumption_value, unit, cost)
VALUES
('LINE-01', '전력', '2026-01-14', 8, 125.5, 'kWh', 18825),
('LINE-01', '전력', '2026-01-14', 9, 132.3, 'kWh', 19845),
('LINE-02', '전력', '2026-01-14', 8, 98.5, 'kWh', 14775),
('LINE-02', '전력', '2026-01-14', 9, 105.2, 'kWh', 15780),
('LINE-03', '전력', '2026-01-14', 8, 75.8, 'kWh', 11370),
('LINE-03', '전력', '2026-01-14', 9, 82.4, 'kWh', 12360),
('LINE-01', '가스', '2026-01-14', 8, 45.2, 'm³', 9040),
('LINE-02', '가스', '2026-01-14', 8, 32.5, 'm³', 6500);

-- ============================================================================
-- 23. 샘플 데이터: maintenance_schedule
-- ============================================================================

INSERT INTO maintenance_schedule
(equipment_id, equipment_name, maintenance_type, scheduled_date, actual_date, technician_name, description, cost, maintenance_status)
VALUES
('EQ-01-001', '프레스 기계', '정기', '2026-01-15', NULL, '이영희', '정기 점검 예정', 500000, '예정'),
('EQ-01-002', '용접 기계', '수리', '2026-01-13', '2026-01-13', '박민준', '용접 토치 교체', 350000, '완료'),
('EQ-02-001', '조립 라인', '개선', '2026-01-20', NULL, '최지원', '생산성 개선 프로젝트', 1000000, '예정'),
('EQ-03-001', '포장 기계', '정기', '2026-01-10', '2026-01-10', '손예은', '윤활유 교체', 200000, '완료');

-- ============================================================================
-- 24. 확장 데이터 확인
-- ============================================================================

SELECT '=== EXTENDED DATA SUMMARY ===' as Status;

SELECT 'Product Pricing:' as Table_Name;
SELECT COUNT(*) as row_count FROM product_pricing;

SELECT 'Worker Info:' as Table_Name;
SELECT COUNT(*) as row_count FROM worker_info;

SELECT 'Material Inventory:' as Table_Name;
SELECT COUNT(*) as row_count FROM material_inventory;

SELECT 'Process Step:' as Table_Name;
SELECT COUNT(*) as row_count FROM process_step;

SELECT 'Quality Inspection:' as Table_Name;
SELECT COUNT(*) as row_count FROM quality_inspection;

SELECT 'Energy Consumption:' as Table_Name;
SELECT COUNT(*) as row_count FROM energy_consumption;

SELECT 'Maintenance Schedule:' as Table_Name;
SELECT COUNT(*) as row_count FROM maintenance_schedule;

-- ============================================================================
-- 25. 대량 더미 데이터 생성 (최근 30일, 3개 라인, 매시간 데이터)
-- ============================================================================

-- 임시 절차 제거 (재실행 시 오류 방지)
DROP PROCEDURE IF EXISTS generate_production_data;

DELIMITER //

CREATE PROCEDURE generate_production_data()
BEGIN
    DECLARE date_counter DATE;
    DECLARE end_date DATE;
    DECLARE hour_counter INT;
    DECLARE line_counter INT;
    DECLARE product_counter INT;
    DECLARE quantity_variance INT;

    SET date_counter = DATE_SUB(CURDATE(), INTERVAL 30 DAY);
    SET end_date = CURDATE();

    WHILE date_counter <= end_date DO
        SET hour_counter = 8;  -- 08:00 부터 시작

        WHILE hour_counter <= 22 DO  -- 22:00 까지
            SET line_counter = 1;

            WHILE line_counter <= 3 DO
                SET product_counter = line_counter;
                SET quantity_variance = FLOOR(RAND() * 100) - 50;  -- -50 ~ 50 변동

                INSERT INTO production_data
                (line_id, product_code, product_name, planned_quantity, actual_quantity, defect_quantity, production_date, production_hour, shift)
                VALUES
                (
                    CONCAT('LINE-0', line_counter),
                    CONCAT('P00', product_counter),
                    CONCAT('제품', CHAR(64 + product_counter)),
                    CASE line_counter
                        WHEN 1 THEN 1000
                        WHEN 2 THEN 800
                        WHEN 3 THEN 600
                    END,
                    CASE line_counter
                        WHEN 1 THEN 980 + quantity_variance
                        WHEN 2 THEN 770 + quantity_variance
                        WHEN 3 THEN 580 + quantity_variance
                    END,
                    FLOOR(RAND() * 50),
                    date_counter,
                    hour_counter,
                    IF(hour_counter < 17, '주간', '야간')
                );

                SET line_counter = line_counter + 1;
            END WHILE;

            SET hour_counter = hour_counter + 1;
        END WHILE;

        SET date_counter = DATE_ADD(date_counter, INTERVAL 1 DAY);
    END WHILE;
END //

DELIMITER ;

-- 프로시저 실행
CALL generate_production_data();

-- ============================================================================
-- 26. 불량 데이터 대량 생성
-- ============================================================================

INSERT INTO defect_data
(production_id, defect_code, defect_name, defect_quantity, defect_rate, defect_type)
SELECT
    p.id,
    CASE MOD(p.id, 4)
        WHEN 0 THEN 'D001'
        WHEN 1 THEN 'D002'
        WHEN 2 THEN 'D003'
        ELSE 'D004'
    END,
    CASE MOD(p.id, 4)
        WHEN 0 THEN '스크래치'
        WHEN 1 THEN '변형'
        WHEN 2 THEN '색상 불균일'
        ELSE '치수 오차'
    END,
    FLOOR(p.defect_quantity * 0.6),
    ROUND(p.defect_quantity * 100.0 / p.actual_quantity, 2),
    CASE MOD(p.id, 3)
        WHEN 0 THEN '외관'
        WHEN 1 THEN '기능'
        ELSE '치수'
    END
FROM production_data p
WHERE p.defect_quantity > 0
LIMIT 3000;

-- ============================================================================
-- 27. 설비 가동 데이터 대량 생성
-- ============================================================================

INSERT INTO equipment_data
(equipment_id, equipment_name, line_id, status, operation_time, downtime, downtime_reason, recorded_date, recorded_hour)
SELECT
    CONCAT('EQ-', LPAD(FLOOR((ROW_NUMBER() OVER (ORDER BY id) MOD 20)) + 1, 2, '0'), '-', LPAD(FLOOR(RAND() * 3) + 1, 3, '0')),
    CASE FLOOR(RAND() * 5)
        WHEN 0 THEN '프레스 기계'
        WHEN 1 THEN '용접 기계'
        WHEN 2 THEN '조립 라인'
        WHEN 3 THEN '검사 기계'
        ELSE '포장 기계'
    END,
    CONCAT('LINE-0', FLOOR(RAND() * 3) + 1),
    CASE FLOOR(RAND() * 10)
        WHEN 0 THEN '정지'
        WHEN 1 THEN '점검'
        ELSE '가동'
    END,
    FLOOR(RAND() * 480) + 1,
    FLOOR(RAND() * 120),
    CASE FLOOR(RAND() * 5)
        WHEN 0 THEN '부품 수급 지연'
        WHEN 1 THEN '정기 점검'
        WHEN 2 THEN '메인터넌스'
        WHEN 3 THEN '청소'
        ELSE NULL
    END,
    DATE_SUB(CURDATE(), INTERVAL FLOOR(RAND() * 30) DAY),
    FLOOR(RAND() * 16) + 8
FROM production_data
LIMIT 2000;

-- ============================================================================
-- 28. 공정 단계 데이터 대량 생성
-- ============================================================================

INSERT INTO process_step
(production_id, product_code, process_sequence, process_name, equipment_id, start_time, end_time, duration_minutes, process_status, worker_id)
SELECT
    p.id,
    p.product_code,
    seq.seq,
    CASE seq.seq
        WHEN 1 THEN '재단'
        WHEN 2 THEN '성형'
        WHEN 3 THEN '조립'
        WHEN 4 THEN '검사'
        ELSE '포장'
    END,
    CONCAT('EQ-', LPAD(FLOOR(RAND() * 20) + 1, 2, '0'), '-001'),
    CONCAT(p.production_date, ' ', LPAD(p.production_hour, 2, '0'), ':', LPAD(FLOOR(RAND() * 60), 2, '0'), ':00'),
    CONCAT(p.production_date, ' ', LPAD(p.production_hour + 1, 2, '0'), ':', LPAD(FLOOR(RAND() * 60), 2, '0'), ':00'),
    FLOOR(RAND() * 120) + 30,
    CASE FLOOR(RAND() * 3)
        WHEN 0 THEN '완료'
        WHEN 1 THEN '진행중'
        ELSE '대기'
    END,
    CONCAT('W', LPAD(FLOOR(RAND() * 7) + 1, 3, '0'))
FROM production_data p
CROSS JOIN (
    SELECT 1 AS seq UNION SELECT 2 UNION SELECT 3 UNION SELECT 4 UNION SELECT 5
) seq
LIMIT 5000;

-- ============================================================================
-- 29. 품질 검사 데이터 대량 생성
-- ============================================================================

INSERT INTO quality_inspection
(production_id, inspection_date, inspection_time, inspector_name, item_code, item_name, specification, measurement_value, pass_fail, remark)
SELECT
    p.id,
    p.production_date,
    CONCAT(LPAD(FLOOR(RAND() * 24), 2, '0'), ':', LPAD(FLOOR(RAND() * 60), 2, '0'), ':00'),
    CASE FLOOR(RAND() * 3)
        WHEN 0 THEN '김철수'
        WHEN 1 THEN '이영희'
        ELSE '박민준'
    END,
    CASE FLOOR(RAND() * 5)
        WHEN 0 THEN 'Q001'
        WHEN 1 THEN 'Q002'
        WHEN 2 THEN 'Q003'
        WHEN 3 THEN 'Q004'
        ELSE 'Q005'
    END,
    CASE FLOOR(RAND() * 5)
        WHEN 0 THEN '길이 검사'
        WHEN 1 THEN '외관 검사'
        WHEN 2 THEN '무게 검사'
        WHEN 3 THEN '기능 검사'
        ELSE '색상 검사'
    END,
    CASE FLOOR(RAND() * 5)
        WHEN 0 THEN '±0.5mm'
        WHEN 1 THEN '±1.0mm'
        WHEN 2 THEN '100±5g'
        WHEN 3 THEN '정상 작동'
        ELSE '표준 색상'
    END,
    ROUND(RAND() * 100, 2),
    IF(RAND() > 0.15, '합격', '부적격'),
    IF(RAND() > 0.15, '정상', '이상 감지')
FROM production_data p
LIMIT 4000;

-- ============================================================================
-- 30. 에너지 소비 데이터 대량 생성
-- ============================================================================

INSERT INTO energy_consumption
(line_id, energy_type, consumption_date, consumption_hour, consumption_value, unit, cost)
SELECT
    CONCAT('LINE-0', FLOOR(RAND() * 3) + 1),
    CASE FLOOR(RAND() * 3)
        WHEN 0 THEN '전력'
        WHEN 1 THEN '가스'
        ELSE '수도'
    END,
    DATE_SUB(CURDATE(), INTERVAL FLOOR(RAND() * 30) DAY),
    FLOOR(RAND() * 16) + 8,
    ROUND(RAND() * 200 + 50, 2),
    CASE FLOOR(RAND() * 3)
        WHEN 0 THEN 'kWh'
        WHEN 1 THEN 'm³'
        ELSE 'ton'
    END,
    FLOOR(RAND() * 50000) + 10000
FROM production_data
LIMIT 2500;

-- ============================================================================
-- 31. 유지보수 기록 대량 생성
-- ============================================================================

INSERT INTO maintenance_schedule
(equipment_id, equipment_name, maintenance_type, scheduled_date, actual_date, technician_name, description, cost, maintenance_status)
SELECT
    CONCAT('EQ-', LPAD(FLOOR(RAND() * 20) + 1, 2, '0'), '-', LPAD(FLOOR(RAND() * 3) + 1, 3, '0')),
    CASE FLOOR(RAND() * 5)
        WHEN 0 THEN '프레스 기계'
        WHEN 1 THEN '용접 기계'
        WHEN 2 THEN '조립 라인'
        WHEN 3 THEN '검사 기계'
        ELSE '포장 기계'
    END,
    CASE FLOOR(RAND() * 3)
        WHEN 0 THEN '정기'
        WHEN 1 THEN '수리'
        ELSE '개선'
    END,
    DATE_ADD(CURDATE(), INTERVAL FLOOR(RAND() * 30) DAY),
    IF(RAND() > 0.6, DATE_ADD(CURDATE(), INTERVAL FLOOR(RAND() * 30) DAY), NULL),
    CASE FLOOR(RAND() * 3)
        WHEN 0 THEN '이영희'
        WHEN 1 THEN '박민준'
        ELSE '최지원'
    END,
    CONCAT('설비 유지보수 작업 - ', FLOOR(RAND() * 100)),
    FLOOR(RAND() * 2000000) + 200000,
    CASE FLOOR(RAND() * 3)
        WHEN 0 THEN '예정'
        WHEN 1 THEN '진행중'
        ELSE '완료'
    END
FROM production_data
LIMIT 1500;

-- ============================================================================
-- 32. 최종 데이터 통계
-- ============================================================================

SELECT '=== DATA GENERATION COMPLETE ===' as Status;

SELECT
    'production_data' as Table_Name,
    COUNT(*) as row_count,
    MIN(production_date) as earliest_date,
    MAX(production_date) as latest_date
FROM production_data;

SELECT 'defect_data' as Table_Name, COUNT(*) as row_count FROM defect_data;
SELECT 'equipment_data' as Table_Name, COUNT(*) as row_count FROM equipment_data;
SELECT 'process_step' as Table_Name, COUNT(*) as row_count FROM process_step;
SELECT 'quality_inspection' as Table_Name, COUNT(*) as row_count FROM quality_inspection;
SELECT 'energy_consumption' as Table_Name, COUNT(*) as row_count FROM energy_consumption;
SELECT 'maintenance_schedule' as Table_Name, COUNT(*) as row_count FROM maintenance_schedule;

SELECT '=== FINAL DATA SUMMARY ===' as Status;
SELECT
    (SELECT COUNT(*) FROM production_data) as production_count,
    (SELECT COUNT(*) FROM defect_data) as defect_count,
    (SELECT COUNT(*) FROM equipment_data) as equipment_count,
    (SELECT COUNT(*) FROM process_step) as process_count,
    (SELECT COUNT(*) FROM quality_inspection) as inspection_count,
    (SELECT COUNT(*) FROM energy_consumption) as energy_count,
    (SELECT COUNT(*) FROM maintenance_schedule) as maintenance_count;
