import yaml
import requests
import time
import subprocess
import re

# ============================================================
# YAML 类型规范化
# ============================================================

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


# ============================================================
# 地区顺序
# ============================================================

REGIONS = [
    "香港",
    "澳门",
    "台湾",
    "新加坡",
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


# ============================================================
# 读取 source.yaml
# ============================================================

print("=" * 60)
print("读取 source.yaml")
print("=" * 60)

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


# ============================================================
# 地区筛选
# ============================================================

region_count = {}

proxies = []


for p in raw_proxies:

    # --------------------------------------------------------
    # 修复节点字段类型
    # --------------------------------------------------------

    p = normalize_proxy(p)


    old_name = p.get(
        "name",
        ""
    )


    # --------------------------------------------------------
    # 删除无效节点
    # --------------------------------------------------------

    if not old_name:
        continue


    if not p.get("server"):
        continue


    if not p.get("type"):
        continue


    # --------------------------------------------------------
    # 判断地区
    # --------------------------------------------------------

    region = None


    for r in REGIONS:

        if r in old_name:

            region = r

            break


    # 狮城统一归入新加坡
    if region == "狮城":

        region = "新加坡"


    if region:

        region_count.setdefault(
            region,
            0
        )

        region_count[region] += 1


        # ----------------------------------------------------
        # 临时名称
        # ----------------------------------------------------

        p["name"] = (
            f"{region}-"
            f"{region_count[region]}"
        )


        proxies.append(p)


print(
    "地区筛选后:",
    len(proxies)
)


# ============================================================
# 生成 Mihomo 测试配置
# ============================================================

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


# ============================================================
# 启动 Mihomo
# ============================================================

print()
print("=" * 60)
print("启动 Mihomo")
print("=" * 60)


process = subprocess.Popen(
    [
        "./mihomo",
        "-f",
        "test.yaml"
    ]
)


# 等待 Mihomo 启动
time.sleep(5)


# ============================================================
# 节点测速
# ============================================================

print()
print("=" * 60)
print("开始测速")
print("=" * 60)


alive = []


for name in names:

    try:

        r = requests.get(

            f"http://127.0.0.1:9090/proxies/{name}/delay",

            params={

                "timeout": 5000,

                "url":
                    "https://www.gstatic.com/generate_204"

            },

            timeout=8
        )


        data = r.json()


        if "delay" in data:

            delay = data["delay"]


            print(
                f"{name}: {delay} ms"
            )


            alive.append(name)


        else:

            print(
                f"{name}: FAIL"
            )


    except Exception as e:

        print(
            f"{name}: FAIL"
        )


print()
print(
    "测速成功节点:",
    len(alive)
)


# ============================================================
# 只保留测速成功节点
# ============================================================

alive_set = set(alive)


clean = []


for p in proxies:

    if p["name"] in alive_set:

        clean.append(p)


# ============================================================
# 按地区顺序排序
# ============================================================

region_index = {

    region: index

    for index, region in enumerate(
        REGIONS
    )

}


def get_region(name):

    for region in REGIONS:

        if name.startswith(
            region + "-"
        ):

            return region


    return None


clean.sort(

    key=lambda p:
        region_index.get(
            get_region(
                p.get("name", "")
            ),
            999
        )

)


# ============================================================
# 测速成功后重新连续编号
# ============================================================

new_region_count = {}


for p in clean:

    old_name = p.get(
        "name",
        ""
    )


    region = get_region(
        old_name
    )


    if not region:
        continue


    new_region_count.setdefault(
        region,
        0
    )


    new_region_count[region] += 1


    p["name"] = (

        f"{region}-"

        f"{new_region_count[region]}"

    )


# ============================================================
# 输出 clean.yaml
# ============================================================

output = {

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


# ============================================================
# 显示最终节点顺序
# ============================================================

print()
print("=" * 60)
print("最终节点顺序")
print("=" * 60)


for p in clean:

    print(
        p["name"]
    )


print()
print("=" * 60)
print(
    "clean.yaml 生成完成:",
    len(clean),
    "个节点"
)
print("=" * 60)


# ============================================================
# 关闭 Mihomo
# ============================================================

process.kill()
