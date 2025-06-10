import json
from datetime import datetime, timedelta
import pandas as pd
import numpy as np
from collections import defaultdict
import os
import pandas as pd
import chardet


def read_csv_safe(file_path):
    try:
        # 检测编码
        with open(file_path, 'rb') as f:
            encoding = chardet.detect(f.read(10000))['encoding']

        # 读取文件
        df = pd.read_csv(
            file_path,
            encoding=encoding,
            sep=None,  # 自动检测分隔符
            engine='python',
            on_bad_lines='warn'  # 跳过错误行
        )
        print("文件读取成功！")
        return df
    except Exception as e:
        print(f"读取失败: {str(e)}")
        return None


def load_building_data(building_info):
    file_path = building_info
    if not os.path.isabs(file_path):
        file_path = os.path.join(os.path.dirname(__file__), file_path)
    print(file_path)
    # 使用示例
    df = read_csv_safe(file_path)
    return df


def safe_time_parse(time_str):
    """安全解析各种时间格式"""
    time_str = time_str.strip()

    # 处理24:00:00特殊情况
    if time_str.endswith('24:00:00'):
        base_time = time_str.replace('24:00:00', '23:59:59')
        dt = datetime.strptime(base_time, "%m/%d %H:%M:%S")
        return dt + timedelta(seconds=1)


    # 尝试多种常见格式
    formats = [
        "%m/%d %H:%M:%S",  # 标准格式
        "%m/%d  %H:%M:%S",  # 多空格
        " %m/%d %H:%M:%S",  # 含年份
        " %m/%d  %H:%M:%S"  # 分隔符为
    ]

    for fmt in formats:
        datetime.strptime(time_str, fmt)


def process_building_loads(df, hourly_data):
    if df is None:
        return

    for _, row in df.iterrows():
            dt = safe_time_parse(row['timestamp'])


            # 计算一年中的小时数（0-8759）
            year_start = datetime(dt.year, 1, 1)
            hour_of_year = (dt - year_start).days * 24 + dt.hour

            if hour_of_year >= 8760:
                print(f"警告: 时间超出范围 {dt}")
                continue

            # 存储负荷数据
            hourly_data["electricity_load"][hour_of_year] += row.get('electricity', 0)
            hourly_data["heat_load"][50][hour_of_year] += row.get('heat', 0)
            hourly_data["cool_load"][20][hour_of_year] += row.get('cooling', 0)


def process_load_data(input_data):
    # 初始化数据结构
    hourly_data = {
        "electricity_load": np.zeros(8760),
        "heat_load": defaultdict(lambda: np.zeros(8760)),
        "cool_load": defaultdict(lambda: np.zeros(8760)),
        "steam_load": defaultdict(lambda: np.zeros(8760)),
        "hydrogen_load": np.zeros(8760),
        "hotwater_load": defaultdict(lambda: np.zeros(8760))
    }

    # 1. 处理建筑负荷数据
    total_heating_area = 0
    total_cooling_area = 0
    total_building_area = 0

    for key, building in input_data.items():
        if key.startswith('building'):
            df = load_building_data(building['building_file'])

            # 不再设置时间索引
            # df.set_index('timestamp', inplace=True)  # 注释掉这行

            # 确保所有数据框长度一致（8760行）
            if len(df) != 8760:
                print(f"警告: 建筑 {key} 的数据行数({len(df)})不是8760行")
                continue

            # 按行位置累加负荷数据
            for hour in range(8760):
                if hour < len(df):  # 防止索引越界
                    if 'electricity_load' in df.columns:
                        hourly_data["electricity_load"][hour] += df.iloc[hour]['electricity_load']
                    if 'heat_load' in df.columns:
                        temp = building.get('heat_temp', 50)
                        hourly_data["heat_load"][temp][hour] += df.iloc[hour]['heat_load']
                    if 'cool_load' in df.columns:
                        temp = building.get('cool_temp', 20)
                        hourly_data["cool_load"][temp][hour] += df.iloc[hour]['cool_load']
                    if 'steam_load' in df.columns:
                        temp = building.get('steam_temp', 100)
                        hourly_data["steam_load"][temp][hour] += df.iloc[hour]['steam_load']
                    if 'hydrogen_load' in df.columns:
                        hourly_data["hydrogen_load"][hour] += df.iloc[hour]['hydrogen_load']
                    if 'hotwater_load' in df.columns:
                        temp = building.get('hotwater_temp', 60)
                        hourly_data["hotwater_load"][temp][hour] += df.iloc[hour]['hotwater_load']
                else:
                    print(f"警告: 建筑 {key} 的数据行数不足8760行")

        # 累加面积数据
        total_heating_area += building.get('heating_area', 0)
        total_cooling_area += building.get('cooling_area', 0)
        total_building_area += building.get('building_area', 0)

    # 2. 处理自定义负荷数据
    year = 2023
    date_range = pd.date_range(start=f'{year}-01-01', end=f'{year}-12-31 23:00', freq='h')

    for key, load in input_data.items():
        if key.startswith('self_add_load'):
            load_name = load['load_name']
            temp = load['temp'] if load['temp'] != "None" else None
            list24 = load['list24']

            # 解析日期范围
            start_month, start_day = map(int, load['start_date'].split('-'))
            end_month, end_day = map(int, load['end_date'].split('-'))

            start_dt = datetime(year, start_month, start_day)
            end_dt = datetime(year, end_month, end_day) + timedelta(days=1)

            # 应用负荷模式
            for hour_idx, dt in enumerate(date_range):
                if start_dt <= dt < end_dt:
                    hour_of_day = dt.hour
                    load_value = list24[hour_of_day]

                    if load_name == "电":
                        hourly_data["electricity_load"][hour_idx] += load_value
                    elif load_name == "热" and temp is not None:
                        hourly_data["heat_load"][temp][hour_idx] += load_value
                    elif load_name == "冷" and temp is not None:
                        hourly_data["cool_load"][temp][hour_idx] += load_value
                    elif load_name == "蒸汽" and temp is not None:
                        hourly_data["steam_load"][temp][hour_idx] += load_value
                    elif load_name == "氢":
                        hourly_data["hydrogen_load"][hour_idx] += load_value
                    elif load_name == "生活热水" and temp is not None:
                        hourly_data["hotwater_load"][temp][hour_idx] += load_value


    # 3. 准备输出数据结构
    def convert_temp_loads(temp_loads):
        return [{"tem": temp, "load": load.tolist()} for temp, load in temp_loads.items()]

    # 小时级数据
    hourly_output = {
        "electricity_load": hourly_data["electricity_load"].tolist(),
        "heat_load": convert_temp_loads(hourly_data["heat_load"]),
        "cool_load": convert_temp_loads(hourly_data["cool_load"]),
        "steam_load": convert_temp_loads(hourly_data["steam_load"]),
        "hydrogen_load": hourly_data["hydrogen_load"].tolist(),
        "hotwater_load": convert_temp_loads(hourly_data["hotwater_load"])
    }

    # 日级数据（按天求和）
    daily_data = {
        "electricity_load": np.sum(hourly_data["electricity_load"].reshape(-1, 24), axis=1).tolist(),
        "heat_load": [{"tem": temp, "load": np.sum(load.reshape(-1, 24), axis=1).tolist()}
                      for temp, load in hourly_data["heat_load"].items()],
        "cool_load": [{"tem": temp, "load": np.sum(load.reshape(-1, 24), axis=1).tolist()}
                      for temp, load in hourly_data["cool_load"].items()],
        "steam_load": [{"tem": temp, "load": np.sum(load.reshape(-1, 24), axis=1).tolist()}
                       for temp, load in hourly_data["steam_load"].items()],
        "hydrogen_load": np.sum(hourly_data["hydrogen_load"].reshape(-1, 24), axis=1).tolist(),
        "hotwater_load": [{"tem": temp, "load": np.sum(load.reshape(-1, 24), axis=1).tolist()}
                          for temp, load in hourly_data["hotwater_load"].items()]
    }

    # 月级数据（按月求和）
    months = date_range.month[:8760]
    monthly_data = {
        "electricity_load": [np.sum(hourly_data["electricity_load"][months == m]) for m in range(1, 13)],
        "heat_load": [{"tem": temp, "load": [np.sum(load[months == m]) for m in range(1, 13)]}
                      for temp, load in hourly_data["heat_load"].items()],
        "cool_load": [{"tem": temp, "load": [np.sum(load[months == m]) for m in range(1, 13)]}
                      for temp, load in hourly_data["cool_load"].items()],
        "steam_load": [{"tem": temp, "load": [np.sum(load[months == m]) for m in range(1, 13)]}
                       for temp, load in hourly_data["steam_load"].items()],
        "hydrogen_load": [np.sum(hourly_data["hydrogen_load"][months == m]) for m in range(1, 13)],
        "hotwater_load": [{"tem": temp, "load": [np.sum(load[months == m]) for m in range(1, 13)]}
                          for temp, load in hourly_data["hotwater_load"].items()]
    }

    # 年级数据（全年总和）
    yearly_data = {
        "electricity_load": np.sum(hourly_data["electricity_load"]).item(),
        "heat_load": [{"tem": temp, "load": np.sum(load).item()}
                      for temp, load in hourly_data["heat_load"].items()],
        "cool_load": [{"tem": temp, "load": np.sum(load).item()}
                      for temp, load in hourly_data["cool_load"].items()],
        "steam_load": [{"tem": temp, "load": np.sum(load).item()}
                       for temp, load in hourly_data["steam_load"].items()],
        "hydrogen_load": np.sum(hourly_data["hydrogen_load"]).item(),
        "hotwater_load": [{"tem": temp, "load": np.sum(load).item()}
                          for temp, load in hourly_data["hotwater_load"].items()]
    }

    # 面积相关数据
    total_heat = sum(np.sum(load) for load in hourly_data["heat_load"].values())
    total_cool = sum(np.sum(load) for load in hourly_data["cool_load"].values())
    total_hotwater = sum(np.sum(load) for load in hourly_data["hotwater_load"].values())
    total_steam = sum(np.sum(load) for load in hourly_data["steam_load"].values())
    total_ele = yearly_data["electricity_load"]

    area_data = {
        "heating_area": total_heating_area,
        "cooling_area": total_cooling_area,
        "heating_per_area": total_heat / total_heating_area if total_heating_area > 0 else 0,
        "cooling_per_area": total_cool / total_cooling_area if total_cooling_area > 0 else 0,
        "ele_per_area": total_ele / total_building_area if total_building_area > 0 else 0,
        "hotwater_per_area": total_hotwater / total_building_area if total_building_area > 0 else 0,
        "steam_per_area": total_steam / total_building_area if total_building_area > 0 else 0,
        "heating_date": date_range[np.argmax(sum(hourly_data["heat_load"].values()))].strftime("%Y-%m-%d %H:%M:%S"),
        "cooling_date": date_range[np.argmax(sum(hourly_data["cool_load"].values()))].strftime("%Y-%m-%d %H:%M:%S"),
        "ele_date": date_range[np.argmax(hourly_data["electricity_load"])].strftime("%Y-%m-%d %H:%M:%S"),
        "hotwater_date": date_range[np.argmax(sum(hourly_data["hotwater_load"].values()))].strftime(
            "%Y-%m-%d %H:%M:%S"),
        "steam_date": date_range[np.argmax(sum(hourly_data["steam_load"].values()))].strftime("%Y-%m-%d %H:%M:%S")
    }

    # 季节性数据
    winter_months = [12, 1, 2]
    summer_months = [6, 7, 8]

    def get_seasonal_profile(load_data, season_months):
        profile = np.zeros(24)
        counts = np.zeros(24)

        for hour in range(8760):
            dt = date_range[hour]
            if dt.month in season_months:
                hour_of_day = dt.hour
                if isinstance(load_data, dict):  # 温度分组负荷
                    profile[hour_of_day] += sum(l[hour] for l in load_data.values())
                else:  # 单一负荷
                    profile[hour_of_day] += load_data[hour]
                counts[hour_of_day] += 1

        with np.errstate(divide='ignore', invalid='ignore'):
            return np.where(counts > 0, profile / counts, 0).tolist()

    seasonal_data = {
        "winter": {
            "date_time": list(range(24)),
            "load": get_seasonal_profile(hourly_data["heat_load"], winter_months)
        },
        "summer": {
            "date_time": list(range(24)),
            "load": get_seasonal_profile(hourly_data["cool_load"], summer_months)
        },
        "ele": {
            "date_time": list(range(24)),
            "load": get_seasonal_profile(hourly_data["electricity_load"], range(1, 13))
        },
        "hotwater": {
            "date_time": list(range(24)),
            "load": get_seasonal_profile(hourly_data["hotwater_load"], range(1, 13))
        },
        "steam": {
            "date_time": list(range(24)),
            "load": get_seasonal_profile(hourly_data["steam_load"], range(1, 13))
        }
    }

    # 最终输出
    output = {
        "hourly_data": hourly_output,
        "daily_data": daily_data,
        "monthly_data": monthly_data,
        "yearly_data": yearly_data,
        "area_data": area_data,
        "seasonal_data": seasonal_data
    }

    return output

if __name__ == "__main__":
    # 读取输入文件
    with open('input.json', 'r', encoding='utf-8') as f:
        input_data = json.load(f)

    # 处理数据
    print("正在处理负荷数据...")
    output_data = process_load_data(input_data)

    # 保存输出文件
    with open('output.json', 'w', encoding='utf-8') as f:
        json.dump(output_data, f, ensure_ascii=False, indent=2)

    print("数据处理完成，结果已保存到output.json")