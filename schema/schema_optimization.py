from pydantic import BaseModel
from typing import List, Optional


class Cycle(BaseModel):
    """
    供暖/供热周期 格式为MM-dd
    """
    start: Optional[str] = None  # 周期开始时间，设为可选
    end: Optional[str] = None  # 周期结束时间，设为可选


class Base(BaseModel):
    area_outside: Optional[float] = None
    power_pv_house_top: Optional[float] = None
    base_method_heating: Optional[str] = None
    base_method_cooling: Optional[str] = None
    base_method_steam: Optional[str] = None
    base_method_hotwater: Optional[str] = None
    cer_enable: Optional[bool] = None
    cer: Optional[float] = None
    other_investment: Optional[float] = None


class SteamBuySellItem(BaseModel):
    temperature: Optional[int] = None
    price: Optional[float] = None


class HeatResource(BaseModel):
    """
    供暖资源配置
    """
    flag: Optional[bool] = None
    heat_resource_flow: Optional[List[float]] = None
    temperature_upper_limit: Optional[float] = None
    temperature_decrease_limit: Optional[float] = None
    cycle: Optional[Cycle] = None


class Trading(BaseModel):
    power_buy_enable: Optional[bool] = None
    power_sell_enable: Optional[bool] = None
    power_buy_price_type: Optional[str] = None
    heat_buy_enable: Optional[bool] = None  # 买热许可
    heat_sell_enable: Optional[bool] = None  # 卖热许可
    cool_buy_enable: Optional[bool] = None  # 买冷许可
    cool_sell_enable: Optional[bool] = None  # 卖冷许可
    h2_buy_enable: Optional[bool] = None  # 买氢许可
    h2_sell_enable: Optional[bool] = None  # 卖氢许可
    steam_buy_enable: Optional[bool] = None  # 买蒸汽许可
    steam_sell_enable: Optional[bool] = None  # 卖蒸汽许可
    steam_buy: Optional[List[SteamBuySellItem]] = None
    steam_sell: Optional[List[SteamBuySellItem]] = None
    hotwater_buy_enable: Optional[bool] = None  # 买热水许可
    hotwater_sell_enable: Optional[bool] = None  # 卖热水许可
    power_buy_24_price: Optional[List[float]] = None
    power_buy_8760_price: Optional[List[float]] = None
    power_buy_capacity_price: Optional[float] = None  # 容量电价
    power_sell_24_price: Optional[List[float]] = None
    # 取消 power_sell_price，若只为单值价格，请拓为 24h，即 power_sell_24_price
    heat_buy_price: Optional[float] = None
    heat_sell_price: Optional[float] = None
    cool_buy_price: Optional[float] = None
    cool_sell_price: Optional[float] = None  # 卖冷单价
    hydrogen_buy_price: Optional[float] = None
    hydrogen_sell_price: Optional[float] = None
    hotwater_buy_price: Optional[float] = None  # 买热水单价
    hotwater_sell_price: Optional[float] = None  # 卖热水单价
    gas_buy_price: Optional[float] = None  # 买天然气单价
    carbon_buy_price: Optional[float] = None
    heat_resource: Optional[HeatResource] = None  # 修改: 将 heat_resource 的类型从 dict 修改为 HeatResource


class Income(BaseModel):
    power_type: Optional[str] = None
    power_price: Optional[float] = None
    heat_type: Optional[str] = None
    heat_price: Optional[float] = None
    cool_type: Optional[str] = None
    cool_price: Optional[float] = None
    hot_water_price: Optional[float] = None
    steam_price: Optional[float] = None


# 新增设备相关的 BaseModel 定义
class CO(BaseModel):
    used: bool = True  # 添加 used 字段，默认值为 True
    power_already: float = 1000
    power_max: float = 10000
    power_min: float = 0
    cost: float = 1000
    crf: float = 10
    beta_co: float = 1.399


class FC(BaseModel):
    used: bool = True  # 添加 used 字段，默认值为 True
    power_already: float = 1
    power_max: float = 10000000
    power_min: float = 300
    cost: float = 8000
    crf: float = 10
    eta_fc_p: float = 15
    eta_ex_g: float = 17
    theta_ex: float = 0.95


class EL(BaseModel):
    used: bool = True  # 添加 used 字段，默认值为 True
    nm3_already: float = 0
    nm3_max: float = 100000
    nm3_min: float = 0
    cost: float = 2240
    crf: float = 7
    eta_el_h: float = 15
    eta_ex_g: float = 17
    theta_ex: float = 0.95


class HST(BaseModel):
    used: bool = True  # 添加 used 字段，默认值为 True
    sto_already: float = 0
    sto_max: float = 100000
    sto_min: float = 0
    cost: float = 3000
    crf: float = 15


class HT(BaseModel):
    used: bool = True  # 添加 used 字段，默认值为 True
    water_already: float = 1
    water_max: float = 2000000
    water_min: float = 0
    cost: float = 0.5
    crf: float = 20
    loss_rate: float = 0.001
    g_storage_max_per_unit: float = 90
    g_storage_min_per_unit: float = 45
    g_power_max_per_unit: float = 90
    g_power_min_per_unit: float = 45


class CT(BaseModel):
    used: bool = True  # 添加 used 字段，默认值为 True
    water_already: float = 1
    water_max: float = 500000
    water_min: float = 0
    cost: float = 0.5
    crf: float = 15
    loss_rate: float = 0.001
    q_storage_max_per_unit: float = 90
    q_storage_min_per_unit: float = 45
    q_power_max_per_unit: float = 90
    q_power_min_per_unit: float = 45


class BAT(BaseModel):
    used: bool = True  # 添加 used 字段，默认值为 True
    power_already: float = 1
    power_max: float = 20000
    power_min: float = 0
    cost: float = 2500
    crf: float = 15
    loss_rate: float = 0.01
    ele_storage_max_per_unit: float = 90
    ele_storage_min_per_unit: float = 45
    ele_power_max_per_unit: float = 90
    ele_power_min_per_unit: float = 45


class SteamStorage(BaseModel):
    used: bool = True  # 添加 used 字段，默认值为 True
    water_already: float = 1
    water_max: float = 2000000
    water_min: float = 0
    cost: float = 0.5
    crf: float = 20
    loss_rate: float = 0.01
    steam_storage_max_per_unit: float = 90
    steam_storage_min_per_unit: float = 45
    steam_power_max_per_unit: float = 90
    steam_power_min_per_unit: float = 45


class PV(BaseModel):
    used: bool = True  # 添加 used 字段，默认值为 True
    power_already: float = 1
    power_max: float = 500
    power_min: float = 500
    cost: float = 3500
    crf: float = 20
    beta_pv: float = 0.95
    pv_data8760: List[float] = [1, 2, 3]
    s_pv_per_unit: float = 100


class SC(BaseModel):
    used: bool = True  # 添加 used 字段，默认值为 True
    area_already: float = 0
    area_max: float = 10000
    area_min: float = 0
    cost: float = 800
    crf: float = 20
    beta_sc: float = 0.72
    theta_ex: float = 0.9
    solar_data8760: List[float] = [1, 2, 3]
    s_sc_per_unit: float = 100


class WD(BaseModel):
    used: bool = True  # 添加 used 字段，默认值为 True
    number_already: float = 0
    number_max: float = 20
    number_min: float = 0
    capacity_unit: float = 1000
    wd_data8760: List[float] = [1, 2, 3]
    cost: float = 4500
    crf: float = 20
    s_wd_per_unit: float = 100


class EB(BaseModel):
    used: bool = True  # 添加 used 字段，默认值为 True
    power_already: float = 1
    power_max: float = 200000
    power_min: float = 600
    cost: float = 700
    crf: float = 10
    beta_eb: float = 0.9


class ABC(BaseModel):
    used: bool = True  # 添加 used 字段，默认值为 True
    power_already: float = 0
    power_max: float = 10000
    power_min: float = 0
    cost: float = 3000
    crf: float = 10
    beta_abc: float = 1.2


class AC(BaseModel):
    used: bool = True  # 添加 used 字段，默认值为 True
    power_already: float = 0
    power_max: float = 10000
    power_min: float = 0
    cost: float = 3000
    crf: float = 10
    beta_ac: float = 4


class HP(BaseModel):
    used: bool = True  # 添加 used 字段，默认值为 True
    power_already: float = 0
    power_max: float = 600
    power_min: float = 0
    cost: float = 3000
    crf: float = 15
    beta_hpg: float = 1.5
    beta_hpq: float = 6


class GHP(BaseModel):
    used: bool = True  # 添加 used 字段，默认值为 True
    power_already: float = 0
    balance_flag: int = 1
    power_max: float = 1000000
    power_min: float = 0
    cost: float = 2500
    crf: float = 15
    beta_ghpg: float = 4.5
    beta_ghpq: float = 6


class GHPDeep(BaseModel):
    used: bool = True  # 添加 used 字段，默认值为 True
    power_already: float = 0
    power_max: float = 1000000
    power_min: float = 0
    cost: float = 2500
    crf: float = 15
    beta_ghpg: float = 4.5


class GTW(BaseModel):
    used: bool = True  # 添加 used 字段，默认值为 True
    number_already: float = 0
    number_max: float = 100000
    number_min: float = 0
    cost: float = 20000
    crf: float = 30
    beta_gtw: float = 7


class GTW2500(BaseModel):
    used: bool = True  # 添加 used 字段，默认值为 True
    number_already: float = 0
    number_max: float = 2
    number_min: float = 0
    cost: float = 2200000
    crf: float = 30
    beta_gtw: float = 410


class HP120(BaseModel):
    power_already: float = 0
    power_max: float = 1000000
    power_min: float = 0
    cost: float = 2700
    crf: float = 10
    cop: float = 2.26
    temperature_in: float = 120
    temperature_out: float = 150
    used: bool = True  # 添加 used 字段，默认值为 True


class CO180(BaseModel):
    used: bool = True  # 添加 used 字段，默认值为 True
    power_already: float = 0
    power_max: float = 10000
    power_min: float = 0
    k_e_m: float = 200
    cost: float = 500
    crf: float = 10
    temperature_in: float = 120
    temperature_out: float = 150


class WHP(BaseModel):
    used: bool = True  # 添加 used 字段，默认值为 True
    power_already: float = 1
    power_max: float = 20000
    power_min: float = 0
    cost: float = 2500
    crf: float = 15
    cop_heat: float = 2.26
    cop_cold: float = 2.26


class Device(BaseModel):
    """
    设备配置类，包含各种能源设备的详细配置。
    """
    co: CO  # 氢气压缩机
    fc: FC  # 燃料电池
    el: EL  # 电解槽
    hst: HST  # 储氢罐
    ht: HT  # 储热水箱
    ct: CT  # 储冷水箱
    bat: BAT  # 电池储能
    steam_storage: SteamStorage  # 蒸汽储能
    pv: PV  # 光伏板
    sc: SC  # 太阳能集热器
    wd: WD  # 风机
    eb: EB  # 电锅炉
    abc: ABC  # 新增设备
    ac: AC  # 空调
    hp: HP  # 空气源热泵
    ghp: GHP  # 浅层地源热泵
    ghp_deep: GHPDeep  # 中深层地源热泵
    gtw: GTW  # 浅层地埋井
    gtw2500: GTW2500  # 中深层地埋井，深度2500
    hp120: HP120  # 高温热泵
    co180: CO180  # 高温蒸汽压缩机
    whp: WHP  # 余热热泵


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
    energy_in_type: List[float]  # 上周已沟通，改为传 [0, 0, 0, 0, 0, 0, 0]，赋值 1 项对应哪个能量
    energy_out_type: List[float]
    device_already: float
    device_max: float
    device_min: float
    cost: float
    crf: float
    energy_in_standard_per_unit: List[float]  # 上周沟通过，改为传 [0, 0, 0, 0, 0, 0, 0]，赋值项对应哪个能量
    energy_out_standard_per_unit: List[float]


class LoadWithTemperature(BaseModel):
    load: List[float]
    temperature: float


class ObjectiveLoad(BaseModel):
    load_area: float  # 负荷面积，来自负荷，上周已沟通
    g_load_area: float  # 热负荷面积，来自负荷，上周已沟通
    q_load_area: float  # 冷负荷面积，来自负荷，上周已沟通
    h2_demand: List[float] = []
    power_demand: List[float] = []
    steam_demand: List[LoadWithTemperature] = []
    cooling_demand: List[LoadWithTemperature] = []
    heating_demand: List[LoadWithTemperature] = []
    hotwater: List[LoadWithTemperature] = []


class OptimizationBody(BaseModel):
    objective_load: ObjectiveLoad
    base: Base
    trading: Trading
    income: Income
    device: Device
    custom_device_storage: List[CustomDeviceStorage]
    custom_device_exchange: List[CustomDeviceExchange]


class OptimizationResponseBody(BaseModel):
    id: Optional[str] = None
    status: Optional[str] = None
    msg: Optional[str] = None
