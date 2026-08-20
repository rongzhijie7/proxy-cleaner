import yaml
import requests
import time
import subprocess


# ======================
# 地区关键词
# ======================

REGIONS = [
    "香港",
    "澳门",
    "台湾",
    "新加坡",
    "狮城",
    "日本",
    "韩国",
    "美国",
    "英国",
    "德国",
    "法国",
    "加拿大",
    "澳大利亚",
    "印度",
    "土耳其"
]


# ======================
# 读取订阅
# ======================

print("读取 source.yaml")


with open(
    "source.yaml",
    "r",
    encoding="utf-8"
) as f:

    config = yaml.safe_load(f)


raw_proxies = config.get(
    "proxies",
    []
)


print(
    "原始节点:",
    len(raw_proxies)
)


# ======================
# 地区筛选 + 重命名
# ======================

region_count = {}

proxies = []


for p in raw_proxies:

    old_name = p.get(
        "name",
        ""
    )


    region = None


    for r in REGIONS:

        if r in old_name:

            region = r
            break


    if region:

        if region == "狮城":
            region = "新加坡"


        region_count.setdefault(
            region,
            0
        )


        region_count[region] += 1


        p["name"] = (
            f"{region}-"
            f"{region_count[region]}"
        )


        proxies.append(p)



print(
    "地区筛选后:",
    len(proxies)
)



# ======================
# 生成 Mihomo 测试配置
# ======================


names = [
    p["name"]
    for p in proxies
]


test_config = {

    "mixed-port":7890,

    "external-controller":
        "127.0.0.1:9090",

    "proxies":
        proxies,


    "proxy-groups":[

        {
            "name":"TEST",
            "type":"url-test",
            "proxies":names,
            "url":
            "https://www.gstatic.com/generate_204",
            "interval":300
        }

    ]

}



with open(
    "test.yaml",
    "w",
    encoding="utf-8"
) as f:

    yaml.dump(
        test_config,
        f,
        allow_unicode=True,
        sort_keys=False
    )



# ======================
# 启动 Mihomo
# ======================

print(
    "启动 Mihomo"
)


process = subprocess.Popen(
    [
        "./mihomo",
        "-f",
        "test.yaml"
    ]
)


time.sleep(5)



# ======================
# 节点测速
# ======================

print(
    "开始测速"
)


alive=[]


for name in names:


    try:

        r=requests.get(

            f"http://127.0.0.1:9090/proxies/{name}/delay",

            params={

                "timeout":5000,

                "url":
                "https://www.gstatic.com/generate_204"

            },

            timeout=8

        )


        data=r.json()


        if "delay" in data:


            delay=data["delay"]


            print(
                name,
                delay,
                "ms"
            )


            alive.append(name)


        else:

            print(
                name,
                "FAIL"
            )


    except Exception:


        print(
            name,
            "FAIL"
        )



print(
    "可用节点:",
    len(alive)
)



# ======================
# 输出 clean.yaml
# ======================


alive_set=set(alive)


clean=[]


for p in proxies:

    if p["name"] in alive_set:

        clean.append(p)



output={

    "proxies":
        clean

}



with open(
    "clean.yaml",
    "w",
    encoding="utf-8"
) as f:


    yaml.dump(

        output,

        f,

        allow_unicode=True,

        sort_keys=False

    )



print(
    "clean.yaml生成完成:",
    len(clean),
    "个节点"
)



process.kill()
