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
import json
from schema.schema_optimization import OptimizationBody

with open("./resource/optimization.json", "r", encoding="utf-8") as f:
    data = json.load(f)

optimization_body = OptimizationBody(**data)

opt_dict = optimization_body.model_dump()

for key, value in opt_dict.items():
    print(f"{key} : {value}")
