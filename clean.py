import requests
import yaml
import re

SOURCE_URL = "https://gist.githubusercontent.com/rongzhijie7/76ce5d8efc7e0f92cda3b59a82536532/raw/VIP"
OUTPUT_FILE = "cleanvip.yaml"

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
    "狮城": "新加坡",
    "united states": "美国",
    "usa": "美国",
    "america": "美国",
    "united kingdom": "英国",
    "uk": "英国",
    "korea": "韩国",
}


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
    return {
        key: normalize_value(value)
        for key, value in proxy.items()
    }


def get_region(name):
    for region in REGIONS:
        if region in name:
            return "新加坡" if region == "狮城" else region

    lower_name = name.lower()

    for alias, region in REGION_ALIASES.items():
        if alias in lower_name:
            return region

    return None


def main():

    print("======================================")
    print("VIP 节点清洗")
    print("======================================")

    # 下载 VIP
    print("下载 VIP Gist...")

    r = requests.get(
        SOURCE_URL,
        timeout=30,
        headers={"User-Agent": "Mozilla/5.0"}
    )

    r.raise_for_status()

    config = yaml.safe_load(r.text)

    raw_proxies = config.get("proxies", [])

    print("原始节点:", len(raw_proxies))

    # --------------------------------------------------
    # 第一阶段：收集实验性、高级
    # --------------------------------------------------

    experimental = {}
    advanced = {}

    for raw in raw_proxies:

        proxy = normalize_proxy(raw)

        name = str(proxy.get("name", ""))

        if not name:
            continue

        if not proxy.get("server"):
            continue

        if not proxy.get("type"):
            continue

        # 实验性
        if "实验性" in name:

            region = get_region(name)

            if not region:
                continue

            if region not in experimental:
                experimental[region] = proxy

        # 高级
        elif "高级" in name:

            region = get_region(name)

            if not region:
                continue

            advanced.setdefault(region, []).append(proxy)

    # --------------------------------------------------
    # 第二阶段：生成最终节点
    # --------------------------------------------------

    result = []

    print()
    print("实验性节点:")

    for region, proxy in experimental.items():

        proxy["name"] = f"{region}专线"

        result.append(proxy)

        print(" ", proxy["name"])

    print()
    print("高级节点:")

    for region, proxies in advanced.items():

        # 每个地区最多两个
        for index, proxy in enumerate(proxies[:2], start=1):

            if index == 1:
                proxy["name"] = f"{region}备用"
            else:
                proxy["name"] = f"{region}备用-{index}"

            result.append(proxy)

            print(" ", proxy["name"])

        if len(proxies) > 2:
            print(
                f"  {region}: "
                f"原有 {len(proxies)} 个，仅保留 2 个"
            )

    # --------------------------------------------------
    # 没有节点时，不覆盖旧文件
    # --------------------------------------------------

    if not result:

        print()
        print("❌ 没有符合条件的节点")
        print("不覆盖原有 cleanvip.yaml")
        return

    # --------------------------------------------------
    # 输出
    # --------------------------------------------------

    output = {
        "proxies": result
    }

    with open(
        OUTPUT_FILE,
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
    print("清洗完成")
    print("最终节点:", len(result))
    print("输出文件:", OUTPUT_FILE)
    print("======================================")


if __name__ == "__main__":
    main()
