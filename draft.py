# ----------------------------------------------------------------------------------------------------------------------
# stu_sum = 5
# grades = ["A", "B", "C", "D", "E"]
# my_dict = {
#     "number_{i}".format(i=i): "grade_{grade}".format(grade=grades[i]) for i in range(stu_sum)
# }
#
# print(my_dict)

# ----------------------------------------------------------------------------------------------------------------------
# 测试 pydantic
# ----------------------------------------------------------------------------------------------------------------------
# import json
# from schema.schema_optimization import OptimizationBody
#
# with open("./resource/optimization.json", "r", encoding="utf-8") as f:
#     data = json.load(f)
#
# optimization_body = OptimizationBody(**data)
#
# opt_dict = optimization_body.model_dump()
#
# for key, value in opt_dict.items():
#     print(f"{key} : {value}")

# ----------------------------------------------------------------------------------------------------------------------

# ----------------------------------------------------------------------------------------------------------------------
import numpy as np
import pandas as pd


def generate_annual_heat_load(start_date, end_date, typical_daily_load):
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


# 示例输入数据
start_date = "10-01"  # 10月1日开始
end_date = "03-01"  # 次年3月1日结束
typical_daily_load = [0.8, 0.7, 0.6, 0.5, 0.4, 0.5,
                      0.8, 1.0, 1.2, 1.3, 1.4, 1.5,
                      1.6, 1.5, 1.4, 1.3, 1.2, 1.3,
                      1.4, 1.5, 1.2, 1.0, 0.9, 0.8]  # 24小时数据

# 生成全年负荷
annual_load = generate_annual_heat_load(start_date, end_date, typical_daily_load)

# 验证结果
print(f"Generated annual load length: {len(annual_load)}")
print("First 24 hours:", annual_load[:24])
print("September 30th (index 6528-6551):", annual_load[6528:6552])
print("October 1st (index 6552-6575):", annual_load[6552:6576])
print("October 2nd (index 6576-6599):", annual_load[6576:6600])
print("February 28th (index 1392-1415):", annual_load[1392:1416])
print("March 1st (index 1416-1439):", annual_load[1416:1440])
print("March 2nd (index 1440-1463):", annual_load[1440:1464])
