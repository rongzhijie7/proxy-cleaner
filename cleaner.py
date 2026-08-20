import yaml
import requests
import time
import subprocess
import os


print("开始生成测试配置")


with open("source.yaml","r",encoding="utf-8") as f:
    config=yaml.safe_load(f)


proxies=config["proxies"]


# 处理重复节点名称
name_count={}

for p in proxies:
    name=p["name"]

    if name in name_count:
        name_count[name]+=1
        p["name"]=f"{name}-{name_count[name]}"
    else:
        name_count[name]=1


names=[]

for p in proxies:
    names.append(p["name"])


test_config={

"mixed-port":7890,

"external-controller":"127.0.0.1:9090",

"proxies":proxies,

"proxy-groups":[
{
"name":"TEST",
"type":"url-test",
"proxies":names,
"url":"https://www.gstatic.com/generate_204",
"interval":300
}
]

}


with open("test.yaml","w",encoding="utf-8") as f:
    yaml.dump(
        test_config,
        f,
        allow_unicode=True
    )


print("启动 Mihomo")


process=subprocess.Popen(
    [
        "./mihomo",
        "-f",
        "test.yaml"
    ]
)


time.sleep(8)


print("读取测速结果")


r=requests.get(
    "http://127.0.0.1:9090/proxies/TEST/delay",
    params={
        "timeout":5000,
        "url":"https://www.gstatic.com/generate_204"
    }
)


print(r.text)


process.kill()
