from docx import Document
import re
import pprint
import json

# 1）打开 docx 并提取所有段落文本
doc = Document("./输出文档/智能性软件输出文本模板-简要版本(3).docx")
content = "\n".join(p.text for p in doc.paragraphs)

# 2）正则抽取
keys = set(re.findall(r"\{([^{}]+)\}", content))

# 3）生成字典
placeholder_dict = {key.strip(): "" for key in sorted(keys)}

# 4）查看结果
pprint.pprint(placeholder_dict)
with open('./输出文档/file_param.json', 'w', encoding='utf-8') as f:
    json.dump(placeholder_dict, f, ensure_ascii=False, indent=4)
