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
        #ele_load = OptimizationBody.objective_load#??????


        # ------------导入价格等数据------------#
        alpha_e = 0.5839                                                        #电网排放因子kg/kWh
        gas_price = 1.2                                                         #天然气价钱
        lambda_ele_in = OptimizationBody.trading.power_buy_8760_price           #每个小时的电价
        lambda_ele_out = OptimizationBody.trading.power_sell_price              #卖电价格
        lambda_g_out = OptimizationBody.trading.heat_sell_price                 #卖热价格
        lambda_h_out = OptimizationBody.trading.hydrogen_sell_price             #卖氢价格
        lambda_h = OptimizationBody.trading.hydrogen_buy_price                  #买氢价格
        cer = OptimizationBody.base.cer                                         #碳减排率
        lambda_steam120_in = OptimizationBody.trading.steam_buy[1].price        #120蒸汽购入价格
        lambda_steam120_out = OptimizationBody.trading.steam_sell[1].price     #120蒸汽出售价格
        lambda_steam180_in = OptimizationBody.trading.steam_buy[0].price        #180蒸汽购入价格
        lambda_steam180_out = OptimizationBody.trading.steam_sell[0].price      #180蒸汽出售价格
        c = 4.2 / 3600                                                          #水的比热容
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
        crf_gtw1 = crf(OptimizationBody.device)#???
        #crf_gtw2 = crf#???
        #crf_gtw3 = crf#???
        #crf_gtw4 = crf#???
        crf_co180 = crf(OptimizationBody.device.co180.crf)
        crf_hp120 = crf(OptimizationBody.device.hp120.crf)
        crf_co = crf(OptimizationBody.device.co.crf)
        #crf_hyd = crf(OptimizationBody.device)#???
        #crf_xb = crf(OptimizationBody.device.)#???
        crf_whp = crf(OptimizationBody.device.whp.crf)

        # --------------单位投资成本数据--------------#
        cost_fc = OptimizationBody.device.fc.cost + support_device(OptimizationBody.device.fc.cost,
                                                                   OptimizationBody.device.fc.se)
        #cost_el = OptimizationBody.device.el.cost + support_device(OptimizationBody.device.el.cost,
                                                                  # OptimizationBody.device.el.se)#???
        cost_hst = OptimizationBody.device.hst.cost + support_device(OptimizationBody.device.hst.cost,
                                                                     OptimizationBody.device.hst.se)
        cost_ht = OptimizationBody.device.ht.cost + support_device(OptimizationBody.device.ht.cost,
                                                                   OptimizationBody.device.ht.se)
        cost_ct = OptimizationBody.device.ct.cost + support_device(OptimizationBody.device.ct.cost,
                                                                   OptimizationBody.device.ct.se)
        #cost_pv = OptimizationBody.device.pv.cost + support_device(OptimizationBody.device.pv.cost,
                                                                 #  OptimizationBody.device.pv.se)#???
        capacity_wd = OptimizationBody.device.wd.capacity_unit
        #cost_wd = capacity_wd * OptimizationBody.device.wd.cost + support_device(OptimizationBody.device.wd.cost,
                                                                               #  OptimizationBody.device.wd.se)#???
        #cost_sc = OptimizationBody.device.sc.cost + support_device(OptimizationBody.device.sc.cost,
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

        return 'success'



