"""
说明：键为字段名，值为对应的描述信息。
注意：
- 此处的描述信息是空字符串，实际使用时请根据实际字段值进行替换；
- 输出文档中使用的重复字段此处不予重复。
"""
import json

file_param = {
    # 1 项目基本情况
    "project_name": "",  # 项目名称
    "project": "",  # 项目概述（来自前端界面的输入）
    "construction_unit": "",  # 项目建设单位概况（来自前端界面的输入）
    "management": "",  # 项目经营模式（来自前端界面的输入）

    # 2 项目建设资源条件及政策分析
    "renewable_energy": "",  # 项目所在地可再生资源禀赋分析（来自前端界面的输入）
    "proj_location": "",  # 项目所在地

    # 3 项目负荷分析
    "energy_demand": "",  # 基础用能需求分析（来自前端界面的输入）
    "weather": "",

    # 表: 室内外气象设计参数
    "province": "",  # 省份
    "city": "",  # 城市
    "longitude": "",  # 经度
    "latitude": "",  # 纬度
    "altitude": "",  # 海拔高度
    "atm_summer": "",  # 夏季大气压力
    "temp_ac_summer_dry": "",  # 夏季空调室外设计干球温度
    "temp_ventilation_summer_dry": "",  # 夏季通风室外设计干球温度
    "temp_ac_summer_wet": "",  # 夏季空调室外设计湿球温度
    "temp_range_summer": "",  # 夏季计算日较差
    "wind_speed_summer_avg": "",  # 夏季平均室外风速
    "temp_ac_daily_summer_avg": "",  # 夏季空气调节日平均室外计算干球温度
    "atm_winter": "",  # 冬季大气压力
    "temp_ac_winter_dry": "",  # 冬季空调室外设计干球温度
    "temp_ventilation_winter_dry": "",  # 冬季通风室外设计干球温度
    "temp_heating_winter_wet": "",  # 冬季采暖室外设计湿球温度
    "humidity_ac_winter": "",  # 冬季空调室外设计相对湿度
    "wind_speed_winter_avg": "",  # 冬季平均室外风速
    "wind_speed_winter_dominant_avg": "",  # 冬季最多风向平均室外风速
    "temp_min_extreme": "",  # 极端最低温度
    "temp_max_extreme": "",  # 极端最高温度
    "atm_transparency": "",  # 大气透明率

    # 表: 负荷计算基础参数
    "building_area": "",  # 建筑面积
    "heat_transfer_coefficient_exterior_wall": "",  # 外墙传热系数
    "heat_transfer_coefficient_roof": "",  # 屋顶传热系数
    "heat_transfer_coefficient_exterior_window": "",  # 外窗传热系数
    "shading_coefficient": "",  # 遮阳系数
    "window_wall_ratio_north": "",  # 窗墙比-北
    "window_wall_ratio_east": "",  # 窗墙比-东
    "window_wall_ratio_west": "",  # 窗墙比-西
    "window_wall_ratio_south": "",  # 窗墙比-南
    "cooling_period": "",  # 供冷时段
    "heating_period": "",  # 供热时段
    # 负荷信息
    "cooling_peak": "",  # 冷负荷年峰值
    "cooling_total": "",  # 冷负荷年总量
    "cooling_avg": "",  # 冷负荷年平均值
    "heat_peak": "",  # 热负荷年峰值
    "heat_total": "",  # 热负荷年总量
    "heat_avg": "",  # 热负荷年平均值
    "steam_peak": "",  # 蒸汽负荷年峰值
    "steam_total": "",  # 蒸汽负荷年总量
    "steam_avg": "",  # 蒸汽负荷年平均值
    "heat_water_peak": "",  # 热水负荷年峰值
    "heat_water_total": "",  # 热水负荷年总量
    "heat_water_avg": "",  # 热水负荷年平均值
    "ele_peak": "",  # 电负荷年峰值
    "ele_total": "",  # 电负荷年总量
    "ele_avg": "",  # 电负荷年平均值
    "other_load": "",  # 其它负荷类型
    "other_peak": "",  # 其它负荷年峰值
    "other_total": "",  # 其它负荷年总量
    "other_avg": "",  # 其它负荷年平均值

    # 5 能源系统设计方案
    "goal": "",  # 规划目标（经济性最优/零碳等）

    # 表: 核心设备参数（机组配置方案）
    "beta_co": "",
    "crf_co": "",
    "eta_fc_p": "",
    "eta_ex_g_fc": "",
    "theta_ex_fc": "",
    "crf_fc": "",
    "eta_el_h": "",
    "eta_ex_g_el": "",
    "theta_ex_el": "",
    "crf_el": "",
    "crf_hst": "",
    "g_storage_max_per_unit": "",
    "g_storage_min_per_unit": "",
    "g_power_max_per_unit": "",
    "g_power_min_per_unit": "",
    "loss_rate_ht": "",
    "crf_ht": "",
    "q_storage_max_per_unit": "",
    "q_storage_min_per_unit": "",
    "q_power_max_per_unit": "",
    "q_power_min_per_unit": "",
    "loss_rate_ct": "",
    "crf_ct": "",
    "ele_storage_max_per_unit": "",
    "ele_storage_min_per_unit": "",
    "ele_power_max_per_unit": "",
    "ele_power_min_per_unit": "",
    "loss_rate_bat": "",
    "crf_bat": "",
    "steam_storage_max_per_unit": "",
    "steam_storage_min_per_unit": "",
    "steam_power_max_per_unit": "",
    "steam_power_min_per_unit": "",
    "loss_rate_steam": "",
    "crf_steam": "",
    "beta_pv": "",
    "s_pv_per_unit": "",
    "crf_pv": "",
    "beta_sc": "",
    "theta_ex_sc": "",
    "s_sc_per_unit": "",
    "crf_sc": "",
    "capacity_unit": "",
    "s_wd_per_unit": "",
    "crf_wd": "",
    "heating_cop_eb": "",
    "investment_unit_price_eb": "",
    "service_life_eb": "",
    "beta_abc": "",
    "crf_abc": "",
    "beta_ac": "",
    "crf_ac": "",
    "beta_hpg": "",
    "beta_hpq": "",
    "crf_hp": "",
    "beta_ghpg": "",
    "beta_ghpq": "",
    "crf_ghp": "",
    "beta_ghpg_deep": "",
    "crf_ghp_deep": "",
    "beta_gtw": "",
    "crf_gtw": "",
    "beta_gtw2500": "",
    "crf_gtw2500": "",
    "cop_hp120": "",
    "temp_in_hp120": "",
    "temp_out_hp120": "",
    "crf_hp120": "",
    "k_e_m": "",  # 蒸汽压缩机压缩耗电量
    "temp_in_co180": "",
    "temp_out_co180": "",
    "crf_co180": "",
    "cop_heat": "",
    "cop_cold": "",
    "crf_whp": "",
    "custom_storage_info": [
        {
            "device_name": "str",
            "energy_storage_max_per_unit": "",
            "energy_storage_min_per_unit": "",
            "energy_power_max_per_unit": "",
            "energy_power_min_per_unit": "",
            "energy_loss": "",
            "crf": ""
        },
        {
            "device_name": "str",
            "energy_storage_max_per_unit": "",
            "energy_storage_min_per_unit": "",
            "energy_power_max_per_unit": "",
            "energy_power_min_per_unit": "",
            "energy_loss": "",
            "crf": ""
        }
    ],
    "custom_exchange_info": [
        {
            "device_name": "str",
            "energy_in_type": "",
            "energy_out_type": "",
            "energy_in_standard_per_unit": "",
            "energy_out_standard_per_unit": "",
            "crf": ""
        },
        {
            "device_name": "str",
            "energy_in_type": "",
            "energy_out_type": "",
            "energy_in_standard_per_unit": "",
            "energy_out_standard_per_unit": "",
            "crf": ""
        }
    ],

    # 5.3 主要运行策略
    "energy_supply": "",  # 主要运行策略，即拟供能方案（来自前端界面的输入）

    # 表: 设备年出力（根据 scheduling_result 中对应项8760小时数据求和而得）
    "co_output": "",  # 氢气压缩机年出力值
    "fc_output": "",  # 燃料电池年出力值
    "el_output": "",  # 电解槽年出力值
    "hst_output": "",  # 储氢罐年出力值
    "ht_output": "",  # 热水罐年出力值
    "ct_output": "",  # 冷水罐年出力值
    "bat_output": "",  # 蓄电池年出力值
    "steam_storage_output": "",  # 蒸汽储罐年出力值
    "pv_output": "",  # 光伏年出力值
    "sc_output": "",  # 太阳能集热器年出力值
    "wd_output": "",  # 风电机组年出力值
    "eb_output": "",  # 电锅炉年出力值
    "abc_output": "",  # 吸收式制冷机年出力值
    "ac_output": "",  # 水冷机组年出力值
    "hp_output": "",  # 空气源热泵年出力值
    "ghp_output": "",  # 浅层地源热泵年出力值
    "ghp_deep_output": "",  # 中深层地源热泵年出力值
    "gtw_output": "",  # 200米浅层地热井年出力值
    "gtw2500_output": "",  # 2500米地热井年出力值
    "hp120_output": "",  # 高温热泵年出力值
    "co180_output": "",  # 蒸汽压缩机年出力值
    "whp_output": "",  # 水源热泵年出力值
    "custom_storage_output": [
        {
            "device_name": "str",
            "output": ""
        },
        {
            "device_name": "str",
            "output": ""
        }
    ],
    "custom_exchange_output": [
        {
            "device_name": "str",
            "output": ""
        },
        {
            "device_name": "str",
            "output": ""
        }
    ],

    # 7 项目经济效益分析
    # 表: 测算基础数据（设备单价）
    "cost_co": "",  # 氢气压缩机单价
    "cost_fc": "",  # 燃料电池单价
    "cost_el": "",  # 电解槽单价
    "cost_hst": "",  # 储氢罐单价
    "cost_ht": "",  # 热水罐单价
    "cost_ct": "",  # 冷水罐单价
    "cost_bat": "",  # 蓄电池单价
    "cost_steam_storage": "",  # 蒸汽储罐单价
    "cost_pv": "",  # 光伏单价
    "cost_sc": "",  # 太阳能集热器单价
    "cost_wd": "",  # 风电机组单价
    "cost_eb": "",  # 电锅炉单价
    "cost_abc": "",  # 吸收式制冷机单价
    "cost_ac": "",  # 水冷机组单价
    "cost_hp": "",  # 空气源热泵单价
    "cost_ghp": "",  # 浅层地源热泵单价
    "cost_ghp_deep": "",  # 中深层地源热泵单价
    "cost_gtw": "",  # 200米浅层地热井单价
    "cost_gtw2500": "",  # 2500米地热井单价
    "cost_hp120": "",  # 高温热泵单价
    "cost_co180": "",  # 蒸汽压缩机单价
    "cost_whp": "",  # 水源热泵单价
    "custom_storage_cost": [
        {
            "device_name": "str",
            "cost": ""
        },
        {
            "device_name": "str",
            "cost": ""
        }
    ],
    "custom_exchange_cost": [
        {
            "device_name": "str",
            "cost": ""
        },
        {
            "device_name": "str",
            "cost": ""
        }
    ],
    "other_investment": "",  # 管网、能管平台投资与设备投资的比例

    "peak_ele_price": "",  # 电价-峰时
    "flat_ele_price": "",  # 电价-平时
    "valley_ele_price": "",  # 电价-谷时
    "hydrogen_buy_price": "",  # 氢气价
    "gas_buy_price": "",  # 天然气价

    # 表: 系统核心设备配置
    "p_co_installed": "",  # 氢气压缩机装机容量
    "co_capex": "",  # 氢气压缩机投资成本
    "p_fc_installed": "",  # 燃料电池装机容量
    "fc_capex": "",  # 燃料电池投资成本
    "p_el_installed": "",  # 电解槽装机容量
    "el_capex": "",  # 电解槽投资成本
    "h_hst_installed": "",  # 储氢罐装机容量
    "hst_capex": "",  # 储氢罐投资成本
    "m_ht_installed": "",  # 热水罐装机容量
    "ht_capex": "",  # 热水罐投资成本
    "m_ct_installed": "",  # 冷水罐装机容量
    "ct_capex": "",  # 冷水罐投资成本
    "p_bat_installed": "",  # 蓄电池装机容量
    "bat_capex": "",  # 蓄电池投资成本
    "steam_storage_installed": "",  # 蒸汽储罐装机容量
    "steam_storage_capex": "",  # 蒸汽储罐投资成本
    "p_pv_installed": "",  # 光伏装机容量
    "pv_capex": "",  # 光伏投资成本
    "s_sc_installed": "",  # 太阳能集热器装机容量
    "sc_capex": "",  # 太阳能集热器投资成本
    "num_wd_installed": "",  # 风电机组装机数量
    "wd_capex": "",  # 风电机组投资成本
    "p_eb_installed": "",  # 电锅炉装机容量
    "eb_capex": "",  # 电锅炉投资成本
    "g_abc_installed": "",  # 吸收式制冷机装机容量
    "abc_capex": "",  # 吸收式制冷机投资成本
    "p_ac_installed": "",  # 水冷机组装机容量
    "ac_capex": "",  # 水冷机组投资成本
    "p_hp_installed": "",  # 空气源热泵装机容量
    "hp_capex": "",  # 空气源热泵投资成本
    "p_ghp_installed": "",  # 浅层地源热泵装机容量
    "ghp_capex": "",  # 浅层地源热泵投资成本
    "p_ghp_deep_installed": "",  # 中深层地源热泵装机容量
    "ghp_deep_capex": "",  # 中深层地源热泵投资成本
    "num_gtw_installed": "",  # 200米浅层地热井装机数量
    "gtw_capex": "",  # 200米浅层地热井投资成本
    "num_gtw2500_installed": "",  # 2500米地热井装机数量
    "gtw2500_capex": "",  # 2500米地热井投资成本
    "p_hp120_installed": "",  # 高温热泵装机容量
    "hp120_capex": "",  # 高温热泵投资成本
    "p_co180_installed": "",  # 蒸汽压缩机装机容量
    "co180_capex": "",  # 蒸汽压缩机投资成本
    "p_whp_installed": "",  # 水源热泵装机容量
    "whp_capex": "",  # 水源热泵投资成本
    "custom_storage_installed": [
        {
            "device_name": "str",
            "installed_capacity": "",
            "capex": ""
        },
        {
            "device_name": "str",
            "installed_capacity": "",
            "capex": ""
        }
    ],
    "custom_exchange_installed": [
        {
            "device_name": "str",
            "installed_capacity": "",
            "capex": ""
        },
        {
            "device_name": "str",
            "installed_capacity": "",
            "capex": ""
        }
    ],
    "capex_other": "",  # 其他设备投资成本

    # 表: 收益明细
    "electricity_load_sum": "",  # 电负荷年总量
    "revenue_ele": "",  # 电负荷年收益
    "heat_load_sum": "",  # 热负荷年总量
    "revenue_heat": "",  # 热负荷年收益
    "cool_load_sum": "",  # 冷负荷年总量
    "revenue_cooling": "",  # 冷负荷年收益
    "hydrogen_load_sum": "",  # 氢负荷年总量
    "revenue_hydrogen": "",  # 氢负荷年收益
    "steam120_load_sum": "",  # 蒸汽负荷年总量
    "revenue_steam120": "",  # 蒸汽负荷年收益
    "steam180_load_sum": "",  # 高温蒸汽负荷年总量
    "revenue_steam180": "",  # 高温蒸汽负荷年收益
    "hotwater_load_sum": "",  # 生活热水负荷年总量
    "revenue_heat_water": "",  # 生活热水负荷年收益
    "ele_sell": "",  # 年卖电量
    "income_ele_sell": "",  # 年卖电收益
    "heat_sell": "",  # 年卖热量
    "income_heat_sell": "",  # 年卖热收益
    "cooling_sell": "",  # 年卖冷量
    "income_cooling_sell": "",  # 年卖冷收益
    "hydrogen_sell": "",  # 年卖氢量
    "income_hydrogen_sell": "",  # 年卖氢收益
    "steam120_sell": "",  # 年卖蒸汽量
    "income_steam120_sell": "",  # 年卖蒸汽收益
    "steam180_sell": "",  # 年卖高温蒸汽量
    "income_steam180_sell": "",  # 年卖高温蒸汽收益
    "heat_water_sell": "",  # 年卖生活热水量
    "income_heat_water_sell": "",  # 年卖生活热水收益

    # 表: 与传统方案对比
    "capex_all": "",  # 本项目初始投资成本
    "payback_period": "",  # 本项目投资回收期
    "capex_all_crf": "",  # 本项目年化投资成本
    "opex_sum": "",  # 本项目年化运行成本
    "cost_annual": "",  # 本项目年化总成本
    "cost_annual_per_energy": "",  # 本项目单位能源成本
    "capex_all_eb": "",  # 电锅炉供热方案初始投资成本
    "payback_period_eb": "",  # 电锅炉供热方案投资回收期
    "capex_all_crf_eb": "",  # 电锅炉供热方案年化投资成本
    "opex_sum_eb": "",  # 电锅炉供热方案年化运行成本
    "cost_annual_eb": "",  # 电锅炉供热方案年化总成本
    "cost_annual_per_energy_eb": "",  # 电锅炉供热方案单位能源成本
    "payback_period_diff_eb": "",  # 本项目与电锅炉供热方案投资回收期差（投资差额回收期）
    "capex_all_hp": "",  # 空气源热泵供热方案初始投资成本
    "payback_period_hp": "",  # 空气源热泵供热方案投资回收期
    "capex_all_crf_hp": "",  # 空气源热泵供热方案年化投资成本
    "opex_sum_hp": "",  # 空气源热泵供热方案年化运行成本
    "cost_annual_hp": "",  # 空气源热泵供热方案年化总成本
    "cost_annual_per_energy_hp": "",  # 空气源热泵供热方案单位能源成本
    "payback_period_diff_hp": "",  # 本项目与空气源热泵供热方案投资回收期差（投资差额回收期）
    "capex_all_gas": "",  # 燃气锅炉供热方案初始投资成本
    "payback_period_gas": "",  # 燃气锅炉供热方案投资回收期
    "capex_all_crf_gas": "",  # 燃气锅炉供热方案年化投资成本
    "opex_sum_gas": "",  # 燃气锅炉供热方案年化运行成本
    "cost_annual_gas": "",  # 燃气锅炉供热方案年化总成本
    "cost_annual_per_energy_gas": "",  # 燃气锅炉供热方案单位能源成本
    "payback_period_diff_gas": "",  # 本项目与燃气锅炉供热方案投资回收期差（投资差额回收期）

    # 8 项目社会效益分析
    "cer": "",  # 碳减排量（吨）
    "co2": "",  # 本项目碳排放量（吨）
    "co2_eb": "",  # 电锅炉供热方案碳排放量（吨）
    "cer_eb": "",  # 本项目与电锅炉供热方案碳减排量（吨）
    "cer_rate_eb": "",  # 本项目与电锅炉供热方案碳减排率（%）
    "co2_hp": "",  # 空气源热泵供热方案碳排放量（吨）
    "cer_hp": "",  # 本项目与空气源热泵供热方案碳减排量（吨）
    "cer_rate_hp": "",  # 本项目与空气源热泵供热方案碳减排率（%）
    "co2_gas": "",  # 燃气锅炉供热方案碳排放量（吨）
    "cer_gas": "",  # 本项目与燃气锅炉供热方案碳减排量（吨）
    "cer_rate_gas": "",  # 本项目与燃气锅炉供热方案碳减排率（%）
    
    # 9 结论
    "ele_area": "",  # 供电面积
    "heating_area": "",  # 供热面积
    "cooling_area": ""  # 供冷面积
}


if __name__ == "__main__":
    with open('file_param.json', 'w', encoding='utf-8') as f:
        json.dump(file_param, f, ensure_ascii=False, indent=4)
