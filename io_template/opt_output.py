import json

result = {
    "sys_performance": {
        # 经济性分析
        "economic_analysis": {
            # 本项目
            "capex_all": 2123.0,  # 初始投资成本 (万元)
            "capex_all_crf": 212.3,  # 年化投资成本 (万元)
            "capex_other": 100.0,  # 附加项目成本 (万元)
            "opex_sum": 34.2,  # 年化运行成本 (万元)
            "cost_annual": 246.5,  # 年化总成本 (万元)
            "cost_annual_per_energy": 0.123,  # 单位能源成本 (元/kWh)
            "payback_period": 5.0,  # 投资回收期 (年)
            "co2": 1234.5,  # 年碳排放量 (吨)
            "cer": 765.5,  # 年碳减排量 (吨)
            "cer_rate": 0.82,  # 实际碳减排率
            # 对比方案: 纯电 (电锅炉供暖) 方案
            "capex_all_eb": 1000.0,  # 初始投资成本 (万元)
            "capex_all_crf_eb": 100.0,  # 年化投资成本 (万元)
            "opex_sum_eb": 20.0,  # 年化运行成本 (万元)
            "cost_annual_eb": 120.0,  # 年化总成本 (万元)
            "cost_annual_per_energy_eb": 0.12,  # 单位能源成本 (元/kWh)
            "payback_period_eb": 6.0,  # 投资回收期 (年)
            "payback_period_diff_eb": 1.0,  # 投资差额回收期 (年)
            "co2_eb": 2000.0,  # 年碳排放量 (吨)
            "cer_eb": 500.0,  # 年碳减排量 (吨)
            "cer_rate_eb": 0.4,  # 碳减排率
            # 对比方案: 纯电 (热泵供暖) 方案
            "capex_all_hp": 1500.0,  # 初始投资成本 (万元)
            "capex_all_crf_hp": 150.0,  # 年化投资成本 (万元)
            "opex_sum_hp": 25.0,  # 年化运行成本 (万元)
            "cost_annual_hp": 130.0,  # 年化总成本 (万元)
            "cost_annual_per_energy_hp": 0.13,  # 单位能源成本 (元/kWh)
            "payback_period_hp": 7.0,  # 投资回收期 (年)
            "payback_period_diff_hp": 2.0,  # 投资差额回收期 (年)
            "co2_hp": 1800.0,  # 年碳排放量 (吨)
            "cer_hp": 434.5,  # 年碳减排量 (吨)
            "cer_rate_hp": 0.35,  # 碳减排率
            # 对比方案: 燃气方案
            "capex_all_gas": 1800.0,  # 初始投资成本 (万元)
            "capex_all_crf_gas": 180.0,  # 年化投资成本 (万元)
            "opex_sum_gas": 30.0,  # 年化运行成本 (万元)
            "cost_annual_gas": 150.0,  # 年化总成本 (万元)
            "cost_annual_per_energy_gas": 0.15,  # 单位能源成本 (元/kWh)
            "payback_period_gas": 8.0,  # 投资回收期 (年)
            "payback_period_diff_gas": 3.0,  # 投资差额回收期 (年)
            "co2_gas": 2500.0,  # 年碳排放量 (吨)
            "cer_gas": 300.0,  # 年碳减排量 (吨)
            "cer_rate_gas": 0.25,  # 碳减排率
        },
        # 收益明细
        "revenue_analysis": {
            "revenue_ele": 10000.0,  # 供电收益 (万元)
            "revenue_heat": 8000.0,  # 供热收益 (万元)
            "revenue_cooling": 5000.0,  # 供冷收益 (万元)
            "revenue_hydrogen": 3000.0,  # 供氢收益 (万元)
            "revenue_steam120": 2000.0,  # 供120℃蒸汽收益 (万元)
            "revenue_steam180": 1500.0,  # 供180℃蒸汽收益 (万元)
            "revenue_heat_water": 1000.0,  # 供生活热水收益 (万元)
            "ele_sell": 1000.0,  # 年售电量 (kWh)
            "heat_sell": 500.0,  # 年售热量 (GJ)
            "cooling_sell": 200.0,  # 年售冷量 (GJ)
            "hydrogen_sell": 300.0,  # 年售氢量 (kg)
            "steam120_sell": 150.0,  # 年售120℃蒸汽量 (t)
            "steam180_sell": 100.0,  # 年售180℃蒸汽量 (t)
            "heat_water_sell": 250.0,  # 年售生活热水量 (kWh)
            "income_ele_sell": 123.4,  # 年售电收入
            "income_heat_sell": 456.7,  # 年售热收入
            "income_cooling_sell": 89.0,  # 年售冷收入
            "income_hydrogen_sell": 67.8,  # 年售氢收入
            "income_steam120_sell": 34.5,  # 年售120℃蒸汽收入
            "income_steam180_sell": 23.1,  # 年售180℃蒸汽收入
            "income_heat_water_sell": 45.6,  # 年售生活热水收入
        },
    },
    "device_result": {
        # 设备配置结果
        "device_capacity": {
            "p_co_installed": 10.0,  # 氢气压缩机装机容量 (kW)
            "p_fc_installed": 100.0,  # 燃料电池装机容量 (kW)
            "p_el_installed": 5.0,  # 电解槽装机容量 (kW)
            "h_hst_installed": 5.0,  # 储氢罐装机容量 (kg)
            "m_ht_installed": 5.0,  # 热水罐装机容量 (kg)
            "m_ct_installed": 5.0,  # 冷水罐装机容量 (kg)
            "p_bat_installed": 10.0,  # 蓄电池装机容量 (kWh)
            "steam_storage_installed": 5.0,  # 蒸汽储罐装机容量 (t)
            "p_pv_installed": 100.0,  # 光伏装机容量 (kW)
            "s_sc_installed": 10.0,  # 太阳能集热器装机面积 (m2)
            "num_wd_installed": 5,  # 风电机组装机数量
            "p_eb_installed": 10.0,  # 电锅炉装机容量 (kW)
            "g_abc_installed": 10.0,  # 吸收式制冷机装机容量 (kW)
            "p_ac_installed": 10.0,  # 水冷机组装机容量 (kW)
            "p_hp_installed": 10.0,  # 空气源热泵装机容量 (kW)
            "p_ghp_installed": 10.0,  # 浅层地源热泵装机容量 (kW)
            "p_ghp_deep_installed": 10.0,  # 中深层地源热泵装机容量 (kW)
            "num_gtw_installed": 5,  # 200米浅层地热井装机数量
            "num_gtw2500_installed": 5,  # 2500米地热井装机数量
            "p_hp120_installed": 10.0,  # 高温热泵装机容量 (kW)
            "p_co180_installed": 10.0,  # 蒸汽压缩机装机容量 (kW)
            "p_whp_installed": 10.0,  # 水源热泵装机容量 (kW)
            "custom_storage_installed": [
                {
                    "device_name": "CustomStorage",
                    "energy_type": "custom_energy",
                    "installed_capacity": 50.0,  # 自定义储能设备装机容量 (kW)
                },
                {
                    "device_name": "CustomStorage2",
                    "energy_type": "custom_energy2",
                    "installed_capacity": 30.0,  # 自定义储能设备装机容量 (kW)
                },
            ],
            "custom_exchange_installed": [
                {
                    "device_name": "CustomExchange",
                    "energy_in_type": [0, 1, 0, 0, 0, 0, 0],
                    "energy_out_type": [0, 0, 1, 0, 0, 0, 0],
                    "installed_capacity": 20.0,  # 自定义能量交换设备装机容量 (kW)
                },
                {
                    "device_name": "CustomExchange2",
                    "energy_in_type": [1, 1, 0, 0, 0, 0, 0],
                    "energy_out_type": [0, 1, 1, 0, 0, 0, 0],
                    "installed_capacity": 15.0,  # 自定义能量交换设备装机容量 (kW)
                },
            ],
        },
        # 设备投资成本
        "device_capex": {
            "co_capex": 100.0,  # 氢气压缩机投资成本 (万元)
            "fc_capex": 200.0,  # 燃料电池投资成本 (万元)
            "el_capex": 50.0,  # 电解槽投资成本 (万元)
            "hst_capex": 30.0,  # 储氢罐投资成本 (万元)
            "ht_capex": 20.0,  # 热水罐投资成本 (万元)
            "ct_capex": 15.0,  # 冷水罐投资成本 (万元)
            "bat_capex": 80.0,  # 蓄电池投资成本 (万元)
            "steam_storage_capex": 40.0,  # 蒸汽储罐投资成本 (万元)
            "pv_capex": 300.0,  # 光伏投资成本 (万元)
            "sc_capex": 60.0,  # 太阳能集热器投资成本 (万元)
            "wd_capex": 25.0,  # 风电机组投资成本 (万元)
            "eb_capex": 70.0,  # 电锅炉投资成本 (万元)
            "abc_capex": 80.0,  # 吸收式制冷机投资成本 (万元)
            "ac_capex": 90.0,  # 水冷机组投资成本 (万元)
            "hp_capex": 110.0,  # 空气源热泵投资成本 (万元)
            "ghp_capex": 120.0,  # 浅层地源热泵投资成本 (万元)
            "ghp_deep_capex": 130.0,  # 中深层地源热泵投资成本 (万元)
            "gtw_capex": 45.0,  # 200米浅层地热井投资成本 (万元)
            "gtw2500_capex": 55.0,  # 2500米地热井投资成本 (万元)
            "hp120_capex": 140.0,  # 高温热泵投资成本 (万元)
            "co180_capex": 150.0,  # 蒸汽压缩机投资成本 (万元)
            "whp_capex": 160.0,  # 水源热泵投资成本 (万元)
            "custom_storage_capex": [
                {
                    "device_name": "CustomStorage",
                    "energy_type": "custom_energy",
                    "capex": 70.0,  # 自定义储能设备投资成本 (万元)
                },
                {
                    "device_name": "CustomStorage2",
                    "energy_type": "custom_energy2",
                    "capex": 50.0,  # 自定义储能设备投资成本 (万元)
                },
            ],
            "custom_exchange_capex": [
                {
                    "device_name": "CustomExchange",
                    "energy_in_type": "ele",
                    "energy_out_type": "heat",
                    "capex": 40.0,  # 自定义能量交换设备投资成本 (万元)
                },
                {
                    "device_name": "CustomExchange2",
                    "energy_in_type": "ele",
                    "energy_out_type": "heat",
                    "capex": 30.0,  # 自定义能量交换设备投资成本 (万元)
                },
            ],
        },
    },
    "scheduling_result": {
        # 能量流交易
        "ele_buy": [8760],
        "ele_sell": [8760],
        "heat_buy": [8760],
        "heat_sell": [8760],
        "cooling_buy": [8760],
        "cooling_sell": [8760],
        "hydrogen_buy": [8760],
        "hydrogen_sell": [8760],
        "steam120_buy": [8760],
        "steam120_sell": [8760],
        "steam180_buy": [8760],
        "steam180_sell": [8760],
        "heat_water_buy": [8760],
        "heat_water_sell": [8760],
        # 设备运行状态
        # 氢气压缩机
        "p_co": [8760],
        # 燃料电池
        "p_fc": [8760],
        "g_fc": [8760],
        "h_fc": [8760],
        # 电解槽
        "p_el": [8760],
        "g_el": [8760],
        "h_el": [8760],
        # 储氢罐
        "h_sto": [8760],
        # 热水罐
        "g_ht": [8760],
        "g_ht_in": [8760],
        "g_ht_out": [8760],
        # 冷水罐
        "q_ct": [8760],
        "q_ct_in": [8760],
        "q_ct_out": [8760],
        # 蓄电池
        "p_bat": [8760],
        "p_bat_ch": [8760],
        "p_bat_dis": [8760],
        # 蒸汽储罐
        "m_steam_storage": [8760],
        "m_steam_storage_in": [8760],
        "m_steam_storage_out": [8760],
        # 光伏
        "p_pv_theory": [8760],
        "p_pv": [8760],
        # 太阳能集热器
        "g_sc": [8760],
        # 风电机组
        "p_wd": [8760],
        # 电锅炉
        "p_eb": [8760],
        "g_eb": [8760],
        # 吸收式制冷机
        "g_abc": [8760],
        "q_abc": [8760],
        # 水冷机组
        "p_ac": [8760],
        "q_ac": [8760],
        # 空气源热泵
        "p_hp": [8760],
        "g_hp": [8760],
        "p_hp_c": [8760],
        "q_hp": [8760],
        # 浅层地源热泵
        "p_ghp": [8760],
        "g_ghp": [8760],
        "p_ghp_c": [8760],
        "q_ghp": [8760],
        "g_ghp_inject": [8760],
        # 中深层地源热泵
        "p_ghp_deep": [8760],
        "g_ghp_deep": [8760],
        # 高温热泵
        "p_hp120": [8760],
        "m_hp120": [8760],
        "g_hp120": [8760],
        # 蒸汽压缩机
        "p_co180": [8760],
        "m_co180_in": [8760],
        "m_co180": [8760],
        # 水源热泵
        "p_whp": [8760],
        "g_whp": [8760],
        "p_whp_c": [8760],
        "q_whp": [8760],

        # 自定义储能设备
        "custom_storage": [
            {
                "device_name": "CustomStorage",
                "energy_type": "custom_energy",
                "storage_state": [8760],
                "storage_in": [8760],
                "storage_out": [8760],
            },
            {
                "device_name": "CustomStorage2",
                "energy_type": "custom_energy2",
                "storage_state": [8760],
                "storage_in": [8760],
                "storage_out": [8760],
            }
        ],
        # 自定义能量交换设备
        "custom_exchange": [
            {
                "device_name": "CustomExchange",
                "energy_in_type": [0, 1, 0, 0, 0, 0, 0],
                "energy_out_type": [0, 0, 1, 0, 0, 0, 0],
                "energy_in": [[8760], [8760], [8760], [8760], [8760], [8760], [8760]],
                "energy_out": [[8760], [8760], [8760], [8760], [8760], [8760], [8760]],
            },
            {
                "device_name": "CustomExchange2",
                "energy_in_type": [1, 1, 0, 0, 0, 0, 0],
                "energy_out_type": [0, 1, 1, 0, 0, 0, 0],
                "energy_in": [[8760], [8760], [8760], [8760], [8760], [8760], [8760]],
                "energy_out": [[8760], [8760], [8760], [8760], [8760], [8760], [8760]],
            }
        ],
        # 总线
        "g_tube": [8760],
        # TODO: (HSL, ZYL, 前端) 此部分输出有变更，删除了 2 个无意义的字段
    }
}


if __name__ == "__main__":
    with open('opt_output.json', 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=4)
