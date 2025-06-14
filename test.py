import json
from service.optimization.intelligent_solution_service import ISService

opt_input_file = "./io_template/opt_input.json"
with open(opt_input_file, 'r', encoding='utf-8') as f:
    param_input = json.load(f)

service = ISService()
result = service.planning_opt(param_input=param_input)
