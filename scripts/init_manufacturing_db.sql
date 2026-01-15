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
