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


#-------------函数定义--------------#
#0：判断数组是多少维数的数组
def is_Empty(arr):
    if not arr:
        return True
    for element in arr:
        if not isinstance(element, list):
            return False
        if not is_Empty(element):
            return False
    return True


def is_multi_dim_arr(arr):
    count = 1
    if type(arr) != list or is_Empty(arr):
        return 0
    while type(arr[0]) == list:
        count += 1
        arr = arr[0]
    return count


#1：保存函数
def to_csv(res, filename, custom_energy_num, custom_device_num, custom_storge_device_num):
    """将规划结果生成csv，并保存到doc文件夹下

    Args:
        res (_type_): dict字典，规划结果
        filename (_type_): 保存的文件名
    """
    res_dict = "doc/"  #保存在doc文件夹
    items = list(res.keys())
    wb = xlwt.Workbook()
    total = wb.add_sheet('garden')
    col = 0
    for i in range(len(items)):
        if res[items[i]] == []:
            continue
        if is_multi_dim_arr(res[items[i]]) == 0:  #数字
            total.write(0, col, items[i])
            total.write(1, col, res[items[i]])
            col += 1
        elif is_multi_dim_arr(res[items[i]]) == 1:  #一维数组
            total.write(0, col, items[i])
            for j in range(len(res[items[i]])):
                total.write(j + 1, col, (res[items[i]])[j])
            col += 1
        elif is_multi_dim_arr(res[items[i]]) == 2:  #二维数组
            for j in range(len(res[items[i]])):
                total.write(0, col, items[i] + str(j))
                for k in range(len(res[items[i]][j])):
                    total.write(k + 1, col, (res[items[i]])[j][k])
                col += 1
        elif is_multi_dim_arr(res[items[i]]) == 3:  #三维数组
            for j in range(len(res[items[i]])):
                for k in range(len(res[items[i]][j])):
                    total.write(0, col, items[i] + str(j) + str(k))
                    for l in range(len(res[items[i]][j][k])):
                        total.write(l + 1, col, (res[items[i]])[j][k][l])
                    col += 1
    wb.save(res_dict + filename)


#2：年化收益率函数
def crf(year):
    """
        将输入文件中的设备寿命转为年化收益率

        Args:
            year: 设备寿命
    """
    i = 0.08
    crf = ((1 + i) ** year) * i / ((1 + i) ** year - 1)
    return crf


#3：计算配套设备价格函数
def support_device(d_cost, d_se):
    return d_cost * d_se


#4：保存结果为json
# def save_json(j,name):
#     res_dict = "doc/" #保存在doc文件夹
#     jj = json.dumps(j)
#     f = open(res_dict+name+".json",'w')
#     f.write(jj)
#     f.close()
#     return 0

def save_json(data, name):
    res_dict = "doc/"  #保存在doc文件夹
    with open(res_dict + name + '.json', 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

class ISService:
    def __init__(self):
        pass

    def exec(self, inputBody: OptimizationBody):

        t0 = time.time()
        # ------------导入自定义数据------------#

        # ------------导入负荷数据------------#
        # ele_load = OptimizationBody.objective_load#??????

        r_solar = OptimizationBody.device.pv.pv_data8760  # 光照强度
        # 添加风电数据
        wind_data = OptimizationBody.device.wd.wd_data8760

        # ------------导入价格等数据------------#
        alpha_e = 0.5839                                                        # 电网排放因子kg/kWh
        gas_price = 1.2                                                         # 天然气价钱
        lambda_ele_in = OptimizationBody.trading.power_buy_8760_price           # 每个小时的电价
        lambda_ele_out = OptimizationBody.trading.power_sell_price              # 卖电价格
        lambda_g_out = OptimizationBody.trading.heat_sell_price                 # 卖热价格
        lambda_h_out = OptimizationBody.trading.hydrogen_sell_price             # 卖氢价格
        lambda_h = OptimizationBody.trading.hydrogen_buy_price                  # 买氢价格
        cer = OptimizationBody.base.cer                                         # 碳减排率
        lambda_steam120_in = OptimizationBody.trading.steam_buy[1].price        # 120蒸汽购入价格
        lambda_steam120_out = OptimizationBody.trading.steam_sell[1].price      # 120蒸汽出售价格
        lambda_steam180_in = OptimizationBody.trading.steam_buy[0].price        # 180蒸汽购入价格
        lambda_steam180_out = OptimizationBody.trading.steam_sell[0].price      # 180蒸汽出售价格
        c = 4.2 / 3600                                                          # 水的比热容
        M = 1000000
        epsilon = 0.0000001

        # 自定义能量流的价格和碳排

        # ---------------------------基本设备库中的设备---------------------------#
        """
        基本设备库中设备符号解释:(20类)
            fc: 燃料电池     el: 电解槽     hst: 储氢罐       ht: 储热水箱
            ct: 储冷水箱     pv: 光伏板     sc: 太阳能集热器   eb: 电锅炉
            ac: 空调        hp: 空气源热泵  ghp: 浅层地源热泵  gtw: 浅层地埋井      ghp_deep: 中深层地源热泵     gtw11234: 不同深度的地埋井
            co: 氢气压缩机   hyd: 水电      hp120:高温热泵     co180:高温蒸汽压缩机 xb: 相变储热模块   whp: 余热热泵   
        """

        # ---------------年化收益率数据--------------#
        crf_fc = crf(OptimizationBody.device.fc.crf)
        crf_el = crf(OptimizationBody.device.el.crf)
        crf_hst = crf(OptimizationBody.device.hst.crf)
        crf_ht = crf(OptimizationBody.device.ht.crf)
        crf_ct = crf(OptimizationBody.device.ct.crf)
        crf_pv = crf(OptimizationBody.device.pv.crf)
        crf_wd = crf(OptimizationBody.device.wd.crf)
        crf_sc = crf(OptimizationBody.device.sc.crf)
        crf_eb = crf(OptimizationBody.device.eb.crf)
        crf_ac = crf(OptimizationBody.device.ac.crf)
        crf_hp = crf(OptimizationBody.device.hp.crf)
        crf_ghp = crf(OptimizationBody.device.ghp.crf)
        crf_ghp_deep = crf(OptimizationBody.device.ghp_deep.crf)
        crf_gtw = crf(OptimizationBody.device.gtw.crf)
        # crf_gtw1 = crf(OptimizationBody.device)#???
        # crf_gtw2 = crf#???
        # crf_gtw3 = crf#???
        # crf_gtw4 = crf#???
        crf_co180 = crf(OptimizationBody.device.co180.crf)
        crf_hp120 = crf(OptimizationBody.device.hp120.crf)
        crf_co = crf(OptimizationBody.device.co.crf)
        # crf_hyd = crf(OptimizationBody.device)#???
        # crf_xb = crf(OptimizationBody.device.)#???
        crf_whp = crf(OptimizationBody.device.whp.crf)

        # --------------单位投资成本数据--------------#
        cost_fc = OptimizationBody.device.fc.cost + support_device(OptimizationBody.device.fc.cost,
                                                                   OptimizationBody.device.fc.se)
        # cost_el = OptimizationBody.device.el.cost + support_device(OptimizationBody.device.el.cost,
                                                                  # OptimizationBody.device.el.se)#???
        cost_hst = OptimizationBody.device.hst.cost + support_device(OptimizationBody.device.hst.cost,
                                                                     OptimizationBody.device.hst.se)
        cost_ht = OptimizationBody.device.ht.cost + support_device(OptimizationBody.device.ht.cost,
                                                                   OptimizationBody.device.ht.se)
        cost_ct = OptimizationBody.device.ct.cost + support_device(OptimizationBody.device.ct.cost,
                                                                   OptimizationBody.device.ct.se)
        # cost_pv = OptimizationBody.device.pv.cost + support_device(OptimizationBody.device.pv.cost,
                                                                 #  OptimizationBody.device.pv.se)#???
        capacity_wd = OptimizationBody.device.wd.capacity_unit
        # cost_wd = capacity_wd * OptimizationBody.device.wd.cost + support_device(OptimizationBody.device.wd.cost,
                                                                               #  OptimizationBody.device.wd.se)#???
        # cost_sc = OptimizationBody.device.sc.cost + support_device(OptimizationBody.device.sc.cost,
                                                                #   OptimizationBody.device.sc.se)#???

        cost_eb = OptimizationBody.device.eb.cost + support_device(OptimizationBody.device.eb.cost,
                                                                   OptimizationBody.device.eb.se)
        cost_ac = OptimizationBody.device.ac.cost + support_device(OptimizationBody.device.ac.cost,
                                                                   OptimizationBody.device.ac.se)
        cost_hp = OptimizationBody.device.hp.cost + support_device(OptimizationBody.device.hp.cost,
                                                                   OptimizationBody.device.hp.se)
        cost_ghp = OptimizationBody.device.ghp.cost + support_device(OptimizationBody.device.ghp.cost,
                                                                     OptimizationBody.device.ghp.se)
        cost_ghp_deep = OptimizationBody.device.ghp_deep.cost + support_device(OptimizationBody.device.ghp_deep.cost,
                                                                               OptimizationBody.device.ghp_deep.se)
        cost_gtw = OptimizationBody.device.gtw.cost + support_device(OptimizationBody.device.gtw.cost,
                                                                     OptimizationBody.device.gtw.se)
        # cost_gtw1
        # cost_gtw2
        # cost_gtw3
        # cost_gtw4
        cost_co = OptimizationBody.device.co.cost + support_device(OptimizationBody.device.co.cost,
                                                                   OptimizationBody.device.co.se)
        # cost_co180 = OptimizationBody.device.co180.cost + support_device(OptimizationBody.device.co180.cost,
                                                              #     OptimizationBody.device.co180.se) #???
        # cost_hyd
        # cost_xb =
        # cost_whp = OptimizationBody.device.whp.cost + support_device(OptimizationBody.device.whp.cost,
                                                                    # OptimizationBody.device.whp.se) #???

        # ---------------效率数据，包括产热、制冷、发电、热转换等--------------#
        # ----fc----#
        eta_ex = 0.95  # fc产的热通过热交换器后的剩余热量系数
        k_fc_p = OptimizationBody.device.fc.eta_fc_p  # 氢转电系数kg——>kWh
        k_fc_g = OptimizationBody.device.fc.eta_ex_g  # 氢转热系数kg——>kWh
        # ----el----#
        # k_el =
        # ----pv----#
        # eta_pv =
        # ----sc----#
        k_sc = OptimizationBody.device.sc.beta_sc
        theta_ex = OptimizationBody.device.sc.theta_ex
        # ----eb----#
        k_eb = OptimizationBody.device.eb.beta_eb
        # ----ac----#
        k_ac = OptimizationBody.device.ac.beta_ac
        # ----hp----#
        k_hp_g = OptimizationBody.device.hp.beta_hpg
        k_hp_q = OptimizationBody.device.hp.beta_hpq
        # ----ghp----#
        k_ghp_g = OptimizationBody.device.ghp.beta_ghpg
        k_ghp_q = OptimizationBody.device.ghp.beta_ghpq
        k_ghp_deep_g = OptimizationBody.device.ghp_deep.beta_ghpg
        # ----gtw----#
        p_gtw = OptimizationBody.device.gtw.beta_gtw
        # p_gtw1
        # p_gtw2
        # p_gtw3
        # p_gtw4
        # ----co----#
        k_co = OptimizationBody.device.co.beta_co
        # ----hyd----#
        # water_hyd_peak =
        # ----xb----#
        # k_xb =
        # ----whp----#
        # k_whp =
        # ----co180----#

        # ----hp120----#
        cop_hp120 = OptimizationBody.device.hp120.cop

        # ----------------特殊场景下的数据导入---------------#
        # 含有水电场景下的接口
        # 无hyd

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
        h_sol = [m.addVar(vtype="C", lb=0, name=f"h_sol{t}") for t in range(period)]  # 卖电power sold
        gas_pur = [m.addVar(vtype="C", lb=0, name=f"gas_pur{t}") for t in range(period)]  # 买天然气
        steam120_pur = [m.addVar(vtype="C", lb=0, name=f"steam120_pur{t}") for t in range(period)]  # 买steam120
        steam120_sol = [m.addVar(vtype="C", lb=0, name=f"steam120_sol{t}") for t in range(period)]  # 卖steam120
        steam180_pur = [m.addVar(vtype="C", lb=0, name=f"steam180_pur{t}") for t in range(period)]  # 买steam180
        steam180_sol = [m.addVar(vtype="C", lb=0, name=f"steam180_sol{t}") for t in range(period)]  # 卖steam180
        # y_pur = [[m.addVar(vtype="C", lb=0, name=f"y_pur{i}{t}") for t in range(period)] for i in
                # range(custom_energy_num)]  # 买天然气  # 涉及自定义能量流

        # 基本设备库中设备变量
        # ----fc----#
        z_fc = [m.addVar(lb=0, ub=1, vtype="B", name=f"z_fc{t}") for t in range(period)]
        p_fc_max = m.addVar(vtype="C", lb=0,
                            ub= OptimizationBody.device.fc.power_max * OptimizationBody.device.fc.power_already,
                            name=f"p_fc_max")  # fc的投资容量（最大功率）
        g_fc = [m.addVar(vtype="C", lb=0, name=f"g_fc{t}") for t in range(period)]  # 燃料电池产热量
        p_fc = [m.addVar(vtype="C", lb=0, name=f"p_fc{t}") for t in range(period)]  # 燃料电池产电量
        h_fc = [m.addVar(vtype="C", lb=0, name=f"h_fc{t}") for t in range(period)]  # 燃料电池用氢量

        # ----el----#
        p_el_max = m.addVar(vtype="C", lb=0,
                            ub= OptimizationBody.device.el.nm3_max * OptimizationBody.device.el.nm3_already,
                            name="p_el_max")  # el的投资容量（最大功率）
        h_el = [m.addVar(vtype="C", lb=0, name=f"h_el{t}") for t in range(period)]  # 电解槽产氢量
        p_el = [m.addVar(vtype="C", lb=0, name=f"p_el{t}") for t in range(period)]  # 电解槽功率

        # ----hst----#
        hst = m.addVar(vtype="C", lb=0,
                       ub= OptimizationBody.device.hst.sto_max * OptimizationBody.device.hst.sto_already,
                       name=f"hst")  # 储氢罐规划容量
        h_sto = [m.addVar(vtype="C", lb=0, name=f"h_sto{t}") for t in range(period)]  # 储氢罐t时刻储氢量

        # ----ht----#
        m_ht = m.addVar(vtype="C", lb=0,
                        ub= OptimizationBody.device.ht.water_max * OptimizationBody.device.ht.water_already,
                        name=f"m_ht")  # 储热罐的规划容量
        g_ht_in = [m.addVar(vtype="C", lb=0, name=f"g_ht_in{t}") for t in range(period)]
        g_ht_out = [m.addVar(vtype="C", lb=0, name=f"g_ht_out{t}") for t in range(period)]
        g_ht = [m.addVar(vtype="C", lb=0, name=f"g_ht{t}") for t in range(period)]  # 存储的热量
        # 写完约束之后再看看有没有需要创建的变量

        # ----ct----#
        m_ct = m.addVar(vtype="C", lb=0,
                        ub= OptimizationBody.device.ct.water_max * OptimizationBody.device.ct.water_already,
                        name=f"m_ct")  # 储冷罐的规划容量
        q_ct_in = [m.addVar(vtype="C", lb=0, name=f"q_ct_in{t}") for t in range(period)]
        q_ct_out = [m.addVar(vtype="C", lb=0, name=f"q_ct_out{t}") for t in range(period)]  # 写完约束之后再看看有没有需要创建的变量
        q_ct = [m.addVar(vtype="C", lb=0, name=f"q_ct{t}") for t in range(period)]  # 存储的冷量

        # ----pv----#
        s_pv = m.addVar(vtype="C", lb=0, name=f"s_pv")  # 光伏板投资面积
        p_pv_max = m.addVar(vtype="C", lb=0, name=f"p_pv_max")  # 光伏板投资面积
        p_pv = [m.addVar(vtype="C", lb=0, ub= OptimizationBody.device.pv.power_max * OptimizationBody.device.pv.power_already,
                     name=f"p_pv{t}") for t in range(period)]  # 光伏板发电功率

        # ----wd----#    p_pv_max = [m.addVar(vtype="C", lb=0,ub= input_json['device']['pv']['power_max']*input_json['device']['pv']['if_use'], name=f"p_pv{t}") for t in range(period)]# 光伏板发电功率
        num_wd = m.addVar(vtype="INTEGER", lb=0,
                          ub= OptimizationBody.device.wd.number_max * OptimizationBody.device.wd.number_already,
                          name=f"num_wd")  # 风电投资数量
        p_wd = [m.addVar(vtype="C", lb=0, name=f"p_wd{t}") for t in range(period)]  # 风电发电功率

        # ----sc----#
        s_sc = m.addVar(vtype="C", lb=0,
                        ub= OptimizationBody.device.sc.area_max * OptimizationBody.device.sc.area_already,
                        name=f"s_sc")  # 太阳能集热器投资面积
        g_sc = [m.addVar(vtype="C", lb=0, name=f"g_sc{t}") for t in range(period)]  # 太阳能集热器收集的热量

        # ----eb----#
        p_eb_max = m.addVar(vtype="C", lb=0,
                            ub= OptimizationBody.device.eb.power_max * OptimizationBody.device.eb.power_already,
                            name=f"p_eb_max")  # 电锅炉投资容量（最大功率）
        g_eb = [m.addVar(vtype="C", lb=0, name=f"g_eb{t}") for t in range(period)]  # 电锅炉产热
        p_eb = [m.addVar(vtype="C", lb=0, name=f"p_eb{t}") for t in range(period)]  # 电锅炉耗电

        # ----ac----#
        p_ac_max = m.addVar(vtype="C", lb=0,
                            ub= OptimizationBody.device.ac.power_max * OptimizationBody.device.ac.power_already,
                            name=f"p_ac_max")  # 空调投资容量（最大功率）
        p_ac = [m.addVar(vtype="C", lb=0, name=f"p_ac{t}") for t in range(period)]  # 电锅炉产热
        q_ac = [m.addVar(vtype="C", lb=0, name=f"q_ac{t}") for t in range(period)]  # 电锅炉耗电

        # ----hp----#
        p_hp_max = m.addVar(vtype="C", lb=0,
                            ub= OptimizationBody.device.hp.power_max * OptimizationBody.device.hp.power_already,
                            name=f"p_hp_max")  # 空气源热泵投资容量（最大功率）
        p_hp = [m.addVar(vtype="C", lb=0, name=f"p_hp{t}") for t in range(period)]  # 热泵产热耗电
        p_hpc = [m.addVar(vtype="C", lb=0, name=f"p_hpc{t}") for t in range(period)]  # 热泵产冷的耗电
        q_hp = [m.addVar(vtype="C", lb=0, name=f"q_hp{t}") for t in range(period)]  # 热泵产冷
        g_hp = [m.addVar(vtype="C", lb=0, name=f"g_hp{t}") for t in range(period)]  # 热泵产热

        # ----ghp----#
        p_ghp_max = m.addVar(vtype="C", lb=0,
                             ub= OptimizationBody.device.ghp.power_max * OptimizationBody.device.ghp.power_already,
                             name=f"p_ghp_max")  # 地源热泵投资容量（最大功率）
        p_ghp = [m.addVar(vtype="C", lb=0, name=f"p_ghp{t}") for t in range(period)]  # 热泵产热耗电
        p_ghpc = [m.addVar(vtype="C", lb=0, name=f"p_ghpc{t}") for t in range(period)]  # 热泵产冷的耗电
        g_ghp = [m.addVar(vtype="C", lb=0, name=f"g_ghp{t}") for t in range(period)]  # 热泵产热
        q_ghp = [m.addVar(vtype="C", lb=0, name=f"q_ghp{t}") for t in range(period)]  # 热泵产冷
        g_ghp_gr = [m.addVar(vtype="C", lb=0, name=f"g_ghp_gr{t}") for t in range(period)]  # 热泵灌热
        p_ghp_deep_max = m.addVar(vtype="C", lb=0,
                                  ub= OptimizationBody.device.ghp_deep.power_max * OptimizationBody.device.ghp_deep.power_already,
                                  name=f"p_ghp_deep_max")  # 地源热泵投资容量（最大功率）
        p_ghp_deep = [m.addVar(vtype="C", lb=0, name=f"p_ghp_deep{t}") for t in range(period)]  # 热泵产热耗电
        g_ghp_deep = [m.addVar(vtype="C", lb=0, name=f"g_ghp_deep{t}") for t in range(period)]  # 热泵产热

        num_gtw = m.addVar(vtype="INTEGER", lb=0,
                           ub= OptimizationBody.device.gtw.number_max * OptimizationBody.device.gtw.number_already,
                           name='num_gtw')  # 地热井投资数量
        # num_gtw1 = m.addVar(vtype="INTEGER", lb=0,
                           # ub=input_json['device']['gtw1']['number_max'] * input_json['device']['gtw1']['if_use'],
                           # name='num_gtw1')  # 2200深度地热井投资数量
        # num_gtw2 = m.addVar(vtype="INTEGER", lb=0,
                           # ub=input_json['device']['gtw2']['number_max'] * input_json['device']['gtw2']['if_use'],
                            # name='num_gtw2')  # 2500深度地热井投资数量
        # num_gtw3 = m.addVar(vtype="INTEGER", lb=0,
                            # ub=input_json['device']['gtw3']['number_max'] * input_json['device']['gtw3']['if_use'],
                            # name='num_gtw3')  # 2600深度地热井投资数量
        # num_gtw4 = m.addVar(vtype="INTEGER", lb=0,
                           # ub=input_json['device']['gtw4']['number_max'] * input_json['device']['gtw4']['if_use'],
                           # name='num_gtw4')  # 2700深度地热井投资数量

        # ----co----#
        p_co_max = m.addVar(vtype="C", lb=0,
                            ub= OptimizationBody.device.co.power_max * OptimizationBody.device.co.power_already,
                            name=f"p_co_max")  # 氢气压缩机投资容量（最大功率）
        p_co = [m.addVar(vtype="C", lb=0, name=f"p_co{t}") for t in range(period)]  # 氢气压缩机工作功率

        # ----hyd----#
        # p_hyd = [m.addVar(vtype="C", lb=0,
                         # ub=input_json["device"]["hyd"]["power_max"] * input_json["device"]["hyd"]["if_use"],
                         # name=f"p_hyd{t}") for t in range(period)]  # 水电使用量
        # ----xb----#
        # g_xb_max = m.addVar(vtype="C", lb=0,
                           # ub=input_json['device']['xb']['s_max'] * input_json['device']['xb']['if_use'],
                           # name=f"g_xb_max")  # 相变储能模块大小（投资容量）
        # s_xb = [m.addVar(vtype="C", lb=0, name=f"s_xb{t}") for t in range(period)]  # 相变储能模块在t时刻的储热量
        # g_xb = [m.addVar(vtype="C", lb=-1000000, name=f"g_xb{t}") for t in range(period)]  # 相变储热充放功率，正值充热，负值放热

        # ----whp----#
        p_whp_max = m.addVar(vtype="C", lb=0,
                             ub=OptimizationBody.device.whp.power_max * OptimizationBody.device.whp.power_already,
                             name=f"p_whp_max")  # 余热热泵投资容量（最大功率）
        p_whp = [m.addVar(vtype="C", lb=0, name=f"p_whp{t}") for t in range(period)]  # 余热热泵产热耗电量
        p_whpg = [m.addVar(vtype="C", lb=0, name=f"p_whpg{t}") for t in range(period)]  # 余热热泵产热耗电量
        p_whpq = [m.addVar(vtype="C", lb=0, name=f"p_whpq{t}") for t in range(period)]  # 余热热泵产热耗电量
        g_whp = [m.addVar(vtype="C", lb=0, name=f"g_whp{t}") for t in range(period)]  # 余热热泵产热
        q_whp = [m.addVar(vtype="C", lb=0, name=f"q_whp{t}") for t in range(period)]  # 余热热泵产冷

        # ----co180----#
        p_co180_max = m.addVar(vtype="C", lb=0,
                               ub= OptimizationBody.device.co180.power_max * OptimizationBody.device.co180.power_already,
                               name=f"p_co180_max")  # 余热热泵投资容量（最大功率）
        p_co180 = [m.addVar(vtype="C", lb=0, name=f"p_co180{t}") for t in range(period)]  # 高温压缩机耗电量
        m_co180 = [m.addVar(vtype="C", lb=0, name=f"m_co180{t}") for t in range(period)]

        # ----hp120----#
        p_hp120_max = m.addVar(vtype="C", lb=0,
                               ub= OptimizationBody.device.hp120.power_max * OptimizationBody.device.hp120.power_already,
                               name=f"p_hp120_max")  # 余热热泵投资容量（最大功率）
        p_hp120 = [m.addVar(vtype="C", lb=0, name=f"p_hp120{t}") for t in range(period)]  # 高温热泵耗电量
        m_hp120 = [m.addVar(vtype="C", lb=0, name=f"m_hp120{t}") for t in range(period)]
        g_hp120 = [m.addVar(vtype="C", lb=0, name=f"g_hp120{t}") for t in range(period)]

        # 用户自定义库中设备变量
        # 能量流顺序 0：电   1：热   2：冷   3：氢   4：气   5：自定义能量流1   6：自定义能量流2 ......

        return 'success'



