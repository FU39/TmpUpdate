import numpy as np
import matplotlib.pyplot as plt
from matplotlib.ticker import MultipleLocator


# 2.1 单位装机光伏和风机出力
def draw_unit_pv_output(pv_data):
    plt.rcParams['font.sans-serif'] = ['SimHei']
    plt.rcParams['axes.unicode_minus'] = False
    plt.figure(figsize=(6, 3.49), dpi=100)

    plt.plot(pv_data, color='#FFA500', label='光伏出力')

    plt.xlabel('小时')
    plt.ylabel('单位装机光伏出力')
    # plt.title('单位装机光伏出力')
    plt.xlim(0, len(pv_data))
    plt.ylim(0, 1.1)

    ax = plt.gca()
    ax.xaxis.set_major_locator(MultipleLocator(24 * 30))
    ax.yaxis.set_major_locator(MultipleLocator(0.2))
    plt.savefig('./io_template/media/pv.png')
    plt.close()


def draw_unit_wind_output(wind_data):
    plt.rcParams['font.sans-serif'] = ['SimHei']
    plt.rcParams['axes.unicode_minus'] = False
    plt.figure(figsize=(6, 3.49), dpi=100)

    plt.plot(wind_data, color='#1E90FF', label='风机出力')

    plt.xlabel('小时')
    plt.ylabel('单位装机风机出力')
    # plt.title('单位装机风机出力')
    plt.xlim(0, len(wind_data))
    plt.ylim(0, 1.1)

    ax = plt.gca()
    ax.xaxis.set_major_locator(MultipleLocator(24 * 30))
    ax.yaxis.set_major_locator(MultipleLocator(0.2))
    plt.savefig('./io_template/media/wd.png')
    plt.close()


# 3.2.3 全年热负荷分布图
def draw_annual_heat_load(heat_load, hotwater_load=None):
    """绘制全年热负荷和生活热水负荷分布堆积柱状图，将热负荷和生活热水负荷以堆积形式展示
    Args:
        heat_load: 热负荷数据，长度为 12，表示每月的热负荷
        hotwater_load: 生活热水负荷数据，默认为 None
    """
    if hotwater_load is None:
        hotwater_load = np.zeros_like(heat_load)
    plt.rcParams['font.sans-serif'] = ['SimHei']
    plt.rcParams['axes.unicode_minus'] = False
    plt.figure(figsize=(7.13, 4.43), dpi=100)

    # 堆积柱状图
    plt.bar(range(1, 13), hotwater_load, bottom=heat_load, color='#FF8C00', label='生活热水负荷', width=0.6)
    plt.bar(range(1, 13), heat_load, color='#FF6347', label='热负荷', width=0.6)

    plt.xticks(range(1, 13))
    plt.xlabel('月份')
    plt.ylabel('负荷')
    # plt.title('全年热负荷分布图')
    plt.xlim(0.5, 12.5)
    plt.legend()
    plt.savefig('./io_template/media/heat_load.png')
    plt.close()


# 3.2.3 全年冷负荷分布图
def draw_annual_cool_load(cool_load):
    plt.rcParams['font.sans-serif'] = ['SimHei']
    plt.rcParams['axes.unicode_minus'] = False
    plt.figure(figsize=(7.13, 4.43), dpi=100)

    plt.bar(range(1, 13), cool_load, color='#4169E1', width=0.6)

    plt.xticks(range(1, 13))
    plt.xlabel('月份')
    plt.ylabel('冷负荷')
    # plt.title('全年冷负荷分布图')
    plt.xlim(0.5, 12.5)
    plt.savefig('./io_template/media/cool_load.png')
    plt.close()


# 3.2.3 典型日冷/热负荷变化图
def draw_typical_day_loads(summer_data, winter_data):
    plt.rcParams['font.sans-serif'] = ['SimHei']
    plt.rcParams['axes.unicode_minus'] = False

    # 夏季典型日冷负荷
    plt.figure(figsize=(7.13, 4.43), dpi=100)
    plt.plot(summer_data, color='#00BFFF', label='冷负荷')
    plt.xticks(range(0, 24, 2))
    plt.xlabel('小时')
    plt.ylabel('负荷')
    # plt.title('夏季典型日冷负荷变化图')
    plt.legend()
    plt.savefig('./io_template/media/day_cool.png')
    plt.close()

    # 冬季典型日热负荷
    plt.figure(figsize=(7.13, 4.43), dpi=100)
    plt.plot(winter_data, color='#FF4500', label='热负荷')
    plt.xticks(range(0, 24, 2))
    plt.xlabel('小时')
    plt.ylabel('负荷')
    # plt.title('冬季典型日热负荷变化图')
    plt.legend()
    plt.savefig('./io_template/media/day_heat.png')
    plt.close()


# 3.2.3 全年蒸汽负荷分布图
def draw_steam_load(steam_load):
    plt.rcParams['font.sans-serif'] = ['SimHei']
    plt.rcParams['axes.unicode_minus'] = False
    plt.figure(figsize=(7.13, 4.43), dpi=100)
    plt.bar(range(1, 13), steam_load, color='#808080', width=0.6)
    plt.xticks(range(1, 13))
    plt.xlabel('月份')
    plt.ylabel('蒸汽负荷')
    # plt.title('全年蒸汽负荷分布图')
    plt.savefig('./io_template/media/steam.png')
    plt.close()


# 3.2.3 典型日蒸汽负荷变化图
def draw_typical_steam_load(steam_day):
    plt.rcParams['font.sans-serif'] = ['SimHei']
    plt.rcParams['axes.unicode_minus'] = False
    plt.figure(figsize=(7.13, 4.43), dpi=100)
    plt.plot(steam_day, color='#696969', marker='o')
    plt.xticks(range(0, 24, 2))
    plt.xlabel('小时')
    plt.ylabel('蒸汽负荷')
    # plt.title('典型日蒸汽负荷变化图')
    plt.savefig('./io_template/media/day_steam.png')
    plt.close()


# 3.2.3 全年生活热水负荷分布图
def draw_hotwater_load(hotwater_load):
    plt.rcParams['font.sans-serif'] = ['SimHei']
    plt.rcParams['axes.unicode_minus'] = False
    plt.figure(figsize=(7.13, 4.43), dpi=100)
    plt.bar(range(1, 13), hotwater_load, color='#FF69B4', width=0.6)
    plt.xticks(range(1, 13))
    plt.xlabel('月份')
    plt.ylabel('生活热水负荷')
    # plt.title('全年生活热水负荷分布图')
    plt.savefig('./io_template/media/water.png')
    plt.close()


# 3.2.3 典型日生活热水负荷变化图
def draw_typical_hotwater_load(hotwater_day):
    plt.rcParams['font.sans-serif'] = ['SimHei']
    plt.rcParams['axes.unicode_minus'] = False
    plt.figure(figsize=(7.13, 4.43), dpi=100)
    plt.plot(hotwater_day, color='#FF1493', linestyle='--')
    plt.xticks(range(0, 24, 2))
    plt.xlabel('小时')
    plt.ylabel('生活热水负荷')
    # plt.title('典型日生活热水负荷变化图')
    plt.savefig('./io_template/media/day_water.png')
    plt.close()


# 3.2.3 全年电力负荷分布图
def draw_electricity_load(elec_load):
    plt.rcParams['font.sans-serif'] = ['SimHei']
    plt.rcParams['axes.unicode_minus'] = False
    plt.figure(figsize=(7.13, 4.43), dpi=100)
    plt.bar(range(1, 13), elec_load, color='#32CD32', width=0.6)
    plt.xticks(range(1, 13))
    plt.xlabel('月份')
    plt.ylabel('电力负荷')
    # plt.title('全年电力负荷分布图')
    plt.savefig('./io_template/media/elec.png')
    plt.close()


# 3.2.3 典型日电力负荷变化图
def draw_typical_electricity_load(elec_day):
    plt.rcParams['font.sans-serif'] = ['SimHei']
    plt.rcParams['axes.unicode_minus'] = False
    plt.figure(figsize=(7.13, 4.43), dpi=100)
    plt.plot(elec_day, color='#228B22', marker='^')
    plt.xticks(range(0, 24, 2))
    # plt.title('典型日电力负荷变化图')
    plt.savefig('./io_template/media/day_elec.png')
    plt.close()


if __name__ == "__main__":
    # 随机生成所有函数的示例数据
    np.random.seed(0)
    pv_data = np.random.rand(8760)  # 8760小时的光伏出力数据
    wind_data = np.random.rand(8760)  # 8760小时的风机出力数据
    heat_load = np.random.rand(12) * 1000  # 12个月的热负荷数据
    hotwater_load = np.random.rand(12) * 500  # 12个月的生活热水负荷数据
    cool_load = np.random.rand(12) * 800  # 12个月的冷负荷数据
    summer_data = np.random.rand(24) * 300  # 夏季典型日冷负荷数据
    winter_data = np.random.rand(24) * 600  # 冬季典型日热负荷数据
    steam_load = np.random.rand(12) * 700  # 12个月的蒸汽负荷数据
    steam_day = np.random.rand(24) * 400  # 典型日蒸汽负荷数据
    hotwater_day = np.random.rand(24) * 100  # 典型日生活热水负荷数据
    elec_load = np.random.rand(12) * 1200  # 12个月的电力负荷数据
    elec_day = np.random.rand(24) * 800  # 典型日电力负荷数据
    # 调用绘图函数
    draw_unit_pv_output(pv_data)
    draw_unit_wind_output(wind_data)
    draw_annual_heat_load(heat_load, hotwater_load=hotwater_load)
    draw_annual_cool_load(cool_load)
    draw_typical_day_loads(summer_data, winter_data)
    draw_steam_load(steam_load)
    draw_typical_steam_load(steam_day)
    draw_hotwater_load(hotwater_load)
    draw_typical_hotwater_load(hotwater_day)
    draw_electricity_load(elec_load)
    draw_typical_electricity_load(elec_day)
