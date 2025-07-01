import time
from datetime import datetime
import random
import xlwt
import xlrd
import json
import numpy as np
import pandas as pd
import pyscipopt
from pyscipopt import Model, quicksum, multidict, SCIP_PARAMSETTING

from schema.schema_optimization import OptimizationBody


def generate_annual_data(start_date, end_date, typical_daily_data):
    """
    生成全年数据，在输入期间内使用典型日数据

    参数:
    start_date (str): 起始日期，格式 "月-日" (e.g., "10-01")
    end_date (str): 结束日期，格式 "月-日" (e.g., "03-01")
    typical_daily_load (list): 典型日24小时数据，长度24

    返回:
    np.array: 全年8760小时数据
    """
    # RE: end_date 需要包含
    # 创建全年时间索引 (2023年，非闰年)
    dates = pd.date_range('2023-01-01', '2023-12-31 23:00:00', freq='h')

    # 初始化全年负荷数据
    annual_load = np.zeros(len(dates))

    # 解析起始和结束日期
    start_month, start_day = map(int, start_date.split('-'))
    end_month, end_day = map(int, end_date.split('-'))

    # 处理跨年采暖季（分两段填充）
    # 第一段：起始日期 -> 年末 (10-01 到 12-31)
    start_mask = (dates.month == start_month) & (dates.day >= start_day)
    end_of_year_mask = dates.month > start_month
    first_period_mask = start_mask | end_of_year_mask

    # 第二段：年初 -> 结束日期 (01-01 到 03-01)
    start_of_year_mask = dates.month < end_month
    end_mask = (dates.month == end_month) & (dates.day <= end_day)
    second_period_mask = start_of_year_mask | end_mask

    # 组合两段得到完整的采暖季
    heating_season_mask = first_period_mask | second_period_mask

    # 获取采暖季内的所有日期（不重复）
    heating_dates = dates[heating_season_mask].normalize().unique()

    # 为采暖季的每一天填充典型日负荷
    for date in heating_dates:
        # 获取当天的24小时索引
        day_mask = (dates >= date) & (dates < date + pd.Timedelta(days=1))
        # 获取当天在全年中的位置索引
        day_indices = np.where(day_mask)[0]
        # 填充典型日负荷数据
        annual_load[day_indices] = typical_daily_data

    return annual_load


def crf(year):
    """将设备寿命转为资本回收率

    Args:
        year: 设备寿命年限

    Returns:
        crf: 资本回收率
    """
    i = 0.08
    crf = ((1 + i) ** year) * i / ((1 + i) ** year - 1)
    return crf


class ISService:
    def __init__(self):
        pass

    def planning_opt(self, param_input: dict):
        # TODO: (DZY) 重要！请使用 test.py 测试当前方案测算代码
        # DONE: 检查所有单位，先以 kWh 为基准，关注冷热负荷单位换算 & 蒸汽负荷单位，请 ZYL 师姐确认生活热水负荷单位 (m3 还是 kWh)
        # DONE: 以注释形式标注单位，与 ZYL 师姐确认后更新代码

        M = 1e9  # 大数M
        c = 4.2 / 3600  # 水的比热容 (kWh/(kg·℃))

        timestamp = time.strftime('%Y-%m-%d|%H:%M:%S', time.localtime())
        print("{}: 开始进行规划建模".format(timestamp))

        # --- 运行天数 --- #
        period = 8760

        #------------导入负荷数据------------#
        ele_load = param_input["objective_load"]["power_demand"]  # 电负荷 (kW)
        heatload_num = len(param_input["objective_load"]["heating_demand"])
        coolload_num = len(param_input["objective_load"]["cooling_demand"])
        steamload_num = len(param_input["objective_load"]["steam_demand"])
        hotwater_num = len(param_input["objective_load"]["hotwater"])
        g_demand = [0] * 8760  # 热负荷 (GJ/h)
        q_demand = [0] * 8760  # 冷负荷 (GJ/h)
        h_demand = param_input["objective_load"]["h2_demand"]  # 氢负荷 (kg/h)
        steam120_demand = [0] * 8760  # 120蒸汽负荷 (t/h)
        steam180_demand = [0] * 8760  # 180蒸汽负荷 (t/h)
        hotwater_demand = [0] * 8760  # 生活热水负荷 (kW)

        for i in range(heatload_num):
            g_demand = np.add(g_demand, param_input["objective_load"]["heating_demand"][i]["load"]).tolist()
        for i in range(coolload_num):
            q_demand = np.add(q_demand, param_input["objective_load"]["cooling_demand"][i]["load"]).tolist()
        for i in range(steamload_num):
            if param_input["objective_load"]["steam_demand"][i]["temperature"] == 120:
                steam120_demand = np.add(steam120_demand, param_input["objective_load"]["steam_demand"][i]["load"]).tolist()
            elif param_input["objective_load"]["steam_demand"][i]["temperature"] == 180:
                steam180_demand = np.add(steam180_demand, param_input["objective_load"]["steam_demand"][i]["load"]).tolist()
        for i in range(hotwater_num):
            hotwater_demand = np.add(hotwater_demand, param_input["objective_load"]["hotwater"][i]["load"]).tolist()
        g_demand = np.multiply(g_demand, (1e6 / 3600)).tolist()  # GJ/h -> kW
        q_demand = np.multiply(q_demand, (1e6 / 3600)).tolist()  # GJ/h -> kW

        # RE: 光伏出力单位 kW/1kW
        pv_data = param_input["device"]["pv"]["pv_data8760"]
        sc_data = param_input["device"]["sc"]["solar_data8760"]
        wd_data = param_input["device"]["wd"]["wd_data8760"]

        if param_input["trading"]["heat_resource"]["flag"] == 0:
            heat_resource = [0] * 8760  # 热源数据
        else:
            heat_resource = generate_annual_data(
                start_date=param_input["trading"]["heat_resource"]["cycle"]["start"],
                end_date=param_input["trading"]["heat_resource"]["cycle"]["end"],
                typical_daily_data=param_input["trading"]["heat_resource"]["heat_resource_flow"]
            ).tolist()

        #------------导入价格等数据------------#
        alpha_e = 0.5839  # 电网排放因子 (kgCO2/kWh)
        alpha_gas = 1.89  # 天然气排放因子 (kgCO2/m3)
        alpha_h = 0  # 氢排放因子 (kgCO2/kg)
        gas_price = param_input["trading"]["gas_buy_price"]  # 天然气价格 (元/m3)
        if param_input["trading"]["power_buy_price_type"] == "1":
            lambda_ele_in = param_input["trading"]["power_buy_24_price"] * 365
            lambda_ele_capacity = 0  # 容量电价 (元/(kW·月))
        elif param_input["trading"]["power_buy_price_type"] == "2":
            lambda_ele_in = param_input["trading"]["power_buy_8760_price"]
            lambda_ele_capacity = 0
        elif param_input["trading"]["power_buy_price_type"] == "3":
            lambda_ele_in = param_input["trading"]["power_buy_24_price"] * 365
            lambda_ele_capacity = param_input["trading"]["power_buy_capacity_price"]
        elif param_input["trading"]["power_buy_price_type"] == "4":
            lambda_ele_in = param_input["trading"]["power_buy_8760_price"]
            lambda_ele_capacity = param_input["trading"]["power_buy_capacity_price"]
        else:
            raise ValueError("Invalid power buy price type. Choose from '24', '8760', '24+capacity', or '8760+capacity'.")
        lambda_ele_out = param_input["trading"]["power_sell_24_price"] * 365  # 逐时卖电价格 (元/kWh)
        lambda_g_in = param_input["trading"]["heat_buy_price"] * 3600 / 1e6  # 买热价格 (元/GJ -> 元/kWh)
        lambda_g_out = param_input["trading"]["heat_sell_price"] * 3600 / 1e6  # 卖热价格 (元/GJ -> 元/kWh)
        lambda_q_in = param_input["trading"]["cool_buy_price"] * 3600 / 1e6  # 买冷价格 (元/GJ -> 元/kWh)
        lambda_q_out = param_input["trading"]["cool_sell_price"] * 3600 / 1e6  # 卖冷价格 (元/GJ -> 元/kWh)
        lambda_h_in = param_input["trading"]["hydrogen_buy_price"]  # 买氢价格 (元/kg)
        lambda_h_out = param_input["trading"]["hydrogen_sell_price"]  # 卖氢价格 (元/kg)
        lambda_steam120_in = param_input["trading"]["steam_buy"][1]["price"]  # 120蒸汽购入价格 (元/t)
        lambda_steam120_out = param_input["trading"]["steam_sell"][1]["price"]  # 120蒸汽出售价格 (元/t)
        lambda_steam180_in = param_input["trading"]["steam_buy"][0]["price"]  # 180蒸汽购入价格 (元/t)
        lambda_steam180_out = param_input["trading"]["steam_sell"][0]["price"]  # 180蒸汽出售价格 (元/t)
        lambda_hotwater_in = param_input["trading"]["hotwater_buy_price"]  # 生活热水购入价格 (元/kWh)
        lambda_hotwater_out = param_input["trading"]["hotwater_sell_price"]  # 生活热水出售价格 (元/kWh)

        #---------------------------基本设备库中的设备---------------------------#
        """
        基本设备库中设备符号解释:
            co: 氢气压缩机, fc: 燃料电池, el: 电解槽,
            hst: 储氢罐, ht: 储热水箱, ct: 储冷水箱, bat: 电池, steam_storage: 蒸汽储能,
            pv: 光伏板, sc: 太阳能集热器, wd: 风力发电机组,
            eb: 电锅炉, ac: 空调, hp: 空气源热泵,
            ghp: 浅层地源热泵, ghp_deep: 中深层地源热泵, gtw: 浅层地埋井, gtw2500: 中深层地热井,
            hp120:高温热泵, co180:高温蒸汽压缩机, whp: 余热热泵
        """
        #---------------年化收益率数据--------------#
        crf_co = crf(param_input["device"]["co"]["crf"])
        crf_fc = crf(param_input["device"]["fc"]["crf"])
        crf_el = crf(param_input["device"]["el"]["crf"])
        crf_hst = crf(param_input["device"]["hst"]["crf"])
        crf_ht = crf(param_input["device"]["ht"]["crf"])
        crf_ct = crf(param_input["device"]["ct"]["crf"])
        crf_bat = crf(param_input["device"]["bat"]["crf"])
        crf_steam_storage = crf(param_input["device"]["steam_storage"]["crf"])
        crf_pv = crf(param_input["device"]["pv"]["crf"])
        crf_sc = crf(param_input["device"]["sc"]["crf"])
        crf_wd = crf(param_input["device"]["wd"]["crf"])
        crf_eb = crf(param_input["device"]["eb"]["crf"])
        crf_abc = crf(param_input["device"]["abc"]["crf"])
        crf_ac = crf(param_input["device"]["ac"]["crf"])
        crf_hp = crf(param_input["device"]["hp"]["crf"])
        crf_ghp = crf(param_input["device"]["ghp"]["crf"])
        crf_ghp_deep = crf(param_input["device"]["ghp_deep"]["crf"])
        crf_gtw = crf(param_input["device"]["gtw"]["crf"])
        crf_gtw2500 = crf(param_input["device"]["gtw2500"]["crf"])
        crf_hp120 = crf(param_input["device"]["hp120"]["crf"])
        crf_co180 = crf(param_input["device"]["co180"]["crf"])
        crf_whp = crf(param_input["device"]["whp"]["crf"])
        # --------------单位投资成本数据--------------#
        cost_co = param_input["device"]["co"]["cost"]
        cost_fc = param_input["device"]["fc"]["cost"]
        cost_el = param_input["device"]["el"]["cost"]
        cost_hst = param_input["device"]["hst"]["cost"]
        cost_ht = param_input["device"]["ht"]["cost"]
        cost_ct = param_input["device"]["ct"]["cost"]
        cost_bat = param_input["device"]["bat"]["cost"]
        cost_steam_storage = param_input["device"]["steam_storage"]["cost"]
        cost_pv = param_input["device"]["pv"]["cost"]
        cost_sc = param_input["device"]["sc"]["cost"]

        capacity_wd = param_input["device"]["wd"]["capacity_unit"]
        cost_wd = capacity_wd * param_input["device"]["wd"]["cost"]
        cost_eb = param_input["device"]["eb"]["cost"]
        cost_abc = param_input["device"]["abc"]["cost"]
        cost_ac = param_input["device"]["ac"]["cost"]
        cost_hp = param_input["device"]["hp"]["cost"]
        cost_ghp =param_input["device"]["ghp"]["cost"]
        cost_ghp_deep = param_input["device"]["ghp_deep"]["cost"]
        cost_gtw = param_input["device"]["gtw"]["cost"]
        cost_gtw2500 = param_input["device"]["gtw2500"]["cost"]
        cost_hp120 = param_input["device"]["hp120"]["cost"]
        cost_co180 = param_input["device"]["co180"]["cost"]
        cost_whp = param_input["device"]["whp"]["cost"]

        # ---------------效率数据，包括产热、制冷、发电、热转换等--------------#
        # ----co----#
        k_co = param_input["device"]["co"]["beta_co"]   # 耗电量系数 （kWh/kg）
        # ----fc----#
        k_fc_p = param_input["device"]["fc"]["eta_fc_p"]  # 氢转电系数 (kWh/kg)
        k_fc_g = param_input["device"]["fc"]["eta_ex_g"]  # 氢转热系数 (kWh/kg)
        fc_theta_ex = param_input["device"]["fc"]["theta_ex"]  # 热回收效率
        # ----el----#
        kg2nm3 = 11.2  # 1kg 氢气体积为 11.2m3
        k_el_h = param_input["device"]["el"]["eta_el_h"]  # 电转氢效率 (kWh/kg)
        k_el_g = param_input["device"]["el"]["eta_ex_g"]  # 电转热效率 (kWh/kWh)
        el_theta_ex = param_input["device"]["el"]["theta_ex"]   # 热回收效率
        nm3_el_already = param_input["device"]["el"]["nm3_already"]
        nm3_el_upper = param_input["device"]["el"]["nm3_max"]
        nm3_el_lower = param_input["device"]["el"]["nm3_min"]
        p_el_already = nm3_el_already / kg2nm3 / k_el_h
        p_el_upper = nm3_el_upper / kg2nm3 / k_el_h
        p_el_lower = nm3_el_lower / kg2nm3 / k_el_h
        # ---hst----#
        # ---ht----#
        k_ht_sto_max = param_input["device"]["ht"]["g_storage_max_per_unit"]  # 储量转热量上限# kwh/kg
        k_ht_sto_min = param_input["device"]["ht"]["g_storage_min_per_unit"]  # 储量转热量下限# kwh/kg
        k_ht_power_max = param_input["device"]["ht"]["g_power_max_per_unit"]  # 储量转供量上限# kwh/kg
        k_ht_power_min = param_input["device"]["ht"]["g_power_min_per_unit"]  # 储量转供量上限# kwh/kg
        loss_ht = param_input["device"]["ht"]["loss_rate"]                    # 能量损失系数
        # ---ct----#
        k_ct_sto_max = param_input["device"]["ct"]["q_storage_max_per_unit"]  # 储量转热量上限# kwh/kg
        k_ct_sto_min = param_input["device"]["ct"]["q_storage_min_per_unit"]  # 储量转热量下限# kwh/kg
        k_ct_power_max = param_input["device"]["ct"]["q_power_max_per_unit"]  # 储量转供量上限# kwh/kg
        k_ct_power_min = param_input["device"]["ct"]["q_power_min_per_unit"]  # 储量转供量上限# kwh/kg
        loss_ct = param_input["device"]["ct"]["loss_rate"]  # 能量损失系数
        # ---bat----#
        k_bat_sto_max = param_input["device"]["bat"]["ele_storage_max_per_unit"]  # 储量转热量上限
        k_bat_sto_min = param_input["device"]["bat"]["ele_storage_min_per_unit"]  # 储量转热量下限
        k_bat_power_max = param_input["device"]["bat"]["ele_power_max_per_unit"]  # 储量转供量上限
        k_bat_power_min = param_input["device"]["bat"]["ele_power_min_per_unit"]  # 储量转供量上限
        loss_bat = param_input["device"]["bat"]["loss_rate"]  # 能量损失系数
        # ---steam_storage----#
        k_steam_sto_max = param_input["device"]["steam_storage"]["steam_storage_max_per_unit"]  # 储量转热量上限
        k_steam_sto_min = param_input["device"]["steam_storage"]["steam_storage_min_per_unit"]  # 储量转热量下限
        k_steam_power_max = param_input["device"]["steam_storage"]["steam_power_max_per_unit"]  # 储量转供量上限
        k_steam_power_min = param_input["device"]["steam_storage"]["steam_power_min_per_unit"]  # 储量转供量上限
        loss_steam_sto = param_input["device"]["steam_storage"]["loss_rate"]  # 能量损失系数
        # ----pv----#
        eta_pv = param_input["device"]["pv"]["beta_pv"]  # 剩余能量系数
        k_s_pv = param_input["device"]["pv"]["s_pv_per_unit"]   # 功率需面积系数   m2/kw
        # ----sc----#
        k_sc = param_input["device"]["sc"]["beta_sc"]       # 面积供热  GJ/m2
        sc_theta_ex = param_input["device"]["sc"]["theta_ex"]   # 能量损失系数
        k_s_sc = param_input["device"]["sc"]["s_sc_per_unit"]   # m2/m2
        # ----wd----#
        k_s_wd = param_input["device"]["wd"]["s_wd_per_unit"]   # m2/台
        # ----eb----#
        k_eb = param_input["device"]["eb"]["beta_eb"]           # %
        #----abc---#
        k_abc = param_input["device"]["abc"]["beta_abc"]        # kWh/kWh
        # ----ac----#
        k_ac = param_input["device"]["ac"]["beta_ac"]           # kwh/kwh
        # ----hp----#
        k_hp_g = param_input["device"]["hp"]["beta_hpg"]        # kwh/kwh
        k_hp_q = param_input["device"]["hp"]["beta_hpq"]        # kwh/kwh
        # ----ghp----#
        k_ghp_g = param_input["device"]["ghp"]["beta_ghpg"]     # kwh/kwh
        k_ghp_q = param_input["device"]["ghp"]["beta_ghpq"]     # kwh/kwh
        k_ghp_deep_g = param_input["device"]["ghp_deep"]["beta_ghpg"]   # kwh/kwh
        # ----gtw----#
        p_gtw = param_input["device"]["gtw"]["beta_gtw"]        # kw/1
        # ----gtw2500----#
        p_gtw2500 = param_input["device"]["gtw2500"]["beta_gtw"]    # kw/1
        # ----hp120----#
        cop_hp120 = param_input["device"]["hp120"]["cop"]           # kwh/kwh
        # ----co180----#
        k_co180 = param_input["device"]["co180"]["k_e_m"]           # kwh/t
        # ----whp----#
        cop_whpg = param_input["device"]["whp"]["cop_heat"]         # kwh/kwh
        cop_whpq = param_input["device"]["whp"]["cop_cold"]         # kwh/kwh
        # ---------------------------用户自定义设备---------------------------#
        ced_data = param_input["custom_device_exchange"]
        csd_data = param_input["custom_device_storage"]
        num_custom_exchange_device = len(ced_data)  # 用户自定义能量交换设备
        num_custom_storage_device = len(csd_data)  # 用户自定义储能设备
        # ---------------第i个自定义设备的年化收益率数据---------------#
        crf_ced = [0] * num_custom_exchange_device
        crf_csd = [0] * num_custom_storage_device
        for i in range(num_custom_exchange_device):
            crf_ced[i] = crf(ced_data[i]["crf"])
        for i in range(num_custom_storage_device):
            crf_csd[i] = crf(csd_data[i]["crf"])
        # --------------第i个自定义设备的单位投资成本--------------#
        cost_ced = [0] * num_custom_exchange_device
        cost_csd = [0] * num_custom_storage_device
        for i in range(num_custom_exchange_device):
            cost_ced[i] = ced_data[i]["cost"]
        for i in range(num_custom_storage_device):
            cost_csd[i] = csd_data[i]["cost"]
        # -----------------------自定义设备的效率数据----------------------#
        # ------0：电   1：热   2：冷   3：氢   4：120蒸汽  5：180蒸汽  6：家用热水（仅自定义设备）------#
        # TODO: (前端, DZY, ZYL) 明确当前自定义设备输入字段合法值，确保 energy_type_list 与前端选项值一值
        energy_type_list = ["电", "热", "冷", "氢", "120蒸汽", "180蒸汽", "生活热水"]
        energy_type_num = len(energy_type_list)

        cop_in2standard_ced = [[0] * energy_type_num] * num_custom_exchange_device
        cop_out2standard_ced = [[0] * energy_type_num] * num_custom_exchange_device
        k_install2sto_max_csd = [0] * num_custom_storage_device
        k_install2sto_min_csd = [0] * num_custom_storage_device
        k_sto2io_max_csd = [0] * num_custom_storage_device
        k_sto2io_min_csd = [0] * num_custom_storage_device
        csd_loss = [0] * num_custom_storage_device  # 能量损失系数
        csd_energy_type_index = [0] * num_custom_storage_device
        for i in range(num_custom_exchange_device):
            cop_in2standard_ced[i] = ced_data[i]["energy_in_standard_per_unit"]
            cop_out2standard_ced[i] = ced_data[i]["energy_out_standard_per_unit"]
        for i in range(num_custom_storage_device):
            device = csd_data[i]
            if device["energy_type"] not in energy_type_list:
                raise ValueError(f"Invalid energy type '{device['energy_type']}' in custom storage device.")
            # 获取能量类型索引
            csd_energy_type_index[i] = energy_type_list.index(device["energy_type"])
            k_install2sto_max_csd[i] = device["energy_storage_max_per_unit"]
            k_install2sto_min_csd[i] = device["energy_storage_min_per_unit"]
            k_sto2io_max_csd[i] = device["energy_power_max_per_unit"]
            k_sto2io_min_csd[i] = device["energy_power_min_per_unit"]
            csd_loss[i] = device["energy_loss"]

        # --- 基准方案信息 --- #
        # TODO: (DZY, ZYL) 确认电锅炉参数如何获取，是在设备库中添加 (device)传输 ，还是在输入中添加独立项传输，请 ZYL 师姐把关
        # TODO: (ZYL) 确认基准方案如何供氢？基准方案是否对两种温度蒸汽进行区分？
        # TODO: (前端) 明确和统一当前传入值的名称
        k_gas = 8.4  # 燃气锅炉热效率 (kWh/m3)，先随意设的
        crf_gas = 10  # 燃气锅炉使用年限，先随意设的
        cost_gas = 1000  # 燃气锅炉单价 (元/m3)，先随意设的
        eta_g_base_dict = {
            "电锅炉": k_eb,  # 电 (kWh) -> 热 (kWh)
            "空气源热泵": k_hp_g,  # 电 (kWh) -> 热 (kWh)
            "燃气锅炉": k_gas,  # 天然气 (m3) -> 热 (kWh)
        }
        eta_q_base_dict = {
            "水冷机组": k_ac,  # 电 (kWh) -> 冷 (kWh)
        }
        eta_steam120_base_dict = {
            "电锅炉": k_eb / 750,  # 电 (kWh) -> 120蒸汽 (t)
            "燃气锅炉": k_gas / 750,  # 天然气 (m3) -> 120蒸汽 (t)
        }
        eta_steam180_base_dict = {
            "电锅炉": k_eb / 770,  # 电 (kWh) -> 180蒸汽 (t)
            "燃气锅炉": k_gas / 770,  # 天然气 (m3) -> 180蒸汽 (t)
        }
        eta_hotwater_base_dict = {
            "电锅炉": k_eb,  # 电 (kWh) -> 生活热水 (kWh)
            "空气源热泵": k_hp_g,  # 电 (kWh) -> 生活热水 (kWh)
            "燃气锅炉": k_gas,  # 天然气 (m3) -> 生活热水 (kWh)
        }

        # -----------------------建立优化模型----------------------------#
        # 建立模型
        m = Model("mip")
        # ---------------创建变量--------------#
        # 规划容量部分变量
        opex_sum = m.addVar(vtype="C", lb=-M, name=f"op_sum")
        opex_sum_pure = m.addVar(vtype="C", lb=-M, name=f"op_sum_pure")  # 纯运行成本
        capex_sum = m.addVar(vtype="C", lb=0, name=f"capex_sum")  # 总设备投资
        capex_crf = m.addVar(vtype="C", lb=0, name=f"capex_crf")  # 总设备年化收益
        ce_h = m.addVar(vtype="C", lb=0, name="ce_h")  # 碳排放量 (买电*碳排因子)
        # 系统级变量
        g_tube = [m.addVar(vtype="C", lb=0, name=f"g_tube{t}") for t in range(period)]
        p_pur = [m.addVar(vtype="C", lb=0, name=f"p_pur{t}") for t in range(period)]  # 买电power purchase
        p_pur_max = m.addVar(vtype="C", lb=0, name=f"p_pur_max")        # 容量电价计算opex使用
        p_sol = [m.addVar(vtype="C", lb=0, name=f"p_sol{t}") for t in range(period)]  # 卖电power sold
        g_pur = [m.addVar(vtype="C", lb=0, name=f"g_pur{t}") for t in range(period)]  # 买热
        g_sol = [m.addVar(vtype="C", lb=0, name=f"g_sol{t}") for t in range(period)]  # 卖热
        q_pur = [m.addVar(vtype="C", lb=0, name=f"q_pur{t}") for t in range(period)]  # 买冷
        q_sol = [m.addVar(vtype="C", lb=0, name=f"q_sol{t}") for t in range(period)]  # 卖冷
        h_pur = [m.addVar(vtype="C", lb=0, name=f"h_pur{t}") for t in range(period)]  # 买氢hydrogen purchase
        h_sol = [m.addVar(vtype="C", lb=0, name=f"h_sol{t}") for t in range(period)]  # 卖氢hydrogen sold
        steam120_pur = [m.addVar(vtype="C", lb=0, name=f"steam120_pur{t}") for t in range(period)]  # 买steam120
        steam120_sol = [m.addVar(vtype="C", lb=0, name=f"steam120_sol{t}") for t in range(period)]  # 卖steam120
        steam180_pur = [m.addVar(vtype="C", lb=0, name=f"steam180_pur{t}") for t in range(period)]  # 买steam180
        steam180_sol = [m.addVar(vtype="C", lb=0, name=f"steam180_sol{t}") for t in range(period)]  # 卖steam180
        hotwater_pur = [m.addVar(vtype="C", lb=0, name=f"hotwater_pur{t}") for t in range(period)]  # 买热水
        hotwater_sol = [m.addVar(vtype="C", lb=0, name=f"hotwater_sol{t}") for t in range(period)]  # 卖热水
        # 基本设备库中设备变量
        # ----co----#
        p_co_max = m.addVar(vtype="C", lb=param_input["device"]["co"]["power_min"],
                            ub=param_input["device"]["co"]["power_max"],
                            name=f"p_co_max")  # 氢气压缩机投资容量（最大功率）
        p_co = [m.addVar(vtype="C", lb=0, name=f"p_co{t}") for t in range(period)]  # 氢气压缩机工作功率
        # ----fc----#
        p_fc_max = m.addVar(vtype="C", lb=param_input["device"]["fc"]["power_min"], ub=param_input["device"]["fc"]["power_max"],
                            name=f"p_fc_max")  # fc的投资容量（最大功率）
        g_fc = [m.addVar(vtype="C", lb=0, name=f"g_fc{t}") for t in range(period)]  # 燃料电池产热量
        p_fc = [m.addVar(vtype="C", lb=0, name=f"p_fc{t}") for t in range(period)]  # 燃料电池产电量
        h_fc = [m.addVar(vtype="C", lb=0, name=f"h_fc{t}") for t in range(period)]  # 燃料电池用氢量
        # ----el----#
        p_el_max = m.addVar(vtype="C", lb=p_el_lower, ub=p_el_upper, name="p_el_max")  # el的投资容量（最大功率）
        h_el = [m.addVar(vtype="C", lb=0, name=f"h_el{t}") for t in range(period)]  # 电解槽产氢量
        p_el = [m.addVar(vtype="C", lb=0, name=f"p_el{t}") for t in range(period)]  # 电解槽功率
        g_el = [m.addVar(vtype="C", lb=0, name=f"g_el{t}") for t in range(period)]  # 电解槽产热
        # ----hst----#
        hst = m.addVar(vtype="C", lb=param_input["device"]["hst"]["sto_min"],
                       ub=param_input["device"]["hst"]["sto_max"],
                       name=f"hst")  # 储氢罐规划容量
        h_sto = [m.addVar(vtype="C", lb=0, name=f"h_sto{t}") for t in range(period)]  # 储氢罐t时刻储氢量
        # ----ht----#
        m_ht = m.addVar(vtype="C", lb=param_input["device"]["ht"]["water_min"],
                        ub=param_input["device"]["ht"]["water_max"],
                        name=f"m_ht")  # 储热罐的规划容量
        g_ht_in = [m.addVar(vtype="C", lb=0, name=f"g_ht_in{t}") for t in range(period)]
        g_ht_out = [m.addVar(vtype="C", lb=0, name=f"g_ht_out{t}") for t in range(period)]
        g_ht = [m.addVar(vtype="C", lb=0, name=f"g_ht{t}") for t in range(period)]  # 存储的热量
        # 写完约束之后再看看有没有需要创建的变量
        # ----ct----#
        m_ct = m.addVar(vtype="C", lb=param_input["device"]["ct"]["water_max"],
                        ub=param_input["device"]["ct"]["water_max"],
                        name=f"m_ct")  # 储冷罐的规划容量
        q_ct_in = [m.addVar(vtype="C", lb=0, name=f"q_ct_in{t}") for t in range(period)]
        q_ct_out = [m.addVar(vtype="C", lb=0, name=f"q_ct_out{t}") for t in range(period)]  # 写完约束之后再看看有没有需要创建的变量
        q_ct = [m.addVar(vtype="C", lb=0, name=f"q_ct{t}") for t in range(period)]  # 存储的冷量
        # ----bat----#
        p_bat_max = m.addVar(vtype="C", lb=param_input["device"]["bat"]["power_min"], ub=param_input["device"]["bat"]["power_max"], name=f"p_bat_max")
        p_bat_in = [m.addVar(vtype="C", lb=0, name=f"p_bat_in{t}") for t in range(period)]
        p_bat_out = [m.addVar(vtype="C", lb=0, name=f"p_bat_out{t}") for t in range(period)]
        p_bat_sto = [m.addVar(vtype="C", lb=0, name=f"p_bat_sto{t}") for t in range(period)]
        # ----steam_storage----#
        m_steam_sto_max = m.addVar(vtype="C",
                                   lb=param_input["device"]["steam_storage"]["water_min"],
                                   ub=param_input["device"]["steam_storage"]["water_max"],
                                   name=f"m_steam_sto_max")
        m_steam_sto_in = [m.addVar(vtype="C", lb=0, name=f"m_steam_sto_in{t}") for t in range(period)]
        m_steam_sto_out = [m.addVar(vtype="C", lb=0, name=f"m_steam_sto_out{t}") for t in range(period)]
        m_steam_sto = [m.addVar(vtype="C", lb=0, name=f"m_steam_sto{t}") for t in range(period)]
        # ----pv----#
        p_pv_max = m.addVar(vtype="C", lb=param_input["device"]["pv"]["power_min"], ub=param_input["device"]["pv"]["power_max"], name=f"p_pv_max")  # 光伏板投资面积
        p_pv = [m.addVar(vtype="C", lb=0,name=f"p_pv{t}") for t in range(period)]  # 光伏板发电功率
        # ----sc----#
        s_sc = m.addVar(vtype="C", lb=param_input["device"]["sc"]["area_min"],
                        ub=param_input["device"]["sc"]["area_max"],
                        name=f"s_sc")  # 太阳能集热器投资面积
        g_sc = [m.addVar(vtype="C", lb=0, name=f"g_sc{t}") for t in range(period)]  # 太阳能集热器收集的热量
        # ----wd----#
        num_wd = m.addVar(vtype="INTEGER", lb=param_input["device"]["wd"]["number_min"],
                          ub=param_input["device"]["wd"]["number_max"],
                          name=f"num_wd")  # 风电投资数量
        p_wd = [m.addVar(vtype="C", lb=0, name=f"p_wd{t}") for t in range(period)]  # 风电发电功率
        # ----eb----#
        p_eb_max = m.addVar(vtype="C", lb=param_input["device"]["eb"]["power_min"],
                            ub=param_input["device"]["eb"]["power_max"],
                            name=f"p_eb_max")  # 电锅炉投资容量（最大功率）
        g_eb = [m.addVar(vtype="C", lb=0, name=f"g_eb{t}") for t in range(period)]  # 电锅炉产热
        p_eb = [m.addVar(vtype="C", lb=0, name=f"p_eb{t}") for t in range(period)]  # 电锅炉耗电
        # ----abc----#
        g_abc_max = m.addVar(vtype="C", lb=param_input["device"]["abc"]["power_min"],
                            ub=param_input["device"]["abc"]["power_max"],
                            name=f"g_abc_max")  # 投资容量（最大功率）
        g_abc = [m.addVar(vtype="C", lb=0, name=f"g_abc{t}") for t in range(period)]  # 耗热
        q_abc = [m.addVar(vtype="C", lb=0, name=f"q_abc{t}") for t in range(period)]  # 产冷
        # ----ac----#
        p_ac_max = m.addVar(vtype="C", lb=param_input["device"]["ac"]["power_min"],
                            ub=param_input["device"]["ac"]["power_max"],
                            name=f"p_ac_max")  # 空调投资容量（最大功率）
        p_ac = [m.addVar(vtype="C", lb=0, name=f"p_ac{t}") for t in range(period)]  # 电锅炉产热
        q_ac = [m.addVar(vtype="C", lb=0, name=f"q_ac{t}") for t in range(period)]  # 电锅炉耗电
        # ----hp----#
        p_hp_max = m.addVar(vtype="C", lb=0,
                            ub=param_input["device"]["hp"]["power_max"],
                            name=f"p_hp_max")  # 空气源热泵投资容量（最大功率）
        p_hp = [m.addVar(vtype="C", lb=0, name=f"p_hp{t}") for t in range(period)]  # 热泵产热耗电
        p_hpc = [m.addVar(vtype="C", lb=0, name=f"p_hpc{t}") for t in range(period)]  # 热泵产冷的耗电
        q_hp = [m.addVar(vtype="C", lb=0, name=f"q_hp{t}") for t in range(period)]  # 热泵产冷
        g_hp = [m.addVar(vtype="C", lb=0, name=f"g_hp{t}") for t in range(period)]  # 热泵产热
        # ----ghp----#
        p_ghp_max = m.addVar(vtype="C", lb=param_input["device"]["ghp"]["power_min"],
                             ub=param_input["device"]["ghp"]["power_max"],
                             name=f"p_ghp_max")  # 地源热泵投资容量（最大功率）
        p_ghp = [m.addVar(vtype="C", lb=0, name=f"p_ghp{t}") for t in range(period)]  # 热泵产热耗电
        p_ghpc = [m.addVar(vtype="C", lb=0, name=f"p_ghpc{t}") for t in range(period)]  # 热泵产冷的耗电
        g_ghp = [m.addVar(vtype="C", lb=0, name=f"g_ghp{t}") for t in range(period)]  # 热泵产热
        q_ghp = [m.addVar(vtype="C", lb=0, name=f"q_ghp{t}") for t in range(period)]  # 热泵产冷
        g_ghp_gr = [m.addVar(vtype="C", lb=0, name=f"g_ghp_gr{t}") for t in range(period)]  # 热泵灌热
        # ----ghp_deep----#
        p_ghp_deep_max = m.addVar(vtype="C", lb=param_input["device"]["ghp_deep"]["power_min"],
                                  ub=param_input["device"]["ghp_deep"]["power_max"],
                                  name=f"p_ghp_deep_max")  # 地源热泵投资容量（最大功率）
        p_ghp_deep = [m.addVar(vtype="C", lb=0, name=f"p_ghp_deep{t}") for t in range(period)]  # 热泵产热耗电
        g_ghp_deep = [m.addVar(vtype="C", lb=0, name=f"g_ghp_deep{t}") for t in range(period)]  # 热泵产热
        # ----gtw----#
        num_gtw = m.addVar(vtype="INTEGER", lb=param_input["device"]["gtw"]["number_min"],
                           ub=param_input["device"]["gtw"]["number_max"],
                           name='num_gtw')  # 地热井投资数量
        # ----gtw2500----#
        num_gtw2500 = m.addVar(vtype="INTEGER", lb=param_input["device"]["gtw2500"]["number_min"],
                           ub=param_input["device"]["gtw2500"]["number_max"],
                           name='num_gtw2')  # 2500深度地热井投资数量
        # ----hp120----#
        p_hp120_max = m.addVar(vtype="C", lb=param_input["device"]["hp120"]["power_min"],
                               ub=param_input["device"]["hp120"]["power_max"],
                               name=f"p_hp120_max")  # 余热热泵投资容量（最大功率）
        p_hp120 = [m.addVar(vtype="C", lb=0, name=f"p_hp120{t}") for t in range(period)]  # 高温热泵耗电量
        m_hp120 = [m.addVar(vtype="C", lb=0, name=f"m_hp120{t}") for t in range(period)]    # 输出120蒸汽
        g_hp120_in = [m.addVar(vtype="C", lb=0, name=f"g_hp120_in{t}") for t in range(period)]  # 输入热源
        # ----co180----#
        p_co180_max = m.addVar(vtype="C", lb=param_input["device"]["co180"]["power_min"],
                               ub=param_input["device"]["co180"]["power_max"],
                               name=f"p_co180_max")  # 余热热泵投资容量（最大功率）
        p_co180 = [m.addVar(vtype="C", lb=0, name=f"p_co180{t}") for t in range(period)]  # 高温压缩机耗电量
        m_co180_in = [m.addVar(vtype="C", lb=0, name=f"m_co180_in{t}") for t in range(period)]
        m_co180_out = [m.addVar(vtype="C", lb=0, name=f"m_co180_out{t}") for t in range(period)]
        # ----whp----#
        p_whp_max = m.addVar(vtype="C", lb=param_input["device"]["whp"]["power_min"],
                             ub=param_input["device"]["whp"]["power_max"],
                             name=f"p_whp_max")  # 余热热泵投资容量（最大功率）
        p_whp = [m.addVar(vtype="C", lb=0, name=f"p_whp{t}") for t in range(period)]  # 余热热泵产热耗电量
        p_whpc = [m.addVar(vtype="C", lb=0, name=f"p_whpc{t}") for t in range(period)]  # 余热热泵产冷耗电量
        g_whp = [m.addVar(vtype="C", lb=0, name=f"g_whp{t}") for t in range(period)]  # 余热热泵产热
        q_whp = [m.addVar(vtype="C", lb=0, name=f"q_whp{t}") for t in range(period)]  # 余热热泵产冷
        # 用户自定义库中设备变量
        # 自定义能量交换设备
        ced_install = [m.addVar(vtype="C", lb=ced_data[i]["device_min"], ub=ced_data[i]["device_max"],
                                name=f"ced_install{i}") for i in range(num_custom_exchange_device)]    # 设备装机容量
        standard_ced = [[m.addVar(vtype="C", lb=0,
                                  name=f"standard_ced{i}{t}") for t in range(period)] for i in range(num_custom_exchange_device)]   # 设备运行中间变量
        ced_energy_in = [[[m.addVar(vtype="C", lb=0,
                                    name=f"ced_energy_in{i}{j}{t}") for t in range(period)] for j in range(energy_type_num)] for i in range(num_custom_exchange_device)]  # 设备i 的能量种类j 在t时刻的输入
        ced_energy_out = [[[m.addVar(vtype="C", lb=0,
                                     name=f"ced_energy_out{i}{j}{t}") for t in range(period)] for j in range(energy_type_num)] for i in range(num_custom_exchange_device)]     # 设备i 的能量种类j 在t时刻的输出
        # 自定义储能设备的设备变量
        csd_install = [m.addVar(vtype="C", lb=csd_data[i]["device_min"], ub=csd_data[i]["device_max"],
                                name=f"csd_install{i}") for i in range(num_custom_storage_device)]  # 设备装机容量
        csd_sto = [[m.addVar(vtype="C", lb=0,
                              name=f"csd_sto{i}{t}") for t in range(period)] for i in range(num_custom_storage_device)]
        csd_energy_in = [[[m.addVar(vtype="C", lb=0,
                                    name=f"csd_energy_in{i}{j}{t}") for t in range(period)] for j in range(energy_type_num)]for i in range(num_custom_storage_device)]
        csd_energy_out = [[[m.addVar(vtype="C", lb=0,
                                     name=f"csd_energy_out{i}{j}{t}") for t in range(period)] for j in range(energy_type_num)]for i in range(num_custom_storage_device)]
        #---------------创建约束条件--------------#
        #-----------------------------系统约束-----------------------------#
        # 能量流顺序 0：电   1：热   2：冷   3：氢   4：120蒸汽  5：180蒸汽  6：家用热水（仅自定义设备）
        for i in range(period):
            # 电总线约束
            m.addCons(
                p_sol[i] + ele_load[i] + p_whp[i] + p_co180[i] + p_hp120[i] + p_el[i] + p_hp[i] + p_hpc[i] + p_ghp[i] + p_ghp_deep[i]
                + p_ghpc[i] + p_eb[i] + p_ac[i] + p_co[i] + p_bat_in[i]
                + quicksum([ced_energy_in[device_index][0][i] for device_index in range(num_custom_exchange_device)])
                + quicksum([csd_energy_in[device_index][0][i] for device_index in range(num_custom_storage_device)])
                == p_pur[i] + p_fc[i] + p_pv[i] + p_wd[i] + p_bat_out[i]
                + quicksum([ced_energy_out[device_index][0][i] for device_index in range(num_custom_exchange_device)])
                + quicksum([csd_energy_out[device_index][0][i] for device_index in range(num_custom_storage_device)])
            )
            # 热总线约束 (包含生活热水)
            m.addCons(
                g_sol[i] + g_tube[i] + hotwater_sol[i] + g_hp120_in[i] + g_ht_in[i] + g_ghp_gr[i] + g_abc[i]
                + quicksum([ced_energy_in[device_index][1][i] for device_index in range(num_custom_exchange_device)])
                + quicksum([csd_energy_in[device_index][1][i] for device_index in range(num_custom_storage_device)])
                + quicksum([ced_energy_in[device_index][6][i] for device_index in range(num_custom_exchange_device)])
                + quicksum([csd_energy_in[device_index][6][i] for device_index in range(num_custom_storage_device)])
                == g_pur[i] + hotwater_pur[i] + g_fc[i] + g_whp[i] + g_ghp_deep[i] + g_eb[i] + g_sc[i] + g_ht_out[i] + g_hp[i] + g_ghp[i] + g_el[i]
                + quicksum([ced_energy_out[device_index][1][i] for device_index in range(num_custom_exchange_device)])
                + quicksum([csd_energy_out[device_index][1][i] for device_index in range(num_custom_storage_device)])
                + quicksum([ced_energy_out[device_index][6][i] for device_index in range(num_custom_exchange_device)])
                + quicksum([csd_energy_out[device_index][6][i] for device_index in range(num_custom_storage_device)])
            )
            m.addCons(g_demand[i] + hotwater_demand[i] == g_tube[i])  # 区分能灌热的和不能灌热的
            # 冷总线约束
            m.addCons(
                q_sol[i] + q_demand[i] + q_ct_in[i]
                + quicksum([ced_energy_in[device_index][2][i] for device_index in range(num_custom_exchange_device)])
                + quicksum([csd_energy_in[device_index][2][i] for device_index in range(num_custom_storage_device)])
                == q_pur[i] + q_ct_out[i] + q_hp[i] + q_ac[i] + q_ghp[i] + q_whp[i] + q_abc[i]
                + quicksum([ced_energy_out[device_index][2][i] for device_index in range(num_custom_exchange_device)])
                + quicksum([csd_energy_out[device_index][2][i] for device_index in range(num_custom_storage_device)])
            )
            # 120蒸气约束
            m.addCons(
                steam120_sol[i] + steam120_demand[i] + m_co180_in[i]
                + quicksum([ced_energy_in[device_index][4][i] for device_index in range(num_custom_exchange_device)])
                + quicksum([csd_energy_in[device_index][4][i] for device_index in range(num_custom_storage_device)])
                == steam120_pur[i] + m_hp120[i]
                + quicksum([ced_energy_out[device_index][4][i] for device_index in range(num_custom_exchange_device)])
                + quicksum([csd_energy_out[device_index][4][i] for device_index in range(num_custom_storage_device)])
            )
            # 180蒸气约束
            m.addCons(
                steam180_sol[i] + steam180_demand[i] + m_steam_sto_in[i]
                + quicksum([ced_energy_in[device_index][5][i] for device_index in range(num_custom_exchange_device)])
                + quicksum([csd_energy_in[device_index][5][i] for device_index in range(num_custom_storage_device)])
                == steam180_pur[i] + m_co180_out[i] + m_steam_sto_out[i]
                + quicksum([ced_energy_out[device_index][5][i] for device_index in range(num_custom_exchange_device)])
                + quicksum([csd_energy_out[device_index][5][i] for device_index in range(num_custom_storage_device)])
            )
        for i in range(period - 1):
            # 氢气约束
            m.addCons(h_sto[i + 1] - h_sto[i] == h_pur[i] + h_el[i] - h_sol[i] - h_fc[i] - h_demand[i]
                      + quicksum([ced_energy_out[device_index][3][i] for device_index in range(num_custom_exchange_device)])
                      + quicksum([csd_energy_out[device_index][3][i] for device_index in range(num_custom_storage_device)])
                      - quicksum([ced_energy_in[device_index][3][i] for device_index in range(num_custom_exchange_device)])
                      - quicksum([csd_energy_in[device_index][3][i] for device_index in range(num_custom_storage_device)]))
        # 初始状态和末状态平衡
        m.addCons(h_sto[0] - h_sto[-1] == h_pur[-1] + h_el[-1] - h_sol[-1] - h_fc[-1] - h_demand[-1]
                  + quicksum([ced_energy_out[device_index][3][-1] for device_index in range(num_custom_exchange_device)])
                  + quicksum([csd_energy_out[device_index][3][-1] for device_index in range(num_custom_storage_device)])
                  - quicksum([ced_energy_in[device_index][3][-1] for device_index in range(num_custom_exchange_device)])
                  - quicksum([csd_energy_in[device_index][3][-1] for device_index in range(num_custom_storage_device)]))
        #-----------------------------整体性约束-----------------------------#
        if param_input["device"]["ghp"]["balance_flag"] == 1:  # 如果需要考虑全年热平衡
            m.addCons(quicksum([g_ghp[i] - p_ghp[i] - q_ghp[i] - p_ghpc[i] - g_ghp_gr[i] for i in range(period)]) == 0)
        # else:
        #     m.addCons(g_ghp_gr[i] == 0)
        for i in range(period):
            # 买能约束
            m.addCons(p_pur[i] <= M * param_input["trading"]["power_buy_enable"])  # 是否允许电网买电
            m.addCons(p_sol[i] <= M * param_input["trading"]["power_sell_enable"])  # 是否允许电网卖电
            m.addCons(g_pur[i] <= M * param_input["trading"]["heat_buy_enable"])  # 是否允许买热
            m.addCons(g_sol[i] <= M * param_input["trading"]["heat_sell_enable"])  # 是否允许卖热
            m.addCons(q_pur[i] <= M * param_input["trading"]["cool_buy_enable"])  # 是否允许买冷
            m.addCons(q_sol[i] <= M * param_input["trading"]["cool_sell_enable"])  # 是否允许卖冷
            m.addCons(h_pur[i] <= M * param_input["trading"]["h2_buy_enable"])  # 是否允许购买氢气
            m.addCons(h_sol[i] <= M * param_input["trading"]["h2_sell_enable"])  # 是否允许出售氢气
            m.addCons(steam120_pur[i] <= M * param_input["trading"]["steam_buy"][1]["enable"])  # 是否允许买120蒸汽
            m.addCons(steam120_sol[i] <= M * param_input["trading"]["steam_sell"][1]["enable"])  # 是否允许卖120蒸汽
            m.addCons(steam180_pur[i] <= M * param_input["trading"]["steam_buy"][0]["enable"])  # 是否允许买180蒸汽
            m.addCons(steam180_sol[i] <= M * param_input["trading"]["steam_sell"][0]["enable"])  # 是否允许卖180蒸汽
            m.addCons(hotwater_pur[i] <= M * param_input["trading"]["hotwater_buy_enable"])  # 是否允许买热水
            m.addCons(hotwater_sol[i] <= M * param_input["trading"]["hotwater_sell_enable"])  # 是否允许卖热水
        #-----------------------------基础设备库的设备约束-----------------------------#
        #-----co----#
            m.addCons(p_co[i] == k_co * h_el[i])  # 压缩氢耗电量约束
            m.addCons(p_co[i] <= p_co_max + param_input["device"]["co"]["power_already"])  # 压缩机运行功率上限
        # ----fc----#
            m.addCons(g_fc[i] <= fc_theta_ex * k_fc_g * h_fc[i])  # 氢转热约束，允许弃热
            m.addCons(p_fc[i] == k_fc_p * h_fc[i])  # 氢转电约束
            m.addCons(p_fc[i] <= p_fc_max + param_input["device"]["fc"]["power_already"])  # 运行功率 <= 规划功率（运行最大功率）+ 已有装机
        #----el----#
            m.addCons(h_el[i] <= k_el_h * p_el[i])  # 电转氢约束
            m.addCons(g_el[i] <= el_theta_ex * k_el_g * p_el[i])
            m.addCons(p_el[i] <= (p_el_max + p_el_already))  # 运行功率 <= 规划功率（运行最大功率）
            m.addCons(h_el[i] <= hst + param_input["device"]["hst"]["sto_already"])  # 产生的氢气质量要小于储氢罐最大储氢容量
        #----hst----#
            m.addCons(h_sto[i] <= hst + param_input["device"]["hst"]["sto_already"])
        #----ht----#
            m.addCons(g_ht[i] <= (m_ht + param_input["device"]["ht"]["water_already"]) * k_ht_sto_max)  # 储热罐存储热量上限
            m.addCons(g_ht[i] >= (m_ht + param_input["device"]["ht"]["water_already"]) * k_ht_sto_min)  # 储热罐存储热量下限
            m.addCons(g_ht_in[i] <= (m_ht + param_input["device"]["ht"]["water_already"]) * k_ht_power_max)
            m.addCons(g_ht_in[i] >= (m_ht + param_input["device"]["ht"]["water_already"]) * k_ht_power_min)
            m.addCons(g_ht_out[i] <= (m_ht + param_input["device"]["ht"]["water_already"]) * k_ht_power_max)
            m.addCons(g_ht_out[i] >= (m_ht + param_input["device"]["ht"]["water_already"]) * k_ht_power_min)
        #----ct----#
            m.addCons(q_ct[i] <= (m_ct + param_input["device"]["ct"]["water_already"]) * k_ct_sto_max)  # 储冷罐存储冷量上限
            m.addCons(q_ct[i] >= (m_ct + param_input["device"]["ct"]["water_already"]) * k_ct_sto_min)  # 储冷罐存储冷量下限
            m.addCons(q_ct_in[i] <= (m_ct + param_input["device"]["ct"]["water_already"]) * k_ct_power_max)
            m.addCons(q_ct_in[i] >= (m_ct + param_input["device"]["ct"]["water_already"]) * k_ct_power_min)
            m.addCons(q_ct_out[i] <= (m_ct + param_input["device"]["ct"]["water_already"]) * k_ct_power_max)
            m.addCons(q_ct_out[i] >= (m_ct + param_input["device"]["ct"]["water_already"]) * k_ct_power_min)
        # ----bat----#
            m.addCons(p_bat_sto[i] <= (p_bat_max + param_input["device"]["bat"]["power_already"]) * k_bat_sto_max)  # 电池上限
            m.addCons(p_bat_sto[i] >= (p_bat_max + param_input["device"]["bat"]["power_already"]) * k_bat_sto_min)  # 电池下限
            m.addCons(p_bat_in[i] <= (p_bat_max + param_input["device"]["bat"]["power_already"]) * k_bat_power_max)
            m.addCons(p_bat_in[i] >= (p_bat_max + param_input["device"]["bat"]["power_already"]) * k_bat_power_min)
            m.addCons(p_bat_out[i] <= (p_bat_max + param_input["device"]["bat"]["power_already"]) * k_bat_power_max)
            m.addCons(p_bat_out[i] >= (p_bat_max + param_input["device"]["bat"]["power_already"]) * k_bat_power_min)
        # ----steam_storage----#
            m.addCons(m_steam_sto[i] <= (m_steam_sto_max + param_input["device"]["steam_storage"]["water_already"]) * k_steam_sto_max)
            m.addCons(m_steam_sto[i] >= (m_steam_sto_max + param_input["device"]["steam_storage"]["water_already"]) * k_steam_sto_min)
            m.addCons(m_steam_sto_in[i] <= (m_steam_sto_max + param_input["device"]["steam_storage"]["water_already"]) * k_steam_power_max)
            m.addCons(m_steam_sto_in[i] >= (m_steam_sto_max + param_input["device"]["steam_storage"]["water_already"]) * k_steam_power_min)
            m.addCons(m_steam_sto_out[i] <= (m_steam_sto_max + param_input["device"]["steam_storage"]["water_already"]) * k_steam_power_max)
            m.addCons(m_steam_sto_out[i] >= (m_steam_sto_max + param_input["device"]["steam_storage"]["water_already"]) * k_steam_power_min)

        # 储能设备约束
        for i in range(period - 1):
            m.addCons(g_ht[i+1] - g_ht[i] == g_ht_in[i] - g_ht_out[i] - loss_ht * g_ht[i])  # 储热罐存储动态变化
            m.addCons(q_ct[i+1] - q_ct[i] == q_ct_in[i] - q_ct_out[i] - loss_ct * q_ct[i])  # 储冷罐存储动态变化
            m.addCons(p_bat_sto[i+1] - p_bat_sto[i] == p_bat_in[i] - p_bat_out[i] - loss_bat * p_bat_sto[i])  # 电池存储动态变化
            m.addCons(m_steam_sto[i+1] - m_steam_sto[i] == m_steam_sto_in[i] - m_steam_sto_out[i] - loss_steam_sto * m_steam_sto[i])
        m.addCons(g_ht[0] - g_ht[-1] == g_ht_in[-1] - g_ht_out[-1] - loss_ht * g_ht[-1])
        m.addCons(q_ct[0] - q_ct[-1] == q_ct_in[-1] - q_ct_out[-1] - loss_ct * q_ct[-1])
        m.addCons(p_bat_sto[0] - p_bat_sto[-1] == p_bat_in[-1] - p_bat_out[-1] - loss_bat * p_bat_sto[-1])
        m.addCons(m_steam_sto[0] - m_steam_sto[-1] == m_steam_sto_in[-1] - m_steam_sto_out[-1] - loss_steam_sto * m_steam_sto[-1])

        for i in range(period):
        # ---pv----#
            m.addCons(p_pv[i] <= eta_pv * (p_pv_max + param_input["device"]["pv"]["power_already"]) * pv_data[i])  # 允许丢弃可再生能源
        # ----sc----#
            m.addCons(g_sc[i] <= k_sc * sc_theta_ex * (s_sc + param_input["device"]["sc"]["area_already"]) * sc_data[i])  # 允许丢弃可再生能源
        # ----wd----#
            m.addCons(p_wd[i] <= ((num_wd + param_input["device"]["wd"]["number_already"]) * wd_data[i] * capacity_wd))  # 允许丢弃可再生能源
        # ---eb----#
            m.addCons(k_eb * p_eb[i] == g_eb[i])  # 电转热约束
            m.addCons(p_eb[i] <= (p_eb_max + param_input["device"]["eb"]["power_already"]))  # 运行功率 <= 规划功率（运行最大功率）
        # ---abc---#
            m.addCons(k_abc * g_abc[i] == q_abc[i])
            m.addCons(g_abc[i] <= (g_abc_max + param_input["device"]["abc"]["power_already"]))
        # ---ac----#
            m.addCons(q_ac[i] == k_ac * p_ac[i])  # 电转冷约束
            m.addCons(p_ac[i] <= (p_ac_max + param_input["device"]["ac"]["power_already"]))  # 运行功率 <= 规划功率（运行最大功率）
        # ---hp----#
            m.addCons(p_hp[i] * k_hp_g == g_hp[i])  # 电转热约束
            m.addCons(p_hpc[i] * k_hp_q == q_hp[i])  # 电转冷约束
            m.addCons(p_hp[i] + p_hpc[i] <= (p_hp_max + param_input["device"]["hp"]["power_already"]))
        # ---ghp----#
            m.addCons(p_ghp[i] * k_ghp_g == g_ghp[i])  # 地源热泵电转热约束
            m.addCons(p_ghpc[i] * k_ghp_q == q_ghp[i])  # 地源热泵电转冷约束
            m.addCons(p_ghp[i] + p_ghpc[i] <= (p_ghp_max + param_input["device"]["ghp"]["power_already"]))  # 热泵供冷运行功率 <= 规划功率（运行最大功率）
            m.addCons(p_ghp_deep[i] * k_ghp_deep_g == g_ghp_deep[i])  # 地源热泵电转热约束
            m.addCons(p_ghp_deep[i] <= (p_ghp_deep_max + param_input["device"]["ghp_deep"]["power_already"]))  # 热泵供热运行功率 <= 规划功率（运行最大功率）
        #----gtw----#
            m.addCons(num_gtw * p_gtw >= g_ghp[i] - p_ghp[i])  # 井和热泵有关联，制热量-电功率=取热量
            m.addCons(num_gtw * p_gtw >= q_ghp[i] + p_ghpc[i])  # 井和热泵有关联，制冷量+电功率=灌热量
            m.addCons(num_gtw2500 * p_gtw2500 >= g_ghp_deep[i] - p_ghp_deep[i])
        # ---hp120----#
            m.addCons(cop_hp120 * p_hp120[i] == m_hp120[i] * 750)  # 750 是热量和蒸汽量换算系数
            m.addCons((cop_hp120 - 1) * p_hp120[i] == g_hp120_in[i])
            m.addCons(p_hp120[i] <= (p_hp120_max + param_input["device"]["hp120"]["power_already"]))
        # ---co180----#
            m.addCons(m_co180_out[i] == m_co180_in[i] * 1.1)
            m.addCons(m_co180_in[i] * k_co180 == p_co180[i])
            m.addCons(p_co180[i] <= (p_co180_max + param_input["device"]["co180"]["power_already"]))
        # ---whp----#
            m.addCons(p_whp[i] * cop_whpg == g_whp[i])
            m.addCons(p_whpc[i] * cop_whpq == q_whp[i])
            m.addCons(g_whp[i] - p_whp[i] <= c * heat_resource[i] * param_input["trading"]["heat_resource"]["temperature_upper_limit"])
            m.addCons(q_whp[i] + p_whpc[i] <= c * heat_resource[i] * param_input["trading"]["heat_resource"]["temperature_decrease_limit"])
            m.addCons(p_whp[i] + p_whpc[i] <= (p_whp_max + param_input["device"]["whp"]["power_already"]))
        #-----------------------------用户自定义的设备约束-----------------------------#
        #---自定义能量交换设备---#
        for t in range(period):
            for i in range(num_custom_exchange_device):
                for j in range(energy_type_num):
                    if param_input["custom_device_exchange"][i]["energy_in_type"][j] == 1:
                        m.addCons(ced_energy_in[i][j][t] * cop_in2standard_ced[i][j] == standard_ced[i][t])
                    elif param_input["custom_device_exchange"][i]["energy_in_type"][j] == 0:
                        m.addCons(ced_energy_in[i][j][t] == 0)
                    else:
                        raise ValueError("Invalid energy type flag!")
                    if param_input["custom_device_exchange"][i]["energy_out_type"][j] == 1:
                        m.addCons(ced_energy_out[i][j][t] * cop_out2standard_ced[i][j] == standard_ced[i][t])
                    elif param_input["custom_device_exchange"][i]["energy_out_type"][j] == 0:
                        m.addCons(ced_energy_out[i][j][t] == 0)
                    else:
                        raise ValueError("Invalid energy type index!")
                m.addCons(standard_ced[i][t] <= ced_install[i] + ced_data[i]["device_already"])
        # ---自定义储能设备的约束--- #
        for i in range(num_custom_storage_device):
            csd_type = csd_energy_type_index[i]  # 能量类型索引
            for j in range(energy_type_num):
                if j == csd_type:
                    for t in range(period):
                        m.addCons(csd_sto[i][t] <= (csd_install[i] + csd_data[i]["device_already"]) * k_install2sto_max_csd[i])
                        m.addCons(csd_sto[i][t] >= (csd_install[i] + csd_data[i]["device_already"]) * k_install2sto_min_csd[i])
                        m.addCons(csd_energy_in[i][j][t] <= (csd_install[i] + csd_data[i]["device_already"]) * k_sto2io_max_csd[i])
                        m.addCons(csd_energy_out[i][j][t] <= (csd_install[i] + csd_data[i]["device_already"]) * k_sto2io_max_csd[i])
                        m.addCons(csd_energy_in[i][j][t] >= (csd_install[i] + csd_data[i]["device_already"]) * k_sto2io_min_csd[i])
                        m.addCons(csd_energy_out[i][j][t] >= (csd_install[i] + csd_data[i]["device_already"]) * k_sto2io_min_csd[i])
                    for t in range(period - 1):
                        m.addCons(csd_sto[i][t+1] - csd_sto[i][t] == csd_energy_in[i][j][t] - csd_energy_out[i][j][t] - csd_loss[i] * csd_sto[i][t])
                    m.addCons(csd_sto[i][0] - csd_sto[i][-1] == csd_energy_in[i][j][-1] - csd_energy_out[i][j][-1] - csd_loss[i] * csd_sto[i][-1])
                else:
                    for t in range(period):
                        m.addCons(csd_energy_in[i][j][t] == 0)
                        m.addCons(csd_energy_out[i][j][t] == 0)

        #-----------------------------安装面积等约束-----------------------------#
        s_outside = param_input["base"]["area_outside"]
        s_roof = param_input["base"]["power_pv_house_top"]
        m.addCons(k_s_pv * p_pv_max + k_s_sc * s_sc + k_s_wd * num_wd <= s_outside + s_roof)
        m.addCons(k_s_wd * num_wd <= s_outside)
        #-----------------------------运行费用约束-----------------------------#
        m.addCons(opex_sum_pure == (quicksum([lambda_ele_in[i] * p_pur[i] for i in range(period)]) + lambda_ele_capacity * p_pur_max * 12
                                    + lambda_g_in * quicksum([g_pur[i] for i in range(period)])
                                    + lambda_q_in * quicksum([q_pur[i] for i in range(period)])
                                    + lambda_h_in * quicksum([h_pur[i] for i in range(period)])
                                    + lambda_steam120_in * quicksum([steam120_pur[i] for i in range(period)])
                                    + lambda_steam180_in * quicksum([steam180_pur[i] for i in range(period)])
                                    + lambda_hotwater_in * quicksum([hotwater_pur[i] for i in range(period)])))
        for i in range(period):
            m.addCons(p_pur[i] <= p_pur_max)
        m.addCons(opex_sum == (opex_sum_pure
                               - quicksum([lambda_ele_out[i] * p_sol[i] for i in range(period)])
                               - lambda_g_out * quicksum([g_sol[i] for i in range(period)])
                               - lambda_q_out * quicksum([q_sol[i] for i in range(period)])
                               - lambda_h_out * quicksum([h_sol[i] for i in range(period)])
                               - lambda_steam120_out * quicksum([steam120_sol[i] for i in range(period)])
                               - lambda_steam180_out * quicksum([steam180_sol[i] for i in range(period)])
                               - lambda_hotwater_out * quicksum([hotwater_sol[i] for i in range(period)])))
        m.addCons(opex_sum <= M)
        #-----------------------------碳减排的约束-----------------------------#
        load2ele_sum = sum(ele_load)
        load2gas_sum = 0
        load2h_sum = 0
        load2co_heat = 0
        load2co_steam = 0
        # 基准方案供热模式
        if param_input["base"]["base_method_heating"] == "集中供热":
            load2co_heat = sum(g_demand) * 319.5 / 1000             # 使用燃煤锅炉供热 供热1000kwh 碳排319.5kg
        elif param_input["base"]["base_method_heating"] == "电锅炉":
            load2ele_sum += sum(g_demand) / eta_g_base_dict["电锅炉"]
        elif param_input["base"]["base_method_heating"] == "空气源热泵":
            load2ele_sum += sum(g_demand) / eta_g_base_dict["空气源热泵"]
        elif param_input["base"]["base_method_heating"] == "燃气锅炉":
            load2gas_sum += sum(g_demand) / eta_g_base_dict["燃气锅炉"]
        else:
            raise ValueError("非法 base_method_heating 值！")
        # 基准方案供冷模式
        if param_input["base"]["base_method_cooling"] == "集中供冷":
            load2ele_sum += sum(q_demand) / k_ac # 用电制冷
        elif param_input["base"]["base_method_cooling"] == "水冷机组":
            load2ele_sum += sum(q_demand) / eta_q_base_dict["水冷机组"]
        else:
            raise ValueError("非法 base_method_cooling 值！")
        # 基准方案供氢模式
        load2h_sum += sum(h_demand)
        # 基准方案供蒸汽模式（测试时先统一为 base_method_steam）
        # 按燃煤系数计算
        if param_input["base"]["base_method_steam"] == "购买蒸汽":
            load2co_steam += sum(steam120_demand) * 750 * 319.5 / 1000
            load2co_steam += sum(steam180_demand) * 770 * 319.5 / 1000
        elif param_input["base"]["base_method_steam"] == "电锅炉":
            load2ele_sum += sum(steam120_demand) / eta_steam120_base_dict["电锅炉"]
            load2ele_sum += sum(steam180_demand) / eta_steam180_base_dict["电锅炉"]
        elif param_input["base"]["base_method_steam"] == "燃气锅炉":
            load2gas_sum += sum(steam120_demand) / eta_steam120_base_dict["燃气锅炉"]
            load2gas_sum += sum(steam180_demand) / eta_steam180_base_dict["燃气锅炉"]
        else:
            raise ValueError("非法 base_method_steam 值！")
        # 基准方案供热水模式
        if param_input["base"]["base_method_hotwater"] == "电锅炉":
            load2ele_sum += sum(hotwater_demand) / eta_hotwater_base_dict["电锅炉"]
        elif param_input["base"]["base_method_hotwater"] == "空气源热泵":
            load2ele_sum += sum(hotwater_demand) / eta_hotwater_base_dict["空气源热泵"]
        elif param_input["base"]["base_method_hotwater"] == "燃气锅炉":
            load2gas_sum += sum(hotwater_demand) / eta_hotwater_base_dict["燃气锅炉"]
        else:
            raise ValueError("非法 base_method_hotwater 值！")

        ce_base = load2ele_sum * alpha_e + load2gas_sum * alpha_gas + load2h_sum * alpha_h + load2co_heat + load2co_steam
        if param_input["base"]["cer_enable"] is True:
            cerr = param_input["base"]["cer"] / 100  # 碳减排率
            m.addCons(ce_h <= (1 - cerr) * ce_base)
        m.addCons(ce_h == quicksum(p_pur) * alpha_e)
        #-----------------------------规划设备花费约束-----------------------------#
        m.addCons(capex_sum == (p_co_max * cost_co + p_fc_max * cost_fc + p_el_max * cost_el
                                + hst * cost_hst + m_ht * cost_ht + m_ct * cost_ct
                                + p_bat_max * cost_bat + m_steam_sto_max * cost_steam_storage
                                + p_pv_max * cost_pv + s_sc * cost_sc + num_wd * cost_wd
                                + p_eb_max * cost_eb + g_abc_max * cost_abc + p_ac_max * cost_ac
                                + p_hp_max * cost_hp + p_ghp_max * cost_ghp + p_ghp_deep_max * cost_ghp_deep
                                + num_gtw * cost_gtw + num_gtw2500 * cost_gtw2500
                                + p_hp120_max * cost_hp120 + p_co180_max * cost_co180 + p_whp_max * cost_whp
                                + quicksum([ced_install[i] * cost_ced[i] for i in range(num_custom_exchange_device)])
                                + quicksum([csd_install[i] * cost_csd[i] for i in range(num_custom_storage_device)])))
        m.addCons(capex_crf == (crf_co * p_co_max * cost_co + crf_fc * p_fc_max * cost_fc + crf_el * p_el_max * cost_el
                                + crf_hst * hst * cost_hst + crf_ht * m_ht * cost_ht + crf_ct * m_ct * cost_ct
                                + crf_bat * p_bat_max * cost_bat + crf_steam_storage * m_steam_sto_max * cost_steam_storage
                                + crf_pv * p_pv_max * cost_pv + crf_sc * s_sc * cost_sc + crf_wd * num_wd * cost_wd
                                + crf_eb * p_eb_max * cost_eb + crf_abc * g_abc_max * cost_abc + crf_ac * p_ac_max * cost_ac
                                + crf_hp * p_hp_max * cost_hp + crf_ghp * p_ghp_max * cost_ghp + crf_ghp_deep * p_ghp_deep_max * cost_ghp_deep
                                + crf_gtw * num_gtw * cost_gtw + crf_gtw2500 * num_gtw2500 * cost_gtw2500
                                + crf_hp120 * p_hp120_max * cost_hp120 + crf_co180 * p_co180_max * cost_co180
                                + crf_whp * p_whp_max * cost_whp
                                + quicksum([crf_ced[i] * ced_install[i] * cost_ced[i] for i in range(num_custom_exchange_device)])
                                + quicksum([crf_csd[i] * csd_install[i] * cost_csd[i] for i in range(num_custom_storage_device)])))

        #-----------------------------目标函数-----------------------------#
        m.setObjective(capex_crf + opex_sum, "minimize")

        #-----------------------------gurobi参数设置-----------------------------#
        # m.params.MIPGap = 0.01
        m.setRealParam("limits/gap", 0.1)  # 设置优化求解的最大间隙
        # m.setPresolve(SCIP_PARAMSETTING.OFF)
        presolve_setting = m.getParam("presolving/maxrounds")
        print(f"当前预求解设置: {presolve_setting}")

        #---------------------------gurobi求解-----------------------------#
        t_start = time.time()
        timestamp_start = time.strftime('%Y-%m-%d|%H:%M:%S', time.localtime(t_start))
        print("{}: 开始求解...".format(timestamp_start))
        m.optimize()
        if m.getStatus() == "optimal":  # 检查是否找到最优解
            t_end = time.time()
            timestamp_end = time.strftime('%Y-%m-%d|%H:%M:%S', time.localtime(t_end))
            time_spend = time.strftime('%Hh %Mm %Ss', time.gmtime(t_end - t_start))
            cost = m.getObjVal()
            print("{}: 求解完成. Optimal value: {}, cost time: {}".format(timestamp_end, cost, time_spend))

        elif m.getStatus() == "gaplimit":
            if m.getNSols() > 0:  # 检查可行解数量
                t_end = time.time()
                timestamp_end = time.strftime('%Y-%m-%d|%H:%M:%S', time.localtime(t_end))
                time_spend = time.strftime('%Hh %Mm %Ss', time.gmtime(t_end - t_start))
                cost = m.getObjVal()
                gap = m.getGap()
                print("{}: 求解完成. Optimal value: {}, gap: {}, cost time: {}".format(timestamp_end, cost, gap, time_spend))
            else:
                print("虽状态为 gaplimit，但未找到可行解！")
                raise ValueError("未找到可行解！请检查模型设置是否正确！")
        else:
            print("Solver status:", m.getStatus())
            # m.writeProblem("m.lp")
            raise ValueError("未找到最优解！请检查模型设置是否正确！")
        # try:
        #     m.optimize()
        # except gp.GurobiError:
        #     print("Optimize failed due to non-convexity")
        # if m.status == GRB.INFEASIBLE or m.status == 4: # 不可行输出冲突约束
        #     print('Model is infeasible')
        # m.computeIIS()
        # m.write('model.ilp')
        # print("Irreducible inconsistent subsystem is written to file 'model.ilp'")

        #---------------------------计算投资回报等信息-----------------------------#
        sys_life = 20  # 系统设计年限
        # whole_energy，包含负荷和出售能量，单位为 kWh
        whole_energy = (sum(ele_load)
                        + sum(g_demand) + sum(q_demand)
                        + sum(h_demand) * 33.3                    # 33.3 为kg转kWh
                        + sum(steam120_demand) * 750 + sum(steam180_demand) * 770
                        + sum(hotwater_demand)
                        + sum(m.getVal(p_sol[i]) for i in range(period))
                        + sum(m.getVal(g_sol[i]) for i in range(period)) + sum(m.getVal(q_sol[i]) for i in range(period))
                        + sum(m.getVal(steam120_sol[i]) for i in range(period)) * 750
                        + sum(m.getVal(steam180_sol[i]) for i in range(period))) * 770

        capex_all = m.getVal(capex_sum) * (1 + param_input["base"]["other_investment"])
        capex_all_crf = m.getVal(capex_crf) + m.getVal(capex_sum) * param_input["base"]["other_investment"] / sys_life
        capex_other = m.getVal(capex_sum) * param_input["base"]["other_investment"]
        cost_annual = capex_all_crf + m.getVal(opex_sum_pure)
        cost_annual_per_energy = cost_annual / (whole_energy + 1e-7)

        # TODO: (前端) 确认返回值
        if param_input["income"]["power_type"] == "买电电价折扣":
            lambda_ele_revenue = [price * param_input["income"]["power_price"] / 100 for price in lambda_ele_in]
        elif param_input["income"]["power_type"] == "固定价格":
            lambda_ele_revenue = [param_input["income"]["power_price"]] * period
        else:
            raise ValueError("非法 power_type 值！")
        revenue_ele = sum(lambda_ele_revenue[i] * ele_load[i] for i in range(period))
        if param_input["base"]["base_method_heating"] == "集中供热":
            if param_input["income"]["heat_type"] == "供暖面积":
                revenue_heat = param_input["income"]["heat_price"] * param_input["objective_load"]["g_load_area"]
            elif param_input["income"]["heat_type"] == "热量":
                revenue_heat = param_input["income"]["heat_price"] * sum(np.multiply(g_demand, (3600 / 1e6)).tolist())
            else:
                raise ValueError("非法 heat_type 值！")
        # TODO: (ZYL) 确认该电价是不是使用 lambda_ele_revenue
        elif param_input["base"]["base_method_heating"] == "电锅炉":
            revenue_heat = sum(lambda_ele_revenue[i] * g_demand[i] / eta_g_base_dict["电锅炉"] for i in range(period))
        elif param_input["base"]["base_method_heating"] == "空气源热泵":
            revenue_heat = sum(lambda_ele_revenue[i] * g_demand[i] / eta_g_base_dict["空气源热泵"] for i in range(period))
        elif param_input["base"]["base_method_heating"] == "燃气锅炉":
            revenue_heat = sum(gas_price * g_demand[i] / eta_g_base_dict["燃气锅炉"] for i in range(period))
        else:
            raise ValueError("非法 base_method_heating 值！")
        if param_input["base"]["base_method_cooling"] == "集中供冷":
            if param_input["income"]["cool_type"] == "供冷面积":
                revenue_cool = param_input["income"]["cool_price"] * param_input["objective_load"]["q_load_area"]
            elif param_input["income"]["cool_type"] == "冷量":
                revenue_cool = param_input["income"]["cool_price"] * sum(np.multiply(q_demand, (3600 / 1e6)).tolist())
            else:
                raise ValueError("非法 cool_type 值！")
        elif param_input["base"]["base_method_cooling"] == "水冷机组":
            revenue_cool = sum(lambda_ele_revenue[i] * q_demand[i] / eta_q_base_dict["水冷机组"] for i in range(period))
        else:
            raise ValueError("非法 base_method_cooling 值！")
        revenue_h = lambda_h_in * sum([h_demand[i] for i in range(period)])
        if param_input["base"]["base_method_steam"] == "购买蒸汽":
            # TODO: (DZY, ZYL) 确认计价方式，是使用 income.steam_price 还是使用 lambda_steam_in
            revenue_steam120 = param_input["income"]["steam_price"] * sum(steam120_demand)
            revenue_steam180 = param_input["income"]["steam_price"] * sum(steam180_demand)
        elif param_input["base"]["base_method_steam"] == "电锅炉":
            revenue_steam120 = sum(lambda_ele_revenue[i] * steam120_demand[i] / eta_steam120_base_dict["电锅炉"] for i in range(period))
            revenue_steam180 = sum(lambda_ele_revenue[i] * steam180_demand[i] / eta_steam180_base_dict["电锅炉"] for i in range(period))
        elif param_input["base"]["base_method_steam"] == "燃气锅炉":
            revenue_steam120 = sum(gas_price * steam120_demand[i] / eta_steam120_base_dict["燃气锅炉"] for i in range(period))
            revenue_steam180 = sum(gas_price * steam180_demand[i] / eta_steam180_base_dict["燃气锅炉"] for i in range(period))
        else:
            raise ValueError("非法 base_method_steam 值！")

        if param_input["base"]["base_method_hotwater"] == "电锅炉":
            revenue_hotwater = sum(lambda_ele_revenue[i] * hotwater_demand[i] / eta_hotwater_base_dict["电锅炉"] for i in range(period))
        elif param_input["base"]["base_method_hotwater"] == "空气源热泵":
            revenue_hotwater = sum(lambda_ele_revenue[i] * hotwater_demand[i] / eta_hotwater_base_dict["空气源热泵"] for i in range(period))
        elif param_input["base"]["base_method_hotwater"] == "燃气锅炉":
            revenue_hotwater = sum(gas_price * hotwater_demand[i] / eta_hotwater_base_dict["燃气锅炉"] for i in range(period))
        else:
            raise ValueError("非法 base_method_hotwater 值！")
        revenue = (revenue_ele + revenue_heat + revenue_cool + revenue_h
                   + revenue_steam120 + revenue_steam180 + revenue_hotwater)
        # 根据基准方案所得投资回收期
        payback_period = capex_all / (revenue - m.getVal(opex_sum) + 1e-7)
        # TODO: (前端) 添加年化净收益字段
        pure_revenue = revenue - m.getVal(opex_sum) + 1e-7
        carbon_emission = m.getVal(ce_h)
        cer = ce_base - carbon_emission
        cer_rate = cer / (ce_base + 1e-7)

        # ---------------------------对比方案: 纯电 (电锅炉供暖) 方案-----------------------------#
        capex_ele_eb = 0
        capex_g_eb = max(g_demand) / k_eb * cost_eb
        opex_cool_eb = 0
        capex_q_eb = 0
        # TODO: (DZY, ZYL) 确认对比方案供冷方式，先使用水冷机组供冷 + 集中供冷
        if param_input["base"]["base_method_cooling"] == "集中供冷":
            if param_input["income"]["cool_type"] == "供冷面积":
                opex_cool_eb = param_input["income"]["cool_price"] * param_input["objective_load"]["q_load_area"]
            elif param_input["income"]["cool_type"] == "冷量":
                opex_cool_eb = param_input["income"]["cool_price"] * sum(np.multiply(q_demand, (3600 / 1e6)).tolist())
            else:
                raise ValueError("非法 cool_type 值！")
        elif param_input["base"]["base_method_cooling"] == "水冷机组":
            capex_q_eb = max(q_demand) / k_ac * cost_ac
        else:
            raise ValueError("非法 base_method_cooling 值！")
        capex_steam120_eb = max(steam120_demand) * 750 / k_eb * cost_eb
        capex_steam180_eb = max(steam180_demand) * 770 / k_eb * cost_eb
        capex_hotwater_eb = max(hotwater_demand) / k_eb * cost_eb
        capex_all_eb = ((capex_ele_eb + capex_g_eb + capex_q_eb
                         + capex_steam120_eb + capex_steam180_eb + capex_hotwater_eb)
                        * (1 + param_input["base"]["other_investment"]))

        if param_input["device"]["eb"]["power_already"] == 0 and param_input["device"]["eb"]["power_maxy"] == 0 :
            capex_all_crf_eb = crf_eb * capex_all_eb + capex_all_eb * param_input["base"]["other_investment"] / 10
        else:
            capex_all_crf_eb = crf(10) * capex_all_eb + capex_all_eb * param_input["base"]["other_investment"] / 10
        p_pur_eb = [(ele_load[i] + g_demand[i] / k_eb + q_demand[i] / k_ac
                     + steam120_demand[i] * 750 / k_eb + steam180_demand[i] * 770 / k_eb
                     + hotwater_demand[i] / k_eb) for i in range(period)]
        opex_sum_eb = (sum(lambda_ele_in[i] * p_pur_eb[i] for i in range(period))
                       + lambda_ele_capacity * max(p_pur_eb) * 12
                       + sum(lambda_h_in * h_demand[i] for i in range(period))
                       + opex_cool_eb)

        cost_annual_eb = capex_all_crf_eb + opex_sum_eb

        whole_energy_contrast = (sum(ele_load)
                                 + sum(g_demand) + sum(q_demand)
                                 + sum(h_demand) * 33.33
                                 + sum(steam120_demand) * 750 + sum(steam180_demand) * 770
                                 + sum(hotwater_demand))
        cost_annual_per_energy_eb = cost_annual_eb / whole_energy_contrast

        revenue_eb = revenue
        payback_period_eb = capex_all_eb / (revenue_eb - opex_sum_eb + 1e-7)
        payback_period_diff_eb = ((capex_all - capex_all_eb)
                                  / ((revenue - m.getVal(opex_sum)) - (revenue_eb - opex_sum_eb) + 1e-7))
        pure_revenue_eb = revenue_eb - opex_sum_eb + 1e-7
        carbon_emission_eb = sum(p_pur_eb) * alpha_e + sum(h_demand) * alpha_h
        cer_eb = ce_base - carbon_emission_eb
        cer_rate_eb = cer_eb / (ce_base + 1e-7)

        # --------------------------对比方案: 纯电 (热泵供暖) 方案-----------------------------#
        capex_ele_hp = 0
        capex_g_hp = max(g_demand) / k_hp_g * cost_hp
        capex_q_hp = max(q_demand) / k_hp_q * cost_hp
        # capex_gq_hp = max(g_demand[i] / k_hp_g + q_demand[i] / k_hp_q for i in range(period)) * cost_hp
        # RE: 蒸汽部分改成电锅炉
        capex_steam120_hp = max(steam120_demand) * 750 / k_eb * cost_eb
        capex_steam180_hp = max(steam180_demand) * 770 / k_eb * cost_eb
        capex_hotwater_hp = max(hotwater_demand) / k_hp_g * cost_hp
        capex_all_hp = ((capex_ele_hp + capex_g_hp + capex_q_hp
                         + capex_steam120_hp + capex_steam180_hp + capex_hotwater_hp)
                        * (1 + param_input["base"]["other_investment"]))
        # RE: 确认年化投资成本如何计算，即热泵使用年限是按输入来
        if param_input["device"]["hp"]["power_already"] == 0 and param_input["device"]["hp"]["power_maxy"] == 0:
            capex_all_crf_hp = crf_hp * capex_all_hp + capex_all_hp * param_input["base"]["other_investment"] / 10
        else:
            capex_all_crf_hp = crf(15) * capex_all_hp + capex_all_hp * param_input["base"]["other_investment"] / 10
        p_pur_hp = [(ele_load[i] + g_demand[i] / k_hp_g + q_demand[i] / k_hp_q
                    + steam120_demand[i] * 750 / k_hp_g + steam180_demand[i] * 770 / k_hp_g
                    + hotwater_demand[i] / k_hp_g) for i in range(period)]

        opex_sum_hp = (sum(lambda_ele_in[i] * p_pur_hp[i] for i in range(period))
                       + lambda_ele_capacity * max(p_pur_hp) * 12
                       + sum(lambda_h_in * h_demand[i] for i in range(period)))
        cost_annual_hp = capex_all_crf_hp + opex_sum_hp
        cost_annual_per_energy_hp = cost_annual_hp / whole_energy_contrast

        revenue_hp = revenue
        payback_period_hp = capex_all_hp / (revenue_hp - opex_sum_hp + 1e-7)
        payback_period_diff_hp = ((capex_all - capex_all_hp)
                                  / ((revenue - m.getVal(opex_sum)) - (revenue_hp - opex_sum_hp) + 1e-7))
        pure_revenue_hp = revenue_hp - opex_sum_hp + 1e-7
        carbon_emission_hp = sum(p_pur_hp) * alpha_e + sum(h_demand) * alpha_h
        cer_hp = ce_base - carbon_emission_hp
        cer_rate_hp = cer_hp / (ce_base + 1e-7)

        # --------------------------对比方案: 燃气方案-----------------------------#
        # RE: 确认过去计算方式中的 0.3525 是元/kwh 效率*元/方*方/kWh
        capex_ele_gas = 0
        capex_g_gas = max(g_demand) / k_gas * cost_gas
        opex_cool_gas = 0
        capex_q_gas = 0
        # RE: 确认对比方案供冷方式，先使用水冷机组供冷+集中供冷
        if param_input["base"]["base_method_cooling"] == "集中供冷":
            if param_input["income"]["cool_type"] == "供冷面积":
                opex_cool_gas = param_input["income"]["cool_price"] * param_input["objective_load"]["q_load_area"]
            elif param_input["income"]["cool_type"] == "冷量":
                opex_cool_gas = param_input["income"]["cool_price"] * sum(np.multiply(q_demand, (3600 / 1e6)).tolist())
            else:
                raise ValueError("非法 cool_type 值！")
        elif param_input["base"]["base_method_cooling"] == "水冷机组":
            capex_q_gas = max(q_demand) / k_ac * cost_ac
        else:
            raise ValueError("非法 base_method_cooling 值！")

        capex_steam120_gas = max(steam120_demand) * 750 / k_gas * cost_gas
        capex_steam180_gas = max(steam180_demand) * 770 / k_gas * cost_gas
        capex_hotwater_gas = max(hotwater_demand) / k_gas * cost_gas
        capex_all_gas = ((capex_ele_gas + capex_g_gas + capex_q_gas
                          + capex_steam120_gas + capex_steam180_gas + capex_hotwater_gas)
                         * (1 + param_input["base"]["other_investment"]))
        capex_all_crf_gas = crf(crf_gas) * capex_all_gas + capex_all_gas * param_input["base"]["other_investment"] / crf_gas
        p_pur_gas = ele_load
        gas_pur_gas = [(g_demand[i] / k_gas + q_demand[i] / k_ac
                        + steam120_demand[i] * 750 / k_gas + steam180_demand[i] * 770 / k_gas
                        + hotwater_demand[i] / k_gas) for i in range(period)]
        opex_sum_gas = (sum(lambda_ele_in[i] * p_pur_gas[i] for i in range(period))
                        + lambda_ele_capacity * max(p_pur_gas) * 12
                        + sum(gas_price * gas_pur_gas[i] for i in range(period))
                        + sum(lambda_h_in * h_demand[i] for i in range(period))
                        +opex_cool_gas)
        cost_annual_gas = capex_all_crf_gas + opex_sum_gas
        cost_annual_per_energy_gas = cost_annual_gas / whole_energy_contrast
        revenue_gas = revenue
        payback_period_gas = capex_all_gas / (revenue_gas - opex_sum_gas + 1e-7)
        payback_period_diff_gas = ((capex_all - capex_all_gas)
                                   / ((revenue - m.getVal(opex_sum)) - (revenue_gas - opex_sum_gas) + 1e-7))
        pure_revenue_gas = revenue_gas - opex_sum_gas + 1e-7
        carbon_emission_gas = sum(p_pur_gas) * alpha_e + sum(gas_pur_gas) * alpha_gas + sum(h_demand) * alpha_h
        cer_gas = ce_base - carbon_emission_gas
        cer_rate_gas = cer_gas / (ce_base + 1e-7)

        # ---------------------------输出结果-----------------------------#
        ele_sell = sum(m.getVal(p_sol[i]) for i in range(period))   # kw
        heat_sell = sum(m.getVal(g_sol[i]) * 3600 / 1e6 for i in range(period))  # 年售热量 (GJ)
        cooling_sell = sum(m.getVal(q_sol[i]) * 3600 / 1e6 for i in range(period))  # 年售冷量 (GJ)
        hydrogen_sell = sum(m.getVal(h_sol[i]) for i in range(period))  # kg
        steam120_sell = sum(m.getVal(steam120_sol[i]) for i in range(period))   # t
        steam180_sell = sum(m.getVal(steam180_sol[i]) for i in range(period))   # t
        heat_water_sell = sum(m.getVal(hotwater_sol[i]) for i in range(period)) # kwh
        income_ele_sell = sum(lambda_ele_out[i] * m.getVal(p_sol[i]) for i in range(period))    # 元
        income_heat_sell = lambda_g_out * sum(m.getVal(g_sol[i]) for i in range(period))    # 元
        income_cooling_sell = lambda_q_out * sum(m.getVal(q_sol[i]) for i in range(period))  # 元
        income_hydrogen_sell = lambda_h_out * sum(m.getVal(h_sol[i]) for i in range(period))    # 元
        income_steam120_sell = lambda_steam120_out * sum(m.getVal(steam120_sol[i]) for i in range(period))  # 元
        income_steam180_sell = lambda_steam180_out * sum(m.getVal(steam180_sol[i]) for i in range(period))  # 元
        income_heat_water_sell = lambda_hotwater_out * sum(m.getVal(hotwater_sol[i]) for i in range(period))   # 元

        co_capex = m.getVal(p_co_max) * cost_co  # 氢气压缩机投资成本 (元)
        fc_capex = m.getVal(p_fc_max) * cost_fc  # 氢气燃料电池投资成本 (元)
        el_capex = m.getVal(p_el_max) * cost_el  # 电解槽投资成本 (元)
        hst_capex = m.getVal(hst) * cost_hst  # 储氢罐投资成本 (元)
        ht_capex = m.getVal(m_ht) * cost_ht  # 热水罐投资成本 (元)
        ct_capex = m.getVal(m_ct) * cost_ct  # 冷水罐投资成本 (元)
        bat_capex = m.getVal(p_bat_max) * cost_bat  # 蓄电池投资成本 (元)
        steam_sto_capex = m.getVal(m_steam_sto_max) * cost_steam_storage  # 蒸汽储罐投资成本 (元)
        pv_capex = m.getVal(p_pv_max) * cost_pv  # 光伏投资成本 (元)
        sc_capex = m.getVal(s_sc) * cost_sc  # 太阳能集热器投资成本 (元)
        wd_capex = m.getVal(num_wd) * cost_wd  # 风电机组投资成本 (元)
        eb_capex = m.getVal(p_eb_max) * cost_eb  # 电锅炉投资成本 (元)
        abc_capex = m.getVal(g_abc_max) * cost_abc  # 吸收式制冷机投资成本 (元)
        ac_capex = m.getVal(p_ac_max) * cost_ac  # 水冷机组投资成本 (元)
        hp_capex = m.getVal(p_hp_max) * cost_hp  # 空气源热泵投资成本 (元)
        ghp_capex = m.getVal(p_ghp_max) * cost_ghp  # 浅层地源热泵投资成本 (元)
        ghp_deep_capex = m.getVal(p_ghp_deep_max) * cost_ghp_deep  # 中深层地源热泵投资成本 (元)
        gtw_capex = m.getVal(num_gtw) * cost_gtw  # 200米浅层地热井投资成本 (元)
        gtw2500_capex = m.getVal(num_gtw2500) * cost_gtw2500  # 2500米地热井投资成本 (元)
        hp120_capex = m.getVal(p_hp120_max) * cost_hp120  # 高温热泵投资成本 (元)
        co180_capex = m.getVal(p_co180_max) * cost_co180  # 蒸汽压缩机投资成本 (元)
        whp_capex = m.getVal(p_whp_max) * cost_whp  # 水源热泵投资成本 (元)

        p_pv_theory = [eta_pv * (m.getVal(p_pv_max) + param_input["device"]["pv"]["power_already"]) * pv_data[i] for i in range(period)]

        custom_storage_installed = []
        custom_exchange_installed = []
        custom_storage_capex = []
        custom_exchange_capex = []
        custom_storage = []
        custom_exchange = []
        for i in range(num_custom_storage_device):
            device = csd_data[i]
            energy_type_index = energy_type_list.index(device["energy_type"])
            custom_storage_installed.append({
                "device_name": device["device_name"],
                "energy_type": device["energy_type"],
                "installed_capacity": m.getVal(csd_install[i])
            })
            custom_storage_capex.append({
                "device_name": device["device_name"],
                "energy_type": device["energy_type"],
                "capex": m.getVal(csd_install[i]) * cost_csd[i]
            })
            custom_storage.append({
                "device_name": device["device_name"],
                "energy_type": device["energy_type"],
                "storage_state": [m.getVal(csd_sto[i][t]) for t in range(period)],
                "storage_in": [m.getVal(csd_energy_in[i][energy_type_index][t]) for t in range(period)],
                "storage_out": [m.getVal(csd_energy_out[i][energy_type_index][t]) for t in range(period)],
            })
        for i in range(num_custom_exchange_device):
            device = ced_data[i]
            energy_in_type_indices = [index for index, value in enumerate(device["energy_in_type"]) if value == 1]
            energy_out_type_indices = [index for index, value in enumerate(device["energy_out_type"]) if value == 1]
            energy_in_type_indices.sort()
            energy_out_type_indices.sort()
            custom_exchange_installed.append({
                "device_name": device["device_name"],
                "energy_in_type": device["energy_in_type"],
                "energy_out_type": device["energy_out_type"],
                "installed_capacity": format(m.getVal(ced_install[i]), ".2f")
            })
            custom_exchange_capex.append({
                "device_name": device["device_name"],
                "energy_in_type": device["energy_in_type"],
                "energy_out_type": device["energy_out_type"],
                "capex": format(m.getVal(ced_install[i]) * cost_ced[i] / 1e4, ".2f")
            })
            custom_exchange.append({
                "device_name": device["device_name"],
                "energy_in_type": device["energy_in_type"],
                "energy_out_type": device["energy_out_type"],
                "energy_in": [[m.getVal(ced_energy_in[i][j][t]) for t in range(period)] for j in energy_in_type_indices],
                "energy_out": [[m.getVal(ced_energy_out[i][j][t]) for t in range(period)] for j in energy_out_type_indices]
            })

        # TODO: (HSL, ZYL) 检查输出是否满足报告需求，包括字段的完整性和单位的一致性
        # TODO: (DZY) 检查输出信息的单位，是否与测算方案中变量单位换算关系一致
        result = {
            "sys_performance": {
                # 经济性分析
                "economic_analysis": {
                    # 本项目
                    "capex_all": format(capex_all / 1e4, ".2f"),  # 初始投资成本 (万元)
                    "capex_all_crf": format(capex_all_crf / 1e4, ".2f"),  # 年化投资成本 (万元)
                    "capex_other": format(capex_other / 1e4, ".2f"),  # 其他投资成本 (万元)
                    "opex_sum": format(m.getVal(opex_sum) / 1e4, ".2f"),  # 年化运行成本 (万元)
                    "cost_annual": format(cost_annual / 1e4, ".2f"),  # 年化总成本 (万元)
                    "pure_revenue": format(pure_revenue, ".2f"),    # 年净收益
                    "cost_annual_per_energy": format(cost_annual_per_energy, ".4f"),  # 单位能源成本 (元/kWh)
                    "payback_period": format(payback_period, ".2f"),  # 投资回收期 (年)
                    "co2": format(carbon_emission / 1e3, ".2f"),  # 年碳排放量 (吨)
                    "cer": format(cer / 1e3, ".2f"),  # 年碳减排量 (吨)
                    "cer_rate": format(cer_rate, ".4f"),  # 实际碳减排率
                    # 对比方案: 纯电 (电锅炉供暖) 方案
                    "capex_all_eb": format(capex_all_eb / 1e4, ".2f"),  # 初始投资成本 (万元)
                    "capex_all_crf_eb": format(capex_all_crf_eb / 1e4, ".2f"),  # 年化投资成本 (万元)
                    "opex_sum_eb": format(opex_sum_eb / 1e4, ".2f"),  # 年化运行成本 (万元)
                    "cost_annual_eb": format(cost_annual_eb / 1e4, ".2f"),  # 年化总成本 (万元)
                    "pure_revenue_eb": format(pure_revenue_eb, ".2f"),  # 年净收益
                    "cost_annual_per_energy_eb": format(cost_annual_per_energy_eb, ".4f"),  # 单位能源成本 (元/kWh)
                    "payback_period_eb": format(payback_period_eb, ".2f"),  # 投资回收期 (年)
                    "payback_period_diff_eb": format(payback_period_diff_eb, ".2f"),  # 投资差额回收期 (年)
                    "co2_eb": format(carbon_emission_eb / 1e3, ".2f"),  # 年碳排放量 (吨)
                    "cer_eb": format(cer_eb / 1e3, ".2f"),  # 年碳减排量 (吨)
                    "cer_rate_eb": format(cer_rate_eb, ".4f"),  # 碳减排率
                    # 对比方案: 纯电 (热泵供暖) 方案
                    "capex_all_hp": format(capex_all_hp / 1e4, ".2f"),  # 初始投资成本 (万元)
                    "capex_all_crf_hp": format(capex_all_crf_hp / 1e4, ".2f"),  # 年化投资成本 (万元)
                    "opex_sum_hp": format(opex_sum_hp / 1e4, ".2f"),  # 年化运行成本 (万元)
                    "cost_annual_hp": format(cost_annual_hp / 1e4, ".2f"),  # 年化总成本 (万元)
                    "pure_revenue_hp": format(pure_revenue_hp, ".2f"),  # 年净收益
                    "cost_annual_per_energy_hp": format(cost_annual_per_energy_hp, ".4f"),  # 单位能源成本 (元/kWh)
                    "payback_period_hp": format(payback_period_hp, ".2f"),  # 投资回收期 (年)
                    "payback_period_diff_hp": format(payback_period_diff_hp, ".2f"),  # 投资差额回收期 (年)
                    "co2_hp": format(carbon_emission_hp / 1e3, ".2f"),  # 年碳排放量 (吨)
                    "cer_hp": format(cer_hp / 1e3, ".2f"),  # 年碳减排量 (吨)
                    "cer_rate_hp": format(cer_rate_hp, ".4f"),  # 碳减排率
                    # 对比方案: 燃气方案
                    "capex_all_gas": format(capex_all_gas / 1e4, ".2f"),  # 初始投资成本 (万元)
                    "capex_all_crf_gas": format(capex_all_crf_gas / 1e4, ".2f"),  # 年化投资成本 (万元)
                    "opex_sum_gas": format(opex_sum_gas / 1e4, ".2f"),  # 年化运行成本 (万元)
                    "cost_annual_gas": format(cost_annual_gas / 1e4, ".2f"),  # 年化总成本 (万元)
                    "pure_revenue_gas": format(pure_revenue_gas, ".2f"),  # 年净收益
                    "cost_annual_per_energy_gas": format(cost_annual_per_energy_gas, ".4f"),  # 单位能源成本 (元/kWh)
                    "payback_period_gas": format(payback_period_gas, ".2f"),  # 投资回收期 (年)
                    "payback_period_diff_gas": format(payback_period_diff_gas, ".2f"),  # 投资差额回收期 (年)
                    "co2_gas": format(carbon_emission_gas / 1e3, ".2f"),  # 年碳排放量 (吨)
                    "cer_gas": format(cer_gas / 1e3, ".2f"),  # 年碳减排量 (吨)
                    "cer_rate_gas": format(cer_rate_gas, ".4f"),  # 碳减排率
                },
                # 收益明细
                "revenue_analysis": {
                    "revenue_ele": format(revenue_ele / 1e4, ".2f"),  # 供电收益 (万元)
                    "revenue_heat": format(revenue_heat / 1e4, ".2f"),  # 供热收益 (万元)
                    "revenue_cooling": format(revenue_cool / 1e4, ".2f"),  # 供冷收益 (万元)
                    "revenue_hydrogen": format(revenue_h / 1e4, ".2f"),  # 供氢收益 (万元)
                    "revenue_steam120": format(revenue_steam120 / 1e4, ".2f"),  # 供120蒸汽收益 (万元)
                    "revenue_steam180": format(revenue_steam180 / 1e4, ".2f"),  # 供180蒸汽收益 (万元)
                    "revenue_heat_water": format(revenue_hotwater / 1e4, ".2f"),  # 生活热水收益 (万元)
                    "ele_sell": format(ele_sell, ".2f"),  # 年售电量 (kWh)
                    "heat_sell": format(heat_sell, ".2f"),  # 年售热量 (GJ)
                    "cooling_sell": format(cooling_sell, ".2f"),  # 年售冷量 (GJ)
                    "hydrogen_sell": format(hydrogen_sell, ".2f"),  # 年售氢量 (kg)
                    "steam120_sell": format(steam120_sell, ".2f"),  # 年售120蒸汽量 (t)
                    "steam180_sell": format(steam180_sell, ".2f"),  # 年售180蒸汽量 (t)
                    "heat_water_sell": format(heat_water_sell, ".2f"),  # 年售生活热水量 (kWh)
                    "income_ele_sell": format(income_ele_sell / 1e4, ".2f"),  # 年售电收入 (万元)
                    "income_heat_sell": format(income_heat_sell / 1e4, ".2f"),  # 年售热收入 (万元)
                    "income_cooling_sell": format(income_cooling_sell / 1e4, ".2f"),  # 年售冷收入 (万元)
                    "income_hydrogen_sell": format(income_hydrogen_sell / 1e4, ".2f"),  # 年售氢收入 (万元)
                    "income_steam120_sell": format(income_steam120_sell / 1e4, ".2f"),  # 年售120蒸汽收入 (万元)
                    "income_steam180_sell": format(income_steam180_sell / 1e4, ".2f"),  # 年售180蒸汽收入 (万元)
                    "income_heat_water_sell": format(income_heat_water_sell / 1e4, ".2f"),  # 年售生活热水收入 (万元)
                },
            },
            "device_result": {
                # 设备配置结果
                # TODO: (HSL, ZYL) 明确报告文档内的单位需求，确保输出与报告需求一致
                "device_capacity": {
                    "p_co_installed": format(m.getVal(p_co_max), ".2f"),  # 氢气压缩机装机容量 (kW)
                    "p_fc_installed": format(m.getVal(p_fc_max), ".2f"),  # 燃料电池装机容量 (kW)
                    "p_el_installed": format(m.getVal(p_el_max), ".2f"),  # 电解槽装机容量 (kW)
                    "h_hst_installed": format(m.getVal(hst), ".2f"),  # 储氢罐装机容量 (kg)
                    "m_ht_installed": format(m.getVal(m_ht) / 1e3, ".2f"),  # 热水罐装机容量 (t)
                    "m_ct_installed": format(m.getVal(m_ct) / 1e3, ".2f"),  # 冷水罐装机容量 (t)
                    "p_bat_installed": format(m.getVal(p_bat_max), ".2f"),  # 蓄电池装机容量 (kW)
                    "steam_storage_installed": format(m.getVal(m_steam_sto_max), ".2f"),  # 蒸汽储罐装机容量 (t)
                    "p_pv_installed": format(m.getVal(p_pv_max), ".2f"),  # 光伏装机容量 (kW)
                    "s_sc_installed": format(m.getVal(s_sc), ".2f"),  # 太阳能集热器装机容量 (m2)
                    "num_wd_installed": format(m.getVal(num_wd), ".2f"),  # 风电机组装机数量
                    "p_eb_installed": format(m.getVal(p_eb_max), ".2f"),  # 电锅炉装机容量 (kW)
                    "g_abc_installed": format(m.getVal(g_abc_max), ".2f"),  # 吸收式制冷机装机容量 (kW)
                    "p_ac_installed": format(m.getVal(p_ac_max), ".2f"),  # 水冷机组装机容量 (kW)
                    "p_hp_installed": format(m.getVal(p_hp_max), ".2f"),  # 空气源热泵装机容量 (kW)
                    "p_ghp_installed": format(m.getVal(p_ghp_max), ".2f"),  # 浅层地源热泵装机容量 (kW)
                    "p_ghp_deep_installed": format(m.getVal(p_ghp_deep_max), ".2f"),  # 中深层地源热泵装机容量 (kW)
                    "num_gtw_installed": format(m.getVal(num_gtw), ".2f"),  # 200米浅层地热井装机数量
                    "num_gtw2500_installed": format(m.getVal(num_gtw2500), ".2f"),  # 2500米地热井装机数量
                    "p_hp120_installed": format(m.getVal(p_hp120_max), ".2f"),  # 高温热泵装机容量 (kW)
                    "p_co180_installed": format(m.getVal(p_co180_max), ".2f"),  # 蒸汽压缩机装机容量 (kW)
                    "p_whp_installed": format(m.getVal(p_whp_max), ".2f"),  # 水源热泵装机容量 (kW)
                    "custom_storage_installed": custom_storage_installed,  # 自定义储能设备装机容量
                    "custom_exchange_installed": custom_exchange_installed,  # 自定义能量交换设备装机容量
                },
                # 设备投资成本
                "device_capex": {
                    "co_capex": format(co_capex / 1e4, ".2f"),  # 氢气压缩机投资成本 (万元)
                    "fc_capex": format(fc_capex / 1e4, ".2f"),  # 氢气燃料电池投资成本 (万元)
                    "el_capex": format(el_capex / 1e4, ".2f"),  # 电解槽投资成本 (万元)
                    "hst_capex": format(hst_capex / 1e4, ".2f"),  # 储氢罐投资成本 (万元)
                    "ht_capex": format(ht_capex / 1e4, ".2f"),  # 热水罐投资成本 (万元)
                    "ct_capex": format(ct_capex / 1e4, ".2f"),  # 冷水罐投资成本 (万元)
                    "bat_capex": format(bat_capex / 1e4, ".2f"),  # 蓄电池投资成本 (万元)
                    "steam_storage_capex": format(steam_sto_capex / 1e4, ".2f"),  # 蒸汽储罐投资成本 (万元)
                    "pv_capex": format(pv_capex / 1e4, ".2f"),  # 光伏投资成本 (万元)
                    "sc_capex": format(sc_capex / 1e4, ".2f"),  # 太阳能集热器投资成本 (万元)
                    "wd_capex": format(wd_capex / 1e4, ".2f"),  # 风电机组投资成本 (万元)
                    "eb_capex": format(eb_capex / 1e4, ".2f"),  # 电锅炉投资成本 (万元)
                    "abc_capex": format(abc_capex / 1e4, ".2f"),  # 吸收式制冷机投资成本 (万元)
                    "ac_capex": format(ac_capex / 1e4, ".2f"),  # 水冷机组投资成本 (万元)
                    "hp_capex": format(hp_capex / 1e4, ".2f"),  # 空气源热泵投资成本 (万元)
                    "ghp_capex": format(ghp_capex / 1e4, ".2f"),  # 浅层地源热泵投资成本 (万元)
                    "ghp_deep_capex": format(ghp_deep_capex / 1e4, ".2f"),  # 中深层地源热泵投资成本 (万元)
                    "gtw_capex": format(gtw_capex / 1e4, ".2f"),  # 200米浅层地热井投资成本 (万元)
                    "gtw2500_capex": format(gtw2500_capex / 1e4, ".2f"),  # 2500米地热井投资成本 (万元)
                    "hp120_capex": format(hp120_capex / 1e4, ".2f"),  # 高温热泵投资成本 (万元)
                    "co180_capex": format(co180_capex / 1e4, ".2f"),  # 蒸汽压缩机投资成本 (万元)
                    "whp_capex": format(whp_capex / 1e4, ".2f"),  # 水源热泵投资成本 (万元)
                    "custom_storage_capex": custom_storage_capex,  # 自定义储能设备投资成本
                    "custom_exchange_capex": custom_exchange_capex,  # 自定义能量交换设备投资成本
                },
            },
            "scheduling_result": {
                # debug 用
                # "ele_load": [ele_load[i] for i in range(period)],
                # "g_demand": [g_demand[i] for i in range(period)],
                # "q_demand": [q_demand[i] for i in range(period)],
                # "h_demand": [h_demand[i] for i in range(period)],
                # "steam120_demand": [steam120_demand[i] for i in range(period)],
                # "steam180_demand": [steam180_demand[i] for i in range(period)],
                # "hotwater_demand": [hotwater_demand[i] for i in range(period)],
                # 能量流交易
                "ele_buy": [m.getVal(p_pur[i]) for i in range(period)],
                "ele_sell": [m.getVal(p_sol[i]) for i in range(period)],
                "heat_buy": [m.getVal(g_pur[i]) for i in range(period)],
                "heat_sell": [m.getVal(g_sol[i]) for i in range(period)],
                "cooling_buy": [m.getVal(q_pur[i]) for i in range(period)],
                "cooling_sell": [m.getVal(q_sol[i]) for i in range(period)],
                "hydrogen_buy": [m.getVal(h_pur[i]) for i in range(period)],
                "hydrogen_sell": [m.getVal(h_sol[i]) for i in range(period)],
                "steam120_buy": [m.getVal(steam120_pur[i]) for i in range(period)],
                "steam120_sell": [m.getVal(steam120_sol[i]) for i in range(period)],
                "steam180_buy": [m.getVal(steam180_pur[i]) for i in range(period)],
                "steam180_sell": [m.getVal(steam180_sol[i]) for i in range(period)],
                "heat_water_buy": [m.getVal(hotwater_pur[i]) for i in range(period)],
                "heat_water_sell": [m.getVal(hotwater_sol[i]) for i in range(period)],
                # 设备运行状态
                # 氢气压缩机
                "p_co": [m.getVal(p_co[i]) for i in range(period)],
                # 燃料电池
                "p_fc": [m.getVal(p_fc[i]) for i in range(period)],
                "g_fc": [m.getVal(g_fc[i]) for i in range(period)],
                "h_fc": [m.getVal(h_fc[i]) for i in range(period)],
                # 电解槽
                "p_el": [m.getVal(p_el[i]) for i in range(period)],
                "g_el": [m.getVal(g_el[i]) for i in range(period)],
                "h_el": [m.getVal(h_el[i]) for i in range(period)],
                # 储氢罐
                "h_sto": [m.getVal(h_sto[i]) for i in range(period)],
                # 热水罐
                "g_ht": [m.getVal(g_ht[i]) for i in range(period)],
                "g_ht_in": [m.getVal(g_ht_in[i]) for i in range(period)],
                "g_ht_out": [m.getVal(g_ht_out[i]) for i in range(period)],
                # 冷水罐
                "q_ct": [m.getVal(q_ct[i]) for i in range(period)],
                "q_ct_in": [m.getVal(q_ct_in[i]) for i in range(period)],
                "q_ct_out": [m.getVal(q_ct_out[i]) for i in range(period)],
                # 蓄电池
                "p_bat": [m.getVal(p_bat_sto[i]) for i in range(period)],
                "p_bat_ch": [m.getVal(p_bat_in[i]) for i in range(period)],
                "p_bat_dis": [m.getVal(p_bat_out[i]) for i in range(period)],
                # 蒸汽储罐
                "m_steam_storage": [m.getVal(m_steam_sto[i]) for i in range(period)],
                "m_steam_storage_in": [m.getVal(m_steam_sto_in[i]) for i in range(period)],
                "m_steam_storage_out": [m.getVal(m_steam_sto_out[i]) for i in range(period)],
                # 光伏
                "p_pv_theory": p_pv_theory,
                "p_pv": [m.getVal(p_pv[i]) for i in range(period)],
                # 太阳能集热器
                "g_sc": [m.getVal(g_sc[i]) for i in range(period)],
                # 风电机组
                "p_wd": [m.getVal(p_wd[i]) for i in range(period)],
                # 电锅炉
                "p_eb": [m.getVal(p_eb[i]) for i in range(period)],
                "g_eb": [m.getVal(g_eb[i]) for i in range(period)],
                # 吸收式制冷机
                "g_abc": [m.getVal(g_abc[i]) for i in range(period)],
                "q_abc": [m.getVal(q_abc[i]) for i in range(period)],
                # 水冷机组
                "p_ac": [m.getVal(p_ac[i]) for i in range(period)],
                "q_ac": [m.getVal(q_ac[i]) for i in range(period)],
                # 空气源热泵
                "p_hp": [m.getVal(p_hp[i]) for i in range(period)],
                "g_hp": [m.getVal(g_hp[i]) for i in range(period)],
                "p_hp_c": [m.getVal(p_hpc[i]) for i in range(period)],
                "q_hp": [m.getVal(q_hp[i]) for i in range(period)],
                # 浅层地源热泵
                "p_ghp": [m.getVal(p_ghp[i]) for i in range(period)],
                "g_ghp": [m.getVal(g_ghp[i]) for i in range(period)],
                "p_ghp_c": [m.getVal(p_ghpc[i]) for i in range(period)],
                "q_ghp": [m.getVal(q_ghp[i]) for i in range(period)],
                "g_ghp_inject": [m.getVal(g_ghp_gr[i]) for i in range(period)],
                # 中深层地源热泵
                "p_ghp_deep": [m.getVal(p_ghp_deep[i]) for i in range(period)],
                "g_ghp_deep": [m.getVal(g_ghp_deep[i]) for i in range(period)],
                # 高温热泵
                "p_hp120": [m.getVal(p_hp120[i]) for i in range(period)],
                "m_hp120": [m.getVal(m_hp120[i]) for i in range(period)],
                "g_hp120": [m.getVal(g_hp120_in[i]) for i in range(period)],
                # 蒸汽压缩机
                "p_co180": [m.getVal(p_co180[i]) for i in range(period)],
                "m_co180_in": [m.getVal(m_co180_in[i]) for i in range(period)],
                "m_co180": [m.getVal(m_co180_out[i]) for i in range(period)],
                # 水源热泵
                "p_whp": [m.getVal(p_whp[i]) for i in range(period)],
                "g_whp": [m.getVal(g_whp[i]) for i in range(period)],
                "p_whp_c": [m.getVal(p_whpc[i]) for i in range(period)],
                "q_whp": [m.getVal(q_whp[i]) for i in range(period)],

                # 自定义储能设备
                "custom_storage": custom_storage,
                # 自定义能量交换设备
                "custom_exchange": custom_exchange,
                # 总线
                "g_tube": [m.getVal(g_tube[i]) for i in range(period)],
            }
        }
        # debug 用
        # for i in range(num_custom_exchange_device):
        #     result["scheduling_result"][f"standard_ced_{i}"] = [m.getVal(standard_ced[i][t]) for t in range(period)]
        #
        # return result

    def exec(self, inputBody: OptimizationBody):
        param_input = inputBody.model_dump()
        planning_result = self.planning_opt(param_input)
        return planning_result
