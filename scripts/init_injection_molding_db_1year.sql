-- ============================================================================
-- EXAONE Manufacturing Database - Injection Molding System
-- Complete redesign for 850-ton injection molding machine
-- 1 YEAR OF DATA (365 days × 24 hours = 24-hour operation)
-- Date: 2026-01-22
-- ============================================================================

USE manufacturing;

-- Drop all existing tables to start fresh
DROP TABLE IF EXISTS maintenance_schedule;
DROP TABLE IF EXISTS energy_consumption;
DROP TABLE IF EXISTS quality_inspection;
DROP TABLE IF EXISTS process_step;
DROP TABLE IF EXISTS material_inventory;
DROP TABLE IF EXISTS worker_info;
DROP TABLE IF EXISTS product_pricing;
DROP TABLE IF EXISTS equipment_data;
DROP TABLE IF EXISTS defect_data;
DROP TABLE IF EXISTS production_data;
DROP TABLE IF EXISTS energy_usage;
DROP TABLE IF EXISTS equipment_maintenance;
DROP TABLE IF EXISTS daily_production;
DROP TABLE IF EXISTS production_summary;
DROP TABLE IF EXISTS injection_cycle;
DROP TABLE IF EXISTS injection_defect_type;
DROP TABLE IF EXISTS injection_process_parameter;
DROP TABLE IF EXISTS material_spec;
DROP TABLE IF EXISTS mold_info;
DROP TABLE IF EXISTS injection_molding_machine;

-- ============================================================================
-- 1. injection_molding_machine (사출기 설비 정보)
-- ============================================================================

CREATE TABLE injection_molding_machine (
    id INT PRIMARY KEY AUTO_INCREMENT COMMENT '설비 ID',
    equipment_id VARCHAR(50) NOT NULL UNIQUE COMMENT '설비 ID (예: IM-850-001)',
    equipment_name VARCHAR(100) NOT NULL COMMENT '설비명 (예: 850 ton Injection Molding Machine)',
    manufacturer VARCHAR(100) COMMENT '제조사',
    capacity_ton INT NOT NULL COMMENT '사출 톤수 (850)',
    installation_date DATE COMMENT '설치 일자',
    last_maintenance_date DATE COMMENT '마지막 유지보수 일자',
    status VARCHAR(20) NOT NULL DEFAULT '가동' COMMENT '상태 (가동/정지/점검)',
    operating_hours BIGINT DEFAULT 0 COMMENT '누적 가동 시간',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_status (status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT '사출기 설비 정보';

-- ============================================================================
-- 2. mold_info (금형 정보)
-- ============================================================================

CREATE TABLE mold_info (
    id INT PRIMARY KEY AUTO_INCREMENT COMMENT '금형 ID',
    mold_code VARCHAR(50) NOT NULL UNIQUE COMMENT '금형 코드 (예: DC1)',
    mold_name VARCHAR(100) NOT NULL COMMENT '금형명 (예: Cap Decor Upper(GD))',
    product_code VARCHAR(50) NOT NULL COMMENT '제품 코드',
    product_name VARCHAR(100) NOT NULL COMMENT '제품명 (예: Cap Decor Upper)',
    cavity_count INT NOT NULL DEFAULT 1 COMMENT '캐비티 수',
    target_weight_g DECIMAL(8,2) NOT NULL COMMENT '목표 제품 중량 (g) (예: 252.5)',
    target_weight_tolerance_minus DECIMAL(8,2) COMMENT '중량 허용공차 (-)',
    target_weight_tolerance_plus DECIMAL(8,2) COMMENT '중량 허용공차 (+)',
    runner_weight_g DECIMAL(8,2) COMMENT '러너 무게 (g)',
    total_weight_g DECIMAL(8,2) COMMENT '총 무게 (제품+러너)',
    cooling_zones INT COMMENT '냉각 존 수',
    hot_runner_zones INT COMMENT '핫 러너 존 수',
    mold_manufacturer VARCHAR(100) COMMENT '금형 제작사',
    status VARCHAR(20) DEFAULT '사용중' COMMENT '상태 (사용중/정지/유지보수)',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_product (product_code),
    INDEX idx_status (status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT '금형 정보';

-- ============================================================================
-- 3. material_spec (원재료 사양)
-- ============================================================================

CREATE TABLE material_spec (
    id INT PRIMARY KEY AUTO_INCREMENT COMMENT 'ID',
    material_code VARCHAR(50) NOT NULL UNIQUE COMMENT '자재 코드 (예: HIPS-001)',
    material_name VARCHAR(100) NOT NULL COMMENT '자재명 (예: HIPS)',
    material_grade VARCHAR(50) COMMENT '등급 (예: Grade A)',
    color VARCHAR(50) COMMENT '색상',
    supplier VARCHAR(100) COMMENT '공급자',
    cylinder_temp_nh INT COMMENT 'NH (Hopper) 온도 (℃)',
    cylinder_temp_h1 INT COMMENT 'H1 실린더 온도 (℃)',
    cylinder_temp_h2 INT COMMENT 'H2 실린더 온도 (℃)',
    cylinder_temp_h3 INT COMMENT 'H3 실린더 온도 (℃)',
    cylinder_temp_h4 INT COMMENT 'H4 실린더 온도 (℃)',
    melting_point_min INT COMMENT '최소 용융 온도 (℃)',
    melting_point_max INT COMMENT '최대 용융 온도 (℃)',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_material (material_code)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT '원재료 사양';

-- ============================================================================
-- 4. injection_process_parameter (사출 공정 파라미터)
-- ============================================================================

CREATE TABLE injection_process_parameter (
    id INT PRIMARY KEY AUTO_INCREMENT COMMENT 'ID',
    mold_id INT NOT NULL COMMENT 'mold_info 외래키',
    material_id INT NOT NULL COMMENT 'material_spec 외래키',
    injection_time INT COMMENT '사출 시간 (초)',
    pressure_hold_time INT COMMENT '보압 시간 (초)',
    cooling_time INT COMMENT '냉각 시간 (초)',
    mold_open_time INT COMMENT '금형 개방 시간 (초)',
    ejection_time INT COMMENT '취출 시간 (초)',
    total_cycle_time INT COMMENT '전체 사이클 시간 (초)',
    injection_pressure_primary INT COMMENT '1차 사출 압력 (bar)',
    injection_pressure_secondary INT COMMENT '2차 사출 압력 (bar)',
    holding_pressure INT COMMENT '보압 (bar)',
    back_pressure INT COMMENT '배압 (bar)',
    mold_temp_fixed INT COMMENT '고정측 금형 온도 (℃)',
    mold_temp_moving INT COMMENT '가동측 금형 온도 (℃)',
    hot_runner_temp INT COMMENT '핫 러너 온도 (℃)',
    screw_rotation_speed INT COMMENT '스크류 회전 속도 (rpm)',
    metering_distance INT COMMENT '계량 거리 (mm)',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (mold_id) REFERENCES mold_info(id),
    FOREIGN KEY (material_id) REFERENCES material_spec(id),
    INDEX idx_mold (mold_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT '사출 공정 파라미터';

-- ============================================================================
-- 5. injection_defect_type (사출 불량 유형)
-- ============================================================================

CREATE TABLE injection_defect_type (
    id INT PRIMARY KEY AUTO_INCREMENT COMMENT 'ID',
    defect_code VARCHAR(50) NOT NULL UNIQUE COMMENT '불량 코드',
    defect_name_kr VARCHAR(100) NOT NULL COMMENT '불량명 (한글)',
    defect_name_en VARCHAR(100) COMMENT '불량명 (영문)',
    defect_category VARCHAR(50) COMMENT '불량 분류 (외관/기능/치수)',
    severity VARCHAR(20) COMMENT '심각도 (경/중/심)',
    cause_description TEXT COMMENT '원인 설명',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT '사출 불량 유형';

-- ============================================================================
-- 6. injection_cycle (개별 사이클 데이터) - 핵심 테이블
-- ============================================================================

CREATE TABLE injection_cycle (
    id BIGINT PRIMARY KEY AUTO_INCREMENT COMMENT '사이클 ID',
    machine_id INT NOT NULL COMMENT '사출기 ID',
    mold_id INT NOT NULL COMMENT '금형 ID',
    material_id INT NOT NULL COMMENT '원재료 ID',
    cycle_date DATE NOT NULL COMMENT '사이클 실행 날짜',
    cycle_hour TINYINT NOT NULL COMMENT '시간 (0-23)',
    cycle_minute TINYINT NOT NULL COMMENT '분 (0-59)',
    cycle_sequence INT NOT NULL COMMENT '시간 내 순서',

    -- 온도 기록 (℃)
    temp_nh INT COMMENT 'NH 온도',
    temp_h1 INT COMMENT 'H1 온도',
    temp_h2 INT COMMENT 'H2 온도',
    temp_h3 INT COMMENT 'H3 온도',
    temp_h4 INT COMMENT 'H4 온도',
    temp_mold_fixed INT COMMENT '고정측 금형 온도',
    temp_mold_moving INT COMMENT '가동측 금형 온도',
    temp_hot_runner INT COMMENT '핫 러너 온도',

    -- 압력 기록 (bar)
    pressure_primary INT COMMENT '1차 사출 압력',
    pressure_secondary INT COMMENT '2차 사출 압력',
    pressure_holding INT COMMENT '보압',

    -- 사이클 결과
    product_weight_g DECIMAL(8,2) COMMENT '제품 무게 (g)',
    weight_deviation_g DECIMAL(8,2) COMMENT '목표 대비 편차 (g)',
    weight_ok BOOLEAN COMMENT '무게 합격 여부',
    has_defect BOOLEAN DEFAULT FALSE COMMENT '불량 여부',
    defect_type_id INT COMMENT '불량 유형 ID',
    defect_description VARCHAR(255) COMMENT '불량 설명',
    visual_inspection_ok BOOLEAN COMMENT '외관 검사 합격',

    -- 메타정보
    operator_id VARCHAR(50) COMMENT '담당 작업자 ID',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (machine_id) REFERENCES injection_molding_machine(id),
    FOREIGN KEY (mold_id) REFERENCES mold_info(id),
    FOREIGN KEY (material_id) REFERENCES material_spec(id),
    FOREIGN KEY (defect_type_id) REFERENCES injection_defect_type(id),
    INDEX idx_date (cycle_date),
    INDEX idx_machine (machine_id),
    INDEX idx_defect (has_defect),
    INDEX idx_weight_ok (weight_ok),
    INDEX idx_created (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT '개별 사이클 데이터';

-- ============================================================================
-- 7. production_summary (생산 요약 - 시간별)
-- ============================================================================

CREATE TABLE production_summary (
    id BIGINT PRIMARY KEY AUTO_INCREMENT COMMENT 'ID',
    summary_date DATE NOT NULL COMMENT '요약 날짜',
    summary_hour TINYINT NOT NULL COMMENT '시간',
    machine_id INT NOT NULL COMMENT '사출기 ID',
    mold_id INT NOT NULL COMMENT '금형 ID',

    -- 생산량
    total_cycles INT DEFAULT 0 COMMENT '총 사이클 수',
    good_products INT DEFAULT 0 COMMENT '정상 제품 수',
    defective_products INT DEFAULT 0 COMMENT '불량 제품 수',
    defect_rate DECIMAL(5,2) COMMENT '불량률 (%)',

    -- 무게
    avg_weight_g DECIMAL(8,2) COMMENT '평균 무게 (g)',
    weight_variance DECIMAL(8,2) COMMENT '무게 표준편차',
    weight_out_of_spec INT DEFAULT 0 COMMENT '규격 외 무게 개수',

    -- 온도
    avg_temp_h1 DECIMAL(5,2) COMMENT '평균 H1 온도',
    avg_temp_h2 DECIMAL(5,2) COMMENT '평균 H2 온도',
    avg_temp_mold DECIMAL(5,2) COMMENT '평균 금형 온도',

    -- 불량
    flash_count INT DEFAULT 0 COMMENT 'Flash 불량 수',
    void_count INT DEFAULT 0 COMMENT 'Void 불량 수',
    weld_line_count INT DEFAULT 0 COMMENT '용접선 불량 수',
    jetting_count INT DEFAULT 0 COMMENT 'Jetting 불량 수',

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (machine_id) REFERENCES injection_molding_machine(id),
    FOREIGN KEY (mold_id) REFERENCES mold_info(id),
    UNIQUE KEY uk_summary (summary_date, summary_hour, machine_id, mold_id),
    INDEX idx_date (summary_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT '시간별 생산 요약';

-- ============================================================================
-- 8. daily_production (일별 생산 통계)
-- ============================================================================

CREATE TABLE daily_production (
    id BIGINT PRIMARY KEY AUTO_INCREMENT COMMENT 'ID',
    production_date DATE NOT NULL UNIQUE COMMENT '생산 날짜',
    machine_id INT NOT NULL COMMENT '사출기 ID',
    mold_id INT NOT NULL COMMENT '금형 ID',

    -- 생산량
    total_cycles_produced INT DEFAULT 0 COMMENT '총 생산 사이클',
    good_products_count INT DEFAULT 0 COMMENT '정상 제품 개수',
    defective_count INT DEFAULT 0 COMMENT '불량 제품 개수',
    defect_rate DECIMAL(5,2) COMMENT '불량률 (%)',

    -- 효율성
    target_production INT COMMENT '목표 생산량',
    production_rate DECIMAL(5,2) COMMENT '생산 달성률 (%)',
    operating_hours_actual INT COMMENT '실제 가동 시간',
    downtime_minutes INT DEFAULT 0 COMMENT '정지 시간 (분)',
    downtime_reason VARCHAR(255) COMMENT '정지 사유',

    -- 무게 분석
    avg_weight_g DECIMAL(8,2) COMMENT '평균 무게',
    weight_min_g DECIMAL(8,2) COMMENT '최소 무게',
    weight_max_g DECIMAL(8,2) COMMENT '최대 무게',
    weight_out_of_spec_count INT DEFAULT 0 COMMENT '규격 외 무게 개수',

    -- 온도 분석
    avg_cylinder_temp DECIMAL(5,2) COMMENT '평균 실린더 온도',
    avg_mold_temp DECIMAL(5,2) COMMENT '평균 금형 온도',
    temp_stability_ok BOOLEAN DEFAULT TRUE COMMENT '온도 안정성 (정상: true)',

    -- 불량 분석
    flash_count INT DEFAULT 0,
    void_count INT DEFAULT 0,
    weld_line_count INT DEFAULT 0,
    jetting_count INT DEFAULT 0,
    flow_mark_count INT DEFAULT 0,
    other_defect_count INT DEFAULT 0,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (machine_id) REFERENCES injection_molding_machine(id),
    FOREIGN KEY (mold_id) REFERENCES mold_info(id),
    INDEX idx_date (production_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT '일별 생산 통계';

-- ============================================================================
-- 9. equipment_maintenance (설비 유지보수)
-- ============================================================================

CREATE TABLE equipment_maintenance (
    id BIGINT PRIMARY KEY AUTO_INCREMENT COMMENT 'ID',
    machine_id INT NOT NULL COMMENT '사출기 ID',
    maintenance_type VARCHAR(50) COMMENT '유지보수 유형 (정기/수리/개선)',
    scheduled_date DATE NOT NULL COMMENT '예정 일자',
    actual_date DATE COMMENT '실제 시공 일자',
    technician_name VARCHAR(50) COMMENT '담당 기술자',
    description TEXT COMMENT '작업 내용',
    parts_replaced VARCHAR(255) COMMENT '교체 부품',
    cost DECIMAL(10,2) COMMENT '작업 비용',
    status VARCHAR(20) COMMENT '상태 (예정/진행중/완료)',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (machine_id) REFERENCES injection_molding_machine(id),
    INDEX idx_machine (machine_id),
    INDEX idx_date (scheduled_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT '설비 유지보수';

-- ============================================================================
-- 10. energy_usage (에너지 사용량)
-- ============================================================================

CREATE TABLE energy_usage (
    id BIGINT PRIMARY KEY AUTO_INCREMENT COMMENT 'ID',
    machine_id INT NOT NULL COMMENT '사출기 ID',
    energy_type VARCHAR(20) COMMENT '에너지 유형 (전력/냉각수)',
    usage_date DATE NOT NULL COMMENT '사용 날짜',
    usage_hour TINYINT COMMENT '시간 (0-23)',
    consumption_value DECIMAL(12,2) NOT NULL COMMENT '사용량',
    unit VARCHAR(10) COMMENT '단위 (kWh/ton)',
    cost DECIMAL(10,2) COMMENT '비용',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (machine_id) REFERENCES injection_molding_machine(id),
    INDEX idx_date (usage_date),
    INDEX idx_machine (machine_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT '에너지 사용량';

-- ============================================================================
-- SAMPLE DATA INSERTION
-- ============================================================================

-- ============================================================================
-- 1. 사출기 설비 정보
-- ============================================================================

INSERT INTO injection_molding_machine
(equipment_id, equipment_name, manufacturer, capacity_ton, installation_date, last_maintenance_date, status)
VALUES
('IM-850-001', '850 ton Injection Molding Machine #1', '경성정밀', 850, '2022-01-15', '2026-01-10', '가동');

-- ============================================================================
-- 2. 원재료 사양 (HIPS)
-- ============================================================================

INSERT INTO material_spec
(material_code, material_name, material_grade, color, supplier,
 cylinder_temp_nh, cylinder_temp_h1, cylinder_temp_h2, cylinder_temp_h3, cylinder_temp_h4,
 melting_point_min, melting_point_max)
VALUES
('HIPS-001', 'HIPS', 'Grade A', 'Black', 'LG Chem',
 220, 225, 230, 215, 200,
 180, 240);

-- ============================================================================
-- 3. 금형 정보 (DC1)
-- ============================================================================

INSERT INTO mold_info
(mold_code, mold_name, product_code, product_name, cavity_count,
 target_weight_g, target_weight_tolerance_minus, target_weight_tolerance_plus,
 runner_weight_g, total_weight_g, cooling_zones, hot_runner_zones, mold_manufacturer, status)
VALUES
('DC1', 'Cap Decor Upper(GD)', 'CPGMREFX23', 'Cap Decor Upper', 1,
 252.5, 250.5, 254.5,
 14.0, 519.0, 2, 5, '경성정밀', '사용중');

-- ============================================================================
-- 4. 불량 유형 정의
-- ============================================================================

INSERT INTO injection_defect_type
(defect_code, defect_name_kr, defect_name_en, defect_category, severity, cause_description)
VALUES
('D001', 'Flash', 'Flash', '외관', '경', '금형 틈새에서 플라스틱이 흘러나옴'),
('D002', 'Void', 'Void/기포', '외관', '중', '제품 내부에 공기 공동 발생'),
('D003', 'Weld Line', 'Weld Line', '외관', '중', '멀티캐비티에서 용융 흐름이 만나는 부분 약화'),
('D004', 'Jetting', 'Jetting', '외관', '중', '게이트 부근에서 좁은 틈으로 빠르게 분사되는 현상'),
('D005', 'Flow Mark', 'Flow Mark', '외관', '경', '멀티캐비티에서 용융 재료의 흐름 자국'),
('D006', 'Gas Generation', 'Gas Generation', '외관', '중', '분해된 플라스틱 가스로 인한 구멍이나 얼룩'),
('D007', 'Color Variation', 'Color Variation', '외관', '경', '색상 불균일'),
('D008', 'Weight Deviation', 'Weight Deviation', '치수', '경', '목표 무게와 편차 발생'),
('D009', 'Dimensional Error', 'Dimensional Error', '치수', '중', '규격 외 치수');

-- ============================================================================
-- 5. 공정 파라미터
-- ============================================================================

INSERT INTO injection_process_parameter
(mold_id, material_id,
 injection_time, pressure_hold_time, cooling_time, mold_open_time, ejection_time, total_cycle_time,
 injection_pressure_primary, injection_pressure_secondary, holding_pressure, back_pressure,
 mold_temp_fixed, mold_temp_moving, hot_runner_temp, screw_rotation_speed, metering_distance)
VALUES
(1, 1,
 8.7, 25, 10, 10, 0, 53.7,
 1200, 900, 700, 70,
 130, 130, 230, 60, 70);

-- ============================================================================
-- 6. 365일 × 24시간 사출 사이클 데이터 생성 (약 585,920개 행)
-- ============================================================================

DROP PROCEDURE IF EXISTS generate_injection_cycles_1year;

DELIMITER //

CREATE PROCEDURE generate_injection_cycles_1year()
BEGIN
    DECLARE date_counter DATE;
    DECLARE end_date DATE;
    DECLARE hour_counter INT;
    DECLARE cycle_counter INT;
    DECLARE total_cycles INT;
    DECLARE rand_weight DECIMAL(8,2);
    DECLARE rand_temp_variation INT;
    DECLARE rand_pressure_variation INT;
    DECLARE rand_defect INT;
    DECLARE defect_type INT;
    DECLARE has_defect BOOLEAN;
    DECLARE weight_ok BOOLEAN;
    DECLARE counter INT DEFAULT 0;

    SET date_counter = DATE_SUB(CURDATE(), INTERVAL 365 DAY);
    SET end_date = CURDATE();

    -- 365일 루프
    WHILE date_counter <= end_date DO
        SET hour_counter = 0;

        -- 24시간 루프 (0시~23시, 24시간 근무)
        WHILE hour_counter <= 23 DO
            SET cycle_counter = 0;
            SET total_cycles = FLOOR(60 * 60 / 53.7);  -- 시간당 약 67개 사이클

            -- 각 사이클 데이터 생성
            WHILE cycle_counter < total_cycles DO
                -- 무게: 정규분포 근처 (252.5 ± 3g)
                SET rand_weight = 252.5 + (RAND() - 0.5) * 6;
                SET weight_ok = ABS(rand_weight - 252.5) <= 2;

                -- 불량 확률: 약 10%
                SET rand_defect = FLOOR(RAND() * 100);
                SET has_defect = rand_defect < 10;

                -- 불량 유형 결정 (1~9)
                IF has_defect THEN
                    SET defect_type = FLOOR(RAND() * 9) + 1;
                ELSE
                    SET defect_type = NULL;
                END IF;

                -- 온도 변동 (±2℃)
                SET rand_temp_variation = FLOOR(RAND() * 5) - 2;
                SET rand_pressure_variation = FLOOR(RAND() * 20) - 10;

                INSERT INTO injection_cycle
                (machine_id, mold_id, material_id, cycle_date, cycle_hour, cycle_minute, cycle_sequence,
                 temp_nh, temp_h1, temp_h2, temp_h3, temp_h4, temp_mold_fixed, temp_mold_moving, temp_hot_runner,
                 pressure_primary, pressure_secondary, pressure_holding,
                 product_weight_g, weight_deviation_g, weight_ok, has_defect, defect_type_id,
                 visual_inspection_ok, operator_id, created_at)
                VALUES
                (1, 1, 1, date_counter, hour_counter, FLOOR(RAND() * 60), cycle_counter,
                 220, 225 + rand_temp_variation, 230 + rand_temp_variation, 215 + rand_temp_variation, 200 + rand_temp_variation,
                 130 + FLOOR(RAND() * 3) - 1, 130 + FLOOR(RAND() * 3) - 1, 230 + FLOOR(RAND() * 2) - 1,
                 1200 + rand_pressure_variation, 900 + rand_pressure_variation, 700 + rand_pressure_variation,
                 rand_weight, rand_weight - 252.5, weight_ok, has_defect, IF(has_defect, defect_type, NULL),
                 IF(has_defect, FALSE, TRUE), 'OP-001', NOW());

                SET cycle_counter = cycle_counter + 1;
                SET counter = counter + 1;

                -- 진행상황 출력 (10만 행마다)
                IF MOD(counter, 100000) = 0 THEN
                    SELECT CONCAT('생성 중: ', counter, ' 행 완료') AS progress;
                END IF;
            END WHILE;

            SET hour_counter = hour_counter + 1;
        END WHILE;

        SET date_counter = DATE_ADD(date_counter, INTERVAL 1 DAY);
    END WHILE;

    SELECT CONCAT('✅ 완료: 총 ', counter, ' 행 생성됨') AS final_result;
END //

DELIMITER ;

-- 프로시저 실행 (약 20~30분 소요)
SELECT '🔄 사이클 데이터 생성 중... (약 20~30분 소요)' AS status;
CALL generate_injection_cycles_1year();

-- ============================================================================
-- 7. 시간별 생산 요약 생성
-- ============================================================================

SELECT '🔄 시간별 요약 생성 중...' AS status;

INSERT INTO production_summary
(summary_date, summary_hour, machine_id, mold_id, total_cycles, good_products, defective_products, defect_rate,
 avg_weight_g, weight_variance, weight_out_of_spec, avg_temp_h1, avg_temp_h2, avg_temp_mold,
 flash_count, void_count, weld_line_count, jetting_count)
SELECT
    ic.cycle_date,
    ic.cycle_hour,
    ic.machine_id,
    ic.mold_id,
    COUNT(*) as total_cycles,
    SUM(CASE WHEN ic.has_defect = FALSE THEN 1 ELSE 0 END) as good_products,
    SUM(CASE WHEN ic.has_defect = TRUE THEN 1 ELSE 0 END) as defective_products,
    ROUND(SUM(CASE WHEN ic.has_defect = TRUE THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 2) as defect_rate,
    ROUND(AVG(ic.product_weight_g), 2) as avg_weight_g,
    ROUND(STDDEV(ic.product_weight_g), 2) as weight_variance,
    SUM(CASE WHEN ic.weight_ok = FALSE THEN 1 ELSE 0 END) as weight_out_of_spec,
    ROUND(AVG(ic.temp_h1), 2) as avg_temp_h1,
    ROUND(AVG(ic.temp_h2), 2) as avg_temp_h2,
    ROUND(AVG((ic.temp_mold_fixed + ic.temp_mold_moving) / 2), 2) as avg_temp_mold,
    SUM(CASE WHEN ic.defect_type_id = 1 THEN 1 ELSE 0 END) as flash_count,
    SUM(CASE WHEN ic.defect_type_id = 2 THEN 1 ELSE 0 END) as void_count,
    SUM(CASE WHEN ic.defect_type_id = 3 THEN 1 ELSE 0 END) as weld_line_count,
    SUM(CASE WHEN ic.defect_type_id = 4 THEN 1 ELSE 0 END) as jetting_count
FROM injection_cycle ic
GROUP BY ic.cycle_date, ic.cycle_hour, ic.machine_id, ic.mold_id;

SELECT '✅ 시간별 요약 생성 완료' AS status;

-- ============================================================================
-- 8. 일별 생산 통계 생성
-- ============================================================================

SELECT '🔄 일별 요약 생성 중...' AS status;

INSERT INTO daily_production
(production_date, machine_id, mold_id, total_cycles_produced, good_products_count, defective_count, defect_rate,
 target_production, production_rate, operating_hours_actual, downtime_minutes, downtime_reason,
 avg_weight_g, weight_min_g, weight_max_g, weight_out_of_spec_count,
 avg_cylinder_temp, avg_mold_temp, temp_stability_ok,
 flash_count, void_count, weld_line_count, jetting_count, flow_mark_count, other_defect_count)
SELECT
    ic.cycle_date,
    ic.machine_id,
    ic.mold_id,
    COUNT(*) as total_cycles_produced,
    SUM(CASE WHEN ic.has_defect = FALSE THEN 1 ELSE 0 END) as good_products_count,
    SUM(CASE WHEN ic.has_defect = TRUE THEN 1 ELSE 0 END) as defective_count,
    ROUND(SUM(CASE WHEN ic.has_defect = TRUE THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 2) as defect_rate,
    1608 as target_production,  -- 24시간 × 67개/시간
    ROUND(SUM(CASE WHEN ic.has_defect = FALSE THEN 1 ELSE 0 END) * 100.0 / 1608, 2) as production_rate,
    24 as operating_hours_actual,
    CASE WHEN COUNT(*) < 1600 THEN FLOOR(RAND() * 120) ELSE 0 END as downtime_minutes,
    CASE WHEN COUNT(*) < 1600 THEN CONCAT('설비 점검 ', FLOOR(RAND() * 10)) ELSE NULL END as downtime_reason,
    ROUND(AVG(ic.product_weight_g), 2) as avg_weight_g,
    ROUND(MIN(ic.product_weight_g), 2) as weight_min_g,
    ROUND(MAX(ic.product_weight_g), 2) as weight_max_g,
    SUM(CASE WHEN ic.weight_ok = FALSE THEN 1 ELSE 0 END) as weight_out_of_spec_count,
    ROUND((AVG(ic.temp_h1) + AVG(ic.temp_h2) + AVG(ic.temp_h3) + AVG(ic.temp_h4)) / 4, 2) as avg_cylinder_temp,
    ROUND(AVG((ic.temp_mold_fixed + ic.temp_mold_moving) / 2), 2) as avg_mold_temp,
    TRUE as temp_stability_ok,
    SUM(CASE WHEN ic.defect_type_id = 1 THEN 1 ELSE 0 END) as flash_count,
    SUM(CASE WHEN ic.defect_type_id = 2 THEN 1 ELSE 0 END) as void_count,
    SUM(CASE WHEN ic.defect_type_id = 3 THEN 1 ELSE 0 END) as weld_line_count,
    SUM(CASE WHEN ic.defect_type_id = 4 THEN 1 ELSE 0 END) as jetting_count,
    SUM(CASE WHEN ic.defect_type_id = 5 THEN 1 ELSE 0 END) as flow_mark_count,
    SUM(CASE WHEN ic.defect_type_id IN (6, 7, 8, 9) THEN 1 ELSE 0 END) as other_defect_count
FROM injection_cycle ic
GROUP BY ic.cycle_date, ic.machine_id, ic.mold_id;

SELECT '✅ 일별 요약 생성 완료' AS status;

-- ============================================================================
-- 9. 유지보수 데이터 샘플
-- ============================================================================

INSERT INTO equipment_maintenance
(machine_id, maintenance_type, scheduled_date, actual_date, technician_name, description, cost, status)
VALUES
(1, '정기', '2026-02-15', NULL, '이영희', '정기 점검 및 부품 교체', 500000, '예정'),
(1, '수리', '2026-01-05', '2026-01-05', '박민준', '핫 러너 히터 교체', 350000, '완료'),
(1, '정기', '2026-01-01', '2026-01-01', '최지원', '필터 교체 및 오일 교체', 200000, '완료'),
(1, '정기', '2025-07-10', '2025-07-10', '이영희', '반년 점검 및 스크류 정비', 800000, '완료'),
(1, '수리', '2025-04-20', '2025-04-20', '박민준', '냉각 시스템 점검', 300000, '완료');

-- ============================================================================
-- 10. 에너지 사용량 데이터
-- ============================================================================

INSERT INTO energy_usage
(machine_id, energy_type, usage_date, usage_hour, consumption_value, unit, cost)
SELECT
    1,
    '전력',
    DATE_SUB(CURDATE(), INTERVAL FLOOR(RAND() * 365) DAY),
    FLOOR(RAND() * 24),
    ROUND(120 + RAND() * 40, 2),
    'kWh',
    ROUND((120 + RAND() * 40) * 150, 0)
FROM injection_cycle
LIMIT 8760;

-- ============================================================================
-- VIEWS (뷰 생성)
-- ============================================================================

DROP VIEW IF EXISTS daily_performance;
CREATE VIEW daily_performance AS
SELECT
    dp.production_date,
    dp.machine_id,
    dp.mold_id,
    dp.good_products_count,
    dp.defective_count,
    dp.defect_rate,
    dp.avg_weight_g,
    dp.avg_cylinder_temp,
    dp.avg_mold_temp,
    ROUND((dp.flash_count + dp.void_count + dp.weld_line_count + dp.jetting_count) * 100.0 /
          (dp.good_products_count + dp.defective_count), 2) as major_defect_rate,
    dp.operating_hours_actual,
    dp.downtime_minutes
FROM daily_production dp;

DROP VIEW IF EXISTS hourly_efficiency;
CREATE VIEW hourly_efficiency AS
SELECT
    ps.summary_date,
    ps.summary_hour,
    ps.total_cycles,
    ps.good_products,
    ps.defect_rate,
    ps.avg_weight_g,
    ps.weight_variance,
    ps.avg_temp_h1,
    ps.avg_temp_h2,
    ps.avg_temp_mold
FROM production_summary ps
ORDER BY ps.summary_date DESC, ps.summary_hour DESC;

DROP VIEW IF EXISTS defect_analysis;
CREATE VIEW defect_analysis AS
SELECT
    idt.defect_name_kr,
    idt.defect_category,
    COUNT(ic.id) as occurrence_count,
    ROUND(COUNT(ic.id) * 100.0 / (SELECT COUNT(*) FROM injection_cycle), 2) as percentage
FROM injection_cycle ic
LEFT JOIN injection_defect_type idt ON ic.defect_type_id = idt.id
WHERE ic.has_defect = TRUE
GROUP BY idt.defect_name_kr, idt.defect_category
ORDER BY occurrence_count DESC;

-- ============================================================================
-- 최종 데이터 통계
-- ============================================================================

SELECT '=== INJECTION MOLDING DATABASE CREATION COMPLETE ===' as Status;
SELECT '📊 데이터 요약' AS Section;

SELECT 'Injection Cycles' as Table_Name, COUNT(*) as row_count FROM injection_cycle;
SELECT 'Production Summary (Hourly)' as Table_Name, COUNT(*) as row_count FROM production_summary;
SELECT 'Daily Production' as Table_Name, COUNT(*) as row_count FROM daily_production;
SELECT 'Equipment Maintenance' as Table_Name, COUNT(*) as row_count FROM equipment_maintenance;
SELECT 'Energy Usage' as Table_Name, COUNT(*) as row_count FROM energy_usage;

SELECT '=== DATA STATISTICS ===' as Status;
SELECT
    (SELECT COUNT(*) FROM injection_cycle) as total_cycles,
    (SELECT SUM(CASE WHEN has_defect = FALSE THEN 1 ELSE 0 END) FROM injection_cycle) as good_products,
    (SELECT SUM(CASE WHEN has_defect = TRUE THEN 1 ELSE 0 END) FROM injection_cycle) as defective_products,
    (SELECT COUNT(DISTINCT cycle_date) FROM injection_cycle) as days_of_data,
    (SELECT ROUND(MIN(product_weight_g), 2) FROM injection_cycle) as min_weight_g,
    (SELECT ROUND(MAX(product_weight_g), 2) FROM injection_cycle) as max_weight_g,
    (SELECT ROUND(AVG(product_weight_g), 2) FROM injection_cycle) as avg_weight_g;

SELECT '=== DEFECT BREAKDOWN ===' as Status;
SELECT
    'Flash' as defect_type,
    COUNT(*) as count,
    ROUND(COUNT(*) * 100.0 / (SELECT COUNT(*) FROM injection_cycle WHERE has_defect = TRUE), 2) as percentage
FROM injection_cycle WHERE defect_type_id = 1
UNION ALL
SELECT 'Void', COUNT(*), ROUND(COUNT(*) * 100.0 / (SELECT COUNT(*) FROM injection_cycle WHERE has_defect = TRUE), 2) FROM injection_cycle WHERE defect_type_id = 2
UNION ALL
SELECT 'Weld Line', COUNT(*), ROUND(COUNT(*) * 100.0 / (SELECT COUNT(*) FROM injection_cycle WHERE has_defect = TRUE), 2) FROM injection_cycle WHERE defect_type_id = 3
UNION ALL
SELECT 'Jetting', COUNT(*), ROUND(COUNT(*) * 100.0 / (SELECT COUNT(*) FROM injection_cycle WHERE has_defect = TRUE), 2) FROM injection_cycle WHERE defect_type_id = 4
UNION ALL
SELECT 'Others', COUNT(*), ROUND(COUNT(*) * 100.0 / (SELECT COUNT(*) FROM injection_cycle WHERE has_defect = TRUE), 2) FROM injection_cycle WHERE defect_type_id IN (5, 6, 7, 8, 9);

SELECT '=== SAMPLE DAILY PRODUCTION (최근 7일) ===' as Status;
SELECT * FROM daily_performance ORDER BY production_date DESC LIMIT 7;

SELECT '=== DATABASE READY ===' as Status;
