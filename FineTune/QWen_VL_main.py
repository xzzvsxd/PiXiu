import torch
from transformers import AutoModelForCausalLM, AutoTokenizer
from FineTune.config import QWen_VL_path

torch.manual_seed(1234)

model_name_or_path = QWen_VL_path

# Note: The default behavior now has injection attack prevention off.
tokenizer = AutoTokenizer.from_pretrained(model_name_or_path, trust_remote_code=True)

# use cuda device
model = AutoModelForCausalLM.from_pretrained(model_name_or_path, device_map="cuda", trust_remote_code=True).eval()

# 1st dialogue turn
query = tokenizer.from_list_format([
    {'image': 'https://qianwen-res.oss-cn-beijing.aliyuncs.com/Qwen-VL/assets/demo.jpeg'},
    {'text': '这是什么'},
])
response, history = model.chat(tokenizer, query=query, history=None)
print(response, history)
# 图中是一名年轻女子在沙滩上和她的狗玩耍，狗的品种可能是拉布拉多。她们坐在沙滩上，狗的前腿抬起来，似乎在和人类击掌。两人之间充满了信任和爱。

# 2nd dialogue turn
response, history = model.chat(tokenizer, '输出"女子"的检测框', history=history)
print(response, history)
# <ref>击掌</ref><box>(517,508),(589,611)</box>
image = tokenizer.draw_bbox_on_latest_picture(response, history)
if image:
    image.save('1.jpg')
else:
    print("no box")
