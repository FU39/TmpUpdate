from pydantic import BaseModel
from typing import List


class Cycle(BaseModel):
    """
    供暖/供热周期 格式为MM-dd
    """
    start: str  # 周期开始时间
    end: str  # 周期结束时间


class LoadItem(BaseModel):
    name: str
    type: str
    temperature: float
    load8760: List[float]


class Base(BaseModel):
    area_outside: float
    power_pv_house_top: float
    base_method_heating: str
    base_method_cooling: str
    base_method_steam: str
    base_method_hotwater: str
    cer_enable: bool
    cer: float
    other_investment: float


class SteamBuySellItem(BaseModel):
    id: int
    name: str
    temperature: float
    price: float
    enable: bool


class HeatResource(BaseModel):
    """
    供暖资源配置
    """
    flag: bool
    heat_resource_flow: List[float]
    temperature_upper_limit: float
    temperature_decrease_limit: float
    cycle: Cycle


class Trading(BaseModel):
    power_buy_enable: bool
    power_sell_enable: bool
    power_buy_price_type: str
    h2_buy_enable: bool
    h2_sell_enable: bool
    heating_buy_enable: bool
    heating_sell_enable: bool
    steam_buy: List[SteamBuySellItem]
    steam_sell: List[SteamBuySellItem]
    power_buy_24_price: List[float]
    power_buy_8760_price: List[float]
    power_sell_24_price: List[float]
    power_sell_price: float
    heat_sell_price: float
    hydrogen_sell_price: float
    heat_buy_price: float
    cool_buy_price: float
    carbon_buy_price: float
    hydrogen_buy_price: float
    heat_resource: HeatResource  # 修改: 将 heat_resource 的类型从 dict 修改为 HeatResource


class Income(BaseModel):
    power_type: str
    power_price: float
    heat_type: str
    heat_price: float
    cool_type: str
    cool_price: float
    hot_water_price: float
    steam_price: float


# 新增设备相关的 BaseModel 定义
class CO(BaseModel):
    power_already: float
    power_max: float
    power_min: float
    cost: float
    crf: float
    se: float
    beta_co: float


class FC(BaseModel):
    power_already: float
    power_max: float
    power_min: float
    cost: float
    crf: float
    se: float
    eta_fc_p: float
    eta_ex_g: float
    theta_ex: float


class HT(BaseModel):
    water_already: float
    water_max: float
    water_min: float
    cost: float
    crf: float
    se: float
    t_max: float
    t_min: float
    t_supply: float


class EB(BaseModel):
    power_already: float
    power_max: float
    power_min: float
    cost: float
    crf: float
    se: float
    beta_eb: float


class AC(BaseModel):
    power_already: float
    power_max: float
    power_min: float
    cost: float
    crf: float
    se: float
    beta_ac: float


class HP(BaseModel):
    power_already: float
    power_max: float
    power_min: float
    cost: float
    crf: float
    se: float
    beta_hpg: float
    beta_hpq: float


class GHP(BaseModel):
    power_already: float
    balance_flag: int
    power_max: float
    power_min: float
    cost: float
    crf: float
    se: float
    beta_ghpg: float
    beta_ghpq: float


class GTW(BaseModel):
    number_already: float
    number_max: float
    number_min: float
    cost: float
    crf: float
    se: float
    beta_gtw: float


class GHPDeep(BaseModel):
    power_already: float
    balance_flag: int
    power_max: float
    power_min: float
    cost: float
    crf: float
    se: float
    beta_ghpg: float


class GTW2500(BaseModel):
    number_already: float
    number_max: float
    number_min: float
    cost: float
    crf: float
    se: float
    beta_gtw: float


class CT(BaseModel):
    water_already: float
    water_max: float
    water_min: float
    cost: float
    crf: float
    se: float
    t_max: float
    t_min: float
    t_supply: float


class HST(BaseModel):
    sto_already: float
    sto_max: float
    sto_min: float
    cost: float
    crf: float
    se: float
    pressure_upper: float
    pressure_lower: float
    inout_max: float


class EL(BaseModel):
    nm3_already: float
    nm3_max: float
    nm3_min: float
    cost: float
    crf: float
    eta_el_h: float
    eta_ex_g: float
    theta_ex: float


class SC(BaseModel):
    area_already: float
    area_max: float
    area_min: float
    cost: float
    crf: float
    beta_sc: float
    theta_ex: float
    solar_data8760: List[float]
    s_sc_per_unit: float


class PV(BaseModel):
    power_already: float
    power_max: float
    power_min: float
    cost: float
    crf: float
    pv_data8760: List[float]
    s_pv_per_unit: float


class WD(BaseModel):
    number_already: float
    number_max: float
    number_min: float
    capacity_unit: float
    wd_data8760: List[float]
    cost: float
    crf: float
    s_pv_per_unit: float


class HP120(BaseModel):
    power_already: float
    power_max: float
    power_min: float
    cost: float
    crf: float
    cop: float
    temperature_in: float
    temperature_out: float


class CO180(BaseModel):
    power_already: float
    power_max: float
    power_min: float
    k_e_m: float
    cost: float
    crf: float
    temperature_in: float
    temperature_out: float


class WHP(BaseModel):
    power_already: float
    power_max: float
    power_min: float
    cost: float
    crf: float
    cop_heat: float
    cop_cold: float


class BAT(BaseModel):
    power_already: float
    power_max: float
    power_min: float
    cost: float
    crf: float
    ele_storage_max_per_unit: float
    ele_storage_min_per_unit: float
    ele_power_max_per_unit: float
    ele_power_min_per_unit: float
    miu_loss: float


class BioStorage(BaseModel):
    bio_already: float
    bio_max: float
    bio_min: float
    cost: float
    crf: float


class SteamStorage(BaseModel):
    water_already: float
    water_max: float
    water_min: float
    cost: float
    crf: float
    steam_storage_max_per_unit: float
    steam_storage_min_per_unit: float
    steam_power_max_per_unit: float
    steam_power_min_per_unit: float
    miu_loss: float


# 修改 Device 类，将 dict 替换为具体的 BaseModel 类型
class Device(BaseModel):
    """
    设备配置类，包含各种能源设备的详细配置。
    """
    co: CO  # 氢气压缩机
    fc: FC  # 燃料电池
    ht: HT  # 储热水箱
    eb: EB  # 电锅炉
    ac: AC  # 空调
    hp: HP  # 空气源热泵
    ghp: GHP  # 浅层地源热泵
    gtw: GTW  # 浅层地埋井
    ghp_deep: GHPDeep  # 中深层地源热泵
    gtw2500: GTW2500  # 中深层地埋井，深度2500
    ct: CT  # 储冷水箱
    hst: HST  # 储氢罐
    el: EL  # 电解槽
    sc: SC  # 太阳能集热器
    pv: PV  # 光伏板
    wd: WD  # 风机
    hp120: HP120  # 高温热泵
    co180: CO180  # 高温蒸汽压缩机
    whp: WHP  # 余热热泵
    bat: BAT  # 电池储能
    bio_storage: BioStorage  # 生物质储能
    steam_storage: SteamStorage  # 蒸汽储能


class CustomDeviceStorage(BaseModel):
    device_name: str
    energy_type: str
    device_already: float
    device_max: float
    device_min: float
    cost: float
    crf: float
    energy_storage_max_per_unit: float
    energy_storage_min_per_unit: float
    energy_power_max_per_unit: float
    energy_power_min_per_unit: float
    energy_loss: float


class CustomDeviceExchange(BaseModel):
    device_name: str
    energy_in_type: str
    energy_out_type: str
    device_already: float
    device_max: float
    device_min: float
    cost: float
    crf: float
    energy_in_standard_per_unit: float
    energy_out_standard_per_unit: float


class OptimizationBody(BaseModel):
    objective_load: List[LoadItem]
    base: Base
    trading: Trading
    income: Income
    device: Device
    custom_device_storage: List[CustomDeviceStorage]
    custom_device_exchange: List[CustomDeviceExchange]
