import json
from schema.schema_optimization import OptimizationBody
from service.optimization.intelligent_solution_service import ISService


def json_compact_lists(obj, indent=4, current_indent=0):
    """递归格式化 JSON 数据, 确保所有列表都紧凑显示在一行上

    Args:
        obj: 要格式化的对象 (可能为字典, 列表或基本数据类型).
        indent: 缩进空格数 (默认为 4).
        current_indent: 当前缩进级别, 用于递归调用.

    Returns:
        格式化后的字符串.
    """
    ind = " " * current_indent
    next_ind = " " * (current_indent + indent)

    if isinstance(obj, dict):
        if not obj:
            return "{}"
        items = []
        for k, v in obj.items():
            # 使用 json.dumps 对 key 进行处理，确保转义正确
            formatted_value = json_compact_lists(v, indent=indent, current_indent=current_indent + indent)
            items.append(f'{next_ind}{json.dumps(k, ensure_ascii=False)}: {formatted_value}')
        return "{\n" + ",\n".join(items) + "\n" + ind + "}"
    elif isinstance(obj, list):
        # 判断列表中是否所有元素均为基本类型
        if all(isinstance(item, (int, float, str, bool, type(None))) for item in obj):
            # 基本类型列表：紧凑输出在一行
            items = [json.dumps(item, ensure_ascii=False) for item in obj]
            return "[" + ", ".join(items) + "]"
        else:
            # 含有非基本类型元素的列表：递归处理
            items = []
            for item in obj:
                formatted_item = json_compact_lists(item, indent=indent, current_indent=current_indent + indent)
                items.append(f"{next_ind}{formatted_item}")
            return "[\n" + ",\n".join(items) + "\n" + ind + "]"
    else:
        # 对基本数据类型直接使用 json.dumps
        return json.dumps(obj, ensure_ascii=False)


def dump_json_with_compact_lists(data: dict, file_path, indent=4):
    """将字典数据写入 JSON 文件, 保证所有列表均在一行中显示

    Args:
        data (dict): 输入数据.
        file_path (str): 输出文件路径.
        indent: 缩进空格数 (默认为 4).
    """
    # 若 data 不是字典类型, 抛出异常
    if not isinstance(data, dict):
        raise TypeError("输入数据不是字典类型, 请检查输入数据格式.")
    json_str = json_compact_lists(data, indent=indent)
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(json_str)


opt_input_file = "./io_template/opt_input_demo.json"
with open(opt_input_file, 'r', encoding='utf-8') as f:
    param_input = json.load(f)

input_body = OptimizationBody.model_validate(param_input)

service = ISService()
# result = service.planning_opt(param_input=param_input)
result = service.exec(input_body)

opt_output_file = "./io_template/opt_output_demo.json"
dump_json_with_compact_lists(result, opt_output_file, indent=4)
