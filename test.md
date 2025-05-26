设备：

```
co 氢气压缩机
fc 燃料电池
el 电解槽
hst 储氢罐
ht 储热水箱
ct 储冷水箱
bat 电池 ?
bio_storage ?
steam_storage ?
pv 光伏板
sc 太阳能集热器
wd 风机
eb 电锅炉
ac 空调
hp 空气源热泵
ghp 浅层地源热泵
ghp_deep 中深层地源热泵
gtw 浅层地埋井
gtw2500 ?
hp120 高温热泵
co180 高温蒸汽压缩机
whp 余热热泵
```



```
objective
process time
receive_year

# --- 规划方案 ---
# 规划容量
p_co_inst
p_fc_inst 燃料电池
p_el_inst 电解槽
h_hst_inst 储氢罐
m_ht_inst 储热水箱
m_ct_inst 储冷水箱
p_pv_inst 光伏板
s_sc_inst 太阳能集热器
num_wd_inst 风机
p_eb_inst 电锅炉
p_ac_inst 空调
p_hp_inst 空气源热泵
p_ghp_inst 浅层地源热泵
p_ghp_deep_inst 中深层地源热泵
num_gtw_inst 浅层地埋井
num_gtw2500_inst ?
p_hp120_inst 高温热泵
p_co180_inst 高温蒸汽压缩机
p_whp_inst 余热热泵
p_bat_inst 电池
steam_storage_inst ?

# 规划容量输出
'x_plan': [m.getVal(x_plan[i]) for i in range(custom_device_num)],
's_i_ele_plan': [m.getVal(s_i_ele_plan[i]) for i in range(custom_storge_device_num[0])],
's_i_hot_plan': [m.getVal(s_i_hot_plan[i]) for i in range(custom_storge_device_num[1])],
's_i_cold_plan': [m.getVal(s_i_cold_plan[i]) for i in range(custom_storge_device_num[2])],
's_i_hydr_plan': [m.getVal(s_i_hydr_plan[i]) for i in range(custom_storge_device_num[3])],
's_i_gas_plan': [m.getVal(s_i_gas_plan[i]) for i in range(custom_storge_device_num[4])],
's_i_xj_plan': [[m.getVal(s_i_xj_plan[j][i]) for i in range(custom_storge_device_num[5 + j])] for j in
                range(custom_energy_num)],

# 规划成本输出
capex_co 氢气压缩机
capex_fc 燃料电池
capex_el 电解槽
capex_hst 储氢罐
capex_ht 储热水箱
capex_ct 储冷水箱
capex_pv 光伏板
capex_sc 太阳能集热器
capex_wd 风机
capex_eb 电锅炉
capex_ac 空调
capex_hp 空气源热泵
capex_ghp 浅层地源热泵
capex_ghp_deep 中深层地源热泵
capex_gtw 浅层地埋井
capex_gtw2500 ?
capex_hp120 高温热泵
capex_co180 高温蒸汽压缩机
capex_whp 余热热泵
capex_bat 电池
capex_steam_storage ?

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

# --- 参数指标 ---
capex  # 总规划成本
opex  # 运行成本
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

# --- 运行结果 ---
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
'g_tube'
'g_tubeTosteam120'
'm_steam120Tosteam180'
'x_j_in'
'x_j_out'
's_i_ele_state'
's_i_ele_out'
's_i_ele_in'
's_i_hot_state'
's_i_hot_out'
's_i_hot_in'
's_i_cold_state'
's_i_cold_out'
's_i_cold_in'
's_i_hydr_state'
's_i_hydr_out'
's_i_hydr_in'
's_i_gas_state'
's_i_gas_out'
's_i_gas_in'
's_i_xj_state'
's_i_xj_out'
's_i_xj_in'
```



## 问题

