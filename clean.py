import yaml
import requests
import subprocess
import time
import urllib.parse
import os
import sys
import re

SOURCE = "source.yaml"
TEST_URL = "https://www.gstatic.com/generate_204"
TIMEOUT = 5000
API = "http://127.0.0.1:9090"

REGIONS = {
    "香港": ["香港", "hong kong", "hongkong"],
    "台湾": ["台湾", "taiwan"],
    "日本": ["日本", "japan"],
    "新加坡": ["新加坡", "狮城", "singapore"],
    "美国": ["美国", "usa", "u.s.a", "america", "united states"],
    "英国": ["英国", "uk", "u.k.", "united kingdom"],
    "韩国": ["韩国", "korea"],
}


def get_region(name):
    name = str(name).lower()

    for region, aliases in REGIONS.items():
        for alias in aliases:
            if alias.lower() in name:
                return region

    return None


def get_type(proxy):
    return str(proxy.get("type", "unknown"))


def get_server(proxy):
    return str(proxy.get("server", ""))


def get_port(proxy):
    return str(proxy.get("port", ""))


def safe_name(name):
    return urllib.parse.quote(str(name), safe="")


def test_node(name):
    url = (
        f"{API}/proxies/{safe_name(name)}/delay"
        f"?timeout={TIMEOUT}"
        f"&url={urllib.parse.quote(TEST_URL, safe='')}"
    )

    try:
        r = requests.get(url, timeout=8)

        try:
            data = r.json()
        except Exception:
            data = r.text

        if r.status_code == 200:
            delay = None

            if isinstance(data, dict):
                delay = data.get("delay")

            return True, delay, r.status_code, data

        return False, None, r.status_code, data

    except Exception as e:
        return False, None, None, str(e)


print("=" * 90)
print("VIP 节点对照诊断")
print("=" * 90)

print("\n# 读取 source.yaml")

with open(SOURCE, "r", encoding="utf-8") as f:
    data = yaml.safe_load(f)

proxies = data.get("proxies", [])

print(f"\n# 原始节点: {len(proxies)}")


# ============================================================
# 1. 筛选实验性节点
# ============================================================

experimental = []

for proxy in proxies:
    name = str(proxy.get("name", ""))

    if "实验性" not in name:
        continue

    region = get_region(name)

    if not region:
        continue

    experimental.append({
        "proxy": proxy,
        "region": region,
        "category": "实验性",
        "original_name": name
    })


# ============================================================
# 2. 筛选高级节点
# ============================================================

advanced_all = {}

for proxy in proxies:
    name = str(proxy.get("name", ""))

    if "高级" not in name:
        continue

    region = get_region(name)

    if not region:
        print(f"跳过高级节点（地区未知）: {name}")
        continue

    advanced_all.setdefault(region, []).append({
        "proxy": proxy,
        "region": region,
        "category": "高级",
        "original_name": name
    })


advanced = []

for region, items in advanced_all.items():
    print(
        f"{region}: 原有 {len(items)} 个高级节点，"
        f"仅测试前 2 个"
    )

    advanced.extend(items[:2])


# ============================================================
# 3. 组成14个VIP候选
# ============================================================

vip_candidates = experimental + advanced

print("\n" + "=" * 80)
print("VIP候选节点")
print("=" * 80)

for i, item in enumerate(vip_candidates, 1):
    proxy = item["proxy"]

    print(
        f"[VIP {i:02d}] "
        f"{item['category']} | "
        f"{item['region']} | "
        f"{item['original_name']} | "
        f"type={get_type(proxy)} | "
        f"server={get_server(proxy)} | "
        f"port={get_port(proxy)}"
    )

print(f"\nVIP候选总数: {len(vip_candidates)}")


# ============================================================
# 4. 自动寻找5个普通节点作为对照
#
# 排除：
#   实验性
#   高级
#   基础
#
# 优先选择名称带地区的普通节点
# ============================================================

control_candidates = []

for proxy in proxies:

    name = str(proxy.get("name", ""))

    if "实验性" in name:
        continue

    if "高级" in name:
        continue

    if "基础" in name:
        continue

    region = get_region(name)

    if not region:
        continue

    control_candidates.append({
        "proxy": proxy,
        "region": region,
        "category": "普通对照",
        "original_name": name
    })

# 尽量覆盖不同地区
selected_controls = []

used_regions = set()

for item in control_candidates:
    if len(selected_controls) >= 5:
        break

    if item["region"] not in used_regions:
        selected_controls.append(item)
        used_regions.add(item["region"])


# 如果地区去重后不足5个，再补
if len(selected_controls) < 5:

    selected_names = {
        x["original_name"]
        for x in selected_controls
    }

    for item in control_candidates:

        if len(selected_controls) >= 5:
            break

        if item["original_name"] in selected_names:
            continue

        selected_controls.append(item)


print("\n" + "=" * 80)
print("普通节点对照组")
print("=" * 80)

for i, item in enumerate(selected_controls, 1):

    proxy = item["proxy"]

    print(
        f"[普通 {i:02d}] "
        f"{item['region']} | "
        f"{item['original_name']} | "
        f"type={get_type(proxy)} | "
        f"server={get_server(proxy)} | "
        f"port={get_port(proxy)}"
    )

print(f"\n普通对照总数: {len(selected_controls)}")


# ============================================================
# 5. 合并测试节点
# ============================================================

all_candidates = vip_candidates + selected_controls

print("\n" + "=" * 90)
print("开始建立 Mihomo 测试配置")
print("=" * 90)

test_proxies = []

seen_names = set()

for item in all_candidates:

    proxy = dict(item["proxy"])
    name = item["original_name"]

    # 防止重名
    if name in seen_names:
        print(f"⚠️ 发现重复节点名称，跳过: {name}")
        continue

    seen_names.add(name)

    # 测试期间完全保持原始节点名称和字段
    proxy["name"] = name

    test_proxies.append(proxy)


test_config = {
    "mixed-port": 7890,
    "allow-lan": False,
    "mode": "rule",

    "log-level": "info",

    "proxies": test_proxies,

    "proxy-groups": [
        {
            "name": "TEST",
            "type": "select",
            "proxies": [p["name"] for p in test_proxies]
        }
    ]
}

with open("test.yaml", "w", encoding="utf-8") as f:
    yaml.safe_dump(
        test_config,
        f,
        allow_unicode=True,
        sort_keys=False
    )

print(f"测试节点数: {len(test_proxies)}")


# ============================================================
# 6. 重启 Mihomo
# ============================================================

print("\n启动 Mihomo...")

subprocess.run(
    ["pkill", "-9", "mihomo"],
    stdout=subprocess.DEVNULL,
    stderr=subprocess.DEVNULL
)

time.sleep(1)

mihomo = subprocess.Popen(
    ["./mihomo", "-f", "test.yaml"],
    stdout=subprocess.DEVNULL,
    stderr=subprocess.DEVNULL
)

time.sleep(3)

try:
    r = requests.get(f"{API}/proxies", timeout=5)

    if r.status_code != 200:
        print("❌ Mihomo API 无法访问")
        sys.exit(1)

except Exception as e:
    print("❌ Mihomo 启动失败:", e)
    sys.exit(1)

print("✅ Mihomo API 正常")


# ============================================================
# 7. 测速
# ============================================================

vip_success = []
vip_failed = []

control_success = []
control_failed = []

print("\n" + "=" * 90)
print("开始测速")
print("=" * 90)


for i, item in enumerate(all_candidates, 1):

    name = item["original_name"]

    print(
        f"\n[{i}/{len(all_candidates)}] "
        f"{item['category']} | "
        f"{item['region']} | "
        f"{name}"
    )

    print(
        f"协议: {get_type(item['proxy'])} | "
        f"服务器: {get_server(item['proxy'])} | "
        f"端口: {get_port(item['proxy'])}"
    )

    success, delay, status, result = test_node(name)

    if success:

        print(
            f"✅ 成功 | HTTP {status} | "
            f"延迟: {delay} ms"
        )

        if item["category"] == "普通对照":
            control_success.append(item)
        else:
            vip_success.append(item)

    else:

        print(
            f"❌ 失败 | HTTP {status} | "
            f"返回: {str(result)[:300]}"
        )

        if item["category"] == "普通对照":
            control_failed.append(item)
        else:
            vip_failed.append(item)


# ============================================================
# 8. 最终统计
# ============================================================

print("\n" + "=" * 90)
print("诊断结果")
print("=" * 90)

print(
    f"\nVIP 实验性/高级:"
    f" {len(vip_success)}/{len(vip_candidates)} 成功"
)

print(
    f"普通节点对照:"
    f" {len(control_success)}/{len(selected_controls)} 成功"
)


# ============================================================
# 9. 成功节点
# ============================================================

print("\n" + "-" * 80)
print("VIP 成功节点")
print("-" * 80)

if vip_success:

    for item in vip_success:

        proxy = item["proxy"]

        print(
            f"✅ {item['region']} | "
            f"{item['original_name']} | "
            f"{get_type(proxy)} | "
            f"{get_server(proxy)}:{get_port(proxy)}"
        )

else:
    print("无")


print("\n" + "-" * 80)
print("普通对照成功节点")
print("-" * 80)

if control_success:

    for item in control_success:

        proxy = item["proxy"]

        print(
            f"✅ {item['region']} | "
            f"{item['original_name']} | "
            f"{get_type(proxy)} | "
            f"{get_server(proxy)}:{get_port(proxy)}"
        )

else:
    print("无")


# ============================================================
# 10. 失败节点
# ============================================================

print("\n" + "-" * 80)
print("VIP 失败节点")
print("-" * 80)

for item in vip_failed:

    proxy = item["proxy"]

    print(
        f"❌ {item['region']} | "
        f"{item['original_name']} | "
        f"{get_type(proxy)} | "
        f"{get_server(proxy)}:{get_port(proxy)}"
    )


print("\n" + "-" * 80)
print("普通对照失败节点")
print("-" * 80)

for item in control_failed:

    proxy = item["proxy"]

    print(
        f"❌ {item['region']} | "
        f"{item['original_name']} | "
        f"{get_type(proxy)} | "
        f"{get_server(proxy)}:{get_port(proxy)}"
    )


print("\n" + "=" * 90)
print("诊断完成")
print("=" * 90)

print(
    "\n注意：本次测试不会生成 cleanvip.yaml，"
    "只用于比较 VIP 节点和普通节点。"
)

mihomo.terminate()

try:
    mihomo.wait(timeout=3)
except subprocess.TimeoutExpired:
    mihomo.kill()
