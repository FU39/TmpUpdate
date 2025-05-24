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
        """
        Args:
            dict (_type_): dict字典，读取负荷数据，包括光照强度，冷热电负荷。
            isloate (_type_): list，零一变量，表示是否允许电网买电，卖电，买氢,买天然气，买其他自定义能量流
            input_json: 从json文件中读取的数据
        """
        t0 = time.time()

        #------------导入自定义数据------------#
        custom_device_num = input_json['custom_device']['total']['num']  #自定义设备总数
        custom_energy_num = input_json['custom_energy']['total']['num']  #自定义能量流总数
        custom_storge_device_num = input_json['custom_device']['total']['storage_device_num']  #自定义储能设备总数

        #-------------负荷输入--------------# 
        # 在read_load.py文件中具体生成（read_load.py代码也需要将工业部分的负荷进行重构，未完成）   
        to_csv(dict, "debug_load.xls", custom_energy_num, custom_device_num, custom_storge_device_num)  # 暂存负荷数据方便debug

        #------------导入负荷数据------------#
        ele_load = dict['ele_load']  #电负荷
        # # for i in range(len(ele_load)):
        # #     if ele_load[i] < 2500:
        # #         ele_load[i] = ele_load[i] * 0.8
        # for i in range(len(ele_load)):
        #     ele_load[i] -= 1000
        #     # ele_load[i] *= 0.8
        g_demand = dict['g_demand']  #热负荷
        q_demand = dict['q_demand']  #冷负荷
        h_demand = dict['h_demand']  #氢负荷
        steam120_demand = dict['steam120_demand']  #120蒸汽负荷，单位吨
        steam180_demand = dict['steam180_demand']  #180蒸汽负荷，单位吨
        # gas_demand = dict['gas_demand']#天然气负荷
        r_solar = dict['r_solar']  #光照强度
        z_g_demand = dict["z_heat_mounth"]  #供热月份，8760h的01数据，1为供热，0为不供热
        z_q_demand = dict["z_cold_mounth"]  #供冷月份，8760h的01数据，1为供冷，0为不供冷

        # 添加风电数据
        wind_data = pd.read_csv(input_json['device']['wd']['file_name'])
        wind_power = list(wind_data['electricity'].fillna(0))
        wind_power = [i for i in wind_power]
        # 现在的风电数据是从GMT时间2019-01-01 00:00:00到2019-12-31 23:00:00的数据，
        # 对应的是从北京时间2019-01-01 08:00:00到2020-01-01 07:00:00的数据
        # 要将风电数据转换为从北京时间2020-01-01 00:00:00到2020-01-01 07:00:00，然后再接上从北京时间2019-01-01 08:00:00到2019-12-31 23:00:00的数据
        wind_power = wind_power[-8:] + wind_power[:-8]

        #------------导入价格等数据------------#
        alpha_e = 0.5839  # 电网排放因子kg/kWh
        gas_price = 1.2  # 天然气价钱
        lambda_ele_in = input_json['price']['TOU_power'] * 365  #每个小时的电价
        lambda_ele_out = input_json['price']['power_sale']  #卖电价格
        lambda_g_out = input_json['price']['heat_sale']  #卖热价格
        lambda_h_out = input_json['price']['hydrogen_sale']  #卖氢价格
        lambda_h = input_json['price']['hydrogen_price']  #买氢价格
        cer = input_json['calc_mode']['cer']  #碳减排率
        lambda_steam120_in = input_json['price']['steam120_price']  #卖电价格
        lambda_steam120_out = input_json['price']['steam120_sale']  #卖电价格
        lambda_steam180_in = input_json['price']['steam180_price']  #卖电价格
        lambda_steam180_out = input_json['price']['steam180_sale']  #卖电价格
        c = 4.2 / 3600  #水的比热容
        M = 1000000
        epsilon = 0.0000001

        #自定义能量流的价格和碳排
        cost_custom_energy = []
        ce_custom_energy = []
        for i in range(custom_energy_num):
            cost_custom_energy.append(input_json['custom_energy']['y' + str(i)]['cost'])  # 第i个能量流的单位kWh价格
            ce_custom_energy.append(input_json['custom_energy']['y' + str(i)]['ce'])  # 第i个能量流的单位碳排

        #------------导入测算模式------------#
        # if isloate_flag ==0:# 连网状态
        #     isloate = [input_json["calc_mode"]['grid']['p_pur_state'],input_json["calc_mode"]['grid']['p_sol_state'],input_json["calc_mode"]['grid']['h_pur_state'],input_json["calc_mode"]['isloate']['gas_pur_state']]
        #     for i in range(custom_energy_num):
        #         isloate.append(input_json["calc_mode"]['isloate']['y' + str(i) + '_pur_state'])

        # if isloate_flag ==1:# 离网状态不能买卖电
        #     isloate = [0,0,input_json["calc_mode"]['isloate']['h_pur_state'],input_json["calc_mode"]['isloate']['gas_pur_state']]
        #     for i in range(custom_energy_num):
        #         isloate.append(input_json["calc_mode"]['isloate']['y' + str(i) + '_pur_state'])

        #---------------------------基本设备库中的设备---------------------------#
        """
        基本设备库中设备符号解释:(20类)
            fc: 燃料电池     el: 电解槽     hst: 储氢罐       ht: 储热水箱
            ct: 储冷水箱     pv: 光伏板     sc: 太阳能集热器   eb: 电锅炉
            ac: 空调        hp: 空气源热泵  ghp: 浅层地源热泵  gtw: 浅层地埋井      ghp_deep: 中深层地源热泵     gtw11234: 不同深度的地埋井
            co: 氢气压缩机   hyd: 水电      hp120:高温热泵     co180:高温蒸汽压缩机 xb: 相变储热模块   whp: 余热热泵   
        """
        #---------------年化收益率数据--------------#
        crf_fc = crf(input_json['device']['fc']['crf'])
        crf_el = crf(input_json['device']['el']['crf'])
        crf_hst = crf(input_json['device']['hst']['crf'])
        crf_ht = crf(input_json['device']['ht']['crf'])
        crf_ct = crf(input_json['device']['ct']['crf'])
        crf_pv = crf(input_json['device']['pv']['crf'])
        crf_wd = crf(input_json['device']['wd']['crf'])
        crf_sc = crf(input_json['device']['sc']['crf'])
        crf_eb = crf(input_json['device']['eb']['crf'])
        crf_ac = crf(input_json['device']['ac']['crf'])
        crf_hp = crf(input_json['device']['hp']['crf'])
        crf_ghp = crf(input_json['device']['ghp']['crf'])
        crf_ghp_deep = crf(input_json['device']['ghp_deep']['crf'])
        crf_gtw = crf(input_json['device']['gtw']['crf'])
        crf_gtw1 = crf(input_json['device']['gtw1']['crf'])
        crf_gtw2 = crf(input_json['device']['gtw2']['crf'])
        crf_gtw3 = crf(input_json['device']['gtw3']['crf'])
        crf_gtw4 = crf(input_json['device']['gtw4']['crf'])
        crf_co180 = crf(input_json['device']['co180']['crf'])
        crf_hp120 = crf(input_json['device']['hp120']['crf'])
        crf_co = crf(input_json['device']['co']['crf'])
        crf_hyd = crf(input_json['device']['hyd']['crf'])
        crf_xb = crf(input_json['device']['xb']['crf'])
        crf_whp = crf(input_json['device']['whp']['crf'])

        #--------------单位投资成本数据--------------#
        cost_fc = input_json['device']['fc']['cost'] + support_device(input_json['device']['fc']['cost'],
                                                                    input_json['device']['fc']['se'])
        cost_el = input_json['device']['el']['cost'] + support_device(input_json['device']['el']['cost'],
                                                                    input_json['device']['el']['se'])
        cost_hst = input_json['device']['hst']['cost'] + support_device(input_json['device']['hst']['cost'],
                                                                        input_json['device']['hst']['se'])
        cost_ht = input_json['device']['ht']['cost'] + support_device(input_json['device']['ht']['cost'],
                                                                    input_json['device']['ht'][
                                                                        'se'])  # rmb/kg 180 # yuan/kwh
        cost_ct = input_json['device']['ct']['cost'] + support_device(input_json['device']['ct']['cost'],
                                                                    input_json['device']['ct'][
                                                                        'se'])  # rmb/kg 180 # yuan/kwh
        cost_pv = input_json['device']['pv']['cost'] + support_device(input_json['device']['pv']['cost'],
                                                                    input_json['device']['pv']['se'])
        capacity_wd = input_json['device']['wd']['capacity']
        cost_wd = input_json['device']['wd']['cost'] * capacity_wd + support_device(
            input_json['device']['wd']['cost'] * capacity_wd, input_json['device']['wd']['se'])
        cost_sc = input_json['device']['sc']['cost'] + support_device(input_json['device']['sc']['cost'],
                                                                    input_json['device']['sc']['se'])
        cost_eb = input_json['device']['eb']['cost'] + support_device(input_json['device']['eb']['cost'],
                                                                    input_json['device']['eb']['se'])
        cost_ac = input_json['device']['ac']['cost'] + support_device(input_json['device']['ac']['cost'],
                                                                    input_json['device']['ac']['se'])
        cost_hp = input_json['device']['hp']['cost'] + support_device(input_json['device']['hp']['cost'],
                                                                    input_json['device']['hp']['se'])
        cost_ghp = input_json['device']['ghp']['cost'] + support_device(input_json['device']['ghp']['cost'],
                                                                        input_json['device']['ghp']['se'])
        cost_ghp_deep = input_json['device']['ghp_deep']['cost'] + support_device(input_json['device']['ghp_deep']['cost'],
                                                                                input_json['device']['ghp_deep']['se'])
        cost_gtw = input_json['device']['gtw']['cost'] + support_device(input_json['device']['gtw']['cost'],
                                                                        input_json['device']['gtw']['se'])
        cost_gtw1 = input_json['device']['gtw1']['cost'] + support_device(input_json['device']['gtw1']['cost'],
                                                                        input_json['device']['gtw1']['se'])
        cost_gtw2 = input_json['device']['gtw2']['cost'] + support_device(input_json['device']['gtw2']['cost'],
                                                                        input_json['device']['gtw2']['se'])
        cost_gtw3 = input_json['device']['gtw3']['cost'] + support_device(input_json['device']['gtw3']['cost'],
                                                                        input_json['device']['gtw3']['se'])
        cost_gtw4 = input_json['device']['gtw4']['cost'] + support_device(input_json['device']['gtw4']['cost'],
                                                                        input_json['device']['gtw4']['se'])
        cost_co = input_json['device']['co']['cost'] + support_device(input_json['device']['co']['cost'],
                                                                    input_json['device']['co']['se'])
        cost_co180 = input_json['device']['co180']['cost'] + support_device(input_json['device']['co180']['cost'],
                                                                            input_json['device']['co180']['se'])
        cost_hp120 = input_json['device']['hp120']['cost'] + support_device(input_json['device']['hp120']['cost'],
                                                                            input_json['device']['hp120']['se'])
        cost_hyd = input_json['device']['hyd']['cost'] + support_device(input_json['device']['hyd']['cost'],
                                                                        input_json['device']['hyd']['se'])
        cost_xb = input_json['device']['xb']['cost'] + support_device(input_json['device']['xb']['cost'],
                                                                    input_json['device']['xb']['se'])
        cost_whp = input_json['device']['whp']['cost'] + support_device(input_json['device']['whp']['cost'],
                                                                        input_json['device']['whp']['se'])

        #---------------效率数据，包括产热、制冷、发电、热转换等--------------#
        #----fc----#
        eta_ex = 0.95  #fc产的热通过热交换器后的剩余热量系数
        k_fc_p = input_json['device']['fc']['eta_fc_p']  #氢转电系数kg——>kWh
        k_fc_g = input_json['device']['fc']['eta_ex_g']  #氢转热系数kg——>kWh
        #----el----#
        k_el = input_json['device']['el']['beta_el']  #电转氢效率
        #----pv----#
        eta_pv = input_json['device']['pv']['beta_pv']  #单位面积下光转电效率
        #----sc----#
        k_sc = input_json['device']['sc']['beta_sc']  #单位面积下光转热效率
        theta_ex = input_json['device']['sc']['theta_ex']  #sc收集的热通过热交换器后的剩余热量系数
        #----eb----#
        k_eb = input_json['device']['eb']['beta_eb']  #电转热效率
        #----ac----#
        k_ac = input_json['device']['ac']['beta_ac']  #电转冷效率
        #----hp----#
        k_hp_g = input_json['device']['hp']['beta_hpg']  #电转热效率
        k_hp_q = input_json['device']['hp']['beta_hpq']  #电转冷效率
        #----ghp----#
        k_ghp_g = input_json['device']['ghp']['beta_ghpg']  #电转热效率-dict['load_sort']*0.3？
        k_ghp_q = input_json['device']['ghp']['beta_ghpq']  #电转冷效率
        k_ghp_deep_g = input_json['device']['ghp_deep']['beta_ghpg']  #电转热效率-dict['load_sort']*0.3？
        #----gtw----#
        p_gtw = input_json['device']['gtw']['beta_gtw']  #井和热泵有关联，制热量-电功率=取热量，制冷量+电功率=灌热量
        p_gtw1 = input_json['device']['gtw1']['beta_gtw']
        p_gtw2 = input_json['device']['gtw2']['beta_gtw']
        p_gtw3 = input_json['device']['gtw3']['beta_gtw']
        p_gtw4 = input_json['device']['gtw4']['beta_gtw']
        #----co----#
        k_co = input_json['device']['co']['beta_co']  #需要压缩氢气量转氢气压缩机功率的效率
        #----hyd----#
        water_hyd_peak = input_json["device"]['hyd']['peak']  #水电的发电功率上限
        #----xb----#
        k_xb = input_json['device']['xb']['p_kwh']  #单位质量的相变储能材料能够储放的热量
        #----whp----#
        k_whp = input_json['device']['whp']['beta_whp']  #电转热，以及热转冷的效率
        #----co180----#

        #----hp120----#
        cop_hp120 = input_json['device']['hp120']['cop']

        #----------------特殊场景下的数据导入---------------#
        #含有水电场景下的接口
        if input_json["device"]['hyd']['flag'] == 1:  # 是1，代表有水电场景
            water = []  #水电
            book = xlrd.open_workbook('load/water.xls')
            data = book.sheet_by_index(0)
            for l in range(0, 8760):
                water.append(data.cell(l, 0).value)
            if input_json["device"]['hyd']['peak'] != -1:  #不是-1，代表需要根据水电峰值对发电功率进行调整
                max_water = max(water)
                water = [water[i] * water_hyd_peak / max_water for i in range(len(water))]

        #---------------------------用户自定义设备---------------------------#

        #---------------第i个自定义设备的年化收益率数据---------------#   
        crf_x = []
        for i in range(custom_device_num):
            crf_x.append(crf(input_json['custom_device']['x' + str(i)]['crf']))

        #--------------第i个自定义设备的单位投资成本--------------#
        cost_x = []
        for i in range(custom_device_num):
            cost_x.append(input_json['custom_device']['x' + str(i)]['cost'] + support_device(
                input_json['custom_device']['x' + str(i)]['cost'], input_json['custom_device']['x' + str(i)]['se']))

        cost_storage_ele = []
        cost_storage_hot = []
        cost_storage_cold = []
        cost_storage_hydr = []
        cost_storage_gas = []
        cost_storage_x = []
        custom_storge_device_num = input_json['custom_device']['total']['storage_device_num']
        for j in range(custom_storge_device_num[0]):
            cost_storage_ele.append(input_json['custom_device']['storage_device_ele' + str(j)]['cost'] + support_device(
                input_json['custom_device']['storage_device_ele' + str(j)]['cost'],
                input_json['custom_device']['storage_device_ele' + str(j)]['se']))
        for j in range(custom_storge_device_num[1]):
            cost_storage_hot.append(input_json['custom_device']['storage_device_hot' + str(j)]['cost'] + support_device(
                input_json['custom_device']['storage_device_hot' + str(j)]['cost'],
                input_json['custom_device']['storage_device_hot' + str(j)]['se']))
        for j in range(custom_storge_device_num[2]):
            cost_storage_cold.append(input_json['custom_device']['storage_device_cold' + str(j)]['cost'] + support_device(
                input_json['custom_device']['storage_device_cold' + str(j)]['cost'],
                input_json['custom_device']['storage_device_cold' + str(j)]['se']))
        for j in range(custom_storge_device_num[3]):
            cost_storage_hydr.append(input_json['custom_device']['storage_device_hydr' + str(j)]['cost'] + support_device(
                input_json['custom_device']['storage_device_hydr' + str(j)]['cost'],
                input_json['custom_device']['storage_device_hydr' + str(j)]['se']))
        for j in range(custom_storge_device_num[4]):
            cost_storage_gas.append(input_json['custom_device']['storage_device_gas' + str(j)]['cost'] + support_device(
                input_json['custom_device']['storage_device_gas' + str(j)]['cost'],
                input_json['custom_device']['storage_device_gas' + str(j)]['se']))
        for i in range(custom_energy_num):
            cost_i_storage_x = []
            for j in range(custom_storge_device_num[5 + i]):
                cost_i_storage_x.append(
                    input_json['custom_device']['storage_device_x' + str(i) + str(j)]['cost'] + support_device(
                        input_json['custom_device']['storage_device_x' + str(i) + str(j)]['cost'],
                        input_json['custom_device']['storage_device_x' + str(i) + str(j)]['se']))
            cost_storage_x.append(cost_i_storage_x)

        #-----------------------自定义设备的效率数据----------------------#
        #------(5+custom_energy_num)*(5+custom_energy_num-1)种组合------#
        k_custom_device = np.zeros((custom_device_num, 5 + custom_energy_num, 5 + custom_energy_num))
        for i in range(custom_device_num):
            for j in range(5 + custom_energy_num):
                for k in range(5 + custom_energy_num):
                    if j == k:
                        k_custom_device[i][j][k] = 0
                    else:
                        k_custom_device[i][j][k] = input_json['custom_device']['x' + str(i)]['coefficient'][j][k]

        #-----------------------建立优化模型----------------------------#
        #运行天数
        period = 8760

        #建立模型
        m = Model("mip")

        #---------------创建变量--------------#
        # 规划容量部分变量
        op_sum = m.addVar(vtype="C", lb=-10000000000, name=f"op_sum")  # 运行费用:买电-卖电+买氢+买水电
        op_sum_pure = m.addVar(vtype="C", lb=-10000000000, name=f"op_sum_pure")  # 运行费用:买电-卖电+买氢+买水电

        capex_sum = m.addVar(vtype="C", lb=0, name=f"capex_sum")  # 总设备投资
        capex_crf = m.addVar(vtype="C", lb=0, name=f"capex_crf")  # 总设备年化收益
        ce_h = m.addVar(vtype="C", lb=0, name="ce_h")  # 碳排放量（买电*碳排因子）

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
        y_pur = [[m.addVar(vtype="C", lb=0, name=f"y_pur{i}{t}") for t in range(period)] for i in
                range(custom_energy_num)]  # 买天然气

        # cost_c = m.addVar(vtype="C", lb=0, name=f"cost_c") # 电、热、冷负荷直接买电开设备来满足所需的钱
        # cost_c_ele = m.addVar(vtype="C", lb=0, name=f"cost_c_ele") # 电负荷直接买电满足所需的钱
        # cost_c_heat = m.addVar(vtype="C", lb=0, name=f"cost_c_heat") # 热负荷通过买电使用电热锅炉满足所需的钱
        # cost_c_cool = m.addVar(vtype="C", lb=0, name=f"cost_c_cool") # 冷负荷通过买电使用空气源热泵满足所需的钱

        # 基本设备库中设备变量
        #----fc----#
        z_fc = [m.addVar(lb=0, ub=1, vtype="B", name=f"z_fc{t}") for t in range(period)]
        p_fc_max = m.addVar(vtype="C", lb=0,
                            ub=input_json['device']['fc']['power_max'] * input_json['device']['fc']['if_use'],
                            name=f"p_fc_max")  # fc的投资容量（最大功率）
        g_fc = [m.addVar(vtype="C", lb=0, name=f"g_fc{t}") for t in range(period)]  # 燃料电池产热量
        p_fc = [m.addVar(vtype="C", lb=0, name=f"p_fc{t}") for t in range(period)]  # 燃料电池产电量
        h_fc = [m.addVar(vtype="C", lb=0, name=f"h_fc{t}") for t in range(period)]  # 燃料电池用氢量

        #----el----#
        p_el_max = m.addVar(vtype="C", lb=0,
                            ub=input_json['device']['el']['power_max'] * input_json['device']['el']['if_use'],
                            name="p_el_max")  # el的投资容量（最大功率）
        h_el = [m.addVar(vtype="C", lb=0, name=f"h_el{t}") for t in range(period)]  # 电解槽产氢量
        p_el = [m.addVar(vtype="C", lb=0, name=f"p_el{t}") for t in range(period)]  # 电解槽功率

        #----hst----#
        hst = m.addVar(vtype="C", lb=0,
                    ub=input_json['device']['hst']['sto_max'] * input_json['device']['hst']['if_use'],
                    name=f"hst")  # 储氢罐规划容量
        h_sto = [m.addVar(vtype="C", lb=0, name=f"h_sto{t}") for t in range(period)]  # 储氢罐t时刻储氢量

        #----ht----#
        m_ht = m.addVar(vtype="C", lb=0,
                        ub=input_json['device']['ht']['water_max'] * input_json['device']['ht']['if_use'],
                        name=f"m_ht")  # 储热罐的规划容量
        g_ht_in = [m.addVar(vtype="C", lb=0, name=f"g_ht_in{t}") for t in range(period)]
        g_ht_out = [m.addVar(vtype="C", lb=0, name=f"g_ht_out{t}") for t in range(period)]
        g_ht = [m.addVar(vtype="C", lb=0, name=f"g_ht{t}") for t in range(period)]  # 存储的热量
        # 写完约束之后再看看有没有需要创建的变量

        #----ct----#
        m_ct = m.addVar(vtype="C", lb=0,
                        ub=input_json['device']['ct']['water_max'] * input_json['device']['ct']['if_use'],
                        name=f"m_ct")  # 储冷罐的规划容量
        q_ct_in = [m.addVar(vtype="C", lb=0, name=f"q_ct_in{t}") for t in range(period)]
        q_ct_out = [m.addVar(vtype="C", lb=0, name=f"q_ct_out{t}") for t in range(period)]  # 写完约束之后再看看有没有需要创建的变量
        q_ct = [m.addVar(vtype="C", lb=0, name=f"q_ct{t}") for t in range(period)]  # 存储的冷量

        #----pv----#
        s_pv = m.addVar(vtype="C", lb=0, name=f"s_pv")  #光伏板投资面积
        p_pv_max = m.addVar(vtype="C", lb=0, name=f"p_pv_max")  #光伏板投资面积
        p_pv = [m.addVar(vtype="C", lb=0, ub=input_json['device']['pv']['power_max'] * input_json['device']['pv']['if_use'],
                        name=f"p_pv{t}") for t in range(period)]  # 光伏板发电功率

        # ----wd----#    p_pv_max = [m.addVar(vtype="C", lb=0,ub= input_json['device']['pv']['power_max']*input_json['device']['pv']['if_use'], name=f"p_pv{t}") for t in range(period)]# 光伏板发电功率
        num_wd = m.addVar(vtype="INTEGER", lb=0,
                        ub=input_json['device']['wd']['number_max'] * input_json['device']['wd']['if_use'],
                        name=f"num_wd")  # 风电投资数量
        p_wd = [m.addVar(vtype="C", lb=0, name=f"p_wd{t}") for t in range(period)]  # 风电发电功率

        #----sc----#
        s_sc = m.addVar(vtype="C", lb=0,
                        ub=input_json['device']['sc']['area_max'] * input_json['device']['sc']['if_use'],
                        name=f"s_sc")  #太阳能集热器投资面积
        g_sc = [m.addVar(vtype="C", lb=0, name=f"g_sc{t}") for t in range(period)]  # 太阳能集热器收集的热量

        #----eb----#
        p_eb_max = m.addVar(vtype="C", lb=0,
                            ub=input_json['device']['eb']['power_max'] * input_json['device']['eb']['if_use'],
                            name=f"p_eb_max")  # 电锅炉投资容量（最大功率）
        g_eb = [m.addVar(vtype="C", lb=0, name=f"g_eb{t}") for t in range(period)]  # 电锅炉产热
        p_eb = [m.addVar(vtype="C", lb=0, name=f"p_eb{t}") for t in range(period)]  # 电锅炉耗电

        #----ac----#
        p_ac_max = m.addVar(vtype="C", lb=0,
                            ub=input_json["device"]["ac"]["power_max"] * input_json['device']['ac']['if_use'],
                            name=f"p_ac_max")  # 空调投资容量（最大功率）
        p_ac = [m.addVar(vtype="C", lb=0, name=f"p_ac{t}") for t in range(period)]  # 电锅炉产热
        q_ac = [m.addVar(vtype="C", lb=0, name=f"q_ac{t}") for t in range(period)]  # 电锅炉耗电

        #----hp----#
        p_hp_max = m.addVar(vtype="C", lb=0,
                            ub=input_json["device"]["hp"]["power_max"] * input_json['device']['hp']['if_use'],
                            name=f"p_hp_max")  # 空气源热泵投资容量（最大功率）
        p_hp = [m.addVar(vtype="C", lb=0, name=f"p_hp{t}") for t in range(period)]  #热泵产热耗电
        p_hpc = [m.addVar(vtype="C", lb=0, name=f"p_hpc{t}") for t in range(period)]  #热泵产冷的耗电
        q_hp = [m.addVar(vtype="C", lb=0, name=f"q_hp{t}") for t in range(period)]  # 热泵产冷
        g_hp = [m.addVar(vtype="C", lb=0, name=f"g_hp{t}") for t in range(period)]  # 热泵产热

        #----ghp----#
        p_ghp_max = m.addVar(vtype="C", lb=0,
                            ub=input_json["device"]["ghp"]["power_max"] * input_json['device']['ghp']['if_use'],
                            name=f"p_ghp_max")  # 地源热泵投资容量（最大功率）
        p_ghp = [m.addVar(vtype="C", lb=0, name=f"p_ghp{t}") for t in range(period)]  #热泵产热耗电
        p_ghpc = [m.addVar(vtype="C", lb=0, name=f"p_ghpc{t}") for t in range(period)]  #热泵产冷的耗电
        g_ghp = [m.addVar(vtype="C", lb=0, name=f"g_ghp{t}") for t in range(period)]  # 热泵产热
        q_ghp = [m.addVar(vtype="C", lb=0, name=f"q_ghp{t}") for t in range(period)]  # 热泵产冷
        g_ghp_gr = [m.addVar(vtype="C", lb=0, name=f"g_ghp_gr{t}") for t in range(period)]  # 热泵灌热
        p_ghp_deep_max = m.addVar(vtype="C", lb=0,
                                ub=input_json["device"]["ghp_deep"]["power_max"] * input_json['device']['ghp_deep'][
                                    'if_use'],
                                name=f"p_ghp_deep_max")  # 地源热泵投资容量（最大功率）
        p_ghp_deep = [m.addVar(vtype="C", lb=0, name=f"p_ghp_deep{t}") for t in range(period)]  #热泵产热耗电
        g_ghp_deep = [m.addVar(vtype="C", lb=0, name=f"g_ghp_deep{t}") for t in range(period)]  # 热泵产热
        #----gtw----#
        num_gtw = m.addVar(vtype="INTEGER", lb=0,
                        ub=input_json['device']['gtw']['number_max'] * input_json['device']['gtw']['if_use'],
                        name='num_gtw')  # 地热井投资数量
        num_gtw1 = m.addVar(vtype="INTEGER", lb=0,
                            ub=input_json['device']['gtw1']['number_max'] * input_json['device']['gtw1']['if_use'],
                            name='num_gtw1')  # 2200深度地热井投资数量
        num_gtw2 = m.addVar(vtype="INTEGER", lb=0,
                            ub=input_json['device']['gtw2']['number_max'] * input_json['device']['gtw2']['if_use'],
                            name='num_gtw2')  # 2500深度地热井投资数量
        num_gtw3 = m.addVar(vtype="INTEGER", lb=0,
                            ub=input_json['device']['gtw3']['number_max'] * input_json['device']['gtw3']['if_use'],
                            name='num_gtw3')  # 2600深度地热井投资数量
        num_gtw4 = m.addVar(vtype="INTEGER", lb=0,
                            ub=input_json['device']['gtw4']['number_max'] * input_json['device']['gtw4']['if_use'],
                            name='num_gtw4')  # 2700深度地热井投资数量

        #----co----#
        p_co_max = m.addVar(vtype="C", lb=0,
                            ub=input_json["device"]["co"]["power_max"] * input_json["device"]["co"]["if_use"],
                            name=f"p_co_max")  # 氢气压缩机投资容量（最大功率）
        p_co = [m.addVar(vtype="C", lb=0, name=f"p_co{t}") for t in range(period)]  # 氢气压缩机工作功率

        #----hyd----#
        p_hyd = [m.addVar(vtype="C", lb=0,
                        ub=input_json["device"]["hyd"]["power_max"] * input_json["device"]["hyd"]["if_use"],
                        name=f"p_hyd{t}") for t in range(period)]  # 水电使用量

        #----xb----#
        g_xb_max = m.addVar(vtype="C", lb=0,
                            ub=input_json['device']['xb']['s_max'] * input_json['device']['xb']['if_use'],
                            name=f"g_xb_max")  # 相变储能模块大小（投资容量）
        s_xb = [m.addVar(vtype="C", lb=0, name=f"s_xb{t}") for t in range(period)]  # 相变储能模块在t时刻的储热量
        g_xb = [m.addVar(vtype="C", lb=-1000000, name=f"g_xb{t}") for t in range(period)]  #相变储热充放功率，正值充热，负值放热

        #----whp----#
        p_whp_max = m.addVar(vtype="C", lb=0,
                            ub=input_json["device"]["whp"]["power_max"] * input_json['device']['whp']['if_use'],
                            name=f"p_whp_max")  # 余热热泵投资容量（最大功率）
        p_whp = [m.addVar(vtype="C", lb=0, name=f"p_whp{t}") for t in range(period)]  # 余热热泵产热耗电量
        p_whpg = [m.addVar(vtype="C", lb=0, name=f"p_whpg{t}") for t in range(period)]  # 余热热泵产热耗电量
        p_whpq = [m.addVar(vtype="C", lb=0, name=f"p_whpq{t}") for t in range(period)]  # 余热热泵产热耗电量
        g_whp = [m.addVar(vtype="C", lb=0, name=f"g_whp{t}") for t in range(period)]  # 余热热泵产热
        q_whp = [m.addVar(vtype="C", lb=0, name=f"q_whp{t}") for t in range(period)]  # 余热热泵产冷

        #----co180----#
        p_co180_max = m.addVar(vtype="C", lb=0,
                            ub=input_json["device"]["co180"]["power_max"] * input_json['device']['co180']['if_use'],
                            name=f"p_co180_max")  # 余热热泵投资容量（最大功率）
        p_co180 = [m.addVar(vtype="C", lb=0, name=f"p_co180{t}") for t in range(period)]  # 高温压缩机耗电量
        m_co180 = [m.addVar(vtype="C", lb=0, name=f"m_co180{t}") for t in range(period)]

        #----hp120----#
        p_hp120_max = m.addVar(vtype="C", lb=0,
                            ub=input_json["device"]["hp120"]["power_max"] * input_json['device']['hp120']['if_use'],
                            name=f"p_hp120_max")  # 余热热泵投资容量（最大功率）
        p_hp120 = [m.addVar(vtype="C", lb=0, name=f"p_hp120{t}") for t in range(period)]  # 高温热泵耗电量
        m_hp120 = [m.addVar(vtype="C", lb=0, name=f"m_hp120{t}") for t in range(period)]
        g_hp120 = [m.addVar(vtype="C", lb=0, name=f"g_hp120{t}") for t in range(period)]

        # 用户自定义库中设备变量
        # 能量流顺序 0：电   1：热   2：冷   3：氢   4：气   5：自定义能量流1   6：自定义能量流2 ......
        x_plan = [m.addVar(vtype="C", lb=0, name=f"x_plan{i}") for i in range(custom_device_num)]  # 自定义设备i的  规划容量
        x_j_in = [
            [[m.addVar(vtype="C", lb=0, name=f"x_j_in{j}{i}{t}") for t in range(period)] for i in range(custom_device_num)]
            for j in range(custom_energy_num + 5)]  # 自定义设备i的  第j个（自定义能量流+5种已知能量流）的  输入变量
        x_j_out = [
            [[m.addVar(vtype="C", lb=0, name=f"x_j_out{j}{i}{t}") for t in range(period)] for i in range(custom_device_num)]
            for j in range(custom_energy_num + 5)]  # 自定义设备i的  第j个（自定义能量流+5种已知能量流）的  输出变量

        # 自定义储能设备的设备变量
        # TODO：可以改进成为矩阵形式，没必要用那么多代码来写（需要在变量设定、约束、目标函数capex_sum上进行修改）
        s_i_hot_plan = [m.addVar(vtype="C", lb=0, name=f"s_i_hot_plan{i}") for i in range(custom_storge_device_num[1])]
        s_i_hot_state = [[m.addVar(vtype="C", lb=0, name=f"s_i_hot_state{i}{t}") for t in range(period)] for i in
                        range(custom_storge_device_num[1])]
        s_i_hot_out = [[m.addVar(vtype="C", lb=0, name=f"s_i_hot_out{i}{t}") for t in range(period)] for i in
                    range(custom_storge_device_num[1])]
        s_i_hot_in = [[m.addVar(vtype="C", lb=0, name=f"s_i_hot_in{i}{t}") for t in range(period)] for i in
                    range(custom_storge_device_num[1])]

        s_i_cold_plan = [m.addVar(vtype="C", lb=0, name=f"s_i_cold_plan{i}") for i in range(custom_storge_device_num[2])]
        s_i_cold_state = [[m.addVar(vtype="C", lb=0, name=f"s_i_cold_state{i}{t}") for t in range(period)] for i in
                        range(custom_storge_device_num[2])]
        s_i_cold_out = [[m.addVar(vtype="C", lb=0, name=f"s_i_cold_out{i}{t}") for t in range(period)] for i in
                        range(custom_storge_device_num[2])]
        s_i_cold_in = [[m.addVar(vtype="C", lb=0, name=f"s_i_cold_in{i}{t}") for t in range(period)] for i in
                    range(custom_storge_device_num[2])]

        s_i_ele_plan = [m.addVar(vtype="C", lb=0, name=f"s_i_ele_plan{i}") for i in range(custom_storge_device_num[0])]
        s_i_ele_state = [[m.addVar(vtype="C", lb=0, name=f"s_i_ele_state{i}{t}") for t in range(period)] for i in
                        range(custom_storge_device_num[0])]
        s_i_ele_out = [[m.addVar(vtype="C", lb=0, name=f"s_i_ele_out{i}{t}") for t in range(period)] for i in
                    range(custom_storge_device_num[0])]
        s_i_ele_in = [[m.addVar(vtype="C", lb=0, name=f"s_i_ele_in{i}{t}") for t in range(period)] for i in
                    range(custom_storge_device_num[0])]

        s_i_hydr_plan = [m.addVar(vtype="C", lb=0, name=f"s_i_hydr_plan{i}") for i in range(custom_storge_device_num[3])]
        s_i_hydr_state = [[m.addVar(vtype="C", lb=0, name=f"s_i_hydr_state{i}{t}") for t in range(period)] for i in
                        range(custom_storge_device_num[3])]
        s_i_hydr_out = [[m.addVar(vtype="C", lb=0, name=f"s_i_hydr_out{i}{t}") for t in range(period)] for i in
                        range(custom_storge_device_num[3])]
        s_i_hydr_in = [[m.addVar(vtype="C", lb=0, name=f"s_i_hydr_in{i}{t}") for t in range(period)] for i in
                    range(custom_storge_device_num[3])]

        s_i_gas_plan = [m.addVar(vtype="C", lb=0, name=f"s_i_gas_plan{i}") for i in range(custom_storge_device_num[4])]
        s_i_gas_state = [[m.addVar(vtype="C", lb=0, name=f"s_i_gas_state{i}{t}") for t in range(period)] for i in
                        range(custom_storge_device_num[4])]
        s_i_gas_out = [[m.addVar(vtype="C", lb=0, name=f"s_i_gas_out{i}{t}") for t in range(period)] for i in
                    range(custom_storge_device_num[4])]
        s_i_gas_in = [[m.addVar(vtype="C", lb=0, name=f"s_i_gas_in{i}{t}") for t in range(period)] for i in
                    range(custom_storge_device_num[4])]

        s_i_xj_plan = [
            [m.addVar(vtype="C", lb=0, name=f"s_i_xj_plan{j}{i}") for i in range(custom_storge_device_num[5 + j])] for j in
            range(custom_energy_num)]
        s_i_xj_state = [[[m.addVar(vtype="C", lb=0, name=f"s_i_xj_state{j}{i}{t}") for t in range(period)] for i in
                        range(custom_storge_device_num[5 + j])] for j in range(custom_energy_num)]
        s_i_xj_out = [[[m.addVar(vtype="C", lb=0, name=f"s_i_xj_out{j}{i}{t}") for t in range(period)] for i in
                    range(custom_storge_device_num[5 + j])] for j in range(custom_energy_num)]
        s_i_xj_in = [[[m.addVar(vtype="C", lb=0, name=f"s_i_xj_in{j}{i}{t}") for t in range(period)] for i in
                    range(custom_storge_device_num[5 + j])] for j in range(custom_energy_num)]

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



########### 添加约束 #############
        #---------------创建约束条件--------------#
        #----------------------------------------------------------#
        # 规划容量上下限约束

        # 基本设备库中设备的规划容量上下限，与if_use相关联，判断前端是否勾选了该设备：1，勾选使用；0，未勾选使用
        #----fc----#
        m.addCons(p_fc_max <= crf(OptimizationBody.device.fc.power_max) * crf(OptimizationBody.device.fc.power_already))
        m.addCons(p_fc_max >= crf(OptimizationBody.device.fc.power_min) * crf(OptimizationBody.device.fc.power_already))

        #----el----#
        m.addCons(p_el_max <= crf(OptimizationBody.device.el.power_max) * crf(OptimizationBody.device.el.nm3_already))
        m.addCons(p_el_max <= 50 * crf(OptimizationBody.device.el.nm3_max) * crf(OptimizationBody.device.el.nm3_already) / 11.2)
        m.addCons(p_el_max >= 50 * crf(OptimizationBody.device.el.nm3_min) * crf(OptimizationBody.device.el.nm3_already) / 11.2)
        m.addCons(p_el_max >= crf(OptimizationBody.device.el.nm3_min) * crf(OptimizationBody.device.el.nm3_already))

        #----hst----#
        m.addCons(hst <= crf(OptimizationBody.device.hst.sto_max) * crf(OptimizationBody.device.hst.sto_already))
        m.addCons(hst >= crf(OptimizationBody.device.hst.sto_min) * crf(OptimizationBody.device.hst.sto_already))

        #----ht----#
        m.addCons(m_ht <= crf(OptimizationBody.device.ht.water_max) * crf(OptimizationBody.device.ht.water_already))
        m.addCons(m_ht >= crf(OptimizationBody.device.ht.water_min) * crf(OptimizationBody.device.ht.water_already))

        #----ct----#
        m.addCons(m_ct <= crf(OptimizationBody.device.ct.water_max) * crf(OptimizationBody.device.ct.water_already))
        m.addCons(m_ct >= crf(OptimizationBody.device.ct.water_min) * crf(OptimizationBody.device.ct.water_already))

        #----pv----#
        m.addCons(p_pv_max <= crf(OptimizationBody.device.pv.power_max) * crf(OptimizationBody.device.pv.power_already))
        m.addCons(p_pv_max >= crf(OptimizationBody.device.pv.power_min) * crf(OptimizationBody.device.pv.power_already))

        # ----wd----#
        m.addCons(num_wd <= crf(OptimizationBody.device.wd.number_max) * crf(OptimizationBody.device.wd.number_already))
        m.addCons(num_wd >= crf(OptimizationBody.device.wd.number_min) * crf(OptimizationBody.device.wd.number_already))

        #----sc----#
        m.addCons(s_sc <= crf(OptimizationBody.device.sc.area_max) * crf(OptimizationBody.device.sc.area_already))
        m.addCons(s_sc >= crf(OptimizationBody.device.sc.area_min) * crf(OptimizationBody.device.sc.area_already))

        #----eb----#
        m.addCons(p_eb_max <= crf(OptimizationBody.device.eb.power_max) * crf(OptimizationBody.device.eb.power_already))
        m.addCons(p_eb_max >= crf(OptimizationBody.device.eb.power_min) * crf(OptimizationBody.device.eb.power_already))

        #----ac----#
        m.addCons(p_ac_max <= crf(OptimizationBody.device.ac.power_max) * crf(OptimizationBody.device.ac.power_already))
        m.addCons(p_ac_max >= crf(OptimizationBody.device.ac.power_min) * crf(OptimizationBody.device.ac.power_already))

        #----hp----#
        m.addCons(p_hp_max <= crf(OptimizationBody.device.hp.power_max) * crf(OptimizationBody.device.hp.power_already))
        m.addCons(p_hp_max >= crf(OptimizationBody.device.hp.power_min) * crf(OptimizationBody.device.hp.power_already))

        #----ghp----#
        m.addCons(p_ghp_max <= crf(OptimizationBody.device.ghp.power_max) * crf(OptimizationBody.device.ghp.power_already))
        m.addCons(p_ghp_max >= crf(OptimizationBody.device.ghp.power_min) * crf(OptimizationBody.device.ghp.power_already))
        m.addCons(
            p_ghp_deep_max <= crf(OptimizationBody.device.ghp_deep.power_max) * crf(OptimizationBody.device.ghp_deep.power_already))
        m.addCons(
            p_ghp_deep_max >= crf(OptimizationBody.device.ghp_deep.power_min) * crf(OptimizationBody.device.ghp_deep.power_already))
        
        #----gtw----#
        m.addCons(num_gtw <= crf(OptimizationBody.device.gtw.number_max) * crf(OptimizationBody.device.gtw.number_already))
        m.addCons(num_gtw >= crf(OptimizationBody.device.gtw.number_min) * crf(OptimizationBody.device.gtw.number_already))

        #----co----#
        m.addCons(p_co_max <= crf(OptimizationBody.device.co.power_max) * crf(OptimizationBody.device.co.power_already))
        m.addCons(p_co_max >= crf(OptimizationBody.device.co.power_min) * crf(OptimizationBody.device.co.power_already))

        #----xb----#               xb未定义
        m.addCons(g_xb_max <= input_json['device']['xb']['s_max'] * input_json['device']['xb']['if_use'])
        m.addCons(g_xb_max <= input_json['device']['xb']['s_min'] * input_json['device']['xb']['if_use'])

        #----whp----#
        m.addCons(p_whp_max <= crf(OptimizationBody.device.whp.power_max) * crf(OptimizationBody.device.whp.power_already))
        m.addCons(p_whp_max >= crf(OptimizationBody.device.whp.power_min) * crf(OptimizationBody.device.whp.power_already))

        #----hp120----#
        m.addCons(p_hp120_max <= crf(OptimizationBody.device.hp120.power_max) * crf(OptimizationBody.device.hp120.power_already))
        m.addCons(p_hp120_max >= crf(OptimizationBody.device.hp120.power_min) * crf(OptimizationBody.device.hp120.power_already))

        #----co180----#
        m.addCons(p_co180_max <= crf(OptimizationBody.device.co180.power_max) * crf(OptimizationBody.device.co180.power_already))
        m.addCons(p_co180_max >= crf(OptimizationBody.device.co180.power_max) * crf(OptimizationBody.device.co180.power_already))

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
        if crf(OptimizationBody.device.ghp.balance_flag) == 1:  #如果需要考虑全年热平衡
            m.addCons(quicksum([g_ghp[i] - p_ghp[i] - q_ghp[i] - p_ghpc[i] - g_ghp_gr[i] for i in range(period)]) == 0)
        for i in range(period):
            # 买能约束      g_sol和gas_pur的未定义以及对120度蒸汽和180度蒸汽的定义未区分
            m.addCons(p_pur[i] <= 1000000000 * crf(OptimizationBody.trading.power_buy_enable))  # 是否允许电网买电
            m.addCons(p_sol[i] <= 1000000000 * crf(OptimizationBody.trading.power_sell_enable))  # 是否允许电网卖电
            m.addCons(h_pur[i] <= 1000000000 * crf(OptimizationBody.trading.h2_buy_enable))  # 是否允许购买氢气
            m.addCons(g_sol[i] <= 1000000000 * input_json['calc_mode']['grid']['g_sol'])  # 是否允许出售天然气
            m.addCons(h_sol[i] <= 1000000000 * crf(OptimizationBody.trading.h2_sell_enable))  # 是否允许出售氢气
            m.addCons(gas_pur[i] <= 1000000000 * input_json['calc_mode']['grid']['gas_pur'])  # 是否允许购买天然气
            m.addCons(steam120_pur[i] <= 1000000000 * input_json['calc_mode']['grid']['steam120_pur'])  # 是否允许买120度蒸汽
            m.addCons(steam120_sol[i] <= 1000000000 * input_json['calc_mode']['grid']['steam120_sol'])  # 是否允许卖120度蒸汽
            m.addCons(steam180_pur[i] <= 1000000000 * input_json['calc_mode']['grid']['steam180_pur'])  # 是否允许买180度蒸汽
            m.addCons(steam180_sol[i] <= 1000000000 * input_json['calc_mode']['grid']['steam180_sol'])  # 是否允许卖180度蒸汽
            for j in range(custom_energy_num):
                m.addCons(y_pur[j][i] <= 1000000000 * (isloate[6 + j]))  # 是否允许购买第j条能量流

            #-----------------------------基础设备库的设备约束-----------------------------#
            #----fc----#
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
            m.addCons(g_ht[i] <= c * m_ht * crf(OptimizationBody.device.ht.t_max))  # 储热罐存储热量上限
            m.addCons(g_ht[i] >= c * m_ht * crf(OptimizationBody.device.ht.t_min))  # 储热罐存储热量下限
        for i in range(period - 1):
            m.addCons(g_ht[i + 1] - g_ht[i] == g_ht_in[i] - g_ht_out[i] - 0.001 * g_ht[i])  # 储热罐存储动态变化
        m.addCons(g_ht[0] - g_ht[-1] == g_ht_in[-1] - g_ht_out[-1] - 0.001 * g_ht[-1])

        #----ct----#
        for i in range(period):
            m.addCons(q_ct[i] <= c * m_ct * crf(OptimizationBody.device.ct.t_max))  # 储冷罐存储冷量上限
            m.addCons(q_ct[i] >= c * m_ct * crf(OptimizationBody.device.ct.t_min))  # 储冷罐存储冷量下限
        for i in range(period - 1):
            m.addCons(q_ct[i] - q_ct[i + 1] == q_ct_in[i] - q_ct_out[i] + 0.001 * q_ct[i])  # 储冷罐存储动态变化
        m.addCons(q_ct[-1] - q_ct[0] == q_ct_in[-1] - q_ct_out[-1] + 0.001 * q_ct[-1])

        for i in range(period):
            #----pv----#
            m.addCons(p_pv[i] <= p_pv_max * r_solar[i])  # 允许丢弃可再生能源

            # ----wd----#
            m.addCons(p_wd[i] <= num_wd * wind_power[i] * crf(OptimizationBody.device.wd.capacity_unit))  # 允许丢弃可再生能源

            #----sc----#
            m.addCons(g_sc[i] <= k_sc * theta_ex * s_sc * r_solar[i])  # 允许丢弃可再生能源

            #----eb----#
            m.addCons(k_eb * p_eb[i] == g_eb[i])  # 电转热约束
            m.addCons(p_eb[i] <= p_eb_max)  # 运行功率 <= 规划功率（运行最大功率）

            #----ac----#
            m.addCons(q_ac[i] == k_ac * p_ac[i])  # 电转冷约束
            m.addCons(p_ac[i] <= p_ac_max)  # 运行功率 <= 规划功率（运行最大功率）

            #----hp----#
            m.addCons(p_hp[i] * k_hp_g == g_hp[i])  # 电转热约束
            m.addCons(p_hp[i] <= p_hp_max)  # 热泵供热运行功率 <= 规划功率（运行最大功率）

            m.addCons(p_hpc[i] * k_hp_q == q_hp[i])  # 电转冷约束
            m.addCons(p_hpc[i] <= p_hp_max)  # 热泵供冷运行功率 <= 规划功率（运行最大功率）

            #----ghp----#
            m.addCons(p_ghp[i] * k_ghp_g == g_ghp[i])  # 地源热泵电转热约束
            m.addCons(p_ghp[i] <= p_ghp_max)  # 热泵供热运行功率 <= 规划功率（运行最大功率）

            m.addCons(p_ghpc[i] * k_ghp_q == q_ghp[i])  # 地源热泵电转冷约束
            m.addCons(p_ghpc[i] <= p_ghp_max)  # 热泵供冷运行功率 <= 规划功率（运行最大功率）

            m.addCons(p_ghp_deep[i] * k_ghp_deep_g == g_ghp_deep[i])  # 地源热泵电转热约束
            m.addCons(p_ghp_deep[i] <= p_ghp_deep_max)  # 热泵供热运行功率 <= 规划功率（运行最大功率）

            #----gtw----#
            m.addCons(num_gtw * p_gtw >= g_ghp[i] - p_ghp[i])  #井和热泵有关联，制热量-电功率=取热量
            m.addCons(num_gtw * p_gtw >= q_ghp[i] + p_ghpc[i])  #井和热泵有关联，制冷量+电功率=灌热量
            m.addCons(
                num_gtw1 * p_gtw1 + num_gtw2 * p_gtw2 + num_gtw3 * p_gtw3 + num_gtw4 * p_gtw4 >= g_ghp_deep[i] - p_ghp_deep[
                    i])

            #----co----#
            m.addCons(p_co[i] == k_co * h_el[i])  # 压缩氢耗电量约束
            m.addCons(p_co[i] <= p_co_max)  #压缩机运行功率上限

            #----whp----#               找不到heat_resourceg和heat_resourceq的对应
            m.addCons(p_whpg[i] * k_whp == g_whp[i])
            m.addCons(g_whp[i] - p_whpg[i] <= input_json['device']['whp']['heat_resourceg'])
            m.addCons(p_whpq[i] * k_whp == q_whp[i])
            m.addCons(q_whp[i] - p_whpq[i] <= input_json['device']['whp']['heat_resourceq'])
            m.addCons(p_whp[i] <= p_whp_max)
            m.addCons(p_whp[i] == p_whpg[i] + p_whpq[i])

            #----xb----#
            m.addCons(s_xb[i] <= g_xb_max)  #相变储热t时刻储量不能超过模块规划大小
        for i in range(period - 1):
            m.addCons(s_xb[i + 1] == s_xb[i] + g_xb[i])
        m.addCons(s_xb[0] == s_xb[-1] + g_xb[-1])

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
                + quicksum(p_hyd) * input_json["device"]["hyd"]["power_cost"]  # 买水电花费
                + lambda_h * quicksum([h_pur[i] for i in range(period)])  # 买氢气花费
                + gas_price * quicksum([gas_pur[i] for i in range(period)])  # 买天然气花费
                + lambda_steam120_in * quicksum([steam120_pur[i] for i in range(period)])  # 买天然气花费
                + lambda_steam180_in * quicksum([steam180_pur[i] for i in range(period)])  # 买天然气花费
                + quicksum([cost_custom_energy[j] * y_pur[j][i] for i in range(period) for j in range(custom_energy_num)])
                - quicksum(p_sol[i] * lambda_ele_out for i in range(period))
                - quicksum(g_sol[i] * lambda_g_out for i in range(period))
                - quicksum(h_sol[i] * lambda_h_out for i in range(period))
                - quicksum(steam120_sol[i] * lambda_steam120_out for i in range(period))
                - quicksum(steam180_sol[i] * lambda_steam180_out for i in range(period))
                )  # 买自定义能量流花费
        m.addCons(op_sum_pure == quicksum([p_pur[i] * lambda_ele_in[i] for i in range(period)])  # 买电花费
                + quicksum(p_hyd) * input_json["device"]["hyd"]["power_cost"]  # 买水电花费
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
                    sum(ele_load) + sum(g_demand) / k_eb + sum(q_demand) / k_ghp_q))  #碳减排约束，买电量不能超过碳排放,即1-碳减排
        m.addCons(ce_h == quicksum(p_pur) * alpha_e)
        #-----------------------------规划设备花费约束-----------------------------#
        m.addCons(capex_sum == (cost_hyd * input_json["device"]['hyd']['flag']
                                + p_pv_max * cost_pv + s_sc * cost_sc + num_wd * cost_wd
                                + p_hp120_max * cost_hp120 + p_co180_max * cost_co180
                                + p_ghp_max * cost_ghp + p_ghp_deep_max * cost_ghp_deep + cost_gtw * num_gtw + cost_gtw1 * num_gtw1 + cost_gtw2 * num_gtw2 + cost_gtw3 * num_gtw3 + cost_gtw4 * num_gtw4
                                + cost_ht * m_ht + cost_ct * m_ct + cost_hst * hst + cost_eb * p_eb_max + cost_ac * p_ac_max + cost_hp * p_hp_max + cost_fc * p_fc_max + cost_el * p_el_max + cost_co * p_co_max + p_whp_max * cost_whp) * (
                            1 + input_json["price"]["PSE"])  # 基本设备库设备的规划成本
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

        m.addCons(capex_crf == cost_hyd * input_json["device"]['hyd'][
            'flag'] * crf_hyd + crf_pv * p_pv_max * cost_pv + crf_wd * num_wd * cost_wd + crf_sc * s_sc * cost_sc + crf_hst * hst * cost_hst + crf_ht * cost_ht * (
                    m_ht) + crf_ct * cost_ct * (m_ct) + crf_hp * cost_hp * p_hp_max
                + crf_gtw * cost_gtw * num_gtw + crf_gtw1 * cost_gtw1 * num_gtw1 + crf_gtw2 * cost_gtw2 * num_gtw2 + crf_gtw3 * cost_gtw3 * num_gtw3 + crf_gtw4 * cost_gtw4 * num_gtw4
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
        load_json = {
            'ele_load': ele_load,  # 电负荷8760h的分时数据/kwh
            'g_demand': g_demand,  # 热负荷8760h的分时数据/kwh
            'q_demand': q_demand,  # 冷负荷8760h的分时数据/kwh
            'wind_power': wind_power,  # 冷负荷8760h的分时数据/kwh
            'r_solar': r_solar}  # 光照强度8760h的分时数据/kwh
        output_json_dict = {
            'ele_load_sum': int(sum(ele_load)),  # 电负荷总量/kwh
            'g_demand_sum': int(sum(g_demand)),  # 热负荷总量/kwh
            'q_demand_sum': int(sum(q_demand)),  # 冷负荷总量/kwh
            'ele_load_max': int(max(ele_load)),  # 电负荷峰值/kwh
            'g_demand_max': int(max(g_demand)),  # 热负荷峰值/kwh
            'q_demand_max': int(max(q_demand)),  # 冷负荷峰值/kwh
            'num_gtw': m.getVal(num_gtw),  # 地热井数目/个
            'num_gtw1': m.getVal(num_gtw1),
            'num_gtw2': m.getVal(num_gtw2),
            'num_gtw3': m.getVal(num_gtw3),
            'num_gtw4': m.getVal(num_gtw4),
            'p_fc_max': m.getVal(p_fc_max),  # 燃料电池容量/kw
            'p_ghp_max': m.getVal(p_ghp_max),  # 地源热泵功率/kw
            'p_ghp_deep_max': m.getVal(p_ghp_deep_max),  # 地源热泵功率/kw
            'p_hp_max': m.getVal(p_hp_max),  # 空气源热泵功率/kw
            'p_whp_max': m.getVal(p_whp_max),  #whp/kw
            'p_ac_max': m.getVal(p_ac_max),
            'p_eb_max': m.getVal(p_eb_max),  # 电热锅炉功率/kw
            'p_el_max': m.getVal(p_el_max),  # 电解槽功率/kw
            'nm3_el_max': 11.2 * m.getVal(p_el_max) / 5,  # 电解槽nm3/nm3
            'hst': m.getVal(hst),  # 储氢罐容量/kg
            'm_ht': m.getVal(m_ht),  # 储热罐/kg
            'm_ct': m.getVal(m_ct),  # 冷水罐/kg
            'p_pv_max': m.getVal(p_pv_max),  # 光伏面积/m2
            'p_wd_max': m.getVal(num_wd) * capacity_wd,  # 风力发电机数量/个
            'area_sc': m.getVal(s_sc),  # 集热器面积/m2
            'p_co': m.getVal(p_co_max),  #氢压机功率/kw
            'g_xb_max': m.getVal(g_xb_max),  #相变储热模块大小/kwh
            'p_hp120_max': m.getVal(p_hp120_max),
            'p_co180_max': m.getVal(p_co180_max),

            'cap_fc': cost_fc * m.getVal(p_fc_max),
            'cap_ghp': cost_ghp * m.getVal(p_ghp_max),
            'cap_ghp_deep': cost_ghp_deep * m.getVal(p_ghp_deep_max),
            'cap_gtw': cost_gtw * m.getVal(num_gtw),
            'cap_gtw1': cost_gtw1 * m.getVal(num_gtw1),
            'cap_gtw2': cost_gtw2 * m.getVal(num_gtw2),
            'cap_gtw3': cost_gtw3 * m.getVal(num_gtw3),
            'cap_gtw4': cost_gtw4 * m.getVal(num_gtw4),
            'cap_hp': cost_hp * m.getVal(p_hp_max),
            'cap_whp': cost_whp * m.getVal(p_whp_max),
            'cap_ac': cost_ac * m.getVal(p_ac_max),
            'cap_eb': cost_eb * m.getVal(p_eb_max),
            'cap_hst': cost_hst * m.getVal(hst),
            'cap_ht': cost_ht * m.getVal(m_ht),
            'cap_ct': cost_ct * m.getVal(m_ct),
            'cap_pv': m.getVal(p_pv_max) * cost_pv,
            'cap_wd': m.getVal(num_wd) * cost_wd,
            'cap_co': cost_co * m.getVal(p_co_max),
            'cap_sc': cost_sc * m.getVal(s_sc),
            'cap_el': cost_el * m.getVal(p_el_max),
            'cap_xb': cost_xb * m.getVal(g_xb_max),
            'cap_hp120': cost_hp120 * m.getVal(p_hp120_max),
            'cap_co180': cost_co180 * m.getVal(p_co180_max),
            # 'cap_x_i': str([cost_x[i] * x_plan[i].X for i in range(custom_device_num)]),  # 所有自定义设备的规划成本放到一个数组里
            # # 所有自定义设备的规划成本放到一个数组里
            # 'cap_storage_hot_i': [cost_storage_hot[i] * s_i_hot_plan[i].X for i in range(custom_storge_device_num[1])],
            # # 所有自定义设备的规划成本放到一个数组里
            # 'cap_storage_cold_i': [cost_storage_cold[i] * s_i_cold_plan[i].X for i in range(custom_storge_device_num[2])],
            # # 所有自定义设备的规划成本放到一个数组里
            # 'cap_storage_hydr_i': [cost_storage_hydr[i] * s_i_hydr_plan[i].X for i in range(custom_storge_device_num[3])],
            # # 所有自定义设备的规划成本放到一个数组里
            # 'cap_storage_gas_i': [cost_storage_gas[i] * s_i_gas_plan[i].X for i in range(custom_storge_device_num[4])],
            # # 所有自定义设备的规划成本放到一个数组里
            # # 需要把cost_storage_x变为二维数组
            # 'cap_storage_x_ij': [
            #     [cost_storage_x[i][j] * s_i_xj_plan[i][j].X for j in range(custom_storge_device_num[5 + i])] for i in
            #     range(custom_energy_num)],  # 所有自定义设备的规划成本放到一个数组里
            "all_cap": format(all_cap / 10000, '.2f'),  #总投资/万元
            "year_cap": format(all_crf / 10000, '.2f'),  # 总投资/万元
            "year_operation": format(m.getVal(op_sum_pure) / 10000, '.2f'),  # 总投资/万元
            "cost_year": format(cost_year / 10000, '.2f'),  # 总投资/万元
            "cost_per_energy": format(cost_per_energy, '.4f'),  # 总投资/万元
            "co2": format(m.getVal(ce_h) / 1000, '.2f'),  # 总投资/万元

            "ele_all_cap": format(ele_cap / 10000, '.2f'),  # 总投资/万元
            "ele_year_cap": format(ele_cap / 10 / 10000, '.2f'),  # 总投资/万元
            "ele_year_operation": format(ele_op / 10000, '.2f'),  # 总投资/万元
            "ele_cost_year": format(ele_cost_year / 10000, '.2f'),  # 总投资/万元
            "ele_cost_per_energy": format(ele_cost_per_energy, '.4f'),  # 总投资/万元
            "ele_co2": format(ele_co2 / 1000, '.2f'),  # 总投资/万元

            "gas_all_cap": format(gas_cap / 10000, '.2f'),  # 总投资/万元
            "gas_year_cap": format(gas_cap / 10 / 10000, '.2f'),  # 总投资/万元
            "gas_year_operation": format(gas_op / 10000, '.2f'),  # 总投资/万元
            "gas_cost_year": format(gas_cost_year / 10000, '.2f'),  # 总投资/万元
            "gas_cost_per_energy": format(gas_cost_per_energy, '.4f'),  # 总投资/万元

            "revenue_ele": format(revenue_ele / 10000, '.2f'),  # 总投资/万元
            "revenue_heat": format(revenue_heat / 10000, '.2f'),  # 总投资/万元
            "revenue_cold": format(revenue_cold / 10000, '.2f'),  # 总投资/万元
            "revenue_steam120": format(revenue_steam120 / 10000, '.2f'),  # 总投资/万元
            "revenue_steam180": format(revenue_steam180 / 10000, '.2f'),  # 总投资/万元
            "revenue_sol_ele": format(sum(m.getVal(p_sol[i]) * lambda_ele_out for i in range(period)) / 10000, '.2f'),
            # 总投资/万元
            "revenue_sol_heat": format(sum(m.getVal(g_sol[i]) * lambda_ele_out for i in range(period)) / 10000, '.2f'),
            # 总投资/万元
            "revenue_sol_steam120": format(
                sum(m.getVal(steam120_sol[i]) * lambda_steam120_out for i in range(period)) / 10000, '.2f'),
            "revenue_sol_steam180": format(
                sum(m.getVal(steam180_sol[i]) * lambda_steam180_out for i in range(period)) / 10000, '.2f'),
            "gas_co2": format(gas_co2 / 1000, '.2f'),  # 总投资/万元
            "receive_year": format(receive_year, '.2f'),  # 投资回报年限/年
            "co2_reduce_ele": format(ele_co2 / 1000 - m.getVal(ce_h) / 1000, '.2f'),  # 投资回报年限/年
            "co2_reduce_gas": format(gas_co2 / 1000 - m.getVal(ce_h) / 1000, '.2f'),  # 投资回报年限/年
            "co2_reduce_ele_rate": format((ele_co2 - m.getVal(ce_h)) / ele_co2, '.2f'),  # 投资回报年限/年
            "co2_reduce_gas_rate": format((gas_co2 - m.getVal(ce_h)) / gas_co2, '.2f'),  # 投资回报年限/年
            "flag_isloate": input_json['calc_mode']['isloate'],
        }
        for i in range(custom_storge_device_num[0]):
            output_json_dict["cost_storage_ele" + str(i)] = cost_storage_ele[i] * m.getVal(s_i_ele_plan[i])
            output_json_dict["s_i_ele_plan" + str(i)] = m.getVal(s_i_ele_plan[i])

        # output_json = demjson.encode(output_json_dict)
        ele_sum_ele_only = np.array(ele_load) + np.array(g_demand) / k_eb + np.array(q_demand) / k_hp_q
        opex_ele_only = sum(np.array(lambda_ele_in) * ele_sum_ele_only)
        co2_ele_only = sum(ele_sum_ele_only) * alpha_e

        operation_output_json = {
            'op_cost':
                {
                    'all_of_revenue':
                        {
                            'all_revenue': format(revenue / 10000, '.2f'),
                            'fixed_revenue': format(input_json['price']['fixed_revenue'] / 10000, '.2f'),
                            'p_revenue': format(
                                sum((m.getVal(p_sol[i]) + ele_load[i]) * lambda_ele_in[i] for i in range(period)), '.2f'),
                            'p_sol_revenue': format(sum((m.getVal(p_sol[i])) * lambda_ele_out for i in range(period)),
                                                    '.2f'),
                            "revenue_heat": format(revenue_heat, '.2f'),
                            "revenue_cold": format(revenue_cold, '.2f'),
                        },
                    'all_of_op_cost':
                        {
                            'all_op_cost': format(m.getVal(op_sum_pure) / 10000, '.2f'),
                            'p_pur_cost': format(sum([m.getVal(p_pur[i]) * lambda_ele_in[i] for i in range(period)]),
                                                '.2f'),
                            'h_pur_cost': format(lambda_h * sum([m.getVal(h_pur[i]) for i in range(period)]), '.2f')
                        },
                    'net_revenue': format((revenue - m.getVal(op_sum)) / 10000, '.2f'),
                    'ele_statistics':
                        {
                            'sum_pv': format(sum(m.getVal(p_pv[i]) for i in range(period)), '.2f'),
                            'sum_wd': format(sum(m.getVal(p_wd[i]) for i in range(period)), '.2f'),
                            'sum_fc': format(sum(m.getVal(p_fc[i]) for i in range(period)), '.2f'),
                            'sum_p_pur': format(sum(m.getVal(p_pur[i]) for i in range(period)), '.2f'),
                            'sum_p_sol': format(sum(m.getVal(p_sol[i]) for i in range(period)), '.2f'),

                        }
                },
            "operation_cost_per_month_per_square": format(
                m.getVal(op_sum) / 12 / max(input_json["load"]["ele_load_area"], input_json["load"]["g_load_area"],
                                            input_json["load"]["q_load_area"]), '.2f'),  #单位面积月均运行成本
            "cost_save_rate": format((opex_ele_only - m.getVal(op_sum)) / opex_ele_only, '.1f'),  #电运行成本节约比例
            "co2": format(m.getVal(ce_h) / 1000, '.1f'),  #总碳排/t
            "cer_rate": format((co2_ele_only - m.getVal(ce_h)) / co2_ele_only * 100, '.1f'),  #与电系统相比的碳减排率
            "cer_perm2": format((co2_ele_only - m.getVal(ce_h)) / max(input_json["load"]["ele_load_area"],
                                                                    input_json["load"]["g_load_area"],
                                                                    input_json["load"]["q_load_area"]) / 1000, '.1f'),
            #电系统每平米的碳减排量/t
            "cer": format((co2_ele_only - m.getVal(ce_h)) / 1000, '.2f'),
        }
        #---------------------------求解结果返回-----------------------------#
        return {'objective': m.getObjVal(),
                'process time': time.time() - t0,
                'receive_year': receive_year,
                #规划成本输出
                'cap_sum': m.getVal(capex_sum),  # 总规划成本
                'cap_fc': cost_fc * m.getVal(p_fc_max),
                'cap_el': cost_el * m.getVal(p_el_max),
                'cap_hst': cost_hst * m.getVal(hst),
                'cap_ht': cost_ht * m.getVal(m_ht),
                'cap_ct': cost_ct * m.getVal(m_ct),
                'cap_pv': m.getVal(p_pv_max) * cost_pv,
                'cap_wd': m.getVal(num_wd) * cost_wd,
                'cap_sc': m.getVal(s_sc) * cost_sc,
                'cap_eb': cost_eb * m.getVal(p_eb_max),
                'cap_ac': cost_ac * m.getVal(p_ac_max),
                'cap_hp': cost_hp * m.getVal(p_hp_max),
                'cap_ghp': cost_ghp * m.getVal(p_ghp_max),
                'cap_ghp_deep': cost_ghp_deep * m.getVal(p_ghp_deep_max),
                'cap_gtw': cost_gtw * m.getVal(num_gtw),
                'cap_gtw1': cost_gtw1 * m.getVal(num_gtw1),
                'cap_gtw2': cost_gtw2 * m.getVal(num_gtw2),
                'cap_gtw3': cost_gtw3 * m.getVal(num_gtw3),
                'cap_gtw4': cost_gtw4 * m.getVal(num_gtw4),
                'cap_co': cost_co * m.getVal(p_co_max),
                'cap_whp': cost_whp * m.getVal(p_whp_max),
                'cap_hp120': cost_hp120 * m.getVal(p_hp120_max),
                'cap_co180': cost_co180 * m.getVal(p_co180_max),
                'cap_x_i': [cost_x[i] * m.getVal(x_plan[i]) for i in range(custom_device_num)],  # 所有自定义设备的规划成本放到一个数组里
                'cap_storage_ele_i': [cost_storage_ele[i] * m.getVal(s_i_ele_plan[i]) for i in
                                    range(custom_storge_device_num[0])],  # 所有自定义设备的规划成本放到一个数组里
                'cap_storage_hot_i': [cost_storage_hot[i] * m.getVal(s_i_hot_plan[i]) for i in
                                    range(custom_storge_device_num[1])],  # 所有自定义设备的规划成本放到一个数组里
                'cap_storage_cold_i': [cost_storage_cold[i] * m.getVal(s_i_cold_plan[i]) for i in
                                    range(custom_storge_device_num[2])],  # 所有自定义设备的规划成本放到一个数组里
                'cap_storage_hydr_i': [cost_storage_hydr[i] * m.getVal(s_i_hydr_plan[i]) for i in
                                    range(custom_storge_device_num[3])],  # 所有自定义设备的规划成本放到一个数组里
                'cap_storage_gas_i': [cost_storage_gas[i] * m.getVal(s_i_gas_plan[i]) for i in
                                    range(custom_storge_device_num[4])],  # 所有自定义设备的规划成本放到一个数组里
                # 需要把cost_storage_x变为二维数组
                'cap_storage_x_ij': [
                    [cost_storage_x[i][j] * m.getVal(s_i_xj_plan[i][j]) for j in range(custom_storge_device_num[5 + i])] for
                    i in range(custom_energy_num)],  # 所有自定义设备的规划成本放到一个数组里

                #规划容量输出
                'p_fc_max': m.getVal(p_fc_max),
                'p_el_max': m.getVal(p_el_max),
                'hst': m.getVal(hst),
                'm_ht': m.getVal(m_ht),
                'm_ct': m.getVal(m_ct),
                'p_pv_max': m.getVal(p_pv_max),
                'num_wd': m.getVal(num_wd),
                's_sc': m.getVal(s_sc),
                'p_eb_max': m.getVal(p_eb_max),
                'p_ac_max': m.getVal(p_ac_max),
                'p_hp_max': m.getVal(p_hp_max),
                'p_ghp_max': m.getVal(p_ghp_max),
                'p_ghp_deep_max': m.getVal(p_ghp_deep_max),
                'num_gtw': m.getVal(num_gtw),
                'num_gtw1': m.getVal(num_gtw1),
                'num_gtw2': m.getVal(num_gtw2),
                'num_gtw3': m.getVal(num_gtw3),
                'num_gtw4': m.getVal(num_gtw4),
                'p_co_max': m.getVal(p_co_max),
                'p_whp_max': m.getVal(p_whp_max),
                'p_hp120_max': m.getVal(p_hp120_max),
                'p_co180_max': m.getVal(p_co180_max),
                'x_plan': [m.getVal(x_plan[i]) for i in range(custom_device_num)],
                's_i_ele_plan': [m.getVal(s_i_ele_plan[i]) for i in range(custom_storge_device_num[0])],
                's_i_hot_plan': [m.getVal(s_i_hot_plan[i]) for i in range(custom_storge_device_num[1])],
                's_i_cold_plan': [m.getVal(s_i_cold_plan[i]) for i in range(custom_storge_device_num[2])],
                's_i_hydr_plan': [m.getVal(s_i_hydr_plan[i]) for i in range(custom_storge_device_num[3])],
                's_i_gas_plan': [m.getVal(s_i_gas_plan[i]) for i in range(custom_storge_device_num[4])],
                's_i_xj_plan': [[m.getVal(s_i_xj_plan[j][i]) for i in range(custom_storge_device_num[5 + j])] for j in
                                range(custom_energy_num)],

                #运行成本输出
                'opex': m.getVal(op_sum),  # 总运行成本

                'h_cost': lambda_h * sum([m.getVal(h_pur[i]) for i in range(period)]),
                'p_cost': sum([m.getVal(p_pur[i]) * lambda_ele_in[i] for i in range(period)]),
                'p_sol_earn': sum([m.getVal(p_sol[i]) for i in range(period)]) * lambda_ele_out,
                'hyd_pur_cost': sum([m.getVal(p_hyd[i]) for i in range(period)]) * input_json["device"]["hyd"][
                    "power_cost"],
                'gas_cost': gas_price * sum([m.getVal(gas_pur[i]) for i in range(period)]),
                'y_cost_j': [cost_custom_energy[j] * sum([m.getVal(y_pur[j][i]) for i in range(period)]) for j in
                            range(custom_energy_num)],

                # "operation_cost": format(op_sum/10000,'.1f'),  # 年化运行总成本/万元
                # "revenue": format(revenue/10000,'.1f'),  # 年化运行收益/万元
                # "operation_cost_per_month_per_square":format(op_sum/12/input_json['load']['load_area'],'.2f'),#单位面积月均运行成本
                # "operation_cost_net":format((revenue-op_sum)/10000,'.1f'),#年化运行净收益/万元
                # 'cer':format((co2_ele_only-ce_h.X)/co2_ele_only,'.1f'),
                # 'cer_self':sum([p_sol[i].X for i in range(period)])/co2_ele_only,
                #"load_per_area":format((sum(ele_load)+sum(g_demand)+sum(q_demand))/8760/input_json["load"]["load_area"]),

                # 负荷
                'ele_load': ele_load,
                'g_demand': g_demand,
                'q_demand': q_demand,
                'h_demand': h_demand,
                'steam120_demand': steam120_demand,
                'steam180_demand': steam180_demand,

                # 运行结果输出
                # 能量流买卖
                'p_pur': [m.getVal(p_pur[i]) for i in range(period)],
                'p_sol': [m.getVal(p_sol[i]) for i in range(period)],
                'p_hyd': [m.getVal(p_hyd[i]) for i in range(period)],
                'h_pur': [m.getVal(h_pur[i]) for i in range(period)],
                'gas_pur': [m.getVal(gas_pur[i]) for i in range(period)],
                'steam120_pur': [m.getVal(steam120_pur[i]) for i in range(period)],
                'steam120_sol': [m.getVal(steam120_sol[i]) for i in range(period)],
                'steam180_pur': [m.getVal(steam180_pur[i]) for i in range(period)],
                'steam180_sol': [m.getVal(steam180_sol[i]) for i in range(period)],
                'y_pur': [[m.getVal(y_pur[j][i]) for i in range(period)] for j in range(custom_energy_num)],
                # fc
                'p_fc': [m.getVal(p_fc[i]) for i in range(period)],
                'g_fc': [m.getVal(g_fc[i]) for i in range(period)],
                'h_fc': [m.getVal(h_fc[i]) for i in range(period)],
                # el
                'p_el': [m.getVal(p_el[i]) for i in range(period)],
                'h_el': [m.getVal(h_el[i]) for i in range(period)],
                #hst
                'h_sto': [m.getVal(h_sto[i]) for i in range(period)],
                #ht
                'g_ht': [m.getVal(g_ht[i]) for i in range(period)],
                'g_ht_in': [m.getVal(g_ht_in[i]) for i in range(period)],
                'g_ht_out': [m.getVal(g_ht_out[i]) for i in range(period)],
                #ct
                'q_ct': [m.getVal(q_ct[i]) for i in range(period)],
                'q_ct_in': [m.getVal(q_ct_in[i]) for i in range(period)],
                'q_ct_out': [m.getVal(q_ct_out[i]) for i in range(period)],
                #pv
                'p_solar_pv': [m.getVal(eta_pv * s_pv) * r_solar[i] for i in range(period)],  # pv吸收太阳能理论发电量
                'p_pv': [m.getVal(p_pv[i]) for i in range(period)],  # 实际pv发电量（可能存在弃光）
                #wd
                'p_wind': [m.getVal(p_wd[i]) for i in range(period)],
                #sc
                'g_sc': [m.getVal(g_sc[i]) for i in range(period)],
                #eb
                'p_eb': [m.getVal(p_eb[i]) for i in range(period)],
                'g_eb': [m.getVal(g_eb[i]) for i in range(period)],
                #ac
                'p_ac': [m.getVal(p_ac[i]) for i in range(period)],
                'q_ac': [m.getVal(q_ac[i]) for i in range(period)],
                #hp
                'p_hp': [m.getVal(p_hp[i]) for i in range(period)],
                'g_hp': [m.getVal(g_hp[i]) for i in range(period)],
                'p_hpc': [m.getVal(p_hpc[i]) for i in range(period)],
                'q_hp': [m.getVal(q_hp[i]) for i in range(period)],
                #ghp
                'p_ghp': [m.getVal(p_ghp[i]) for i in range(period)],
                'p_ghpc': [m.getVal(p_ghpc[i]) for i in range(period)],
                'q_ghp': [m.getVal(q_ghp[i]) for i in range(period)],
                'g_ghp': [m.getVal(g_ghp[i]) for i in range(period)],
                'g_ghp_gr': [m.getVal(g_ghp_gr[i]) for i in range(period)],
                # ghp_deep
                'p_ghp_deep': [m.getVal(p_ghp_deep[i]) for i in range(period)],
                'g_ghp_deep': [m.getVal(g_ghp_deep[i]) for i in range(period)],
                #co
                'p_co': [m.getVal(p_co[i]) for i in range(period)],
                #whp
                'p_whp': [m.getVal(p_whp[i]) for i in range(period)],
                #hp120
                'p_hp120': [m.getVal(p_hp120[i]) for i in range(period)],
                'm_hp120': [m.getVal(m_hp120[i]) for i in range(period)],
                'g_hp120': [m.getVal(g_hp120[i]) for i in range(period)],
                #co180
                'p_co180': [m.getVal(p_co180[i]) for i in range(period)],

                #总线
                'g_tube': [m.getVal(g_tube[i]) for i in range(period)],
                'g_tubeTosteam120': [m.getVal(g_tubeTosteam120[i]) for i in range(period)],
                'm_steam120Tosteam180': [m.getVal(m_steam120Tosteam180[i]) for i in range(period)],

                'x_j_in': [[[m.getVal(x_j_in[j][i][t]) for t in range(period)] for i in range(custom_device_num)] for j in
                        range(custom_energy_num)],
                'x_j_out': [[[m.getVal(x_j_out[j][i][t]) for t in range(period)] for i in range(custom_device_num)] for j in
                            range(custom_energy_num)],

                's_i_ele_state': [[m.getVal(s_i_ele_state[i][t]) for t in range(period)] for i in
                                range(custom_storge_device_num[0])],
                's_i_ele_out': [[m.getVal(s_i_ele_out[i][t]) for t in range(period)] for i in
                                range(custom_storge_device_num[0])],
                's_i_ele_in': [[m.getVal(s_i_ele_in[i][t]) for t in range(period)] for i in
                            range(custom_storge_device_num[0])],

                's_i_hot_state': [[m.getVal(s_i_hot_state[i][t]) for t in range(period)] for i in
                                range(custom_storge_device_num[1])],
                's_i_hot_out': [[m.getVal(s_i_hot_out[i][t]) for t in range(period)] for i in
                                range(custom_storge_device_num[1])],
                's_i_hot_in': [[m.getVal(s_i_hot_in[i][t]) for t in range(period)] for i in
                            range(custom_storge_device_num[1])],

                's_i_cold_state': [[m.getVal(s_i_cold_state[i][t]) for t in range(period)] for i in
                                range(custom_storge_device_num[2])],
                's_i_cold_out': [[m.getVal(s_i_cold_out[i][t]) for t in range(period)] for i in
                                range(custom_storge_device_num[2])],
                's_i_cold_in': [[m.getVal(s_i_cold_in[i][t]) for t in range(period)] for i in
                                range(custom_storge_device_num[2])],

                's_i_hydr_state': [[m.getVal(s_i_hydr_state[i][t]) for t in range(period)] for i in
                                range(custom_storge_device_num[3])],
                's_i_hydr_out': [[m.getVal(s_i_hydr_out[i][t]) for t in range(period)] for i in
                                range(custom_storge_device_num[3])],
                's_i_hydr_in': [[m.getVal(s_i_hydr_in[i][t]) for t in range(period)] for i in
                                range(custom_storge_device_num[3])],

                's_i_gas_state': [[m.getVal(s_i_gas_state[i][t]) for t in range(period)] for i in
                                range(custom_storge_device_num[4])],
                's_i_gas_out': [[m.getVal(s_i_gas_out[i][t]) for t in range(period)] for i in
                                range(custom_storge_device_num[4])],
                's_i_gas_in': [[m.getVal(s_i_gas_in[i][t]) for t in range(period)] for i in
                            range(custom_storge_device_num[4])],

                's_i_xj_state': [[[m.getVal(s_i_xj_state[j][i][t]) for t in range(period)] for i in
                                range(custom_storge_device_num[5 + j])] for j in range(custom_energy_num)],
                's_i_xj_out': [
                    [[m.getVal(s_i_xj_out[j][i][t]) for t in range(period)] for i in range(custom_storge_device_num[5 + j])]
                    for j in range(custom_energy_num)],
                's_i_xj_in': [
                    [[m.getVal(s_i_xj_in[j][i][t]) for t in range(period)] for i in range(custom_storge_device_num[5 + j])]
                    for j in range(custom_energy_num)],
                }, output_json_dict, operation_output_json, load_json

        return 'success'



