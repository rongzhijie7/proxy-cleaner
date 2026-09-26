import yaml
import sys

SOURCE = "source.yaml"
OUTPUT = "cleanvip.yaml"

# ============================================================
# 配置
# ============================================================

# 每个地区最多保留几个高级节点
MAX_ADVANCED_PER_REGION = 2

# 只处理这些地区
REGIONS = {
    "香港": ["香港", "hong kong", "hongkong"],
    "台湾": ["台湾", "taiwan"],
    "日本": ["日本", "japan"],
    "新加坡": ["新加坡", "狮城", "singapore"],
    "美国": ["美国", "usa", "america", "united states"],
    "英国": ["英国", "uk", "united kingdom"],
    "韩国": ["韩国", "korea"],
}


# ============================================================
# 根据节点名称识别地区
# ============================================================

def get_region(name):
    name_lower = str(name).lower()

    for region, aliases in REGIONS.items():
        for alias in aliases:
            if alias.lower() in name_lower:
                return region

    return None


# ============================================================
# 判断节点类型
# ============================================================

def is_experimental(name):
    """
    实验性节点同时支持：

    1. 实验性 IEPL
    2. [实验]

    例如：
    🇭🇰 香港实验性 IEPL 专线 1
    [实验] 🇭🇰 香港
    """

    name = str(name)

    return (
        "实验性" in name
        or "[实验]" in name
        or "【实验】" in name
    )


def is_advanced(name):
    """
    高级节点同时支持：

    [高级]
    高级
    """

    name = str(name)

    return (
        "高级" in name
        or "[高级]" in name
        or "【高级】" in name
    )


def is_basic(name):
    """
    基础节点全部排除
    """

    name = str(name)

    return (
        "基础" in name
        or "[基础]" in name
        or "【基础】" in name
    )


# ============================================================
# 开始
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
# 第一阶段：实验性节点
# ============================================================

experimental = {}

print("\n" + "-" * 80)
print("筛选实验性节点")
print("-" * 80)

for proxy in proxies:

    name = str(proxy.get("name", ""))

    # 基础节点永远不要
    if is_basic(name):
        continue

    if not is_experimental(name):
        continue

    region = get_region(name)

    if not region:
        print(f"跳过实验性节点（地区未知）: {name}")
        continue

    # 每个地区只保留第一个
    if region in experimental:
        continue

    experimental[region] = proxy

    print(f"✅ {region} 专线 <- {name}")


# ============================================================
# 第二阶段：高级节点
# ============================================================

advanced = {}

print("\n" + "-" * 80)
print("筛选高级节点")
print("-" * 80)

for proxy in proxies:

    name = str(proxy.get("name", ""))

    # 基础节点永远不要
    if is_basic(name):
        continue

    if not is_advanced(name):
        continue

    region = get_region(name)

    if not region:
        print(f"跳过高级节点（地区未知）: {name}")
        continue

    if region not in advanced:
        advanced[region] = []

    # 每个地区最多两个高级节点
    if len(advanced[region]) >= MAX_ADVANCED_PER_REGION:
        continue

    advanced[region].append(proxy)

    number = len(advanced[region])

    print(
        f"✅ {region} 备用-{number} <- {name}"
    )


# ============================================================
# 第三阶段：生成最终节点
# ============================================================

result = []

print("\n" + "=" * 80)
print("生成最终节点")
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

    old_name = proxy.get("name", "")

    new_proxy["name"] = new_name

    result.append(new_proxy)

    print(
        f"实验性: {old_name} → {new_name}"
    )


# ------------------------------------------------------------
# 高级 → 备用
# ------------------------------------------------------------

for region in REGIONS:

    if region not in advanced:
        continue

    for index, proxy in enumerate(
        advanced[region],
        1
    ):

        new_proxy = dict(proxy)

        old_name = proxy.get("name", "")

        if index == 1:
            new_name = f"{region}备用"
        else:
            new_name = f"{region}备用-{index}"

        new_proxy["name"] = new_name

        result.append(new_proxy)

        print(
            f"高级: {old_name} → {new_name}"
        )


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

        print(f"❌ 发现重复名称: {name}")
        sys.exit(1)

    names.add(name)


print("✅ 节点名称没有重复")


# ============================================================
# 生成 cleanvip.yaml
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
# 最终统计
# ============================================================

print("\n" + "=" * 80)
print("最终结果")
print("=" * 80)

print(f"原始节点: {len(proxies)}")
print(f"实验性节点: {len(experimental)}")
print(
    f"高级节点: "
    f"{sum(len(items) for items in advanced.values())}"
)
print(f"最终节点: {len(result)}")


# ============================================================
# 输出最终节点
# ============================================================

print("\n" + "-" * 80)
print("cleanvip.yaml 节点")
print("-" * 80)

for i, proxy in enumerate(result, 1):

    print(
        f"{i:02d}. "
        f"{proxy.get('name')}"
    )


print("\n" + "=" * 80)
print("✅ 筛选完成")
print("=" * 80)

print(f"最终生成: {OUTPUT}")
print("不测速、不删除，仅根据 VIP 源文件原始名称筛选。")
