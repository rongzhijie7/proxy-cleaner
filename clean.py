import yaml
import requests
import sys

GIST_URL = "https://gist.githubusercontent.com/rongzhijie7/76ce5d8efc7e0f92cda3b59a82536532/raw/VIP"
OUTPUT = "cleanvip.yaml"

MAX_ADVANCED_PER_REGION = 2

REGIONS = {
    "香港": ["香港", "hong kong", "hongkong"],
    "台湾": ["台湾", "taiwan"],
    "日本": ["日本", "japan"],
    "新加坡": ["新加坡", "狮城", "singapore"],
    "美国": ["美国", "usa", "america", "united states"],
    "英国": ["英国", "uk", "united kingdom"],
    "韩国": ["韩国", "korea"],
}


def get_region(name):
    name_lower = str(name).lower()

    for region, aliases in REGIONS.items():
        for alias in aliases:
            if alias.lower() in name_lower:
                return region

    return None


def is_experimental(name):
    name = str(name)

    return (
        "实验性" in name
        or "[实验]" in name
        or "【实验】" in name
    )


def is_advanced(name):
    name = str(name)

    return (
        "高级" in name
        or "[高级]" in name
        or "【高级】" in name
    )


def is_basic(name):
    name = str(name)

    return (
        "基础" in name
        or "[基础]" in name
        or "【基础】" in name
    )


print("=" * 80)
print("VIP 节点筛选")
print("=" * 80)

# ============================================================
# 直接读取 VIP Gist
# ============================================================

print("\n正在读取 VIP Gist...")

try:
    response = requests.get(
        GIST_URL,
        timeout=30,
        headers={
            "User-Agent": "Mozilla/5.0"
        }
    )

    response.raise_for_status()

    data = yaml.safe_load(response.text)

except Exception as e:
    print(f"❌ 读取 VIP Gist 失败: {e}")
    sys.exit(1)


if not isinstance(data, dict):
    print("❌ VIP Gist 不是有效的 YAML 配置")
    sys.exit(1)


proxies = data.get("proxies", [])

if not isinstance(proxies, list):
    print("❌ VIP Gist 中没有有效的 proxies")
    sys.exit(1)


print(f"VIP 原始节点: {len(proxies)}")


# ============================================================
# 实验性节点
# 每个地区只保留第一个
# ============================================================

experimental = {}

print("\n" + "-" * 80)
print("筛选实验性节点")
print("-" * 80)

for proxy in proxies:

    if not isinstance(proxy, dict):
        continue

    name = str(proxy.get("name", ""))

    # 基础节点不要
    if is_basic(name):
        continue

    # 不是实验节点不要
    if not is_experimental(name):
        continue

    region = get_region(name)

    if not region:
        print(f"跳过未知地区: {name}")
        continue

    # 每个地区只保留第一个
    if region in experimental:
        continue

    experimental[region] = proxy

    print(f"✅ {region}专线 ← {name}")


# ============================================================
# 高级节点
# 每个地区最多保留两个
# ============================================================

advanced = {}

print("\n" + "-" * 80)
print("筛选高级节点")
print("-" * 80)

for proxy in proxies:

    if not isinstance(proxy, dict):
        continue

    name = str(proxy.get("name", ""))

    # 基础节点不要
    if is_basic(name):
        continue

    # 不是高级节点不要
    if not is_advanced(name):
        continue

    region = get_region(name)

    if not region:
        print(f"跳过未知地区: {name}")
        continue

    if region not in advanced:
        advanced[region] = []

    # 每个地区最多两个
    if len(advanced[region]) >= MAX_ADVANCED_PER_REGION:
        continue

    advanced[region].append(proxy)

    number = len(advanced[region])

    if number == 1:
        new_name = f"{region}备用"
    else:
        new_name = f"{region}备用-{number}"

    print(f"✅ {new_name} ← {name}")


# ============================================================
# 生成最终结果
# ============================================================

result = []

print("\n" + "=" * 80)
print("生成 cleanvip.yaml")
print("=" * 80)


# ------------------------------------------------------------
# 实验性 → 专线
# ------------------------------------------------------------

for region in REGIONS:

    if region not in experimental:
        continue

    proxy = experimental[region]

    new_proxy = dict(proxy)

    new_name = f"{region}专线"

    new_proxy["name"] = new_name

    result.append(new_proxy)

    print(f"{proxy.get('name', '')} → {new_name}")


# ------------------------------------------------------------
# 高级 → 备用
# ------------------------------------------------------------

for region in REGIONS:

    if region not in advanced:
        continue

    for index, proxy in enumerate(advanced[region], 1):

        new_proxy = dict(proxy)

        if index == 1:
            new_name = f"{region}备用"
        else:
            new_name = f"{region}备用-{index}"

        new_proxy["name"] = new_name

        result.append(new_proxy)

        print(f"{proxy.get('name', '')} → {new_name}")


# ============================================================
# 检查重复名称
# ============================================================

print("\n" + "=" * 80)
print("检查节点名称")
print("=" * 80)

names = set()

for proxy in result:

    name = proxy.get("name", "")

    if name in names:
        print(f"❌ 重复节点名称: {name}")
        sys.exit(1)

    names.add(name)


print("✅ 节点名称没有重复")


# ============================================================
# 写入 cleanvip.yaml
# ============================================================

output = {
    "proxies": result
}

try:

    with open(OUTPUT, "w", encoding="utf-8") as f:

        yaml.safe_dump(
            output,
            f,
            allow_unicode=True,
            sort_keys=False
        )

except Exception as e:

    print(f"❌ 写入 {OUTPUT} 失败: {e}")
    sys.exit(1)


# ============================================================
# 最终统计
# ============================================================

experimental_count = len(experimental)

advanced_count = sum(
    len(items)
    for items in advanced.values()
)

print("\n" + "=" * 80)
print("筛选完成")
print("=" * 80)

print(f"VIP 原始节点 : {len(proxies)}")
print(f"实验性节点   : {experimental_count}")
print(f"高级节点     : {advanced_count}")
print(f"最终节点     : {len(result)}")

print("\ncleanvip.yaml:")

for i, proxy in enumerate(result, 1):
    print(f"{i:02d}. {proxy.get('name', '')}")

print("\n" + "=" * 80)
print("✅ 完成")
print("=" * 80)
