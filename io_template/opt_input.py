import json

input_data = {
    # 负荷数据列表
    "sys_load": {
        "electricity_load": [0] * 8760,  # 电力负荷数据，8760小时
        "heat_load": {
            "heat1": {
                "tem": 50,  # 温度(°C)
                "load": [0] * 8760  # 第1项热负荷数据，8760小时
            },
            "heatn": {
                "tem": 60,  # 温度(°C)
                "load": [0] * 8760  # 第n项热负荷数据，8760小时
            }
        },
        "cool_load": {
            "cool1": {
                "tem": 7,  # 温度(°C)
                "load": [0] * 8760  # 第1项冷负荷数据，8760小时
            },
            "cooln": {
                "tem": 5,  # 温度(°C)
                "load": [0] * 8760  # 第n项冷负荷数据，8760小时
            }
        },
        "steam_load": {
            "steam1": {
                "tem": 180,  # 温度(°C)
                "load": [0] * 8760  # 第1项蒸汽负荷数据，8760小时
            },
            "steamn": {
                "tem": 120,  # 温度(°C)
                "load": [0] * 8760  # 第n项蒸汽负荷数据，8760小时
            }
        },
        "hydrogen_load": [0] * 8760,  # 氢气负荷数据，8760小时
        "hotwater_load": {
            "hotwater1": {
                "tem": 60,  # 温度(°C)
                "load": [0] * 8760  # 第1项生活热水负荷数据，8760小时
            },
            "hotwatern": {
                "tem": 50,  # 温度(°C)
                "load": [0] * 8760  # 第n项生活热水负荷数据，8760小时
            }
        }
    },

    # 基础配置参数
    "base": {
        # 可用空地面积
        "area_outside": 5000,
        # 屋顶可铺设光伏装机
        "power_pv_house_top": 1000,
        # 基准方案-供暖
        "base_method_heating": "str",
        # 基准方案-供冷
        "base_method_cooling": "str",
        # 基准方案-供蒸汽
        "base_method_steam": "str",
        # 基准方案-供生活热水
        "base_method_hotwater": "str",
        # 是否启用碳减排
        "cer_enable": True,
        # 碳减排率
        "cer": 0.45,
        # 管网、能管平台投资与设备投资的比例
        "other_investment": 0.2
    },

    # 能源交易配置
    "trading": {
        # 买电许可
        "power_buy_enable": True,
        # 卖电许可
        "power_sell_enable": False,
        # 买电电价类型
        "power_buy_price_type": "str",
        # 买氢许可
        "h2_buy_enable": True,
        # 卖氢许可
        "h2_sell_enable": False,
        # 买热许可
        "heating_buy_enable": False,
        # 卖热许可
        "heating_sell_enable": False,

        # 买蒸汽许可
        "steam_buy": [
            {
                "id": 0,
                "name": "180度蒸汽",
                "temperature": 180,
                "price": 180,
                "enable": True
            },
            {
                "id": 0,
                "name": "120度蒸汽",
                "temperature": 120,
                "price": 120,
                "enable": True
            }
        ],

        # 卖蒸汽许可
        "steam_sell": [
            {
                "id": 0,
                "name": "180度蒸汽",
                "temperature": 180,
                "price": 180,
                "enable": True
            },
            {
                "id": 0,
                "name": "120度蒸汽",
                "temperature": 120,
                "price": 120,
                "enable": True
            }
        ],

        # 分时电价
        "power_buy_24_price": [0.42] * 24,

        # 逐时电价（上传电价文件的数据）
        "power_buy_8760_price": [0.42] * 8760,

        # 容量电价
        "power_buy_capacity_price": 0.2,  # 无容量电价输入则默认为0

        # 逐时卖电电价(元/kWh)
        "power_sell_24_price": [0.42] * 24,

        # 卖热价格(元/GJ)
        "heat_sell_price": 1.515,
        # 卖冷价格(元/GJ)
        "cool_sell_price": 1.515,
        # 卖热价格(元/kg)
        "hydrogen_sell_price": 1.515,
        # 买热价格(元/GJ)
        "heat_buy_price": 29,
        # 买冷价格(元/GJ)
        "cool_buy_price": 40,
        # 买氢价格(元/kg)
        "hydrogen_buy_price": 25,
        # 买天然气价格
        "gas_buy_price": 2.5,

        # 热源配置
        "heat_resource": {
            # 是否启用热源
            "flag": True,
            # 典型日水源流量
            "heat_resource_flow": [0.42] * 24,
            # 可升温温度上限(°C)
            "temperature_upper_limit": 5,
            # 可降温温度上限(°C)
            "temperature_decrease_limit": 5,
            # 运行周期
            "cycle": {
                "start": "10-01",  # 可用水源开始日期(月-日)
                "end": "05-01"  # 可用水源结束日期(月-日)
            }
        }
    },

    # 收入配置
    "income": {
        # 供电收益计算方式
        "power_type": "买电电价折扣/固定价格",
        # 供电折扣(元/kWh)
        "power_price_discount": 0,
        # 供热收益计算方式
        "heat_type": "供暖面积/热量",
        # heat_type选供暖面积为单位面积供暖季收费，选热量为单位热量供应收益
        "heat_price": 0,
        # 冷量收入类型
        "cool_type": "供冷面积/冷量",
        # cool_type选供冷面积为单位面积供l冷季收费，选热量为单位冷量供应收益
        "cool_price": 0,
        # 供生活热水价格
        "hot_water_price": 0,
        # 供蒸汽价格(元/吨)
        "steam_price": 0
    },

    # 设备配置
    "device": {
        # 氢气压缩机（前端没写明氢气，应该改成氢气压缩机）
        "co": {
            "power_already": 1000,  # 已有装机
            "power_max": 10000,  # 新增装机上限
            "power_min": 0,  # 新增装机下限
            "cost": 1000,  # 单位装机投资成本
            "crf": 10,  # 设备寿命
            "beta_co": 1.399  # 耗电系数
        },

        # 燃料电池
        "fc": {
            "power_already": 1,
            "power_max": 10000000,
            "power_min": 300,
            "cost": 8000,
            "crf": 10,
            "eta_fc_p": 15,  # 氢转电系数
            "eta_ex_g": 17,  # 氢转热系数
            "theta_ex": 0.95  # 热回收效率
        },

        # 电解槽
        "el": {
            "nm3_already": 0,  # 已有装机
            "nm3_max": 100000,  # 新增装机上限
            "nm3_min": 0,  # 新增装机下限
            "cost": 2240,
            "crf": 7,
            "eta_el_h": 15,  # 电转氢系数
            "eta_ex_g": 17,  # 电转热系数
            "theta_ex": 0.95  # 热回收效率
        },

        # 储氢罐
        "hst": {
            "sto_already": 0,  # 已有装机
            "sto_max": 100000,  # 新增装机上限
            "sto_min": 0,  # 新增装机下限
            "cost": 3000,
            "crf": 15,
        },

        # 热水罐
        "ht": {
            "water_already": 1,  # 已有容量
            "water_max": 2000000,  # 新增装机上限
            "water_min": 0,  # 新增装机下限
            "cost": 0.5,
            "crf": 20,
            "loss_rate": 0.001,  # 能量损失系数
            "g_storage_max_per_unit": 90,  # 单位容量储热量上限
            "g_storage_min_per_unit": 45,  # 单位容量储热量下限
            "g_power_max_per_unit": 90,  # 单位容量供取热量上限
            "g_power_min_per_unit": 45  # 单位容量供取热量下限
        },

        # 冷水罐
        "ct": {
            "water_already": 1,  # 已有容量
            "water_max": 500000,  # 新增容量上限
            "water_min": 0,  # 新增容量下限
            "cost": 0.5,
            "crf": 15,
            "loss_rate": 0.001,  # 能量损失系数
            "q_storage_max_per_unit": 90,  # 单位容量储冷量上限
            "q_storage_min_per_unit": 45,  # 单位容量储冷量下限
            "q_power_max_per_unit": 90,  # 单位容量供取冷量上限
            "q_power_min_per_unit": 45  # 单位容量供取冷量下限
        },

        # 蓄电池
        "bat": {
            "power_already": 1,  # 已有容量
            "power_max": 20000,  # 新增容量下限
            "power_min": 0,  # 新增容量上限
            "cost": 2500,
            "crf": 15,
            "loss_rate": 0.01,
            "ele_storage_max_per_unit": 90,  # 单位容量能量上限（前端文字对应修改-增加 单位容量）
            "ele_storage_min_per_unit": 45,  # 单位容量能量下限（前端文字对应修改-增加 单位容量）
            "ele_power_max_per_unit": 90,  # 单位容量充放功率上限
            "ele_power_min_per_unit": 45,  # 单位容量充放功率下限
        },

        # 蒸汽储罐
        "steam_storage": {
            "water_already": 1,  # 已有容量
            "water_max": 2000000,  # 新增容量上限
            "water_min": 0,  # 新增容量下限
            "cost": 0.5,
            "crf": 20,
            "loss_rate": 0.01,
            "steam_storage_max_per_unit": 90,  # 单位容量储蒸汽量上限
            "steam_storage_min_per_unit": 45,  # 单位容量储蒸汽量下限
            "steam_power_max_per_unit": 90,  # 单位容量供取蒸汽量上限
            "steam_power_min_per_unit": 45,  # 单位容量供取蒸汽量下限
        },

        # 光伏
        "pv": {
            "power_already": 1,
            "power_max": 500,
            "power_min": 500,
            "cost": 3500,
            "crf": 20,
            "beta_pv": 0.95,  # 光伏转换效率
            "pv_data8760": [1, 2, 3],  # 单位装机光伏出力，8760小时
            "s_pv_per_unit": 100  # 单位装机占地面积
        },
        
        # 太阳能集热器
        "sc": {
            "area_already": 0,
            "area_max": 10000,
            "area_min": 0,
            "cost": 800,
            "crf": 20,
            "beta_sc": 0.72,  # 光热转换效率
            "theta_ex": 0.9,  # 热回收效率
            "solar_data8760": [1, 2, 3],  # 全年太阳辐射数据，8760小时
            "s_sc_per_unit": 100  # 单位装机占地面积
        },

        # 风电机组
        "wd": {
            "number_already": 0,  # 已有装机数量
            "number_max": 20,  # 新增装机上限
            "number_min": 0,  # 新增装机下限
            "capacity_unit": 1000,  # 单台风机装机
            "wd_data8760": [1, 2, 3],  # 单位装机风机出力，8760小时
            "cost": 4500,
            "crf": 20,
            "s_wd_per_unit": 100  # 单位装机占地面积
        },
        
        # 电锅炉
        "eb": {
            "power_already": 1,
            "power_max": 200000,
            "power_min": 600,
            "cost": 700,
            "crf": 10,
            "beta_eb": 0.9  # 电制热效率
        },

        # 吸收式制冷机
        "abc": {
            "power_already": 0,
            "power_max": 10000,
            "power_min": 0,
            "cost": 3000,
            "crf": 10,
            "beta_abc": 1.2,  # 制冷COP
        },

        # 水冷机组
        "ac": {
            "power_already": 0,
            "power_max": 10000,
            "power_min": 0,
            "cost": 3000,
            "crf": 10,
            "beta_ac": 4  # 制冷COP
        },

        # 空气源热泵
        "hp": {
            "power_already": 0,
            "power_max": 600,
            "power_min": 0,
            "cost": 3000,
            "crf": 15,
            "beta_hpg": 1.5,  # 制热COP
            "beta_hpq": 6  # 制冷COP
        },

        # 浅层地源热泵
        "ghp": {
            "power_already": 0,
            "balance_flag": 1,  # 全年热平衡 是1否0
            "power_max": 1000000,
            "power_min": 0,
            "cost": 2500,
            "crf": 15,
            "beta_ghpg": 4.5,  # 制热COP
            "beta_ghpq": 6  # 制冷COP
        },

        # 中深层地源热泵
        "ghp_deep": {
            "power_already": 0,
            "power_max": 1000000,
            "power_min": 0,
            "cost": 2500,
            "crf": 15,
            "beta_ghpg": 4.5  # 制热COP
        },

        # 200米浅层地热井
        "gtw": {
            "number_already": 0,  # 已有井数
            "number_max": 100000,  # 新增装机数上限
            "number_min": 0,  # 新增装机数下限
            "cost": 20000,
            "crf": 30,
            "beta_gtw": 7  # 单井换热功率
        },

        # 2500米地热井
        "gtw2500": {
            "number_already": 0,  # 已有井数
            "number_max": 2,  # 新增装机数上限
            "number_min": 0,  # 新增装机数下限
            "cost": 2200000,
            "crf": 30,
            "beta_gtw": 410  # 单井换热功率
        },

        # 高温热泵
        "hp120": {
            "power_already": 0,
            "power_max": 1000000,
            "power_min": 0,
            "cost": 2700,
            "crf": 10,
            "cop": 2.26,  # 制热COP
            "temperature_in": 120,  # 热源温度
            "temperature_out": 150  # 产热温度
        },

        # 蒸汽压缩机，这个前端文字对应改为蒸汽压缩机吧
        "co180": {
            "power_already": 0,
            "power_max": 10000,
            "power_min": 0,
            "k_e_m": 200,  # 压缩耗电量
            "cost": 500,
            "crf": 10,
            "temperature_in": 120,  # 输入温度
            "temperature_out": 150  # 输出温度
        },

        # 水源热泵
        "whp": {
            "power_already": 1,
            "power_max": 20000,
            "power_min": 0,
            "cost": 2500,
            "crf": 15,
            "cop_heat": 2.26,  # 制热COP
            "cop_cold": 2.26  # 制冷COP
        },
    },

    # 自定义储能设备
    "custom_device_storage": [
        {
            "device_name": "str",  # 设备名称
            "energy_type": "str",  # 能量存储介质
            "device_already": 100,  # 已有容量
            "device_max": 2000000,  # 新增容量上限
            "device_min": 0,  # 新增容量下限
            "cost": 0.5,  # 单位存储介质投资成本
            "crf": 20,
            "energy_storage_max_per_unit": 90,  # 单位容量储能量上限
            "energy_storage_min_per_unit": 45,  # 单位容量储能量下限
            "energy_power_max_per_unit": 90,  # 单位容量供取能量上限
            "energy_power_min_per_unit": 45,  # 单位容量供取能量下限
            "energy_loss": 0.01  # 能量损失系数
        },
        {
            "device_name": "str",
            "energy_type": "str",
            "device_already": 100,
            "device_max": 2000000,
            "device_min": 0,
            "cost": 0.5,
            "crf": 20,
            "energy_storage_max_per_unit": 90,
            "energy_storage_min_per_unit": 45,
            "energy_power_max_per_unit": 90,
            "energy_power_min_per_unit": 45,
            "energy_loss": 0.01
        }
    ],

    # 自定义能量转换设备
    "custom_device_exchange": [
        {
            "device_name": "str",  # 设备名称
            "energy_in_type": "str",  # 单位装机满负荷运行时的能源输入类型
            "energy_out_type": "str",  # 单位装机满负荷运行时的能源输出类型
            "device_already": 100,  # 已有装机
            "device_max": 2000000,  # 新增装机上限
            "device_min": 0,  # 新增装机下限
            "cost": 0.5,
            "crf": 20,
            "energy_in_standard_per_unit": 90,  # 单位装机满负荷运行时的能源输入量
            "energy_out_standard_per_unit": 45  # 单位装机满负荷运行时的能源输出量
        },
        {
            "device_name": "str",
            "energy_in_type": "str",
            "energy_out_type": "str",
            "device_already": 100,
            "device_max": 2000000,
            "device_min": 0,
            "cost": 0.5,
            "crf": 20,
            "energy_in_standard_per_unit": 90,
            "energy_out_standard_per_unit": 45
        }
    ]
}


if __name__ == "__main__":
    with open('opt_input.json', 'w', encoding='utf-8') as f:
        json.dump(input_data, f, ensure_ascii=False, indent=4)
