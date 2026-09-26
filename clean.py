import yaml
import sys

SOURCE = "source.yaml"
OUTPUT = "cleanvip.yaml"


# ============================================================
# 地区识别
# ============================================================

REGIONS = {
    "香港": [
        "香港",
        "hong kong",
        "hongkong",
    ],

    "台湾": [
        "台湾",
        "taiwan",
    ],

    "日本": [
        "日本",
        "japan",
    ],

    "新加坡": [
        "新加坡",
        "狮城",
        "singapore",
    ],

    "美国": [
        "美国",
        "usa",
        "america",
        "united states",
    ],

    "英国": [
        "英国",
        "uk",
        "united kingdom",
    ],

    "韩国": [
        "韩国",
        "korea",
    ],
}


def get_region(name):
    """
    根据节点名称识别地区
    """
    name_lower = str(name).lower()

    for region, aliases in REGIONS.items():

        for alias in aliases:

            if alias.lower() in name_lower:
                return region

    return None


# ============================================================
# 读取源文件
# ============================================================

print("=" * 80)
print("VIP 节点筛选")
print("=" * 80)

print("\n读取 source.yaml...")

try:

    with open(SOURCE, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

except Exception as e:

    print(f"❌ 读取 source.yaml 失败: {e}")
    sys.exit(1)


if not isinstance(data, dict):

    print("❌ source.yaml 格式错误")
    sys.exit(1)


proxies = data.get("proxies", [])

if not isinstance(proxies, list):

    print("❌ source.yaml 中没有有效的 proxies")
    sys.exit(1)


print(f"原始节点: {len(proxies)}")


# ============================================================
# 第一类：实验性
#
# 每个地区最多保留 1 个
# ============================================================

experimental = {}

print("\n" + "-" * 80)
print("筛选实验性节点")
print("-" * 80)


for proxy in proxies:

    name = str(proxy.get("name", ""))

    if "实验性" not in name:
        continue

    region = get_region(name)

    if not region:

        print(
            f"跳过实验性节点（地区未知）: {name}"
        )

        continue

    # 每个地区只保留第一个
    if region in experimental:

        continue

    experimental[region] = proxy

    print(
        f"✅ {region} <- {name}"
    )


# ============================================================
# 第二类：高级
#
# 每个地区最多保留 2 个
# ============================================================

advanced = {}

print("\n" + "-" * 80)
print("筛选高级节点")
print("-" * 80)


for proxy in proxies:

    name = str(proxy.get("name", ""))

    if "高级" not in name:
        continue

    region = get_region(name)

    if not region:

        print(
            f"跳过高级节点（地区未知）: {name}"
        )

        continue

    advanced.setdefault(region, [])

    if len(advanced[region]) >= 2:
        continue

    advanced[region].append(proxy)

    print(
        f"✅ {region} 高级-{len(advanced[region])} "
        f"<- {name}"
    )


# ============================================================
# 生成最终节点
# ============================================================

result = []


print("\n" + "=" * 80)
print("生成最终节点")
print("=" * 80)


# ============================================================
# 实验性
# ============================================================

for region, proxy in experimental.items():

    new_proxy = dict(proxy)

    new_proxy["name"] = f"{region}专线"

    result.append(new_proxy)

    print(
        f"实验性: {proxy.get('name')} "
        f"→ {new_proxy['name']}"
    )


# ============================================================
# 高级
# ============================================================

for region, items in advanced.items():

    for index, proxy in enumerate(items, 1):

        new_proxy = dict(proxy)

        if index == 1:

            new_name = f"{region}备用"

        else:

            new_name = f"{region}备用-{index}"

        new_proxy["name"] = new_name

        result.append(new_proxy)

        print(
            f"高级: {proxy.get('name')} "
            f"→ {new_name}"
        )


# ============================================================
# 最终检查
# ============================================================

print("\n" + "=" * 80)
print("最终结果")
print("=" * 80)


print(f"原始节点: {len(proxies)}")
print(f"实验性: {len(experimental)}")
print(
    f"高级: {sum(len(x) for x in advanced.values())}"
)
print(f"最终节点: {len(result)}")


# ============================================================
# 防止名称重复
# ============================================================

names = []

for proxy in result:

    name = proxy.get("name")

    if name in names:

        print(
            f"❌ 发现重复名称: {name}"
        )

        sys.exit(1)

    names.append(name)


# ============================================================
# 输出
# ============================================================

output = {
    "proxies": result
}


try:

    with open(
        OUTPUT,
        "w",
        encoding="utf-8"
    ) as f:

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
# 输出清单
# ============================================================

print("\n" + "-" * 80)
print("cleanvip.yaml 节点")
print("-" * 80)


for i, proxy in enumerate(result, 1):

    print(
        f"{i:02d}. {proxy.get('name')}"
    )


print("\n" + "=" * 80)
print("✅ 筛选完成")
print("=" * 80)

print(
    f"最终生成: {OUTPUT}"
)

print(
    "本版本不测速、不删除节点，仅按照名称规则筛选。"
)
