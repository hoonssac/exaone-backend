#!/usr/bin/env python3
"""
2026-01-23 ~ 2026-01-28 현실적인 제조 데이터 생성
"""

import sys
sys.path.insert(0, '/app')

from datetime import datetime, timedelta
from decimal import Decimal
import random
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

# MySQL 연결
DATABASE_URL = "mysql+pymysql://exaone_user:exaone_password@mysql:3306/manufacturing"
engine = create_engine(DATABASE_URL, echo=False)
Session = sessionmaker(bind=engine)
session = Session()

# 현실적인 제조 데이터 생성
dates = [
    datetime(2026, 1, 23).date(),
    datetime(2026, 1, 24).date(),
    datetime(2026, 1, 25).date(),
    datetime(2026, 1, 26).date(),
    datetime(2026, 1, 27).date(),
    datetime(2026, 1, 28).date(),
    datetime(2026, 1, 29).date(),
]

# 각 날짜별로 현실적인 값
data_for_dates = [
    {
        'date': dates[0],  # 2026-01-23
        'total_cycles': 1580,
        'good_products': 1560,
        'defective': 20,
        'target': 1600,
        'operating_hours': 8,
        'downtime': 15,
        'downtime_reason': '정기점검',
        'avg_weight': 252.3,
        'min_weight': 250.8,
        'max_weight': 253.9,
        'weight_out_of_spec': 2,
        'avg_cylinder_temp': 220,
        'avg_mold_temp': 130,
        'flash': 5,
        'void': 3,
        'weld_line': 2,
        'jetting': 1,
        'flow_mark': 2,
        'other_defect': 7,
    },
    {
        'date': dates[1],  # 2026-01-24
        'total_cycles': 1620,
        'good_products': 1598,
        'defective': 22,
        'target': 1600,
        'operating_hours': 8,
        'downtime': 10,
        'downtime_reason': '금형 교체',
        'avg_weight': 252.1,
        'min_weight': 250.5,
        'max_weight': 254.2,
        'weight_out_of_spec': 1,
        'avg_cylinder_temp': 219,
        'avg_mold_temp': 131,
        'flash': 6,
        'void': 4,
        'weld_line': 1,
        'jetting': 2,
        'flow_mark': 3,
        'other_defect': 6,
    },
    {
        'date': dates[2],  # 2026-01-25
        'total_cycles': 1650,
        'good_products': 1630,
        'defective': 20,
        'target': 1600,
        'operating_hours': 8,
        'downtime': 5,
        'downtime_reason': None,
        'avg_weight': 252.5,
        'min_weight': 250.7,
        'max_weight': 254.0,
        'weight_out_of_spec': 0,
        'avg_cylinder_temp': 221,
        'avg_mold_temp': 129,
        'flash': 4,
        'void': 2,
        'weld_line': 3,
        'jetting': 1,
        'flow_mark': 1,
        'other_defect': 9,
    },
    {
        'date': dates[3],  # 2026-01-26
        'total_cycles': 1590,
        'good_products': 1560,
        'defective': 30,
        'target': 1600,
        'operating_hours': 7,
        'downtime': 45,
        'downtime_reason': '온도 센서 교체',
        'avg_weight': 251.9,
        'min_weight': 249.8,
        'max_weight': 254.5,
        'weight_out_of_spec': 4,
        'avg_cylinder_temp': 218,
        'avg_mold_temp': 132,
        'flash': 10,
        'void': 6,
        'weld_line': 2,
        'jetting': 3,
        'flow_mark': 2,
        'other_defect': 7,
    },
    {
        'date': dates[4],  # 2026-01-27
        'total_cycles': 1610,
        'good_products': 1585,
        'defective': 25,
        'target': 1600,
        'operating_hours': 8,
        'downtime': 20,
        'downtime_reason': '라인 점검',
        'avg_weight': 252.4,
        'min_weight': 250.9,
        'max_weight': 254.1,
        'weight_out_of_spec': 1,
        'avg_cylinder_temp': 220,
        'avg_mold_temp': 130,
        'flash': 7,
        'void': 3,
        'weld_line': 2,
        'jetting': 2,
        'flow_mark': 2,
        'other_defect': 9,
    },
    {
        'date': dates[5],  # 2026-01-28
        'total_cycles': 1625,
        'good_products': 1600,
        'defective': 25,
        'target': 1600,
        'operating_hours': 8,
        'downtime': 12,
        'downtime_reason': None,
        'avg_weight': 252.2,
        'min_weight': 250.6,
        'max_weight': 254.3,
        'weight_out_of_spec': 2,
        'avg_cylinder_temp': 221,
        'avg_mold_temp': 129,
        'flash': 5,
        'void': 4,
        'weld_line': 2,
        'jetting': 1,
        'flow_mark': 2,
        'other_defect': 11,
    },
    {
        'date': dates[6],  # 2026-01-29 (오늘)
        'total_cycles': 1640,
        'good_products': 1618,
        'defective': 22,
        'target': 1600,
        'operating_hours': 8,
        'downtime': 8,
        'downtime_reason': None,
        'avg_weight': 252.3,
        'min_weight': 250.8,
        'max_weight': 254.1,
        'weight_out_of_spec': 1,
        'avg_cylinder_temp': 220,
        'avg_mold_temp': 130,
        'flash': 4,
        'void': 3,
        'weld_line': 2,
        'jetting': 1,
        'flow_mark': 1,
        'other_defect': 11,
    },
]

# 기존 데이터 삭제 (2026-01-23 이후)
try:
    session.execute(text("DELETE FROM daily_production WHERE production_date >= '2026-01-23'"))
    session.commit()
    print("✅ 기존 데이터 삭제 완료")
except Exception as e:
    print(f"❌ 삭제 오류: {e}")
    session.rollback()

# 새 데이터 삽입
try:
    for data in data_for_dates:
        defect_rate = round(data['defective'] / data['total_cycles'] * 100, 2)
        production_rate = round(data['total_cycles'] / data['target'] * 100, 2)

        sql = """
        INSERT INTO daily_production (
            production_date, machine_id, mold_id,
            total_cycles_produced, good_products_count, defective_count, defect_rate,
            target_production, production_rate,
            operating_hours_actual, downtime_minutes, downtime_reason,
            avg_weight_g, weight_min_g, weight_max_g, weight_out_of_spec_count,
            avg_cylinder_temp, avg_mold_temp, temp_stability_ok,
            flash_count, void_count, weld_line_count, jetting_count, flow_mark_count, other_defect_count
        ) VALUES (
            :production_date, 1, 1,
            :total_cycles, :good_products, :defective, :defect_rate,
            :target, :production_rate,
            :operating_hours, :downtime, :downtime_reason,
            :avg_weight, :min_weight, :max_weight, :weight_out_of_spec,
            :avg_cylinder_temp, :avg_mold_temp, 1,
            :flash, :void, :weld_line, :jetting, :flow_mark, :other_defect
        )
        """

        session.execute(text(sql), {
            'production_date': data['date'],
            'total_cycles': data['total_cycles'],
            'good_products': data['good_products'],
            'defective': data['defective'],
            'defect_rate': defect_rate,
            'target': data['target'],
            'production_rate': production_rate,
            'operating_hours': data['operating_hours'],
            'downtime': data['downtime'],
            'downtime_reason': data['downtime_reason'],
            'avg_weight': Decimal(str(data['avg_weight'])),
            'min_weight': Decimal(str(data['min_weight'])),
            'max_weight': Decimal(str(data['max_weight'])),
            'weight_out_of_spec': data['weight_out_of_spec'],
            'avg_cylinder_temp': data['avg_cylinder_temp'],
            'avg_mold_temp': data['avg_mold_temp'],
            'flash': data['flash'],
            'void': data['void'],
            'weld_line': data['weld_line'],
            'jetting': data['jetting'],
            'flow_mark': data['flow_mark'],
            'other_defect': data['other_defect'],
        })

    session.commit()
    print("=" * 60)
    print("✅ 현실적인 제조 데이터 생성 완료!")
    print("=" * 60)
    print("\n생성된 데이터:")
    print("-" * 60)

    for data in data_for_dates:
        result = session.execute(text(
            "SELECT total_cycles_produced, good_products_count, defective_count, defect_rate, production_rate FROM daily_production WHERE production_date = :date"
        ), {'date': data['date']}).fetchone()

        if result:
            print(f"📅 {data['date']} | 생산: {result[0]}개 | 양품: {result[1]}개 | 불량: {result[2]}개 | 불량률: {result[3]}% | 생산율: {result[4]}%")

    print("-" * 60)

except Exception as e:
    print(f"❌ 데이터 삽입 오류: {e}")
    session.rollback()
finally:
    session.close()
