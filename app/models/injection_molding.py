"""
사출 성형 제조 데이터 모델 (MySQL)

injection_molding_machine, mold_info, material_spec, injection_cycle 등
사출 성형 제조 시스템의 모든 테이블 정의
"""

from sqlalchemy import Column, Integer, String, Text, DateTime, Float, Boolean, Date, DECIMAL, BigInteger, TINYINT, ForeignKey
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.db.database import Base


# ============================================================================
# 마스터 데이터 테이블
# ============================================================================

class InjectionMoldingMachine(Base):
    """
    사출기 설비 정보
    850톤 사출기 등 기본 정보 저장
    """
    __tablename__ = "injection_molding_machine"

    id = Column(Integer, primary_key=True, autoincrement=True, comment="설비 ID")
    equipment_id = Column(String(50), unique=True, nullable=False, comment="설비 코드 (IM-850-001)")
    equipment_name = Column(String(100), nullable=False, comment="설비명")
    manufacturer = Column(String(100), comment="제조사 (경성정밀)")
    capacity_ton = Column(Integer, nullable=False, comment="사출 톤수 (850)")
    installation_date = Column(Date, comment="설치 일자")
    last_maintenance_date = Column(Date, comment="마지막 유지보수 일자")
    status = Column(String(20), default="가동", comment="상태 (가동/정지/점검)")
    operating_hours = Column(BigInteger, default=0, comment="누적 가동 시간")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), comment="등록 일시")

    def __repr__(self):
        return f"<InjectionMoldingMachine(id={self.id}, equipment_id={self.equipment_id})>"


class MoldInfo(Base):
    """
    금형 정보
    DC1 (Cap Decor Upper) 등 금형 사양 저장
    """
    __tablename__ = "mold_info"

    id = Column(Integer, primary_key=True, autoincrement=True, comment="금형 ID")
    mold_code = Column(String(50), unique=True, nullable=False, comment="금형 코드 (DC1)")
    mold_name = Column(String(100), nullable=False, comment="금형명 (Cap Decor Upper(GD))")
    product_code = Column(String(50), nullable=False, comment="제품 코드 (CPGMREFX23)")
    product_name = Column(String(100), nullable=False, comment="제품명")
    cavity_count = Column(Integer, default=1, comment="캐비티 수")
    target_weight_g = Column(DECIMAL(8, 2), nullable=False, comment="목표 제품 무게 (252.5g)")
    target_weight_tolerance_minus = Column(DECIMAL(8, 2), comment="무게 허용공차 - (250.5g)")
    target_weight_tolerance_plus = Column(DECIMAL(8, 2), comment="무게 허용공차 + (254.5g)")
    runner_weight_g = Column(DECIMAL(8, 2), comment="러너 무게 (14.0g)")
    total_weight_g = Column(DECIMAL(8, 2), comment="총 무게 (519.0g)")
    cooling_zones = Column(Integer, comment="냉각 존 수")
    hot_runner_zones = Column(Integer, comment="핫 러너 존 수")
    mold_manufacturer = Column(String(100), comment="금형 제작사")
    status = Column(String(20), default="사용중", comment="상태 (사용중/정지/유지보수)")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), comment="등록 일시")

    def __repr__(self):
        return f"<MoldInfo(id={self.id}, mold_code={self.mold_code}, product_name={self.product_name})>"


class MaterialSpec(Base):
    """
    원재료 사양
    HIPS 등 재료 물성 및 온도 설정값 저장
    """
    __tablename__ = "material_spec"

    id = Column(Integer, primary_key=True, autoincrement=True, comment="자재 ID")
    material_code = Column(String(50), unique=True, nullable=False, comment="자재 코드 (HIPS-001)")
    material_name = Column(String(100), nullable=False, comment="자재명 (HIPS)")
    material_grade = Column(String(50), comment="등급 (Grade A)")
    color = Column(String(50), comment="색상 (Black)")
    supplier = Column(String(100), comment="공급사 (LG Chem)")
    cylinder_temp_nh = Column(Integer, comment="NH 온도 (220℃)")
    cylinder_temp_h1 = Column(Integer, comment="H1 온도 (225℃)")
    cylinder_temp_h2 = Column(Integer, comment="H2 온도 (230℃)")
    cylinder_temp_h3 = Column(Integer, comment="H3 온도 (215℃)")
    cylinder_temp_h4 = Column(Integer, comment="H4 온도 (200℃)")
    melting_point_min = Column(Integer, comment="최소 용융 온도 (180℃)")
    melting_point_max = Column(Integer, comment="최대 용융 온도 (240℃)")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), comment="등록 일시")

    def __repr__(self):
        return f"<MaterialSpec(id={self.id}, material_code={self.material_code})>"


class InjectionProcessParameter(Base):
    """
    공정 파라미터
    금형과 재료별 최적 공정 조건 (온도, 압력, 시간 등)
    """
    __tablename__ = "injection_process_parameter"

    id = Column(Integer, primary_key=True, autoincrement=True, comment="파라미터 ID")
    mold_id = Column(Integer, ForeignKey("mold_info.id"), nullable=False, comment="금형 ID (외래키)")
    material_id = Column(Integer, ForeignKey("material_spec.id"), nullable=False, comment="재료 ID (외래키)")
    injection_time = Column(Integer, comment="사출 시간 (8.7초)")
    pressure_hold_time = Column(Integer, comment="보압 시간 (25초)")
    cooling_time = Column(Integer, comment="냉각 시간 (10초)")
    mold_open_time = Column(Integer, comment="금형 개방 시간 (10초)")
    ejection_time = Column(Integer, comment="취출 시간 (0초)")
    total_cycle_time = Column(Integer, comment="전체 사이클 시간 (53.7초)")
    injection_pressure_primary = Column(Integer, comment="1차 사출 압력 (1200bar)")
    injection_pressure_secondary = Column(Integer, comment="2차 사출 압력 (900bar)")
    holding_pressure = Column(Integer, comment="보압 (700bar)")
    back_pressure = Column(Integer, comment="배압 (70bar)")
    mold_temp_fixed = Column(Integer, comment="고정측 금형 온도 (130℃)")
    mold_temp_moving = Column(Integer, comment="가동측 금형 온도 (130℃)")
    hot_runner_temp = Column(Integer, comment="핫 러너 온도 (230℃)")
    screw_rotation_speed = Column(Integer, comment="스크류 회전 속도 (60rpm)")
    metering_distance = Column(Integer, comment="계량 거리 (70mm)")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), comment="등록 일시")

    def __repr__(self):
        return f"<InjectionProcessParameter(id={self.id}, mold_id={self.mold_id})>"


class InjectionDefectType(Base):
    """
    불량 유형
    Flash, Void, Weld Line 등 9가지 불량 유형 정의
    """
    __tablename__ = "injection_defect_type"

    id = Column(Integer, primary_key=True, autoincrement=True, comment="불량 유형 ID")
    defect_code = Column(String(50), unique=True, nullable=False, comment="불량 코드 (D001-D009)")
    defect_name_kr = Column(String(100), nullable=False, comment="불량명 (한글)")
    defect_name_en = Column(String(100), comment="불량명 (영문)")
    defect_category = Column(String(50), comment="불량 분류 (외관/기능/치수)")
    severity = Column(String(20), comment="심각도 (경/중/심)")
    cause_description = Column(Text, comment="원인 설명")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), comment="등록 일시")

    def __repr__(self):
        return f"<InjectionDefectType(id={self.id}, defect_code={self.defect_code}, name={self.defect_name_kr})>"


# ============================================================================
# 생산 데이터 테이블 (핵심)
# ============================================================================

class InjectionCycle(Base):
    """
    개별 사이클 데이터 (핵심 테이블)
    각 사이클마다 기록되는 상세한 생산 데이터
    585,920행 (365일 × 24시간 × 67개/시간)
    """
    __tablename__ = "injection_cycle"

    id = Column(BigInteger, primary_key=True, autoincrement=True, comment="사이클 ID")
    machine_id = Column(Integer, ForeignKey("injection_molding_machine.id"), nullable=False, comment="설비 ID")
    mold_id = Column(Integer, ForeignKey("mold_info.id"), nullable=False, comment="금형 ID")
    material_id = Column(Integer, ForeignKey("material_spec.id"), nullable=False, comment="재료 ID")
    cycle_date = Column(Date, nullable=False, comment="사이클 실행 날짜")
    cycle_hour = Column(TINYINT, nullable=False, comment="시간 (0-23)")
    cycle_minute = Column(TINYINT, nullable=False, comment="분 (0-59)")
    cycle_sequence = Column(Integer, nullable=False, comment="시간 내 순서")

    # 온도 데이터
    temp_nh = Column(Integer, comment="NH 온도 (℃)")
    temp_h1 = Column(Integer, comment="H1 온도 (℃)")
    temp_h2 = Column(Integer, comment="H2 온도 (℃)")
    temp_h3 = Column(Integer, comment="H3 온도 (℃)")
    temp_h4 = Column(Integer, comment="H4 온도 (℃)")
    temp_mold_fixed = Column(Integer, comment="고정측 금형 온도 (℃)")
    temp_mold_moving = Column(Integer, comment="가동측 금형 온도 (℃)")
    temp_hot_runner = Column(Integer, comment="핫 러너 온도 (℃)")

    # 압력 데이터
    pressure_primary = Column(Integer, comment="1차 사출 압력 (bar)")
    pressure_secondary = Column(Integer, comment="2차 사출 압력 (bar)")
    pressure_holding = Column(Integer, comment="보압 (bar)")

    # 결과 데이터
    product_weight_g = Column(DECIMAL(8, 2), comment="제품 무게 (g)")
    weight_deviation_g = Column(DECIMAL(8, 2), comment="목표 대비 편차 (g)")
    weight_ok = Column(Boolean, comment="무게 합격 여부")
    has_defect = Column(Boolean, default=False, comment="불량 여부")
    defect_type_id = Column(Integer, ForeignKey("injection_defect_type.id"), comment="불량 유형 ID")
    defect_description = Column(String(255), comment="불량 설명")
    visual_inspection_ok = Column(Boolean, comment="외관 검사 합격 여부")

    operator_id = Column(String(50), comment="담당 작업자 ID")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), comment="등록 일시")

    def __repr__(self):
        return f"<InjectionCycle(id={self.id}, date={self.cycle_date}, weight={self.product_weight_g})>"


class ProductionSummary(Base):
    """
    시간별 생산 요약
    injection_cycle을 1시간 단위로 집계
    8,760행 (365일 × 24시간)
    """
    __tablename__ = "production_summary"

    id = Column(BigInteger, primary_key=True, autoincrement=True, comment="요약 ID")
    summary_date = Column(Date, nullable=False, comment="요약 날짜")
    summary_hour = Column(TINYINT, nullable=False, comment="시간 (0-23)")
    machine_id = Column(Integer, ForeignKey("injection_molding_machine.id"), nullable=False, comment="설비 ID")
    mold_id = Column(Integer, ForeignKey("mold_info.id"), nullable=False, comment="금형 ID")

    total_cycles = Column(Integer, default=0, comment="총 사이클 수")
    good_products = Column(Integer, default=0, comment="정상 제품 수")
    defective_products = Column(Integer, default=0, comment="불량 제품 수")
    defect_rate = Column(DECIMAL(5, 2), comment="불량률 (%)")

    avg_weight_g = Column(DECIMAL(8, 2), comment="평균 무게 (g)")
    weight_variance = Column(DECIMAL(8, 2), comment="무게 표준편차")
    weight_out_of_spec = Column(Integer, default=0, comment="규격 외 무게 개수")

    avg_temp_h1 = Column(DECIMAL(5, 2), comment="평균 H1 온도 (℃)")
    avg_temp_h2 = Column(DECIMAL(5, 2), comment="평균 H2 온도 (℃)")
    avg_temp_mold = Column(DECIMAL(5, 2), comment="평균 금형 온도 (℃)")

    flash_count = Column(Integer, default=0, comment="Flash 불량 수")
    void_count = Column(Integer, default=0, comment="Void 불량 수")
    weld_line_count = Column(Integer, default=0, comment="Weld Line 불량 수")
    jetting_count = Column(Integer, default=0, comment="Jetting 불량 수")

    created_at = Column(DateTime(timezone=True), server_default=func.now(), comment="등록 일시")

    def __repr__(self):
        return f"<ProductionSummary(date={self.summary_date}, hour={self.summary_hour})>"


class DailyProduction(Base):
    """
    일별 생산 통계
    injection_cycle을 1일 단위로 집계
    365행 (365일)
    """
    __tablename__ = "daily_production"

    id = Column(BigInteger, primary_key=True, autoincrement=True, comment="요약 ID")
    production_date = Column(Date, nullable=False, unique=True, comment="생산 날짜")
    machine_id = Column(Integer, ForeignKey("injection_molding_machine.id"), nullable=False, comment="설비 ID")
    mold_id = Column(Integer, ForeignKey("mold_info.id"), nullable=False, comment="금형 ID")

    total_cycles_produced = Column(Integer, default=0, comment="총 사이클 수")
    good_products_count = Column(Integer, default=0, comment="정상 제품 개수")
    defective_count = Column(Integer, default=0, comment="불량 제품 개수")
    defect_rate = Column(DECIMAL(5, 2), comment="불량률 (%)")

    target_production = Column(Integer, comment="목표 생산량 (1,608)")
    production_rate = Column(DECIMAL(5, 2), comment="생산 달성률 (%)")
    operating_hours_actual = Column(Integer, comment="실제 가동 시간")
    downtime_minutes = Column(Integer, default=0, comment="정지 시간 (분)")
    downtime_reason = Column(String(255), comment="정지 사유")

    avg_weight_g = Column(DECIMAL(8, 2), comment="평균 무게 (g)")
    weight_min_g = Column(DECIMAL(8, 2), comment="최소 무게 (g)")
    weight_max_g = Column(DECIMAL(8, 2), comment="최대 무게 (g)")
    weight_out_of_spec_count = Column(Integer, default=0, comment="규격 외 무게 개수")

    avg_cylinder_temp = Column(DECIMAL(5, 2), comment="평균 실린더 온도 (℃)")
    avg_mold_temp = Column(DECIMAL(5, 2), comment="평균 금형 온도 (℃)")
    temp_stability_ok = Column(Boolean, default=True, comment="온도 안정성 여부")

    flash_count = Column(Integer, default=0, comment="Flash 불량 수")
    void_count = Column(Integer, default=0, comment="Void 불량 수")
    weld_line_count = Column(Integer, default=0, comment="Weld Line 불량 수")
    jetting_count = Column(Integer, default=0, comment="Jetting 불량 수")
    flow_mark_count = Column(Integer, default=0, comment="Flow Mark 불량 수")
    other_defect_count = Column(Integer, default=0, comment="기타 불량 수")

    created_at = Column(DateTime(timezone=True), server_default=func.now(), comment="등록 일시")

    def __repr__(self):
        return f"<DailyProduction(date={self.production_date}, defect_rate={self.defect_rate})>"


# ============================================================================
# 운영 데이터 테이블
# ============================================================================

class EquipmentMaintenance(Base):
    """
    설비 유지보수
    정기, 수리, 개선 등 유지보수 기록
    """
    __tablename__ = "equipment_maintenance"

    id = Column(BigInteger, primary_key=True, autoincrement=True, comment="유지보수 ID")
    machine_id = Column(Integer, ForeignKey("injection_molding_machine.id"), nullable=False, comment="설비 ID")
    maintenance_type = Column(String(50), comment="유지보수 유형 (정기/수리/개선)")
    scheduled_date = Column(Date, nullable=False, comment="예정 일자")
    actual_date = Column(Date, comment="실제 시공 일자")
    technician_name = Column(String(50), comment="담당 기술자")
    description = Column(Text, comment="작업 내용")
    parts_replaced = Column(String(255), comment="교체 부품")
    cost = Column(DECIMAL(10, 2), comment="작업 비용 (원)")
    status = Column(String(20), comment="상태 (예정/진행중/완료)")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), comment="등록 일시")

    def __repr__(self):
        return f"<EquipmentMaintenance(id={self.id}, type={self.maintenance_type}, status={self.status})>"


class EnergyUsage(Base):
    """
    에너지 사용량
    시간별 전력, 냉각수 등 에너지 소비 기록
    """
    __tablename__ = "energy_usage"

    id = Column(BigInteger, primary_key=True, autoincrement=True, comment="에너지 ID")
    machine_id = Column(Integer, ForeignKey("injection_molding_machine.id"), nullable=False, comment="설비 ID")
    energy_type = Column(String(20), comment="에너지 유형 (전력/냉각수)")
    usage_date = Column(Date, nullable=False, comment="사용 날짜")
    usage_hour = Column(TINYINT, comment="시간 (0-23)")
    consumption_value = Column(DECIMAL(12, 2), nullable=False, comment="사용량")
    unit = Column(String(10), comment="단위 (kWh/ton)")
    cost = Column(DECIMAL(10, 2), comment="비용 (원)")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), comment="등록 일시")

    def __repr__(self):
        return f"<EnergyUsage(id={self.id}, date={self.usage_date}, type={self.energy_type})>"
