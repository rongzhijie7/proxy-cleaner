```python
import yaml
import requests
import time
import subprocess
import re

# ======================
# YAML类型规范化
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

    # ======================
    # 修复节点字段类型
    # ======================

    p = normalize_proxy(p)

    old_name = p.get(
        "name",
        ""
    )

    # ======================
    # 删除无效节点
    # ======================

    if not old_name:
        continue

    if not p.get("server"):
        continue

    if not p.get("type"):
        continue

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


# ======================
# 启动 Mihomo
# ======================

print(
    "
