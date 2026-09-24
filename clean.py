import yaml
import requests
import time
import subprocess
import re
import urllib.parse


# ======================
# YAML 类型规范化
# ======================

def normalize_value(v):

    if isinstance(v, str):

        if v.lower() == "true":
            return True

        if v.lower() == "false":
            return False

        if re.fullmatch(r"\d+", v):
            return int(v)

    return v


def normalize_proxy(proxy):

    new_proxy = {}

    for key, value in proxy.items():
        new_proxy[key] = normalize_value(value)

    return new_proxy


# ======================
# 地区关键词
# ======================

REGIONS = [
    "香港",
    "台湾",
    "日本",
    "新加坡",
    "狮城",
    "美国",
    "英国",
    "韩国",
]


REGION_ALIASES = {
    "hong kong": "香港",
    "hongkong": "香港",
    "taiwan": "台湾",
    "japan": "日本",
    "singapore": "新加坡",
    "united states": "美国",
    "usa": "美国",
    "america": "美国",
    "united kingdom": "英国",
    "uk": "英国",
    "korea": "韩国",
}


def get_region(name):

    for region in REGIONS:

        if region in name:

            if region == "狮城":
                return "新加坡"

            return region

    lower_name = name.lower()

    for alias, region in REGION_ALIASES.items():

        if alias in lower_name:
            return region

    return None


# ======================
# 读取 source.yaml
# ======================

print()
print("======================================")
print("读取 source.yaml")
print("======================================")


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
# 地区筛选
# ======================

region_count = {}

proxies = []


for raw_proxy in raw_proxies:

    p = normalize_proxy(raw_proxy)

    old_name = str(
        p.get(
            "name",
            ""
        )
    )


    if not old_name:
        continue


    if not p.get("server"):
        continue


    if not p.get("type"):
        continue


    region = get_region(old_name)


    if not region:
        continue


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


print()
print("======================================")
print("地区筛选完成")
print("======================================")

print(
    "筛选后节点:",
    len(proxies)
)


for p in proxies:

    print(
        p["name"],
        "<-",
        p.get("server")
    )


# ======================
# 生成 Mihomo 测试配置
# ======================

names = [
    p["name"]
    for p in proxies
]


test_config = {

    "mixed-port": 7890,

    "external-controller":
        "127.0.0.1:9090",

    "proxies":
        proxies,

    "proxy-groups": [

        {

            "name": "TEST",

            "type": "url-test",

            "proxies": names,

            "url":
                "https://www.gstatic.com/generate_204",

            "interval": 300

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


print()
print("test.yaml 已生成")


# ======================
# 启动 Mihomo
# ======================

print()
print("======================================")
print("启动 Mihomo")
print("======================================")


process = subprocess.Popen(
    [
        "./mihomo",
        "-f",
        "test.yaml"
    ]
)


# ======================
# 等待 Mihomo
# ======================

print("等待 Mihomo API...")


api_ready = False


for i in range(20):

    try:

        r = requests.get(
            "http://127.0.0.1:9090/proxies",
            timeout=2
        )


        if r.status_code == 200:

            api_ready = True

            print(
                "Mihomo API 已启动"
            )

            break


    except Exception:

        pass


    time.sleep(1)


if not api_ready:

    print(
        "❌ Mihomo API 启动失败"
    )

    process.kill()

    raise SystemExit(1)


time.sleep(3)


# ======================
# 节点测速
# ======================

print()
print("======================================")
print("开始节点测速")
print("======================================")


alive = []


for index, name in enumerate(
    names,
    start=1
):

    print()
    print(
        f"[{index}/{len(names)}]",
        name
    )


    encoded_name = urllib.parse.quote(
        name,
        safe=""
    )


    try:

        r = requests.get(

            f"http://127.0.0.1:9090/proxies/{encoded_name}/delay",

            params={

                "timeout": 5000,

                "url":
                    "https://www.gstatic.com/generate_204"

            },

            timeout=8

        )


        print(
            "HTTP:",
            r.status_code
        )


        print(
            "返回:",
            r.text[:500]
        )


        if r.status_code != 200:

            print(
                "❌ 测速失败"
            )

            continue


        data = r.json()


        if "delay" in data:

            delay = data["delay"]


            print(
                "✅ 延迟:",
                delay,
                "ms"
            )


            alive.append(name)


        else:

            print(
                "❌ 没有 delay"
            )


    except Exception as e:

        print(
            "❌ 异常:",
            repr(e)
        )


# ======================
# 输出结果
# ======================

print()
print("======================================")
print("测速完成")
print("======================================")


print(
    "检测节点:",
    len(proxies)
)


print(
    "测速成功:",
    len(alive)
)


print(
    "测速失败:",
    len(proxies) - len(alive)
)


# ======================
# 暂时不删除
# ======================

output = {

    "proxies":
        proxies

}


with open(
    "cleanvip.yaml",
    "w",
    encoding="utf-8"
) as f:

    yaml.dump(

        output,

        f,

        allow_unicode=True,

        sort_keys=False

    )


print()
print("======================================")
print("cleanvip.yaml 已生成")
print("======================================")

print(
    "输出节点:",
    len(proxies)
)


# ======================
# 关闭 Mihomo
# ======================

print()
print("关闭 Mihomo")


process.kill()

try:

    process.wait(
        timeout=5
    )

except Exception:

    pass
