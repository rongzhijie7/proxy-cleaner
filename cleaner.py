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


print("开始逐节点测速")


alive=[]

for name in names:

    try:

        r=requests.get(
            f"http://127.0.0.1:9090/proxies/{name}/delay",
            params={
                "timeout":5000,
                "url":"https://www.gstatic.com/generate_204"
            },
            timeout=8
        )

        result=r.json()

        if "delay" in result:

            print(
                name,
                result["delay"],
                "ms"
            )

            alive.append(name)

        else:
            print(
                name,
                "FAIL"
            )

    except Exception as e:

        print(
            name,
            "ERROR"
        )


print(
    "可用节点:",
    len(alive)
)


process.kill()
