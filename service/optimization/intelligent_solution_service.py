import pyscipopt
from pyscipopt import Model, quicksum, multidict
import numpy as np
import xlwt
import xlrd
import json
import pandas as pd
import random
import time

from schema.schema_optimization import OptimizationBody


def generate_annual_load(start_date, end_date, typical_daily_load):
    """
    生成全年热负荷数据，采暖季期间使用典型日负荷数据

    参数:
    start_date (str): 采暖季起始日期，格式 "月-日" (e.g., "10-01")
    end_date (str): 采暖季结束日期，格式 "月-日" (e.g., "03-01")
    typical_daily_load (list): 典型日24小时负荷数据，长度24

    返回:
    np.array: 全年8760小时负荷数据
    """
    # 创建全年时间索引 (2023年，非闰年)
    dates = pd.date_range('2023-01-01', '2023-12-31 23:00:00', freq='H')

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
        annual_load[day_indices] = typical_daily_load

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

    def exec(self, inputBody: OptimizationBody):

        param_input = inputBody.model_dump()
        M = 1e9  # 大数M

        # 开始计时
        t0 = time.time()

        #------------导入负荷数据------------#
        ele_load = param_input["sys_load"]["electricity_load"]
        heatload_num = len(param_input["sys_load"]["heat_load"])
        coolload_num = len(param_input["sys_load"]["cool_load"])
        steamload_num = len(param_input["sys_load"]["steam_load"])
        hotwater_num = len(param_input["sys_load"]["hotwater_load"])
        g_demand = [0] * 8760
        q_demand = [0] * 8760
        h_demand = param_input["sys_load"]["hydrogen_load"]
        steam120_demand = [0] * 8760
        steam180_demand = [0] * 8760
        hotwater_demand = [0] * 8760
        for i in range(heatload_num):
            g_demand += param_input["sys_load"]["heat_load"]['heat'+str(i)]["load"]
        for i in range(coolload_num):
            q_demand = param_input["sys_load"]["cool_load"]['heat'+str(i)]["load"]
        for i in range(steamload_num):
            if param_input["sys_load"]["steam_load"]['steam'+str(i)]["tem"] == 120:
                steam120_demand += param_input["sys_load"]["steam_load"]['steam'+str(i)]["load"]
            elif param_input["sys_load"]["steam_load"]['steam'+str(i)]["tem"] == 180:
                steam180_demand += param_input["sys_load"]["steam_load"]['steam' + str(i)]["load"]
        for i in range(hotwater_num):
            hotwater_demand += param_input["sys_load"]["hotwater_load"]['hotwater'+str(i)]["load"]
        g_demand += hotwater_demand  # 合并热需求

        pv_data = param_input["device"]["pv"]["pv_data8760"]
        sc_data = param_input["device"]["sc"]["solar_data8760"]
        wd_data = param_input["device"]["wd"]["wd_data8760"]

        if param_input["trading"]["heat_resource"]["flag"] == 0:
            heat_resource = [0] * 8760  # 热源数据
        else:
            heat_resource = generate_annual_load(
                start_date=param_input["trading"]["heat_resource"]["cycle"]["start"],
                end_date=param_input["trading"]["heat_resource"]["cycle"]["end"],
                typical_daily_load=param_input["trading"]["heat_resource"]["heat_resource_flow"]
            ).tolist()

        #------------导入价格等数据------------#
        alpha_e = 0.5839  # 电网排放因子kg/kWh
        gas_price = 1.2  # 天然气价钱
        lambda_ele_in = param_input["trading"]["power_buy_8760_price"]           # 每个小时的电价
        lambda_ele_out = param_input["trading"]["power_sell_24_price"]              # 卖电价格
        lambda_g_out = param_input["trading"]["heat_sell_price"]                 # 卖热价格
        lambda_h_out = param_input["trading"]["hydrogen_sell_price"]             # 卖氢价格
        lambda_h = param_input["trading"]["hydrogen_buy_price"]                  # 买氢价格
        cer = param_input["base"]["cer"]                                          # 碳减排率
        lambda_steam120_in = param_input["trading"]["steam_buy"][1]["price"]        # 120蒸汽购入价格
        lambda_steam120_out = param_input["trading"]["steam_sell"][1]["price"]      # 120蒸汽出售价格
        lambda_steam180_in = param_input["trading"]["steam_buy"][0]["price"]        # 180蒸汽购入价格
        lambda_steam180_out = param_input["trading"]["steam_sell"][0]["price"]      # 180蒸汽出售价格
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
        cost_steam_storage = param_input["device"]["steam_sorage"]["cost"]
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
        k_co = param_input["device"]["co"]["beta_co"]
        # ----fc----#
        k_fc_p = param_input["device"]["fc"]["eta_fc_p"]  # 氢转电系数kg——>kWh
        k_fc_g = param_input["device"]["fc"]["eta_fc_g"] # 氢转热系数kg——>kWh
        fc_theta_ex = param_input["device"]["fc"]["theta_ex"]  # 热回收效率
        # ----el----#
        kg2nm3 = 11.2  # 1kg氢气体积为11.2标方
        k_el_h = param_input["device"]["el"]["eta_el_h"]  # 电转氢效率
        k_el_g = param_input["device"]["el"]["eta_el_g"]
        el_theta_ex = param_input["device"]["el"]["theta_ex"]
        nm3_el_already = param_input["device"]["el"]["nm3_already"]
        nm3_el_upper = param_input["device"]["el"]["nm3_max"]
        nm3_el_lower = param_input["device"]["el"]["nm3_min"]
        p_el_already = nm3_el_already / kg2nm3 / k_el_h
        p_el_upper = nm3_el_upper / kg2nm3 / k_el_h
        p_el_lower = nm3_el_lower / kg2nm3 / k_el_h
        # ---hst----#
        # ---ht----#
        k_ht_sto_max = param_input["device"]["ht"]["g_storage_max_per_unit"]  # 储量转热量上限
        k_ht_sto_min = param_input["device"]["ht"]["g_storage_min_per_unit"]  # 储量转热量下限
        k_ht_power_max = param_input["device"]["ht"]["g_power_max_per_unit"]  # 储量转供量上限
        k_ht_power_min = param_input["device"]["ht"]["g_power_min_per_unit"]  # 储量转供量上限
        loss_ht = param_input["device"]["ht"]["loss_rate"]                    # 能量损失系数
        # ---ct----#
        k_ct_sto_max = param_input["device"]["ct"]["q_storage_max_per_unit"]  # 储量转热量上限
        k_ct_sto_min = param_input["device"]["ct"]["q_storage_min_per_unit"]  # 储量转热量下限
        k_ct_power_max = param_input["device"]["ct"]["q_power_max_per_unit"]  # 储量转供量上限
        k_ct_power_min = param_input["device"]["ct"]["q_power_min_per_unit"]  # 储量转供量上限
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
        eta_pv = param_input["device"]["pv"]["beta_pv"]  # 单位面积下光转电效率
        k_s_pv= param_input["device"]["pv"]["s_pv_per_unit"]
        # ----sc----#
        k_sc = param_input["device"]["sc"]["beta_sc"]
        sc_theta_ex = param_input["device"]["sc"]["theta_ex"]
        k_s_sc = param_input["device"]["sc"]["s_sc_per_unit"]
        # ----wd----#
        k_s_wd = param_input["device"]["wd"]["s_wd_per_unit"]
        # ----eb----#
        k_eb = param_input["device"]["eb"]["beta_eb"]
        #----abc---#
        k_abc = param_input["device"]["abc"]["beta_abc"]
        # ----ac----#
        k_ac = param_input["device"]["ac"]["beta_ac"]
        # ----hp----#
        k_hp_g = param_input["device"]["hp"]["beta_hpg"]
        k_hp_q = param_input["device"]["hp"]["beta_hpq"]
        # ----ghp----#
        k_ghp_g = param_input["device"]["ghp"]["beta_ghpg"]
        k_ghp_q = param_input["device"]["ghp"]["beta_ghpq"]
        k_ghp_deep_g = param_input["device"]["ghp_deep"]["beta_ghpg"]
        # ----gtw----#
        p_gtw = param_input["device"]["gtw"]["beta_gtw"]
        # ----gtw2500----#
        p_gtw2500 = param_input["device"]["gtw2500"]["beta_gtw"]
        # ----hp120----#
        cop_hp120 = param_input["device"]["hp120"]["cop"]
        # ----co180----#
        k_co180 = param_input["device"]["co180"]["k_e_m"]
        # ----whp----#
        cop_whpg = param_input["device"]["whp"]["cop_heat"]
        cop_whpq = param_input["device"]["whp"]["cop_cold"]
        # ---------------------------用户自定义设备---------------------------#
        num_custom_exchange_device = len(param_input["device"]["custom_device_exchange"])       # 用户自定义能量交换设备
        num_custom_storage_device = len(param_input["device"]["custom_device_storage"])         # 用户自定义储能设备
        # ---------------第i个自定义设备的年化收益率数据---------------#
        crf_ced = [0] * num_custom_exchange_device
        crf_csd = [0] * num_custom_storage_device
        for i in range(num_custom_exchange_device):
            crf_ced[i] = crf(param_input["device"]["custom_device_exchange"][i]["crf"])
        for i in range(num_custom_storage_device):
            crf_csd[i] = crf(param_input["device"]["custom_device_storage"][i]["crf"])
        # --------------第i个自定义设备的单位投资成本--------------#
        cost_ced = [0] * num_custom_exchange_device
        cost_csd = [0] * num_custom_storage_device
        for i in range(num_custom_exchange_device):
            cost_ced[i] = param_input["device"]["custom_device_exchange"][i]["cost"]
        for i in range(num_custom_storage_device):
            cost_csd[i] = param_input["device"]["custom_device_storage"][i]["cost"]
        # -----------------------自定义设备的效率数据----------------------#
        # ------0：电   1：热   2：冷   3：氢   4：120蒸汽  5：180蒸汽  6：家用热水（仅自定义设备）------#
        # TODO: 初始化时按照维数来，否则后面可能会出现问题
        energy_type_num = 7
        cop_in2standerd_ced = [[0] * energy_type_num] * num_custom_exchange_device
        cop_standerd2out_ced = [[0] * energy_type_num] * num_custom_exchange_device
        k_install2sto_max_csd = [[0] * energy_type_num] * num_custom_storage_device
        k_install2sto_min_csd = [[0] * energy_type_num] * num_custom_storage_device
        k_sto2io_max_csd = [0] * num_custom_storage_device
        k_sto2io_min_csd = [0] * num_custom_storage_device
        for i in range(num_custom_exchange_device):
            cop_in2standerd_ced[i] = param_input["device"]["custom_device_exchange"][i]["energy_in_standard_per_unit"]
            cop_standerd2out_ced[i] = param_input["device"]["custom_device_exchange"][i]["energy_out_standard_per_unit"]
        for i in range(num_custom_storage_device):
            k_install2sto_max_csd[i] = param_input["device"]["custom_device_storage"][i]["energy_storage_max_per_unit"]
            k_install2sto_min_csd[i] = param_input["device"]["custom_device_storage"][i]["energy_storage_min_per_unit"]
            k_sto2io_max_csd[i] = param_input["device"]["custom_device_storage"][i]["energy_power_max_per_unit"]
            k_sto2io_min_csd[i] = param_input["device"]["custom_device_storage"][i]["energy_power_min_per_unit"]
        # -----------------------建立优化模型----------------------------#
        # 运行天数
        period = 8760
        # 建立模型
        m = Model("mip")
        # ---------------创建变量--------------#
        # 规划容量部分变量
        op_sum = m.addVar(vtype="C", lb=-10000000000, name=f"op_sum")  # 运行费用:买电-卖电+买氢+买水电
        op_sum_pure = m.addVar(vtype="C", lb=-10000000000, name=f"op_sum_pure")  # 运行费用:买电-卖电+买氢+买水电
        capex_sum = m.addVar(vtype="C", lb=0, name=f"capex_sum")  # 总设备投资
        capex_crf = m.addVar(vtype="C", lb=0, name=f"capex_crf")  # 总设备年化收益
        ce_h = m.addVar(vtype="C", lb=0, name="ce_h")  # 碳排放量（买电*碳排因子
        # 系统级变量
        g_tube = [m.addVar(vtype="C", lb=0, name=f"g_tube{t}") for t in range(period)]
        p_pur = [m.addVar(vtype="C", lb=0, name=f"p_pur{t}") for t in range(period)]  # 买电power purchase
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
        m_steam120_sto_max = m.addVar(vtype="C", lb=param_input["device"]["steam_storage"]["water_min"],
                                      ub=param_input["device"]["steam_storage"]["water_max"],
                                      name=f"m_steam120_sto_max")
        m_steam180_sto_max = m.addVar(vtype="C", lb=param_input["device"]["steam_storage"]["water_min"],
                                      ub=param_input["device"]["steam_storage"]["water_max"],
                                      name=f"m_steam180_sto_max")
        m_steam120_sto_in = [m.addVar(vtype="C", lb=0, name=f"m_steam120_sto_in{t}") for t in range(period)]
        m_steam120_sto_out = [m.addVar(vtype="C", lb=0, name=f"m_steam120_sto_out{t}") for t in range(period)]
        m_steam180_sto_in = [m.addVar(vtype="C", lb=0, name=f"m_steam180_sto_in{t}") for t in range(period)]
        m_steam180_sto_out = [m.addVar(vtype="C", lb=0, name=f"m_steam120_sto_out{t}") for t in range(period)]
        m_steam120_sto = [m.addVar(vtype="C", lb=0, name=f"m_steam120_sto{t}") for t in range(period)]
        m_steam180_sto = [m.addVar(vtype="C", lb=0, name=f"m_steam180_sto{t}") for t in range(period)]
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
        ced_install = [m.addVar(vtype="C", lb=param_input["device"]["custom_device_exchange"][i]["device_min"],
                                ub=param_input["device"]["custom_device_exchange"][i]["device_max"],
                                name=f"ced_install{i}") for i in range(num_custom_exchange_device)]    # 设备装机容量
        standard_ced = [[m.addVar(vtype="C", lb=0,
                                  name=f"standard_ced{i}{t}") for t in range(period)] for i in range(num_custom_exchange_device)]   # 设备运行中间变量
        ced_energy_in = [[[m.addVar(vtype="C", lb=0,
                                    name=f"ced_energy_in{i}{j}{t}") for t in range(period)] for j in range(energy_type_num)] for i in range(num_custom_exchange_device)]  # 设备i 的能量种类j 在t时刻的输入
        ced_energy_out = [[[m.addVar(vtype="C", lb=0,
                                     name=f"ced_energy_out{i}{j}{t}") for t in range(period)] for j in range(energy_type_num)] for i in range(num_custom_exchange_device)]     # 设备i 的能量种类j 在t时刻的输出
        # 自定义储能设备的设备变量
        csd_install = [m.addVar(vtype="C", lb=param_input["device"]["custom_device_storage"][i]["device_min"],
                                ub=param_input["device"]["custom_device_storage"][i]["device_max"],
                                name=f"csd_install{i}") for i in range(num_custom_exchange_device)]  # 设备装机容量
        csd_sto = [[m.addVar(vtype="C", lb=0,
                             name=f"csd_sto{i}{t}") for t in range(period)] for i in range(num_custom_storage_device)]
        csd_energy_in = [[[m.addVar(vtype="C", lb=0,
                                    name=f"csd_energy_in{i}{j}{t}") for t in range(period)] for j in range(energy_type_num)] for i in range(num_custom_storage_device)]
        csd_energy_out = [[[m.addVar(vtype="C", lb=0,
                                     name=f"csd_energy_out{i}{j}{t}") for t in range(period)] for j in range(energy_type_num)] for i in range(num_custom_storage_device)]
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
            # 热总线约束
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
            m.addCons(g_demand[i] == g_tube[i])  # 区分能灌热的和不能灌热的
            # 冷总线约束
            m.addCons(
                q_sol[i] + q_demand[i] + q_ct_in[i]
                + quicksum([ced_energy_in[device_index][2][i] for device_index in range(num_custom_exchange_device)])
                + quicksum([csd_energy_in[device_index][2][i] for device_index in range(num_custom_storage_device)])
                == q_pur[i] + q_ct_out[i] + q_hp[i] + q_ac[i] + q_ghp[i] + q_whp[i] + q_abc[i]
                + quicksum([ced_energy_out[device_index][2][i] for device_index in range(num_custom_exchange_device)])
                + quicksum([csd_energy_out[device_index][2][i] for device_index in range(num_custom_storage_device)])
            )
            # 高温120度蒸气约束
            m.addCons(
                steam120_sol[i] + steam120_demand[i] + m_co180_in[i] + m_steam120_sto_in[i]
                + quicksum([ced_energy_in[device_index][4][i] for device_index in range(num_custom_exchange_device)])
                + quicksum([csd_energy_in[device_index][4][i] for device_index in range(num_custom_storage_device)])
                == steam120_pur[i] + m_hp120[i] + m_steam120_sto_out[i]
                + quicksum([ced_energy_out[device_index][4][i] for device_index in range(num_custom_exchange_device)])
                + quicksum([csd_energy_out[device_index][4][i] for device_index in range(num_custom_storage_device)])
            )
            # 高温180度蒸气约束
            m.addCons(
                steam180_sol[i] + steam180_demand[i] + m_steam180_sto_in[i]
                + quicksum([ced_energy_in[device_index][5][i] for device_index in range(num_custom_exchange_device)])
                + quicksum([csd_energy_in[device_index][5][i] for device_index in range(num_custom_storage_device)])
                == steam180_pur[i] + m_co180_out[i] + m_steam180_sto_out[i]
                + quicksum([ced_energy_out[device_index][5][i] for device_index in range(num_custom_exchange_device)])
                + quicksum([csd_energy_out[device_index][5][i] for device_index in range(num_custom_storage_device)])
            )
        for i in range(period - 1):
            # 氢气约束
            m.addCons(h_sto[i + 1] - h_sto[i] == h_pur[i] + h_el[i] - h_sol[i] - h_demand[i] - h_fc[i]
                      + quicksum([ced_energy_out[device_index][3][i] for device_index in range(num_custom_exchange_device)])
                      + quicksum([csd_energy_out[device_index][3][i] for device_index in range(num_custom_storage_device)])
                      - quicksum([ced_energy_in[device_index][3][i] for device_index in range(num_custom_exchange_device)])
                      - quicksum([csd_energy_in[device_index][5][i] for device_index in range(num_custom_storage_device)]))
        # 初始状态和末状态平衡
        m.addCons(h_sto[0] - h_sto[-1] == h_pur[-1] + h_el[-1] - h_fc[-1] - h_demand[-1]
                  + quicksum([ced_energy_out[device_index][3][-1] for device_index in range(num_custom_exchange_device)])
                  + quicksum([csd_energy_out[device_index][3][-1] for device_index in range(num_custom_storage_device)])
                  - quicksum([ced_energy_in[device_index][3][-1] for device_index in range(num_custom_exchange_device)])
                  - quicksum([csd_energy_in[device_index][5][-1] for device_index in range(num_custom_storage_device)]))
        #-----------------------------整体性约束-----------------------------#
        if param_input["device"]["ghp"]["balance_flag"] == 1:  # 如果需要考虑全年热平衡
            m.addCons(quicksum([g_ghp[i] - p_ghp[i] - q_ghp[i] - p_ghpc[i] - g_ghp_gr[i] for i in range(period)]) == 0)
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
            m.addCons(steam120_pur[i] <= M * param_input["trading"]["steam_buy"][1]["enable"])  # 是否允许买120度蒸汽
            m.addCons(steam120_sol[i] <= M * param_input["trading"]["steam_sell"][1]["enable"])  # 是否允许卖120度蒸汽
            m.addCons(steam180_pur[i] <= M * param_input["trading"]["steam_buy"][0]["enable"])  # 是否允许买180度蒸汽
            m.addCons(steam180_sol[i] <= M * param_input["trading"]["steam_sell"][0]["enable"])  # 是否允许卖180度蒸汽
            m.addCons(hotwater_pur[i] <= M * param_input["trading"]["hotwater_buy_enable"])  # 是否允许买热水
            m.addCons(hotwater_sol[i] <= M * param_input["trading"]["hotwater_sell_enable"])  # 是否允许卖热水
        #-----------------------------基础设备库的设备约束-----------------------------#
        # TODO: 检查设备建模正确性
        for i in range(period):
        #-----co----#
            m.addCons(p_co[i] == k_co * h_el[i])  # 压缩氢耗电量约束
            m.addCons(p_co[i] <= p_co_max + param_input["device"]["co"]["power_already"])  # 压缩机运行功率上限
        # ----fc----#
            m.addCons(g_fc[i] <= fc_theta_ex * k_fc_g * h_fc[i])  # 氢转热约束，允许弃热
            m.addCons(p_fc[i] == k_fc_p * h_fc[i])  # 氢转电约束
            m.addCons(p_fc[i] <= p_fc_max + param_input["device"]["fc"]["power_already"])  # 运行功率 <= 规划功率（运行最大功率）+ 已有装机
        #----el----#
            m.addCons(h_el[i] <= el_theta_ex * k_el_h * p_el[i])  # 电转氢约束
            m.addCons(g_el[i] <= k_el_g * p_el[i])
            m.addCons(p_el[i] <= p_el_max + p_el_already)  # 运行功率 <= 规划功率（运行最大功率）
            m.addCons(h_el[i] <= hst + param_input["device"]["hst"]["sto_already"])  # 产生的氢气质量要小于储氢罐最大储氢容量
        #----hst----#
            m.addCons(h_sto[i] <= hst + param_input["device"]["hst"]["sto_already"])
        # TODO: 重点检查储能设备，如下方更改是不是更符合艳玲师姐构建输入的意图，请与师姐确认
        # PS: 通过查看 git 历史可以查看代码的变更记录
        #----ht----#
            m.addCons(g_ht[i] <= (m_ht + param_input["device"]["ht"]["water_already"]) * k_ht_sto_max)  # 储热罐存储热量上限
            m.addCons(g_ht[i] >= (m_ht + param_input["device"]["ht"]["water_already"]) * k_ht_sto_min)  # 储热罐存储热量下限
            m.addCons(g_ht_in[i] <= (m_ht + param_input["device"]["ht"]["water_already"]) * k_ht_power_max)
            m.addCons(g_ht_in[i] >= (m_ht + param_input["device"]["ht"]["water_already"]) * k_ht_power_min)
            m.addCons(g_ht_out[i] <= (m_ht + param_input["device"]["ht"]["water_already"]) * k_ht_power_max)
            m.addCons(g_ht_out[i] >= (m_ht + param_input["device"]["ht"]["water_already"]) * k_ht_power_min)
        for i in range(period - 1):
            m.addCons(g_ht[i + 1] - g_ht[i] == g_ht_in[i] - g_ht_out[i] - loss_ht * g_ht[i])  # 储热罐存储动态变化
        m.addCons(g_ht[0] - g_ht[-1] == g_ht_in[-1] - g_ht_out[-1] - loss_ht * g_ht[-1])
        #----ct----#
        for i in range(period):
            m.addCons(q_ct[i] <= (m_ct + param_input["device"]["ct"]["water_already"]) * k_ct_sto_max)  # 储冷罐存储冷量上限
            m.addCons(q_ct[i] >= (m_ct + param_input["device"]["ct"]["water_already"]) * k_ct_sto_min)  # 储冷罐存储冷量下限
            m.addCons(q_ct_in[i] <= q_ct[i] * k_ct_power_max)
            m.addCons(q_ct_in[i] >= q_ct[i] * k_ct_power_min)
            m.addCons(q_ct_out[i] <= q_ct[i] * k_ct_power_max)
            m.addCons(q_ct_out[i] >= q_ct[i] * k_ct_power_min)
        for i in range(period - 1):
            m.addCons(q_ct[i+1] - q_ct[i] == q_ct_in[i] - q_ct_out[i] - loss_ct * q_ct[i])  # 储冷罐存储动态变化
        m.addCons(q_ct[0] - q_ct[-1] == q_ct_in[-1] - q_ct_out[-1] - loss_ct * q_ct[-1])
        # ----bat----#
        for i in range(period):
            m.addCons(p_bat_sto[i] <= (p_bat_max + param_input["device"]["bat"]["power_already"]) * k_bat_sto_max)  # 电池上限
            m.addCons(p_bat_sto[i] >= (p_bat_max + param_input["device"]["bat"]["power_already"]) * k_bat_sto_min)  # 电池下限
            m.addCons(p_bat_in[i] <= p_bat_sto[i] * k_bat_power_max)
            m.addCons(p_bat_in[i] >= p_bat_sto[i] * k_bat_power_min)
            m.addCons(p_bat_out[i] <= p_bat_sto[i] * k_bat_power_max)
            m.addCons(p_bat_out[i] >= p_bat_sto[i] * k_bat_power_min)
        for i in range(period - 1):
            m.addCons(p_bat_sto[i+1] - p_bat_sto[i] == p_bat_in[i] - q_ct_out[i] - loss_bat * p_bat_sto[i])  # 电池存储动态变化
        m.addCons(p_bat_sto[0] - p_bat_sto[-1] == p_bat_in[-1] - q_ct_out[-1] - loss_bat * p_bat_sto[-1])
        # ----steam_storage----#
        for i in range(period):
            m.addCons(
                m_steam120_sto[i] <= (m_steam120_sto_max + param_input["device"]["steam_storage"]["water_already"])
                * k_steam_sto_max)
            m.addCons(
                m_steam120_sto[i] >= (m_steam120_sto_max + param_input["device"]["steam_storage"]["water_already"])
                * k_steam_sto_min)
            m.addCons(
                m_steam180_sto[i] <= (m_steam180_sto_max + param_input["device"]["steam_storage"]["water_already"])
                * k_steam_sto_max)
            m.addCons(
                m_steam180_sto[i] >= (m_steam180_sto_max + param_input["device"]["steam_storage"]["water_already"])
                * k_steam_sto_min)
            m.addCons(m_steam120_sto_in[i] <= m_steam120_sto[i] * k_steam_power_max)
            m.addCons(m_steam120_sto_in[i] >= m_steam120_sto[i] * k_steam_power_min)
            m.addCons(m_steam120_sto_out[i] <= m_steam120_sto[i] * k_steam_power_max)
            m.addCons(m_steam120_sto_out[i] >= m_steam120_sto[i] * k_steam_power_min)
            m.addCons(m_steam180_sto_in[i] <= m_steam180_sto[i] * k_steam_power_max)
            m.addCons(m_steam180_sto_in[i] >= m_steam180_sto[i] * k_steam_power_min)
            m.addCons(m_steam180_sto_out[i] <= m_steam180_sto[i] * k_steam_power_max)
            m.addCons(m_steam180_sto_out[i] >= m_steam180_sto[i] * k_steam_power_min)
        for i in range(period - 1):
            m.addCons(m_steam120_sto[i+1] - m_steam120_sto[i] == m_steam120_sto_in[i] - m_steam120_sto_out[i]
                      - loss_steam_sto * m_steam120_sto[i])
            m.addCons(m_steam180_sto[i+1] - m_steam180_sto[i] == m_steam180_sto_in[i] - m_steam180_sto_out[i]
                      - loss_steam_sto * m_steam180_sto[i])
        m.addCons(m_steam120_sto[0] - m_steam120_sto[-1] == m_steam120_sto_in[-1] - m_steam120_sto_out[-1]
                  - loss_steam_sto * m_steam120_sto[-1])
        m.addCons(m_steam180_sto[0] - m_steam180_sto[-1] == m_steam180_sto_in[-1] - m_steam180_sto_out[-1]
                  - loss_steam_sto * m_steam180_sto[-1])

        for i in range(period):
        # ---pv----#
            m.addCons(p_pv[i] <= (p_pv_max + param_input["device"]["pv"]["power_already"]) * pv_data[i])  # 允许丢弃可再生能源
        # ----sc----#
            m.addCons(g_sc[i] <= k_sc * sc_theta_ex * (s_sc + param_input["device"]["sc"]["area_already"]) * sc_data[i])  # 允许丢弃可再生能源
        # ----wd----#
            m.addCons(p_wd[i] <= (num_wd + param_input["device"]["wd"]["number_already"]) * wd_data[i] * capacity_wd)  # 允许丢弃可再生能源
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
            m.addCons(p_hp[i] <= (p_hp_max + param_input["device"]["hp"]["power_already"]))  # 热泵供热运行功率 <= 规划功率（运行最大功率）
            m.addCons(p_hpc[i] * k_hp_q == q_hp[i])  # 电转冷约束
            m.addCons(p_hpc[i] <= (p_hp_max + param_input["device"]["hp"]["power_already"]))  # 热泵供冷运行功率 <= 规划功率（运行最大功率）
            m.addCons(p_hp[i] + p_hpc[i] <= (p_hp_max + param_input["device"]["hp"]["power_already"]))
        # ---ghp----#
            m.addCons(p_ghp[i] * k_ghp_g == g_ghp[i])  # 地源热泵电转热约束
            m.addCons(p_ghp[i] <= (p_ghp_max + param_input["device"]["ghp"]["power_already"]))  # 热泵供热运行功率 <= 规划功率（运行最大功率）
            m.addCons(p_ghpc[i] * k_ghp_q == q_ghp[i])  # 地源热泵电转冷约束
            m.addCons(p_ghpc[i] <= (p_ghp_max + param_input["device"]["ghp"]["power_already"]))  # 热泵供冷运行功率 <= 规划功率（运行最大功率）
            m.addCons(p_ghp_deep[i] * k_ghp_deep_g == g_ghp_deep[i])  # 地源热泵电转热约束
            m.addCons(p_ghp_deep[i] <= (p_ghp_deep_max + param_input["device"]["ghp_deep"]["power_already"]))  # 热泵供热运行功率 <= 规划功率（运行最大功率）
        #----gtw----#
        # TODO: 我觉得没问题，存疑点在哪儿？
            m.addCons(num_gtw * p_gtw >= g_ghp[i] - p_ghp[i])  # 井和热泵有关联，制热量-电功率=取热量
            m.addCons(num_gtw * p_gtw >= q_ghp[i] + p_ghpc[i])  # 井和热泵有关联，制冷量+电功率=灌热量
            m.addCons(num_gtw2500 * p_gtw2500 >= g_ghp_deep[i] - p_ghp_deep[i])
        # ---hp120----#
            m.addCons(cop_hp120 * p_hp120[i] == m_hp120[i] * 750) # 750是热量和蒸汽量换算系数
            m.addCons((cop_hp120 - 1) * p_hp120[i] == g_hp120_in[i])
            m.addCons(p_hp120[i] <= (p_hp120_max + param_input["device"]["hp120"]["power_already"]))
        # ---co180----#
            m.addCons(m_co180_out[i] == m_co180_in[i] * 1.1)
            m.addCons(m_co180_in[i] * k_co180 == p_co180[i])
            m.addCons(p_co180[i] <= (p_co180_max + param_input["device"]["co180"]["power_already"]))
        # ---whp----#
        # TODO: 这个是真建模有问题，和艳玲师姐确认水源热泵（余热热泵）是否可以供冷，热源信息如何处理
            m.addCons(p_whp[i] * cop_whpg == g_whp[i])
            m.addCons(p_whpc[i] * cop_whpq == q_whp[i])
            m.addCons(g_whp[i] - p_whp[i] <= heat_resource[i])
            # TODO: 供冷处理
            m.addCons(p_whp[i] + p_whpc[i]<= (p_whp_max + param_input["device"]["whp"]["power_already"]))
        #-----------------------------用户自定义的设备约束-----------------------------#
        #---自定义能量交换设备---#
        for t in range(period):
            for i in range(num_custom_exchange_device):
                for j in range(energy_type_num):
                    m.addCons(ced_energy_in[i][j][t] * cop_in2standerd_ced[i][j] == standard_ced[i][j][t])
                    m.addCons(ced_energy_out[i][j][t] * cop_standerd2out_ced[i][j] == standard_ced[i][j][t])
            m.addCons(standard_ced[i][t] <= ced_install[i] + param_input["device"]["custom_device_exchange"][i]["device_already"])
        #---自定义储能设备的约束--#       # t+1状态 - t状态 = 输入 - 输出
        for i in range(num_custom_storage_device):
            for j in range(energy_type_num):
                for t in range(period - 1):
                    m.addCons(csd_sto[i][j][t+1] - csd_sto[i][j][t] == csd_energy_in[i][j][t] - ced_energy_out[i][j][t])
                    m.addCons(
                        csd_sto[i][j][t] <= (ced_install[i] + param_input["device"]["custom_device_storage"][i]["device_already"])
                                             * k_install2sto_max_csd)
                    m.addCons(
                        csd_sto[i][j][t] >= (ced_install[i] + param_input["device"]["custom_device_storage"][i]["device_already"])
                                             * k_install2sto_min_csd)
                    m.addCons(ced_energy_in[i][j][t] <= csd_sto[i][j][t] * k_sto2io_max_csd)
                    m.addCons(ced_energy_out[i][j][t] <= csd_sto[i][j][t] * k_sto2io_max_csd)
                    m.addCons(ced_energy_in[i][j][t] >= csd_sto[i][j][t] * k_sto2io_min_csd)
                    m.addCons(ced_energy_out[i][j][t] >= csd_sto[i][j][t] * k_sto2io_min_csd)
                m.addCons(csd_sto[i][j][0] - csd_sto[i][j][-1] == csd_energy_in[i][j][-1] - ced_energy_out[i][j][-1])
        #-----------------------------安装面积等约束-----------------------------#
        s_outside = param_input["base"]["area_outside"]
        s_roof = param_input["base"]["power_pv_house_top"]
        m.addCons(k_s_pv * p_pv_max + k_s_sc * s_sc + k_s_wd * num_wd <= s_outside + s_roof)
        m.addCons(k_s_wd * num_wd <= s_outside)
        #-----------------------------运行费用约束-----------------------------#
        m.addCons(op_sum == quicksum([p_pur[i] * lambda_ele_in[i] for i in range(period)])  # 买电花费
                  + lambda_h * quicksum([h_pur[i] for i in range(period)])  # 买氢气花费
                  + gas_price * quicksum([gas_pur[i] for i in range(period)])  # 买天然气花费
                  + lambda_steam120_in * quicksum([steam120_pur[i] for i in range(period)])  # 买120steam花费
                  + lambda_steam180_in * quicksum([steam180_pur[i] for i in range(period)])  # 买180steam花费
                  - quicksum(p_sol[i] * lambda_ele_out for i in range(period))
                  - quicksum(g_sol[i] * lambda_g_out for i in range(period))
                  - quicksum(h_sol[i] * lambda_h_out for i in range(period))
                  - quicksum(steam120_sol[i] * lambda_steam120_out for i in range(period))
                  - quicksum(steam180_sol[i] * lambda_steam180_out for i in range(period))
                  )
        m.addCons(op_sum_pure == quicksum([p_pur[i] * lambda_ele_in[i] for i in range(period)])  # 买电花费
                  + lambda_h * quicksum([h_pur[i] for i in range(period)])  # 买氢气花费
                  + gas_price * quicksum([gas_pur[i] for i in range(period)])  # 买天然气花费
                  + lambda_steam120_in * quicksum([steam120_pur[i] for i in range(period)])  # 买天然气花费
                  + lambda_steam180_in * quicksum([steam180_pur[i] for i in range(period)])  # 买天然气花费
                  )  # 买自定义能量流花费

        m.addCons(op_sum <= input_json['price']['op_max'][1 - isloate[1]])  #运行费用上限（在允许卖电和不允许卖电模式下的运行费用上限不同）
        #-----------------------------碳减排的约束-----------------------------#
        m.addCons(quicksum(p_pur) <= (1 - cer) * (
                    sum(ele_load) + sum(g_demand) / k_eb + sum(q_demand) / k_ghp_q))  # 碳减排约束，买电量不能超过碳排放,即1-碳减排
        m.addCons(ce_h == quicksum(p_pur) * alpha_e)
        #-----------------------------规划设备花费约束-----------------------------#
        m.addCons(capex_sum == (p_pv_max * cost_pv + s_sc * cost_sc + num_wd * cost_wd
                                + p_hp120_max * cost_hp120 + p_co180_max * cost_co180 + cost_bat * p_bat_max
                                + cost_steam_storage * (m_steam120_sto_max + m_steam180_sto_max)
                                + p_ghp_max * cost_ghp + p_ghp_deep_max * cost_ghp_deep + cost_gtw * num_gtw
                                + cost_gtw2500 * num_gtw2500 + cost_eb * p_eb_max + cost_abc * g_abc_max
                                + cost_ht * m_ht + cost_ct * m_ct + cost_hst * hst + cost_ac * p_ac_max
                                + cost_hp * p_hp_max + cost_fc * p_fc_max + cost_el * p_el_max + cost_co * p_co_max
                                + p_whp_max * cost_whp) * (1 + input_json["price"]["PSE"])  # 基本设备库设备的规划成本
                                + quicksum([cost_ced[i] * ced_install[i] for i in range(num_custom_exchange_device)]) * (1 + input_json["price"]["PSE"])
                                + quicksum([cost_csd[i] * csd_install[i] for i in range(num_custom_storage_device)]) * (1 + input_json["price"]["PSE"])
                )  # 自定义设备规划成本

        m.addCons(capex_sum <= input_json['price']['capex_max'][1 - isloate[0]])  # 总规划成本上限（在允许买电和不允许买电模式下的运行费用上限不同）

        m.addCons(capex_crf == crf_pv * p_pv_max * cost_pv + crf_wd * num_wd * cost_wd + crf_sc * s_sc * cost_sc
                                + crf_hst * hst * cost_hst + crf_ht * cost_ht * m_ht + crf_ct * cost_ct * m_ct
                                + crf_hp * cost_hp * p_hp_max + crf_bat * cost_bat * p_bat_max
                                + crf_steam_storage * cost_steam_storage * (m_steam120_sto_max + m_steam180_sto_max)
                                + crf_gtw * cost_gtw * num_gtw + crf_gtw2500 * cost_gtw2500 * num_gtw2500
                                + crf_hp120 * p_hp120_max * cost_hp120 + crf_co180 * p_co180_max * cost_co180
                                + crf_ghp * cost_ghp * p_ghp_max + crf_ghp_deep * cost_ghp_deep * p_ghp_deep_max
                                + crf_eb * cost_eb * p_eb_max + crf_ac * cost_ac * p_ac_max + crf_fc * p_fc_max * cost_fc
                                + crf_el * p_el_max * cost_el + crf_co * p_co_max * cost_co + crf_abc * g_abc_max * cost_abc
                                + crf_whp * p_whp_max * cost_whp
                                + quicksum([cost_ced[i] * ced_install[i] * crf_ced[i] for i in range(num_custom_exchange_device)])
                                + quicksum([cost_csd[i] * csd_install[i] * crf_csd[i] for i in range(num_custom_storage_device)])
                  )
        #-----------------------------目标函数-----------------------------#
        m.setObjective(input_json['calc_mode']['obj']['capex_sum'] * capex_sum
                    + input_json['calc_mode']['obj']['capex_crf'] * capex_crf
                    + input_json['calc_mode']['obj']['opex'] * op_sum, "minimize")

        #-----------------------------gurobi参数设置-----------------------------#
        # m.params.MIPGap = 0.01
        m.setRealParam("limits/gap", 0.1)  # 设置优化求解的最大间隙

        #---------------------------gurobi求解-----------------------------#
        m.optimize()
        sol = m.getBestSol()
        cost = m.getObjVal()
        print("Optimal value:", cost)
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
        revenue = 0
        revenue_ele = sum(ele_load[i] * lambda_ele_in[i] for i in range(period))
        revenue += revenue_ele

        if input_json["revenue"]["if_central_heating"] == 1:
            revenue_heat = input_json["price"]["heat_price"] * input_json["load"]["g_load_area"]
        else:
            revenue_heat = sum([g_demand[i] / k_eb * lambda_ele_in[i] for i in range(period)])
        revenue += revenue_heat

        if input_json["revenue"]["if_central_cooling"] == 1:
            revenue_cold = input_json["price"]["cold_price"] * input_json["load"]["q_load_area"]
        else:
            revenue_cold = sum([q_demand[i] / k_ac * lambda_ele_in[i] for i in range(period)])
        revenue += revenue_cold

        revenue_steam120 = 0
        revenue_steam180 = 0
        if input_json["revenue"]["if_central_steam120"] == 1:
            revenue_steam120 = input_json["price"]["steam120_price"] * (sum([steam120_demand[i] for i in range(period)]))
            revenue += revenue_steam120
        if input_json["revenue"]["if_central_steam180"] == 1:
            revenue_steam180 = input_json["price"]["steam180_price"] * (sum([steam180_demand[i] for i in range(period)]))
            revenue += revenue_steam180

        all_cap = m.getVal(capex_sum) * (1 + input_json["other_investment"])
        all_crf = m.getVal(capex_crf) + m.getVal(capex_sum) * input_json["other_investment"] / 20
        receive_year = all_cap / (revenue - m.getVal(op_sum) + 0.000001)
        cost_year = all_crf + m.getVal(op_sum_pure)
        whole_energy = (sum(ele_load) + sum(g_demand) + sum(q_demand) + sum(steam120_demand) * 750 + sum(
            steam180_demand) * 770 + sum(h_demand) * 37 + sum(m.getVal(p_sol[i]) for i in range(period)) + sum(
            m.getVal(g_sol[i]) for i in range(period)) + sum(m.getVal(steam120_sol[i]) for i in range(period)) + sum(
            m.getVal(steam180_sol[i]) for i in range(period)))
        cost_per_energy = cost_year / whole_energy

        # ---------------------------纯电系统信息-----------------------------#
        ele_cap_ele = 0
        ele_cap_g = max(g_demand) / k_eb * cost_eb
        ele_cap_steam120 = max(steam120_demand) / k_eb * cost_eb
        ele_cap_steam180 = max(steam180_demand) / k_eb * cost_eb
        ele_cap_q = max(q_demand) / k_ac * cost_ac
        ele_cap = (ele_cap_ele + ele_cap_g + ele_cap_q + ele_cap_steam120 + ele_cap_steam180) * (
                    1 + input_json["other_investment"])
        ele_op_ele = sum([ele_load[i] * lambda_ele_in[i] for i in range(period)])
        ele_op_g = sum([g_demand[i] / k_eb * lambda_ele_in[i] for i in range(period)])
        ele_op_steam120 = sum([steam120_demand[i] * 750 / k_eb * lambda_ele_in[i] for i in range(period)])
        ele_op_steam180 = sum([steam120_demand[i] * 750 / k_eb * lambda_ele_in[i] for i in range(period)])
        ele_op_q = sum([q_demand[i] / k_ac * lambda_ele_in[i] for i in range(period)])
        ele_op = ele_op_ele + ele_op_g + ele_op_q + ele_op_steam120 + ele_op_steam180
        ele_cost_year = ele_cap / 10 + ele_op
        ele_cost_per_energy = ele_cost_year / whole_energy
        ele_co2 = (sum([ele_load[i] for i in range(period)]) + sum([g_demand[i] / k_eb for i in range(period)]) + sum(
            [q_demand[i] / k_ac for i in range(period)])) * 0.581

        # --------------------------电气系统信息-----------------------------#
        gas_cap_ele = 0
        gas_cap_g = max(g_demand) / 0.9 * 700
        gas_cap_steam120 = max(steam120_demand) / 0.9 * 700
        gas_cap_steam180 = max(steam180_demand) / 0.9 * 700
        gas_cap_q = max(q_demand) / k_ac * cost_ac
        gas_cap = (gas_cap_ele + gas_cap_g + gas_cap_q + gas_cap_steam120 + gas_cap_steam180) * (
                    1 + input_json["other_investment"])
        gas_op_ele = sum([ele_load[i] * lambda_ele_in[i] for i in range(period)])
        gas_op_g = sum([g_demand[i] * 0.3525 for i in range(period)])
        gas_op_steam120 = sum([steam120_demand[i] * 750 * 0.3525 for i in range(period)])
        gas_op_steam180 = sum([steam180_demand[i] * 750 * 0.3525 for i in range(period)])
        gas_op_q = sum([q_demand[i] / k_ac * lambda_ele_in[i] for i in range(period)])
        gas_op = gas_op_ele + gas_op_g + gas_op_q + gas_op_steam120 + gas_op_steam180
        gas_cost_year = gas_cap / 10 + gas_op
        gas_cost_per_energy = gas_cost_year / whole_energy
        gas_co2 = (sum([ele_load[i] for i in range(period)]) + sum(
            [q_demand[i] / k_ac for i in range(period)])) * 0.581 + sum([g_demand[i] for i in range(period)]) * 0.2142

        #---------------------------文档生成需要的规划结果---------------------------------#
        for i in range(custom_storge_device_num[0]):
            output_json_dict["cost_storage_ele" + str(i)] = cost_storage_ele[i] * m.getVal(s_i_ele_plan[i])
            output_json_dict["s_i_ele_plan" + str(i)] = m.getVal(s_i_ele_plan[i])

        # output_json = demjson.encode(output_json_dict)
        ele_sum_ele_only = np.array(ele_load) + np.array(g_demand) / k_eb + np.array(q_demand) / k_hp_q
        opex_ele_only = sum(np.array(lambda_ele_in) * ele_sum_ele_only)
        co2_ele_only = sum(ele_sum_ele_only) * alpha_e
        result = {
            "sys_performance": {

                'all_revenue': revenue,
                'fixed_revenue': fixed_revenue,
                'p_revenue': p_revenue,
                'p_sol_revenue': p_sol_revenue,
                'revenue_ele': revenue_ele,
                'revenue_heat': revenue_heat,
                'revenue_cold': revenue_cold,
                'revenue_steam120': format(revenue_steam120 / 10000, '.2f'), # 万元
                'revenue_steam180': revenue_steam180,
                'revenue_sol_ele': revenue_sol_ele,
                'revenue_sol_heat': revenue_sol_heat,



            },
            "device_result": {
                "device_capacity": {
                    'p_co_installed': m.getVal(p_co_max),
                    'p_fc_installed': m.getVal(p_fc_max),
                    'p_el_installed': m.getVal(p_el_max),
                    'h_hst_installed': m.getVal(hst),
                    'm_ht_installed': m.getVal(m_ht),
                    'm_ct_installed': m.getVal(m_ct),
                    # 'bat'
                    # 'steam_storage'
                    'p_pv_installed': m.getVal(p_pv_max),
                    's_sc_installed': m.getVal(s_sc),
                    'num_wd_installed': m.getVal(num_wd),
                    'p_eb_installed': m.getVal(p_eb_max),
                    'p_ac_installed': m.getVal(p_ac_max),
                    'p_hp_installed': m.getVal(p_hp_max),
                    'p_ghp_installed': m.getVal(p_ghp_max),
                    'p_ghp_deep_installed': m.getVal(p_ghp_deep_max),
                    'num_gtw_installed': m.getVal(num_gtw),
                    'num_gtw2500_installed': m.getVal(num_gtw2500),
                    'p_hp120_installed': m.getVal(p_hp120_max),
                    'p_co180_installed': m.getVal(p_co180_max),
                    'p_whp_installed': m.getVal(p_whp_max),
                },
                "device_capex": {
                    'capex_co': cost_co * m.getVal(p_co_max),
                    'capex_fc': cost_fc * m.getVal(p_fc_max),
                    'capex_el': cost_el * m.getVal(p_el_max),
                    'capex_hst': cost_hst * m.getVal(hst),
                    'capex_ht': cost_ht * m.getVal(m_ht),
                    'capex_ct': cost_ct * m.getVal(m_ct),
                    # bat
                    # steam_storage
                    'capex_pv': cost_pv * m.getVal(p_pv_max),
                    'capex_sc': cost_sc * m.getVal(s_sc),
                    'capex_wd': cost_wd * m.getVal(num_wd),
                    'capex_eb': cost_eb * m.getVal(p_eb_max),
                    'capex_ac': cost_ac * m.getVal(p_ac_max),
                    'capex_hp': cost_hp * m.getVal(p_hp_max),
                    'capex_ghp': cost_ghp * m.getVal(p_ghp_max),
                    'capex_ghp_deep': cost_ghp_deep * m.getVal(p_ghp_deep_max),
                    'capex_gtw': cost_gtw * m.getVal(num_gtw),
                    'capex_gtw2500': cost_gtw * m.getVal(num_gtw2500),
                    'capex_hp120': cost_hp120 * m.getVal(p_hp120_max),
                    'capex_co180': cost_co180 * m.getVal(p_co180_max),
                    'capex_whp': cost_whp * m.getVal(p_whp_max),
                },
            },
            "scheduling_result": {
                # 能量流买卖
                'p_pur': [m.getVal(p_pur[i]) for i in range(period)],
                'p_sol': [m.getVal(p_sol[i]) for i in range(period)],
                'h_pur': [m.getVal(h_pur[i]) for i in range(period)],
                'gas_pur': [m.getVal(gas_pur[i]) for i in range(period)],
                'steam120_pur': [m.getVal(steam120_pur[i]) for i in range(period)],
                'steam120_sol': [m.getVal(steam120_sol[i]) for i in range(period)],
                'steam180_pur': [m.getVal(steam180_pur[i]) for i in range(period)],
                'steam180_sol': [m.getVal(steam180_sol[i]) for i in range(period)],
                'y_pur': [[m.getVal(y_pur[j][i]) for i in range(period)] for j in range(custom_energy_num)],  # 自定义能量流
                # co
                'p_co': [m.getVal(p_co[i]) for i in range(period)],
                # fc
                'p_fc': [m.getVal(p_fc[i]) for i in range(period)],
                'g_fc': [m.getVal(g_fc[i]) for i in range(period)],
                'h_fc': [m.getVal(h_fc[i]) for i in range(period)],
                # el
                'p_el': [m.getVal(p_el[i]) for i in range(period)],
                'h_el': [m.getVal(h_el[i]) for i in range(period)],
                # hst
                'h_sto': [m.getVal(h_sto[i]) for i in range(period)],
                # ht
                'g_ht': [m.getVal(g_ht[i]) for i in range(period)],
                'g_ht_in': [m.getVal(g_ht_in[i]) for i in range(period)],
                'g_ht_out': [m.getVal(g_ht_out[i]) for i in range(period)],
                # ct
                'q_ct': [m.getVal(q_ct[i]) for i in range(period)],
                'q_ct_in': [m.getVal(q_ct_in[i]) for i in range(period)],
                'q_ct_out': [m.getVal(q_ct_out[i]) for i in range(period)],
                # bat

                # steam_storage
                # pv
                'p_solar_pv': [m.getVal(eta_pv * s_pv) * r_solar[i] for i in range(period)],  # pv吸收太阳能理论发电量
                'p_pv': [m.getVal(p_pv[i]) for i in range(period)],  # 实际pv发电量（可能存在弃光）
                # sc
                'g_sc': [m.getVal(g_sc[i]) for i in range(period)],
                # wd
                'p_wind': [m.getVal(p_wd[i]) for i in range(period)],
                # eb
                'p_eb': [m.getVal(p_eb[i]) for i in range(period)],
                'g_eb': [m.getVal(g_eb[i]) for i in range(period)],
                # ac
                'p_ac': [m.getVal(p_ac[i]) for i in range(period)],
                'q_ac': [m.getVal(q_ac[i]) for i in range(period)],
                # hp
                'p_hp': [m.getVal(p_hp[i]) for i in range(period)],
                'g_hp': [m.getVal(g_hp[i]) for i in range(period)],
                'p_hpc': [m.getVal(p_hpc[i]) for i in range(period)],
                'q_hp': [m.getVal(q_hp[i]) for i in range(period)],
                # ghp
                'p_ghp': [m.getVal(p_ghp[i]) for i in range(period)],
                'p_ghpc': [m.getVal(p_ghpc[i]) for i in range(period)],
                'q_ghp': [m.getVal(q_ghp[i]) for i in range(period)],
                'g_ghp': [m.getVal(g_ghp[i]) for i in range(period)],
                'g_ghp_gr': [m.getVal(g_ghp_gr[i]) for i in range(period)],
                # ghp_deep
                'p_ghp_deep': [m.getVal(p_ghp_deep[i]) for i in range(period)],
                'g_ghp_deep': [m.getVal(g_ghp_deep[i]) for i in range(period)],
                # gtw

                # gtw2500

                # hp120
                'p_hp120': [m.getVal(p_hp120[i]) for i in range(period)],
                'm_hp120': [m.getVal(m_hp120[i]) for i in range(period)],
                'g_hp120': [m.getVal(g_hp120[i]) for i in range(period)],
                # co180
                'p_co180': [m.getVal(p_co180[i]) for i in range(period)],
                # whp
                'p_whp': [m.getVal(p_whp[i]) for i in range(period)],
            },
        }
        return result
