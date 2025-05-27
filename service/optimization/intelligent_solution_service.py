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


def support_device(d_cost, d_se):
    """计算配套设备价格函数
    """
    return d_cost * d_se


class ISService:
    def __init__(self):
        pass

    def exec(self, inputBody: OptimizationBody):
        t0 = time.time()
        #------------导入自定义数据------------#

        #------------导入负荷数据------------#
        for i in range(len(inputBody.objective_load)):
            if inputBody.objective_load[i].type == "steam" and inputBody.objective_load[i].temperature == "180":
                steam180_demand = inputBody.objective_load[i].load8760
            elif inputBody.objective_load[i].type == "steam" and inputBody.objective_load[i].temperature == "120":
                steam120_demand = inputBody.objective_load[i].load8760
            elif inputBody.objective_load[i].type == "power":
                ele_load = inputBody.objective_load[i].load8760
            elif inputBody.objective_load[i].type == "heating":
                g_demand = inputBody.objective_load[i].load8760
            elif inputBody.objective_load[i].type == "cooling":
                q_demand = inputBody.objective_load[i].load8760
            elif inputBody.objective_load[i].type == "hydrogen":
                h_demand = inputBody.objective_load[i].load8760
            elif inputBody.objective_load[i].type == "hotwater":
                hotwater_demand = inputBody.objective_load[i].load8760

        r_solar = inputBody.device.pv.pv_data8760  # 光照强度
        wind_power = inputBody.device.wd.wd_data8760  # 风电数据

        #------------导入价格等数据------------#
        alpha_e = 0.5839  # 电网排放因子kg/kWh
        gas_price = 1.2  # 天然气价钱
        lambda_ele_in = inputBody.trading.power_buy_8760_price           # 每个小时的电价
        lambda_ele_out = inputBody.trading.power_sell_price              # 卖电价格
        lambda_g_out = inputBody.trading.heat_sell_price                 # 卖热价格
        lambda_h_out = inputBody.trading.hydrogen_sell_price             # 卖氢价格
        lambda_h = inputBody.trading.hydrogen_buy_price                  # 买氢价格
        cer = inputBody.base.cer                                         # 碳减排率
        lambda_steam120_in = inputBody.trading.steam_buy[1].price        # 120蒸汽购入价格
        lambda_steam120_out = inputBody.trading.steam_sell[1].price      # 120蒸汽出售价格
        lambda_steam180_in = inputBody.trading.steam_buy[0].price        # 180蒸汽购入价格
        lambda_steam180_out = inputBody.trading.steam_sell[0].price      # 180蒸汽出售价格
        c = 4.2 / 3600                                                   # 水的比热容

        # 自定义能量流的价格和碳排

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
        crf_co = crf(inputBody.device.co.crf)
        crf_fc = crf(inputBody.device.fc.crf)
        crf_el = crf(inputBody.device.el.crf)
        crf_hst = crf(inputBody.device.hst.crf)
        crf_ht = crf(inputBody.device.ht.crf)
        crf_ct = crf(inputBody.device.ct.crf)
        crf_bat = crf(inputBody.device.bat.crf)
        crf_steam_storage = crf(inputBody.device.steam_storage.crf)
        crf_pv = crf(inputBody.device.pv.crf)
        crf_sc = crf(inputBody.device.sc.crf)
        crf_wd = crf(inputBody.device.wd.crf)
        crf_eb = crf(inputBody.device.eb.crf)
        crf_ac = crf(inputBody.device.ac.crf)
        crf_hp = crf(inputBody.device.hp.crf)
        crf_ghp = crf(inputBody.device.ghp.crf)
        crf_ghp_deep = crf(inputBody.device.ghp_deep.crf)
        crf_gtw = crf(inputBody.device.gtw.crf)
        crf_gtw2500 = crf(inputBody.device.gtw2500.crf)
        crf_hp120 = crf(inputBody.device.hp120.crf)
        crf_co180 = crf(inputBody.device.co180.crf)
        crf_whp = crf(inputBody.device.whp.crf)

        # --------------单位投资成本数据--------------#
        cost_co = inputBody.device.co.cost + support_device(inputBody.device.co.cost,
                                                            inputBody.device.co.se)
        cost_fc = inputBody.device.fc.cost + support_device(inputBody.device.fc.cost,
                                                            inputBody.device.fc.se)
        cost_el = inputBody.device.el.cost + support_device(inputBody.device.el.cost,
                                                            inputBody.device.el.se)#???
        cost_hst = inputBody.device.hst.cost + support_device(inputBody.device.hst.cost,
                                                              inputBody.device.hst.se)
        cost_ht = inputBody.device.ht.cost + support_device(inputBody.device.ht.cost,
                                                            inputBody.device.ht.se)
        cost_ct = inputBody.device.ct.cost + support_device(inputBody.device.ct.cost,
                                                            inputBody.device.ct.se)
        cost_bat = inputBody.device.bat.cost + support_device(inputBody.device.bat.cost,
                                                              inputBody.device.bat.se)#???
        cost_steam_storage = inputBody.device.steam_storage.cost + support_device(inputBody.device.steam_storage.cost,
                                                                                  inputBody.device.steam_storage.se)#???
        cost_pv = inputBody.device.pv.cost + support_device(inputBody.device.pv.cost,
                                                            inputBody.device.pv.se)#???
        cost_sc = inputBody.device.sc.cost + support_device(inputBody.device.sc.cost,
                                                             inputBody.device.sc.se)#???
        capacity_wd = inputBody.device.wd.capacity_unit
        cost_wd = capacity_wd * inputBody.device.wd.cost + support_device(inputBody.device.wd.cost,
                                                                         inputBody.device.wd.se)#???
        cost_eb = inputBody.device.eb.cost + support_device(inputBody.device.eb.cost,
                                                            inputBody.device.eb.se)
        cost_ac = inputBody.device.ac.cost + support_device(inputBody.device.ac.cost,
                                                            inputBody.device.ac.se)
        cost_hp = inputBody.device.hp.cost + support_device(inputBody.device.hp.cost,
                                                            inputBody.device.hp.se)
        cost_ghp = inputBody.device.ghp.cost + support_device(inputBody.device.ghp.cost,
                                                              inputBody.device.ghp.se)
        cost_ghp_deep = inputBody.device.ghp_deep.cost + support_device(inputBody.device.ghp_deep.cost,
                                                                        inputBody.device.ghp_deep.se)
        cost_gtw = inputBody.device.gtw.cost + support_device(inputBody.device.gtw.cost,
                                                              inputBody.device.gtw.se)
        cost_gtw2500 = inputBody.device.gtw2500.cost + support_device(inputBody.device.gtw2500.cost,
                                                                      inputBody.device.gtw2500.se)
        cost_hp120 = inputBody.device.hp120.cost + support_device(inputBody.device.hp120.cost,
                                                                  inputBody.device.hp120.se)#???
        cost_co180 = inputBody.device.co180.cost + support_device(inputBody.device.co180.cost,
                                                                  inputBody.device.co180.se)#???
        cost_whp = inputBody.device.whp.cost + support_device(inputBody.device.whp.cost,
                                                              inputBody.device.whp.se) #???

        # ---------------效率数据，包括产热、制冷、发电、热转换等--------------#
        # ----co----#
        k_co = inputBody.device.co.beta_co
        # ----fc----#
        eta_ex = 0.95  # fc产的热通过热交换器后的剩余热量系数  # 待匹配
        k_fc_p = inputBody.device.fc.eta_fc_p  # 氢转电系数kg——>kWh
        k_fc_g = inputBody.device.fc.eta_ex_g  # 氢转热系数kg——>kWh
        # ----el----#
        k_el = input_json['device']['el']['beta_el']  #电转氢效率
        # ---hst----#
        # ---ht----#
        # ---ct----#
        # ---bat----#
        # ---steam_storage----#
        # ----pv----#
        eta_pv = input_json['device']['pv']['beta_pv']  #单位面积下光转电效率
        # ----sc----#
        k_sc = inputBody.device.sc.beta_sc
        theta_ex = inputBody.device.sc.theta_ex
        # ----wd----#
        # ----eb----#
        k_eb = inputBody.device.eb.beta_eb
        # ----ac----#
        k_ac = inputBody.device.ac.beta_ac
        # ----hp----#
        k_hp_g = inputBody.device.hp.beta_hpg
        k_hp_q = inputBody.device.hp.beta_hpq
        # ----ghp----#
        k_ghp_g = inputBody.device.ghp.beta_ghpg
        k_ghp_q = inputBody.device.ghp.beta_ghpq
        k_ghp_deep_g = inputBody.device.ghp_deep.beta_ghpg
        # ----gtw----#
        p_gtw = inputBody.device.gtw.beta_gtw
        # ----gtw2500----#
        p_gtw2500 = inputBody.device.gtw2500.beta_gtw
        # ----hp120----#
        cop_hp120 = inputBody.device.hp120.cop
        # ----co180----#
        # ----whp----#
        k_whp = input_json['device']['whp']['beta_whp']  #电转热，以及热转冷的效率

        # ---------------------------用户自定义设备---------------------------#
        # ---------------第i个自定义设备的年化收益率数据---------------#

        # --------------第i个自定义设备的单位投资成本--------------#

        # -----------------------自定义设备的效率数据----------------------#
        # ------(5+custom_energy_num)*(5+custom_energy_num-1)种组合------#

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
        g_tubeTosteam120 = [m.addVar(vtype="C", lb=0, name=f"g_tubeTosteam120{t}") for t in range(period)]
        m_steam120Tosteam180 = [m.addVar(vtype="C", lb=0, name=f"m_steam120Tosteam180{t}") for t in range(period)]
        h_pur = [m.addVar(vtype="C", lb=0, name=f"h_pur{t}") for t in range(period)]  # 买氢hydrogen purchase
        p_pur = [m.addVar(vtype="C", lb=0, name=f"p_pur{t}") for t in range(period)]  # 买电power purchase
        p_sol = [m.addVar(vtype="C", lb=0, name=f"p_sol{t}") for t in range(period)]  # 卖电power sold
        g_sol = [m.addVar(vtype="C", lb=0, name=f"g_sol{t}") for t in range(period)]  # 卖电power sold
        h_sol = [m.addVar(vtype="C", lb=0, name=f"h_sol{t}") for t in range(period)]  # 卖氢hydrogen sold
        gas_pur = [m.addVar(vtype="C", lb=0, name=f"gas_pur{t}") for t in range(period)]  # 买天然气
        steam120_pur = [m.addVar(vtype="C", lb=0, name=f"steam120_pur{t}") for t in range(period)]  # 买steam120
        steam120_sol = [m.addVar(vtype="C", lb=0, name=f"steam120_sol{t}") for t in range(period)]  # 卖steam120
        steam180_pur = [m.addVar(vtype="C", lb=0, name=f"steam180_pur{t}") for t in range(period)]  # 买steam180
        steam180_sol = [m.addVar(vtype="C", lb=0, name=f"steam180_sol{t}") for t in range(period)]  # 卖steam180
        y_pur = [[m.addVar(vtype="C", lb=0, name=f"y_pur{i}{t}") for t in range(period)] for i in
                     range(custom_energy_num)]  # 买天然气  # 涉及自定义能量流

        # 基本设备库中设备变量
        # ----co----#
        p_co_max = m.addVar(vtype="C", lb=0,
                            ub=inputBody.device.co.power_max * inputBody.device.co.power_already,
                            name=f"p_co_max")  # 氢气压缩机投资容量（最大功率）
        p_co = [m.addVar(vtype="C", lb=0, name=f"p_co{t}") for t in range(period)]  # 氢气压缩机工作功率
        # ----fc----#
        z_fc = [m.addVar(lb=0, ub=1, vtype="B", name=f"z_fc{t}") for t in range(period)]
        p_fc_max = m.addVar(vtype="C", lb=0,
                            ub= inputBody.device.fc.power_max * inputBody.device.fc.power_already,
                            name=f"p_fc_max")  # fc的投资容量（最大功率）
        g_fc = [m.addVar(vtype="C", lb=0, name=f"g_fc{t}") for t in range(period)]  # 燃料电池产热量
        p_fc = [m.addVar(vtype="C", lb=0, name=f"p_fc{t}") for t in range(period)]  # 燃料电池产电量
        h_fc = [m.addVar(vtype="C", lb=0, name=f"h_fc{t}") for t in range(period)]  # 燃料电池用氢量
        # ----el----#
        p_el_max = m.addVar(vtype="C", lb=0,
                            ub= inputBody.device.el.nm3_max * inputBody.device.el.nm3_already,
                            name="p_el_max")  # el的投资容量（最大功率）
        h_el = [m.addVar(vtype="C", lb=0, name=f"h_el{t}") for t in range(period)]  # 电解槽产氢量
        p_el = [m.addVar(vtype="C", lb=0, name=f"p_el{t}") for t in range(period)]  # 电解槽功率
        # ----hst----#
        hst = m.addVar(vtype="C", lb=0,
                       ub= inputBody.device.hst.sto_max * inputBody.device.hst.sto_already,
                       name=f"hst")  # 储氢罐规划容量
        h_sto = [m.addVar(vtype="C", lb=0, name=f"h_sto{t}") for t in range(period)]  # 储氢罐t时刻储氢量
        # ----ht----#
        m_ht = m.addVar(vtype="C", lb=0,
                        ub= inputBody.device.ht.water_max * inputBody.device.ht.water_already,
                        name=f"m_ht")  # 储热罐的规划容量
        g_ht_in = [m.addVar(vtype="C", lb=0, name=f"g_ht_in{t}") for t in range(period)]
        g_ht_out = [m.addVar(vtype="C", lb=0, name=f"g_ht_out{t}") for t in range(period)]
        g_ht = [m.addVar(vtype="C", lb=0, name=f"g_ht{t}") for t in range(period)]  # 存储的热量
        # 写完约束之后再看看有没有需要创建的变量
        # ----ct----#
        m_ct = m.addVar(vtype="C", lb=0,
                        ub= inputBody.device.ct.water_max * inputBody.device.ct.water_already,
                        name=f"m_ct")  # 储冷罐的规划容量
        q_ct_in = [m.addVar(vtype="C", lb=0, name=f"q_ct_in{t}") for t in range(period)]
        q_ct_out = [m.addVar(vtype="C", lb=0, name=f"q_ct_out{t}") for t in range(period)]  # 写完约束之后再看看有没有需要创建的变量
        q_ct = [m.addVar(vtype="C", lb=0, name=f"q_ct{t}") for t in range(period)]  # 存储的冷量
        # ----bat----#

        # ----steam_storage----#

        # ----pv----#
        s_pv = m.addVar(vtype="C", lb=0, name=f"s_pv")  # 光伏板投资面积
        p_pv_max = m.addVar(vtype="C", lb=0, name=f"p_pv_max")  # 光伏板投资面积
        p_pv = [m.addVar(vtype="C", lb=0, ub= inputBody.device.pv.power_max * inputBody.device.pv.power_already,
                     name=f"p_pv{t}") for t in range(period)]  # 光伏板发电功率
        # ----sc----#
        s_sc = m.addVar(vtype="C", lb=0,
                        ub=inputBody.device.sc.area_max * inputBody.device.sc.area_already,
                        name=f"s_sc")  # 太阳能集热器投资面积
        g_sc = [m.addVar(vtype="C", lb=0, name=f"g_sc{t}") for t in range(period)]  # 太阳能集热器收集的热量
        # ----wd----#
        num_wd = m.addVar(vtype="INTEGER", lb=0,
                          ub= inputBody.device.wd.number_max * inputBody.device.wd.number_already,
                          name=f"num_wd")  # 风电投资数量
        p_wd = [m.addVar(vtype="C", lb=0, name=f"p_wd{t}") for t in range(period)]  # 风电发电功率
        # ----eb----#
        p_eb_max = m.addVar(vtype="C", lb=0,
                            ub= inputBody.device.eb.power_max * inputBody.device.eb.power_already,
                            name=f"p_eb_max")  # 电锅炉投资容量（最大功率）
        g_eb = [m.addVar(vtype="C", lb=0, name=f"g_eb{t}") for t in range(period)]  # 电锅炉产热
        p_eb = [m.addVar(vtype="C", lb=0, name=f"p_eb{t}") for t in range(period)]  # 电锅炉耗电
        # ----ac----#
        p_ac_max = m.addVar(vtype="C", lb=0,
                            ub= inputBody.device.ac.power_max * inputBody.device.ac.power_already,
                            name=f"p_ac_max")  # 空调投资容量（最大功率）
        p_ac = [m.addVar(vtype="C", lb=0, name=f"p_ac{t}") for t in range(period)]  # 电锅炉产热
        q_ac = [m.addVar(vtype="C", lb=0, name=f"q_ac{t}") for t in range(period)]  # 电锅炉耗电
        # ----hp----#
        p_hp_max = m.addVar(vtype="C", lb=0,
                            ub= inputBody.device.hp.power_max * inputBody.device.hp.power_already,
                            name=f"p_hp_max")  # 空气源热泵投资容量（最大功率）
        p_hp = [m.addVar(vtype="C", lb=0, name=f"p_hp{t}") for t in range(period)]  # 热泵产热耗电
        p_hpc = [m.addVar(vtype="C", lb=0, name=f"p_hpc{t}") for t in range(period)]  # 热泵产冷的耗电
        q_hp = [m.addVar(vtype="C", lb=0, name=f"q_hp{t}") for t in range(period)]  # 热泵产冷
        g_hp = [m.addVar(vtype="C", lb=0, name=f"g_hp{t}") for t in range(period)]  # 热泵产热
        # ----ghp----#
        p_ghp_max = m.addVar(vtype="C", lb=0,
                             ub= inputBody.device.ghp.power_max * inputBody.device.ghp.power_already,
                             name=f"p_ghp_max")  # 地源热泵投资容量（最大功率）
        p_ghp = [m.addVar(vtype="C", lb=0, name=f"p_ghp{t}") for t in range(period)]  # 热泵产热耗电
        p_ghpc = [m.addVar(vtype="C", lb=0, name=f"p_ghpc{t}") for t in range(period)]  # 热泵产冷的耗电
        g_ghp = [m.addVar(vtype="C", lb=0, name=f"g_ghp{t}") for t in range(period)]  # 热泵产热
        q_ghp = [m.addVar(vtype="C", lb=0, name=f"q_ghp{t}") for t in range(period)]  # 热泵产冷
        g_ghp_gr = [m.addVar(vtype="C", lb=0, name=f"g_ghp_gr{t}") for t in range(period)]  # 热泵灌热
        # ----ghp_deep----#
        p_ghp_deep_max = m.addVar(vtype="C", lb=0,
                                  ub= inputBody.device.ghp_deep.power_max * inputBody.device.ghp_deep.power_already,
                                  name=f"p_ghp_deep_max")  # 地源热泵投资容量（最大功率）
        p_ghp_deep = [m.addVar(vtype="C", lb=0, name=f"p_ghp_deep{t}") for t in range(period)]  # 热泵产热耗电
        g_ghp_deep = [m.addVar(vtype="C", lb=0, name=f"g_ghp_deep{t}") for t in range(period)]  # 热泵产热
        # ----gtw----#
        num_gtw = m.addVar(vtype="INTEGER", lb=0,
                           ub= inputBody.device.gtw.number_max * inputBody.device.gtw.number_already,
                           name='num_gtw')  # 地热井投资数量
        # ----gtw2500----#
        num_gtw2500 = m.addVar(vtype="INTEGER", lb=0,
                           ub=inputBody.device.gtw2500.number_max * inputBody.device.gtw2500.number_already,
                           name='num_gtw2')  # 2500深度地热井投资数量
        # ----hp120----#
        p_hp120_max = m.addVar(vtype="C", lb=0,
                               ub=inputBody.device.hp120.power_max * inputBody.device.hp120.power_already,
                               name=f"p_hp120_max")  # 余热热泵投资容量（最大功率）
        p_hp120 = [m.addVar(vtype="C", lb=0, name=f"p_hp120{t}") for t in range(period)]  # 高温热泵耗电量
        m_hp120 = [m.addVar(vtype="C", lb=0, name=f"m_hp120{t}") for t in range(period)]
        g_hp120 = [m.addVar(vtype="C", lb=0, name=f"g_hp120{t}") for t in range(period)]
        # ----co180----#
        p_co180_max = m.addVar(vtype="C", lb=0,
                               ub=inputBody.device.co180.power_max * inputBody.device.co180.power_already,
                               name=f"p_co180_max")  # 余热热泵投资容量（最大功率）
        p_co180 = [m.addVar(vtype="C", lb=0, name=f"p_co180{t}") for t in range(period)]  # 高温压缩机耗电量
        m_co180 = [m.addVar(vtype="C", lb=0, name=f"m_co180{t}") for t in range(period)]
        # ----whp----#
        p_whp_max = m.addVar(vtype="C", lb=0,
                             ub=inputBody.device.whp.power_max * inputBody.device.whp.power_already,
                             name=f"p_whp_max")  # 余热热泵投资容量（最大功率）
        p_whp = [m.addVar(vtype="C", lb=0, name=f"p_whp{t}") for t in range(period)]  # 余热热泵功率
        p_whpg = [m.addVar(vtype="C", lb=0, name=f"p_whpg{t}") for t in range(period)]  # 余热热泵产热耗电量
        p_whpq = [m.addVar(vtype="C", lb=0, name=f"p_whpq{t}") for t in range(period)]  # 余热热泵产冷耗电量
        g_whp = [m.addVar(vtype="C", lb=0, name=f"g_whp{t}") for t in range(period)]  # 余热热泵产热
        q_whp = [m.addVar(vtype="C", lb=0, name=f"q_whp{t}") for t in range(period)]  # 余热热泵产冷
        # 用户自定义库中设备变量
        # 能量流顺序 0：电   1：热   2：冷   3：氢   4：气   5：自定义能量流1   6：自定义能量流2 ......

        # 自定义储能设备的设备变量

        #---------------创建约束条件--------------#
        #----------------------------------------------------------#
        # 规划容量上下限约束

        # 基本设备库中设备的规划容量上下限，与if_use相关联，判断前端是否勾选了该设备：1，勾选使用；0，未勾选使用
        # ----co----#
        m.addCons(p_co_max <= inputBody.device.co.power_max * inputBody.device.co.power_already)
        m.addCons(p_co_max >= inputBody.device.co.power_min * inputBody.device.co.power_already)
        #----fc----#
        m.addCons(p_fc_max <= inputBody.device.fc.power_max * inputBody.device.fc.power_already)
        m.addCons(p_fc_max >= inputBody.device.fc.power_min * inputBody.device.fc.power_already)
        #----el----#
        m.addCons(p_el_max <= inputBody.device.el.power_max * inputBody.device.el.nm3_already)
        m.addCons(p_el_max <= 50 * inputBody.device.el.nm3_max * inputBody.device.el.nm3_already / 11.2)
        m.addCons(p_el_max >= 50 * inputBody.device.el.nm3_min * inputBody.device.el.nm3_already / 11.2)
        m.addCons(p_el_max >= inputBody.device.el.nm3_min * inputBody.device.el.nm3_already)
        #----hst----#
        m.addCons(hst <= inputBody.device.hst.sto_max * inputBody.device.hst.sto_already)
        m.addCons(hst >= inputBody.device.hst.sto_min * inputBody.device.hst.sto_already)
        #----ht----#
        m.addCons(m_ht <= inputBody.device.ht.water_max * inputBody.device.ht.water_already)
        m.addCons(m_ht >= inputBody.device.ht.water_min * inputBody.device.ht.water_already)
        #----ct----#
        m.addCons(m_ct <= inputBody.device.ct.water_max * inputBody.device.ct.water_already)
        m.addCons(m_ct >= inputBody.device.ct.water_min * inputBody.device.ct.water_already)
        # ----bat----#

        # ----steam_storage----#

        #----pv----#
        m.addCons(p_pv_max <= inputBody.device.pv.power_max * inputBody.device.pv.power_already)
        m.addCons(p_pv_max >= inputBody.device.pv.power_min * inputBody.device.pv.power_already)
        # ----sc----#
        m.addCons(s_sc <= inputBody.device.sc.area_max * inputBody.device.sc.area_already)
        m.addCons(s_sc >= inputBody.device.sc.area_min * inputBody.device.sc.area_already)
        # ----wd----#
        m.addCons(num_wd <= inputBody.device.wd.number_max * inputBody.device.wd.number_already)
        m.addCons(num_wd >= inputBody.device.wd.number_min * inputBody.device.wd.number_already)
        #----eb----#
        m.addCons(p_eb_max <= inputBody.device.eb.power_max * inputBody.device.eb.power_already)
        m.addCons(p_eb_max >= inputBody.device.eb.power_min * inputBody.device.eb.power_already)
        #----ac----#
        m.addCons(p_ac_max <= inputBody.device.ac.power_max * inputBody.device.ac.power_already)
        m.addCons(p_ac_max >= inputBody.device.ac.power_min * inputBody.device.ac.power_already)
        #----hp----#
        m.addCons(p_hp_max <= inputBody.device.hp.power_max * inputBody.device.hp.power_already)
        m.addCons(p_hp_max >= inputBody.device.hp.power_min * inputBody.device.hp.power_already)
        #----ghp----#
        m.addCons(p_ghp_max <= inputBody.device.ghp.power_max * inputBody.device.ghp.power_already)
        m.addCons(p_ghp_max >= inputBody.device.ghp.power_min * inputBody.device.ghp.power_already)
        # ----ghp_deep----#
        m.addCons(p_ghp_deep_max <= inputBody.device.ghp_deep.power_max * inputBody.device.ghp_deep.power_already)
        m.addCons(p_ghp_deep_max >= inputBody.device.ghp_deep.power_min * inputBody.device.ghp_deep.power_already)
        #----gtw----#
        m.addCons(num_gtw <= inputBody.device.gtw.number_max * inputBody.device.gtw.number_already)
        m.addCons(num_gtw >= inputBody.device.gtw.number_min * inputBody.device.gtw.number_already)
        # ----gtw2500----#
        m.addCons(num_gtw2500 <= inputBody.device.gtw2500.number_max * inputBody.device.gtw2500.number_already)
        m.addCons(num_gtw2500 >= inputBody.device.gtw2500.number_min * inputBody.device.gtw2500.number_already)
        # ----hp120----#
        m.addCons(p_hp120_max <= inputBody.device.hp120.power_max * inputBody.device.hp120.power_already)
        m.addCons(p_hp120_max >= inputBody.device.hp120.power_min * inputBody.device.hp120.power_already)
        # ----co180----#
        m.addCons(p_co180_max <= inputBody.device.co180.power_max * inputBody.device.co180.power_already)
        m.addCons(p_co180_max >= inputBody.device.co180.power_max * inputBody.device.co180.power_already)
        #----whp----#
        m.addCons(p_whp_max <= inputBody.device.whp.power_max * inputBody.device.whp.power_already)
        m.addCons(p_whp_max >= inputBody.device.whp.power_min * inputBody.device.whp.power_already)

        # 用户自定义设备的规划容量上下限
        for i in range(custom_device_num):
            m.addCons(x_plan[i] <= input_json['custom_device']['x' + str(i)]['power_max'])
            m.addCons(x_plan[i] >= input_json['custom_device']['x' + str(i)]['power_min'])
        for i in range(custom_storge_device_num[0]):
            m.addCons(s_i_ele_plan[i] <= input_json['custom_device']['storage_device_ele' + str(i)]['power_max'])
            m.addCons(s_i_ele_plan[i] >= input_json['custom_device']['storage_device_ele' + str(i)]['power_min'])
            # m.addCons(s_i_ele_plan[i]<=p_fc_max)
            for j in range(period):
                m.addCons(s_i_ele_plan[i] >= s_i_ele_state[i][j])
        for i in range(custom_storge_device_num[1]):
            m.addCons(s_i_hot_plan[i] <= input_json['custom_device']['storage_device_hot' + str(i)]['power_max'])
            m.addCons(s_i_hot_plan[i] >= input_json['custom_device']['storage_device_hot' + str(i)]['power_min'])
            for j in range(period):
                m.addCons(s_i_hot_plan[i] >= s_i_hot_state[i][j])
        for i in range(custom_storge_device_num[2]):
            m.addCons(s_i_cold_plan[i] <= input_json['custom_device']['storage_device_cold' + str(i)]['power_max'])
            m.addCons(s_i_cold_plan[i] >= input_json['custom_device']['storage_device_cold' + str(i)]['power_min'])
            for j in range(period):
                m.addCons(s_i_cold_plan[i] >= s_i_cold_state[i][j])
        for i in range(custom_storge_device_num[3]):
            m.addCons(s_i_hydr_plan[i] <= input_json['custom_device']['storage_device_hydr' + str(i)]['power_max'])
            m.addCons(s_i_hydr_plan[i] >= input_json['custom_device']['storage_device_hydr' + str(i)]['power_min'])
            for j in range(period):
                m.addCons(s_i_hydr_plan[i] >= s_i_hydr_state[i][j])
        for i in range(custom_storge_device_num[4]):
            m.addCons(s_i_gas_plan[i] <= input_json['custom_device']['storage_device_gas' + str(i)]['power_max'])
            m.addCons(s_i_gas_plan[i] >= input_json['custom_device']['storage_device_gas' + str(i)]['power_min'])
            for j in range(period):
                m.addCons(s_i_gas_plan[i] >= s_i_gas_state[i][j])
        for j in range(custom_energy_num):
            for i in range(custom_storge_device_num[5 + j]):
                m.addCons(
                    s_i_xj_plan[j][i] <= input_json['custom_device']['storage_device_x' + str(j) + str(i)]['power_max'])
                m.addCons(
                    s_i_xj_plan[j][i] >= input_json['custom_device']['storage_device_x' + str(j) + str(i)]['power_min'])
                for l in range(period):
                    m.addCons(s_i_xj_plan[j][i] >= s_i_xj_state[j][i][l])

        #-----------------------------系统约束-----------------------------#
        # 能量流顺序 0：电   1：热   2：冷   3：氢   4：气   5：自定义能量流1   6：自定义能量流2 ......
        for i in range(period):  # 最后一天分开写的必要性？
            # 电总线约束
            m.addCons(
                p_whp[i] + p_co180[i] + p_hp120[i] + p_el[i] + p_sol[i] + p_hp[i] + p_hpc[i] + p_ghp[i] + p_ghp_deep[i] +
                p_ghpc[i] + p_eb[i] + p_ac[i] + p_co[i] + ele_load[i]
                + (quicksum([x_j_in[0][device_index][i] for device_index in range(custom_device_num)]))
                + (quicksum(
                    [s_i_ele_in[storage_device_index][i] for storage_device_index in range(custom_storge_device_num[0])]))
                == p_hyd[i] + p_pur[i] + p_fc[i] + p_pv[i] + p_wd[i]
                + (quicksum([x_j_out[0][device_index][i] for device_index in range(custom_device_num)]))
                + (quicksum(
                    [s_i_ele_out[storage_device_index][i] for storage_device_index in range(custom_storge_device_num[0])])))
            # 热总线约束
            m.addCons(g_tubeTosteam120[i] + g_tube[i]
                    + (quicksum([x_j_in[1][device_index][i] for device_index in range(custom_device_num)]))
                    + (quicksum(
                [s_i_hot_in[storage_device_index][i] for storage_device_index in range(custom_storge_device_num[1])]))
                    == g_fc[i] + g_whp[i] + g_ghp_deep[i] + g_eb[i] + g_sc[i] - g_ghp_gr[i] - g_ht_in[i] + g_ht_out[i] -
                    g_xb[i] + g_hp[i] + g_ghp[i]
                    + (quicksum([x_j_out[1][device_index][i] for device_index in range(custom_device_num)]))
                    + (quicksum(
                [s_i_hot_out[storage_device_index][i] for storage_device_index in range(custom_storge_device_num[1])])))
            m.addCons(g_demand[i] == g_tube[i])  #区分能灌热的和不能灌热的
            # 冷总线约束
            m.addCons(q_demand[i]
                    + (quicksum([x_j_in[2][device_index][i] for device_index in range(custom_device_num)]))
                    + (quicksum(
                [s_i_cold_in[storage_device_index][i] for storage_device_index in range(custom_storge_device_num[2])]))
                    == q_ct_out[i] - q_ct_in[i] + q_hp[i] + q_ac[i] + q_ghp[i] + q_whp[i]
                    + (quicksum([x_j_out[2][device_index][i] for device_index in range(custom_device_num)]))
                    + (quicksum(
                [s_i_cold_out[storage_device_index][i] for storage_device_index in range(custom_storge_device_num[2])])))
            # 天然气约束
            m.addCons((quicksum([x_j_in[4][device_index][i] for device_index in range(custom_device_num)]))
                    + (quicksum(
                [s_i_gas_in[storage_device_index][i] for storage_device_index in range(custom_storge_device_num[4])]))
                    == gas_pur[i]
                    + (quicksum([x_j_out[4][device_index][i] for device_index in range(custom_device_num)]))
                    + (quicksum(
                [s_i_gas_out[storage_device_index][i] for storage_device_index in range(custom_storge_device_num[4])])))

            # 高温120度蒸气约束
            m.addCons(steam120_demand[i] == m_hp120[i] + steam120_pur[i] - steam120_sol[i] - m_steam120Tosteam180[i])

            # 高温120度热泵hp120约束
            m.addCons(750 * m_hp120[i] == g_hp120[i])
            m.addCons(cop_hp120 * p_hp120[i] == g_hp120[i])
            m.addCons((cop_hp120 - 1) * g_tubeTosteam120[i] + p_hp120[i] == g_hp120[i])
            m.addCons(p_hp120[i] <= p_hp120_max)

            # 高温180度蒸气约束
            m.addCons(steam180_demand[i] == m_steam120Tosteam180[i] + steam180_pur[i] - steam180_sol[i])

            # co180约束
            m.addCons(200 * m_steam120Tosteam180[i] == p_co180[i])
            m.addCons(m_hp120[i] >= m_steam120Tosteam180[i])
            m.addCons(p_co180[i] <= p_co180_max)

            # 其他能量流的系统约束
            for j in range(custom_energy_num):
                m.addCons((quicksum([x_j_in[j][device_index][i] for device_index in range(custom_device_num)]))
                        + (quicksum([s_i_xj_in[j][storage_device_index][i] for storage_device_index in
                                    range(custom_storge_device_num[5 + j])]))
                        == y_pur[j][i]
                        + (quicksum([x_j_out[j][device_index][i] for device_index in range(custom_device_num)]))
                        + (quicksum([s_i_xj_out[j][storage_device_index][i] for storage_device_index in
                                    range(custom_storge_device_num[5 + j])])))
                # 第j条自定义能量流的系统平衡约束： 设备用能 = 买能 + 设备产能

        for i in range(period - 1):
            # 氢气约束
            m.addCons(h_sto[i + 1] - h_sto[i] == h_pur[i] + h_el[i] - h_fc[i] - h_demand[i]
                    + (quicksum([x_j_out[3][device_index][i] for device_index in range(custom_device_num)])) - (
                        quicksum([x_j_in[3][device_index][i] for device_index in range(custom_device_num)]))
                    + (quicksum(
                [s_i_hydr_out[storage_device_index][i] for storage_device_index in range(custom_storge_device_num[3])])) - (
                        quicksum([s_i_hydr_in[storage_device_index][i] for storage_device_index in
                                    range(custom_storge_device_num[3])])))
            # 氢气储罐在t+1时刻的储量为t时刻+买氢-燃料电池消耗
        m.addCons(h_sto[0] - h_sto[-1] == h_pur[-1] + h_el[-1] - h_fc[-1] - h_demand[-1]
                + (quicksum([x_j_out[3][device_index][-1] for device_index in range(custom_device_num)])) - (
                    quicksum([x_j_in[3][device_index][-1] for device_index in range(custom_device_num)]))
                + (quicksum(
            [s_i_hydr_out[storage_device_index][-1] for storage_device_index in range(custom_storge_device_num[3])])) - (
                    quicksum([s_i_hydr_in[storage_device_index][-1] for storage_device_index in
                                range(custom_storge_device_num[3])])))
        # 初始状态和末状态平衡

        #-----------------------------设备约束-----------------------------#
        if crf(inputBody.device.ghp.balance_flag) == 1:  #如果需要考虑全年热平衡
            m.addCons(quicksum([g_ghp[i] - p_ghp[i] - q_ghp[i] - p_ghpc[i] - g_ghp_gr[i] for i in range(period)]) == 0)
        for i in range(period):
            # 买能约束      g_sol和gas_pur的未定义以及对120度蒸汽和180度蒸汽的定义未区分
            m.addCons(p_pur[i] <= 1000000000 * inputBody.trading.power_buy_enable)  # 是否允许电网买电
            m.addCons(p_sol[i] <= 1000000000 * inputBody.trading.power_sell_enable)  # 是否允许电网卖电
            m.addCons(h_pur[i] <= 1000000000 * inputBody.trading.h2_buy_enable)  # 是否允许购买氢气
            m.addCons(g_sol[i] <= 1000000000 * input_json['calc_mode']['grid']['g_sol'])  # 是否允许出售天然气
            m.addCons(h_sol[i] <= 1000000000 * inputBody.trading.h2_sell_enable)  # 是否允许出售氢气
            m.addCons(gas_pur[i] <= 1000000000 * input_json['calc_mode']['grid']['gas_pur'])  # 是否允许购买天然气
            m.addCons(steam120_pur[i] <= 1000000000 * inputBody.trading.steam_buy[1].enable)  # 是否允许买120度蒸汽
            m.addCons(steam120_sol[i] <= 1000000000 * inputBody.trading.steam_sol[1].enable)  # 是否允许卖120度蒸汽
            m.addCons(steam180_pur[i] <= 1000000000 * inputBody.trading.steam_buy[0].enable)  # 是否允许买180度蒸汽
            m.addCons(steam180_sol[i] <= 1000000000 * inputBody.trading.steam_sol[0].enable)  # 是否允许卖180度蒸汽
            for j in range(custom_energy_num):
                m.addCons(y_pur[j][i] <= 1000000000 * (isloate[6 + j]))  # 是否允许购买第j条能量流

        #-----------------------------基础设备库的设备约束-----------------------------#
        for i in range(period):
        # ----co----#
            m.addCons(p_co[i] == k_co * h_el[i])  # 压缩氢耗电量约束
            m.addCons(p_co[i] <= p_co_max)  # 压缩机运行功率上限
        # ----fc----#
            m.addCons(g_fc[i] <= eta_ex * k_fc_g * h_fc[i])  # 氢转热约束，允许弃热
            m.addCons(1000000 * z_fc[i] >= g_fc[i])  # 可以弃掉燃料电池的热
            m.addCons(p_fc[i] == k_fc_p * h_fc[i])  # 氢转电约束
            m.addCons(p_fc[i] <= p_fc_max)  # 运行功率 <= 规划功率（运行最大功率）
        #----el----#
            m.addCons(p_el[i] <= p_el_max)  # 运行功率 <= 规划功率（运行最大功率）
            m.addCons(h_el[i] <= k_el * p_el[i])  # 电转氢约束
            m.addCons(h_el[i] <= hst)  # 有问题？产生的氢气质量要小于储氢罐最大储氢容量
        #----hst----#
            m.addCons(h_sto[i] <= hst)
        #----ht----#
            m.addCons(g_ht[i] <= c * m_ht * inputBody.device.ht.t_max)  # 储热罐存储热量上限
            m.addCons(g_ht[i] >= c * m_ht * inputBody.device.ht.t_min)  # 储热罐存储热量下限
        for i in range(period - 1):
            m.addCons(g_ht[i + 1] - g_ht[i] == g_ht_in[i] - g_ht_out[i] - 0.001 * g_ht[i])  # 储热罐存储动态变化
        m.addCons(g_ht[0] - g_ht[-1] == g_ht_in[-1] - g_ht_out[-1] - 0.001 * g_ht[-1])
        #----ct----#
        for i in range(period):
            m.addCons(q_ct[i] <= c * m_ct * inputBody.device.ct.t_max)  # 储冷罐存储冷量上限
            m.addCons(q_ct[i] >= c * m_ct * inputBody.device.ct.t_min)  # 储冷罐存储冷量下限
        for i in range(period - 1):
            m.addCons(q_ct[i] - q_ct[i + 1] == q_ct_in[i] - q_ct_out[i] + 0.001 * q_ct[i])  # 储冷罐存储动态变化
        m.addCons(q_ct[-1] - q_ct[0] == q_ct_in[-1] - q_ct_out[-1] + 0.001 * q_ct[-1])
        # ----bat----#

        # ----steam_storage----#

        for i in range(period):
        # ---pv----#
            m.addCons(p_pv[i] <= p_pv_max * r_solar[i])  # 允许丢弃可再生能源
        # ----sc----#
            m.addCons(g_sc[i] <= k_sc * theta_ex * s_sc * r_solar[i])  # 允许丢弃可再生能源
        # ----wd----#
            m.addCons(p_wd[i] <= num_wd * wind_power[i] * crf(inputBody.device.wd.capacity_unit))  # 允许丢弃可再生能源
        # ---eb----#
            m.addCons(k_eb * p_eb[i] == g_eb[i])  # 电转热约束
            m.addCons(p_eb[i] <= p_eb_max)  # 运行功率 <= 规划功率（运行最大功率）
        # ---ac----#
            m.addCons(q_ac[i] == k_ac * p_ac[i])  # 电转冷约束
            m.addCons(p_ac[i] <= p_ac_max)  # 运行功率 <= 规划功率（运行最大功率）
        # ---hp----#
            m.addCons(p_hp[i] * k_hp_g == g_hp[i])  # 电转热约束
            m.addCons(p_hp[i] <= p_hp_max)  # 热泵供热运行功率 <= 规划功率（运行最大功率）
            m.addCons(p_hpc[i] * k_hp_q == q_hp[i])  # 电转冷约束
            m.addCons(p_hpc[i] <= p_hp_max)  # 热泵供冷运行功率 <= 规划功率（运行最大功率）
        # ---ghp----#
            m.addCons(p_ghp[i] * k_ghp_g == g_ghp[i])  # 地源热泵电转热约束
            m.addCons(p_ghp[i] <= p_ghp_max)  # 热泵供热运行功率 <= 规划功率（运行最大功率）
            m.addCons(p_ghpc[i] * k_ghp_q == q_ghp[i])  # 地源热泵电转冷约束
            m.addCons(p_ghpc[i] <= p_ghp_max)  # 热泵供冷运行功率 <= 规划功率（运行最大功率）
            m.addCons(p_ghp_deep[i] * k_ghp_deep_g == g_ghp_deep[i])  # 地源热泵电转热约束
            m.addCons(p_ghp_deep[i] <= p_ghp_deep_max)  # 热泵供热运行功率 <= 规划功率（运行最大功率）
        #----gtw----#
            m.addCons(num_gtw * p_gtw >= g_ghp[i] - p_ghp[i])  #井和热泵有关联，制热量-电功率=取热量
            m.addCons(num_gtw * p_gtw >= q_ghp[i] + p_ghpc[i])  #井和热泵有关联，制冷量+电功率=灌热量
            m.addCons(num_gtw2500 * p_gtw2500 >= g_ghp_deep[i] - p_ghp_deep[i]) # 存疑
        # ---hp120----#

        # ---co180----#

        # ---whp----#               找不到heat_resourceg和heat_resourceq的对应
            m.addCons(p_whpg[i] * k_whp == g_whp[i])
            m.addCons(g_whp[i] - p_whpg[i] <= input_json['device']['whp']['heat_resourceg'])
            m.addCons(p_whpq[i] * k_whp == q_whp[i])
            m.addCons(q_whp[i] - p_whpq[i] <= input_json['device']['whp']['heat_resourceq'])
            m.addCons(p_whp[i] <= p_whp_max)
            m.addCons(p_whp[i] == p_whpg[i] + p_whpq[i])


        #-----------------------------用户自定义的设备约束-----------------------------#
        for i in range(period):
            for device_index in range(custom_device_num):
                for energy_output_index in range(5 + custom_energy_num):
                    m.addCons(quicksum(x_j_in[energy_input_index][device_index][i]
                                    * k_custom_device[device_index][energy_input_index][energy_output_index] for
                                    energy_input_index in range(5 + custom_energy_num))
                            == x_j_out[energy_output_index][device_index][i])
        # 第device_index个设备的 第energy_output_index条能量流(多输入单输出)的 由所有能量流乘以一个转化系数构成 第i时段的 约束 

        for device_index in range(custom_device_num):
            standard_energy = input_json['custom_device']['x' + str(device_index)]['standard_energy']
            for i in range(period):
                m.addCons(x_j_in[standard_energy][device_index][i] <= x_plan[device_index])  #输入与规划量的上界关系
                for j in range(5 + custom_energy_num):
                    m.addCons(x_j_in[standard_energy][device_index][i] *
                            input_json['custom_device']['x' + str(device_index)]['input_energy'][j] ==
                            x_j_in[j][device_index][i])  #输入的各条能量流固定输入的比例

        # TODO 是否存在点问题？

        # 自定义储能设备的约束 j+1状态 - j状态 = j输入 - j输出
        for j in range(period - 1):
            for i in range(custom_storge_device_num[0]):
                m.addCons(s_i_ele_state[i][j + 1] - 0.98 * s_i_ele_state[i][j] == s_i_ele_in[i][j] - s_i_ele_out[i][j])
            for i in range(custom_storge_device_num[1]):
                m.addCons(s_i_hot_state[i][j + 1] - s_i_hot_state[i][j] == s_i_hot_in[i][j] - s_i_hot_out[i][j])
            for i in range(custom_storge_device_num[2]):
                m.addCons(s_i_cold_state[i][j + 1] - s_i_cold_state[i][j] == s_i_cold_in[i][j] - s_i_cold_out[i][j])
            for i in range(custom_storge_device_num[3]):
                m.addCons(s_i_hydr_state[i][j + 1] - s_i_hydr_state[i][j] == s_i_hydr_in[i][j] - s_i_hydr_out[i][j])
            for i in range(custom_storge_device_num[4]):
                m.addCons(s_i_gas_state[i][j + 1] - s_i_gas_state[i][j] == s_i_gas_in[i][j] - s_i_gas_out[i][j])
            for l in range(custom_energy_num):
                for i in range(custom_storge_device_num[5 + l]):
                    m.addCons(s_i_xj_state[l][i][j + 1] - s_i_xj_state[l][i][j] == s_i_xj_in[l][i][j] - s_i_xj_out[l][i][j])
        for i in range(custom_storge_device_num[0]):
            m.addCons(s_i_ele_state[i][0] - 0.98 * s_i_ele_state[i][-1] == s_i_ele_in[i][-1] - s_i_ele_out[i][-1])
        for i in range(custom_storge_device_num[1]):
            m.addCons(s_i_hot_state[i][0] - s_i_hot_state[i][-1] == s_i_hot_in[i][-1] - s_i_hot_out[i][-1])
        for i in range(custom_storge_device_num[2]):
            m.addCons(s_i_cold_state[i][0] - s_i_cold_state[i][-1] == s_i_cold_in[i][-1] - s_i_cold_out[i][-1])
        for i in range(custom_storge_device_num[3]):
            m.addCons(s_i_hydr_state[i][0] - s_i_hydr_state[i][-1] == s_i_hydr_in[i][-1] - s_i_hydr_out[i][-1])
        for i in range(custom_storge_device_num[4]):
            m.addCons(s_i_gas_state[i][0] - s_i_gas_state[i][-1] == s_i_gas_in[i][-1] - s_i_gas_out[i][-1])
        for l in range(custom_energy_num):
            for i in range(custom_storge_device_num[5 + l]):
                m.addCons(s_i_xj_state[l][i][0] - s_i_xj_state[l][i][-1] == s_i_xj_in[l][i][-1] - s_i_xj_out[l][i][-1])

        #-----------------------------安装面积等约束-----------------------------#  未定义
        s_sum = input_json['renewable_energy']['s_renewable_energy_max']
        m.addCons(s_pv * input_json['device']['pv']['beta_pv'] == p_pv_max)
        m.addCons(s_pv + s_sc <= s_sum)

        #-----------------------------运行费用约束-----------------------------# hyb未定义
        m.addCons(op_sum == quicksum([p_pur[i] * lambda_ele_in[i] for i in range(period)])  # 买电花费
                + lambda_h * quicksum([h_pur[i] for i in range(period)])  # 买氢气花费
                + gas_price * quicksum([gas_pur[i] for i in range(period)])  # 买天然气花费
                + lambda_steam120_in * quicksum([steam120_pur[i] for i in range(period)])  # 买120steam花费
                + lambda_steam180_in * quicksum([steam180_pur[i] for i in range(period)])  # 买180steam花费
                + quicksum([cost_custom_energy[j] * y_pur[j][i] for i in range(period) for j in range(custom_energy_num)])
                - quicksum(p_sol[i] * lambda_ele_out for i in range(period))
                - quicksum(g_sol[i] * lambda_g_out for i in range(period))
                - quicksum(h_sol[i] * lambda_h_out for i in range(period))
                - quicksum(steam120_sol[i] * lambda_steam120_out for i in range(period))
                - quicksum(steam180_sol[i] * lambda_steam180_out for i in range(period))
                )  # 买自定义能量流花费
        m.addCons(op_sum_pure == quicksum([p_pur[i] * lambda_ele_in[i] for i in range(period)])  # 买电花费
                + lambda_h * quicksum([h_pur[i] for i in range(period)])  # 买氢气花费
                + gas_price * quicksum([gas_pur[i] for i in range(period)])  # 买天然气花费
                + lambda_steam120_in * quicksum([steam120_pur[i] for i in range(period)])  # 买天然气花费
                + lambda_steam180_in * quicksum([steam180_pur[i] for i in range(period)])  # 买天然气花费
                + quicksum([cost_custom_energy[j] * y_pur[j][i] for i in range(period) for j in range(custom_energy_num)])
                )  # 买自定义能量流花费

        m.addCons(op_sum <= input_json['price']['op_max'][1 - isloate[1]])  #运行费用上限（在允许卖电和不允许卖电模式下的运行费用上限不同）
        #price 未定义
        # m.addCons(cost_c_ele == sum([ele_load[i]*lambda_ele_in[i] for i in range(period)]))
        # m.addCons(cost_c_heat == sum([g_demand[i]/0.95*lambda_ele_in[i] for i in range(period)]))#/(3.41))
        # m.addCons(cost_c_cool == sum([q_demand[i]/4*lambda_ele_in[i] for i in range(period)]))#/3.8)
        # m.addCons(cost_c == cost_c_cool+cost_c_heat+cost_c_ele)

        #-----------------------------碳减排的约束-----------------------------#
        m.addCons(quicksum(p_pur) <= (1 - cer) * (
                    sum(ele_load) + sum(g_demand) / k_eb + sum(q_demand) / k_ghp_q))  # 碳减排约束，买电量不能超过碳排放,即1-碳减排
        m.addCons(ce_h == quicksum(p_pur) * alpha_e)
        #-----------------------------规划设备花费约束-----------------------------#
        m.addCons(capex_sum == (+ p_pv_max * cost_pv + s_sc * cost_sc + num_wd * cost_wd
                                + p_hp120_max * cost_hp120 + p_co180_max * cost_co180
                                + p_ghp_max * cost_ghp + p_ghp_deep_max * cost_ghp_deep + cost_gtw * num_gtw + cost_gtw2500 * num_gtw2500
                                + cost_ht * m_ht + cost_ct * m_ct + cost_hst * hst + cost_eb * p_eb_max + cost_ac * p_ac_max + cost_hp * p_hp_max + cost_fc * p_fc_max + cost_el * p_el_max + cost_co * p_co_max + p_whp_max * cost_whp) * (1 + input_json["price"]["PSE"])  # 基本设备库设备的规划成本
                + quicksum([cost_x[i] * x_plan[i] for i in range(custom_device_num)]) * (
                            1 + input_json["price"]["PSE"])  # 自定义设备规划成本
                + quicksum([cost_storage_ele[i] * s_i_ele_plan[i] for i in range(custom_storge_device_num[0])]) * (
                            1 + input_json["price"]["PSE"])
                + quicksum([cost_storage_hot[i] * s_i_hot_plan[i] for i in range(custom_storge_device_num[1])]) * (
                            1 + input_json["price"]["PSE"])
                + quicksum([cost_storage_cold[i] * s_i_cold_plan[i] for i in range(custom_storge_device_num[2])]) * (
                            1 + input_json["price"]["PSE"])
                + quicksum([cost_storage_hydr[i] * s_i_hydr_plan[i] for i in range(custom_storge_device_num[3])]) * (
                            1 + input_json["price"]["PSE"])
                + quicksum([cost_storage_gas[i] * s_i_gas_plan[i] for i in range(custom_storge_device_num[4])]) * (
                            1 + input_json["price"]["PSE"])
                + quicksum(
            [quicksum([cost_storage_x[i][j] * s_i_xj_plan[i][j] for j in range(custom_storge_device_num[5 + i])]) for i in
            range(custom_energy_num)]) * (1 + input_json["price"]["PSE"])
                )  # 自定义设备规划成本

        m.addCons(capex_sum <= input_json['price']['capex_max'][1 - isloate[0]])  # 总规划成本上限（在允许买电和不允许买电模式下的运行费用上限不同）

        m.addCons(capex_crf == crf_pv * p_pv_max * cost_pv + crf_wd * num_wd * cost_wd + crf_sc * s_sc * cost_sc + crf_hst * hst * cost_hst + crf_ht * cost_ht * (
                    m_ht) + crf_ct * cost_ct * (m_ct) + crf_hp * cost_hp * p_hp_max
                + crf_gtw * cost_gtw * num_gtw + crf_gtw2500 * cost_gtw2500 * num_gtw2500
                + crf_hp120 * p_hp120_max * cost_hp120 + crf_co180 * p_co180_max * cost_co180 + crf_ghp * cost_ghp * p_ghp_max + crf_ghp_deep * cost_ghp_deep * p_ghp_deep_max + crf_eb * cost_eb * p_eb_max + crf_ac * cost_ac * p_ac_max + crf_fc * p_fc_max * cost_fc + crf_el * p_el_max * cost_el + crf_co * p_co_max * cost_co + crf_xb * cost_xb * g_xb_max + crf_whp * p_whp_max * cost_whp
                + quicksum([cost_x[i] * x_plan[i] for i in range(custom_device_num)]) * (
                            1 + input_json["price"]["PSE"])  # 自定义设备规划成本
                + quicksum(
            [cost_storage_ele[i] * s_i_ele_plan[i] * crf(input_json['custom_device']['storage_device_ele' + str(i)]['crf'])
            for i in range(custom_storge_device_num[0])])
                + quicksum(
            [cost_storage_hot[i] * s_i_hot_plan[i] * crf(input_json['custom_device']['storage_device_hot' + str(i)]['crf'])
            for i in range(custom_storge_device_num[1])])
                + quicksum([cost_storage_cold[i] * s_i_cold_plan[i] * crf(
            input_json['custom_device']['storage_device_cold' + str(i)]['crf']) for i in
                            range(custom_storge_device_num[2])])
                + quicksum([cost_storage_hydr[i] * s_i_hydr_plan[i] * crf(
            input_json['custom_device']['storage_device_hydr' + str(i)]['crf']) for i in
                            range(custom_storge_device_num[3])])
                + quicksum(
            [cost_storage_gas[i] * s_i_gas_plan[i] * crf(input_json['custom_device']['storage_device_gas' + str(i)]['crf'])
            for i in range(custom_storge_device_num[4])])
                + quicksum([quicksum([cost_storage_x[i][j] * s_i_xj_plan[i][j] * crf(
            input_json['custom_device']['storage_device_x' + str(i) + str(j)]['crf']) for j in
                                        range(custom_storge_device_num[5 + i])]) for i in range(custom_energy_num)]))

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



