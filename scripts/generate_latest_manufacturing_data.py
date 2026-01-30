"""
최신 제조 데이터 생성 스크립트

2026-01-23 ~ 2026-01-29까지의 데이터 생성
- injection_cycle: 사이클 데이터 (매시간 ~67개)
- production_summary: 시간별 요약
- daily_summary: 일일 요약
"""

import sys
sys.path.insert(0, '/app')

from datetime import datetime, timedelta
from decimal import Decimal
import random
import logging
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# MySQL 연결 설정
DATABASE_URL = "mysql+pymysql://exaone_user:exaone_password@mysql:3306/manufacturing"
engine = create_engine(DATABASE_URL, echo=False)
Session = sessionmaker(bind=engine)

class ManufacturingDataGenerator:
    """제조 데이터 생성기"""

    def __init__(self):
        self.session = Session()
        self.machine_id = 1  # 유일한 사출기
        self.mold_id = 1  # 유일한 금형
        self.material_id = 1  # 유일한 재료

    def generate_cycle_data(self, cycle_date, cycle_hour, cycle_minute, cycle_sequence, daily_defect_rate=0.02):
        """개별 사이클 데이터 생성"""

        # 온도: 정상 범위 ± 약간의 변동
        temp_nh = random.randint(218, 222)
        temp_h1 = random.randint(223, 227)
        temp_h2 = random.randint(228, 232)
        temp_h3 = random.randint(213, 217)
        temp_h4 = random.randint(198, 202)
        temp_mold_fixed = random.randint(128, 132)
        temp_mold_moving = random.randint(128, 132)
        temp_hot_runner = random.randint(228, 232)

        # 압력: 정상 범위
        pressure_primary = random.randint(1180, 1220)
        pressure_secondary = random.randint(880, 920)
        pressure_holding = random.randint(680, 720)

        # 제품 무게: 목표 252.5g ± 2g (허용공차: 250.5~254.5g)
        target_weight = 252.5
        # 90%는 정상, 10%는 약간 벗어남
        if random.random() < 0.90:
            product_weight = round(Decimal(str(target_weight + random.uniform(-1.5, 1.5))), 2)
        else:
            product_weight = round(Decimal(str(target_weight + random.uniform(-2.5, 2.5))), 2)

        weight_deviation = round(product_weight - Decimal(str(target_weight)), 2)

        # 무게 합격 판정
        weight_ok = Decimal('250.5') <= product_weight <= Decimal('254.5')

        # 불량 판정 (일일 변동된 불량률 적용)
        has_defect = random.random() < daily_defect_rate
        defect_type_id = random.randint(1, 9) if has_defect else None
        defect_description = None
        visual_inspection_ok = not has_defect

        if has_defect:
            defect_names = [
                "Flash (플래시)", "Void (보이드)", "Weld Line (용접선)",
                "Shrinkage (수축)", "Warping (뒤틀림)", "Stress (응력)",
                "Color Variation (색상 변화)", "Surface Defect (표면 결함)",
                "Incomplete Fill (미충전)"
            ]
            defect_description = defect_names[defect_type_id - 1]

        # 작업자 ID (5명이 번갈아가며)
        operator_id = f"OP{(cycle_sequence % 5) + 1:02d}"

        return {
            'machine_id': self.machine_id,
            'mold_id': self.mold_id,
            'material_id': self.material_id,
            'cycle_date': cycle_date,
            'cycle_hour': cycle_hour,
            'cycle_minute': cycle_minute,
            'cycle_sequence': cycle_sequence,
            'temp_nh': temp_nh,
            'temp_h1': temp_h1,
            'temp_h2': temp_h2,
            'temp_h3': temp_h3,
            'temp_h4': temp_h4,
            'temp_mold_fixed': temp_mold_fixed,
            'temp_mold_moving': temp_mold_moving,
            'temp_hot_runner': temp_hot_runner,
            'pressure_primary': pressure_primary,
            'pressure_secondary': pressure_secondary,
            'pressure_holding': pressure_holding,
            'product_weight_g': product_weight,
            'weight_deviation_g': weight_deviation,
            'weight_ok': weight_ok,
            'has_defect': has_defect,
            'defect_type_id': defect_type_id,
            'defect_description': defect_description,
            'visual_inspection_ok': visual_inspection_ok,
            'operator_id': operator_id
        }

    def generate_day_data(self, target_date):
        """특정 날짜의 전체 데이터 생성"""
        logger.info(f"🔄 {target_date} 데이터 생성 시작...")

        batch_data = []

        # 일일 변동 추가: 기본값 67개/시간 ± 10% (60~74개 범위)
        base_cycles_per_hour = 67
        daily_variance = random.uniform(0.90, 1.10)  # 90~110%
        cycle_sequence_per_hour = int(base_cycles_per_hour * daily_variance)

        daily_defect_rate = random.uniform(0.008, 0.035)  # 0.8~3.5% 불량률 변동

        logger.info(f"  📊 시간당 생산 사이클: {cycle_sequence_per_hour}개 (변동: {daily_variance*100:.1f}%)")
        logger.info(f"  📊 예상 일일 불량률: {daily_defect_rate*100:.2f}%")

        # 24시간 × 변동된 사이클 수
        for hour in range(24):
            for seq in range(cycle_sequence_per_hour):
                minute = int((seq / cycle_sequence_per_hour) * 60)

                cycle_data = self.generate_cycle_data(
                    cycle_date=target_date,
                    cycle_hour=hour,
                    cycle_minute=minute,
                    cycle_sequence=seq + 1,
                    daily_defect_rate=daily_defect_rate
                )
                batch_data.append(cycle_data)

        # 배치 INSERT (1,000개씩)
        insert_sql = """
        INSERT INTO injection_cycle (
            machine_id, mold_id, material_id, cycle_date, cycle_hour, cycle_minute,
            cycle_sequence, temp_nh, temp_h1, temp_h2, temp_h3, temp_h4,
            temp_mold_fixed, temp_mold_moving, temp_hot_runner,
            pressure_primary, pressure_secondary, pressure_holding,
            product_weight_g, weight_deviation_g, weight_ok, has_defect,
            defect_type_id, defect_description, visual_inspection_ok, operator_id, created_at
        ) VALUES (
            :machine_id, :mold_id, :material_id, :cycle_date, :cycle_hour, :cycle_minute,
            :cycle_sequence, :temp_nh, :temp_h1, :temp_h2, :temp_h3, :temp_h4,
            :temp_mold_fixed, :temp_mold_moving, :temp_hot_runner,
            :pressure_primary, :pressure_secondary, :pressure_holding,
            :product_weight_g, :weight_deviation_g, :weight_ok, :has_defect,
            :defect_type_id, :defect_description, :visual_inspection_ok, :operator_id, NOW()
        )
        """

        batch_size = 1000
        for i in range(0, len(batch_data), batch_size):
            batch = batch_data[i:i + batch_size]
            try:
                with engine.connect() as conn:
                    conn.execute(text(insert_sql), batch)
                    conn.commit()
                logger.info(f"  ✅ {i + len(batch)}/{len(batch_data)} 삽입 완료")
            except Exception as e:
                logger.error(f"  ❌ 삽입 오류: {str(e)}")
                raise

        logger.info(f"✅ {target_date} 데이터 생성 완료 ({len(batch_data):,}개)")
        return len(batch_data)

    def generate_hourly_summary(self):
        """시간별 생산 요약 재생성 (최근 5일)"""
        logger.info("🔄 시간별 요약 데이터 생성 중...")

        sql = """
        INSERT INTO production_summary (
            machine_id, mold_id, material_id, summary_date, summary_hour,
            total_cycles, good_cycles, defect_cycles, defect_rate,
            avg_weight_g, min_weight_g, max_weight_g,
            avg_temp_nh, avg_pressure_primary,
            created_at
        )
        SELECT
            machine_id, mold_id, material_id,
            cycle_date, cycle_hour,
            COUNT(*) as total_cycles,
            SUM(CASE WHEN has_defect = 0 THEN 1 ELSE 0 END) as good_cycles,
            SUM(CASE WHEN has_defect = 1 THEN 1 ELSE 0 END) as defect_cycles,
            ROUND(SUM(CASE WHEN has_defect = 1 THEN 1 ELSE 0 END) / COUNT(*) * 100, 2) as defect_rate,
            ROUND(AVG(product_weight_g), 2) as avg_weight_g,
            MIN(product_weight_g) as min_weight_g,
            MAX(product_weight_g) as max_weight_g,
            ROUND(AVG(temp_nh), 2) as avg_temp_nh,
            ROUND(AVG(pressure_primary), 2) as avg_pressure_primary,
            NOW()
        FROM injection_cycle
        WHERE cycle_date >= DATE_SUB(CURDATE(), INTERVAL 5 DAY)
        GROUP BY machine_id, mold_id, material_id, cycle_date, cycle_hour
        ON DUPLICATE KEY UPDATE
            total_cycles = VALUES(total_cycles),
            good_cycles = VALUES(good_cycles),
            defect_cycles = VALUES(defect_cycles),
            defect_rate = VALUES(defect_rate),
            avg_weight_g = VALUES(avg_weight_g),
            min_weight_g = VALUES(min_weight_g),
            max_weight_g = VALUES(max_weight_g),
            avg_temp_nh = VALUES(avg_temp_nh),
            avg_pressure_primary = VALUES(avg_pressure_primary)
        """

        try:
            with engine.connect() as conn:
                conn.execute(text(sql))
                conn.commit()
            logger.info("✅ 시간별 요약 생성 완료")
        except Exception as e:
            logger.error(f"❌ 시간별 요약 생성 오류: {str(e)}")

    def generate_daily_summary(self):
        """일일 생산 요약 재생성 (최근 5일)"""
        logger.info("🔄 일일 요약 데이터 생성 중...")

        sql = """
        INSERT INTO daily_summary (
            machine_id, mold_id, material_id, summary_date,
            total_cycles, good_cycles, defect_cycles, defect_rate,
            avg_weight_g, min_weight_g, max_weight_g,
            created_at
        )
        SELECT
            machine_id, mold_id, material_id, cycle_date,
            COUNT(*) as total_cycles,
            SUM(CASE WHEN has_defect = 0 THEN 1 ELSE 0 END) as good_cycles,
            SUM(CASE WHEN has_defect = 1 THEN 1 ELSE 0 END) as defect_cycles,
            ROUND(SUM(CASE WHEN has_defect = 1 THEN 1 ELSE 0 END) / COUNT(*) * 100, 2) as defect_rate,
            ROUND(AVG(product_weight_g), 2) as avg_weight_g,
            MIN(product_weight_g) as min_weight_g,
            MAX(product_weight_g) as max_weight_g,
            NOW()
        FROM injection_cycle
        WHERE cycle_date >= DATE_SUB(CURDATE(), INTERVAL 5 DAY)
        GROUP BY machine_id, mold_id, material_id, cycle_date
        ON DUPLICATE KEY UPDATE
            total_cycles = VALUES(total_cycles),
            good_cycles = VALUES(good_cycles),
            defect_cycles = VALUES(defect_cycles),
            defect_rate = VALUES(defect_rate),
            avg_weight_g = VALUES(avg_weight_g),
            min_weight_g = VALUES(min_weight_g),
            max_weight_g = VALUES(max_weight_g)
        """

        try:
            with engine.connect() as conn:
                conn.execute(text(sql))
                conn.commit()
            logger.info("✅ 일일 요약 생성 완료")
        except Exception as e:
            logger.error(f"❌ 일일 요약 생성 오류: {str(e)}")

    def run(self):
        """전체 데이터 생성 실행"""
        logger.info("=" * 60)
        logger.info("제조 데이터 최신화 시작")
        logger.info("=" * 60)

        try:
            # 2026-01-23 ~ 2026-01-29 데이터 생성
            start_date = datetime(2026, 1, 23).date()
            end_date = datetime(2026, 1, 29).date()

            current_date = start_date
            total_cycles = 0

            while current_date <= end_date:
                cycles = self.generate_day_data(current_date)
                total_cycles += cycles
                current_date += timedelta(days=1)

            # 요약 데이터 생성
            self.generate_hourly_summary()
            self.generate_daily_summary()

            logger.info("=" * 60)
            logger.info(f"✅ 모든 데이터 생성 완료!")
            logger.info(f"   - 생성된 사이클: {total_cycles:,}개")
            logger.info(f"   - 날짜 범위: 2026-01-23 ~ 2026-01-29")
            logger.info(f"   - 최신 날짜: 2026-01-29")
            logger.info("=" * 60)

        except Exception as e:
            logger.error(f"❌ 데이터 생성 오류: {str(e)}")
            raise
        finally:
            self.session.close()


if __name__ == "__main__":
    generator = ManufacturingDataGenerator()
    generator.run()
