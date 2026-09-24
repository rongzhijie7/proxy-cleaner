import yaml
import requests
import subprocess
import time
import urllib.parse
import sys


SOURCE = "source.yaml"
TEST_URL = "https://www.gstatic.com/generate_204"

API = "http://127.0.0.1:9090"
API_PORT = 9090

TIMEOUT = 5000

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


def proxy_type(proxy):
    return str(proxy.get("type", "unknown"))


def proxy_server(proxy):
    return str(proxy.get("server", ""))


def proxy_port(proxy):
    return str(proxy.get("port", ""))


def encode_name(name):
    return urllib.parse.quote(str(name), safe="")


def test_node(name):
    url = (
        f"{API}/proxies/{encode_name(name)}/delay"
        f"?timeout={TIMEOUT}"
        f"&url={urllib.parse.quote(TEST_URL, safe='')}"
    )

    try:
        r = requests.get(url, timeout=8)

        try:
            result = r.json()
        except Exception:
            result = r.text

        if r.status_code == 200:
            delay = None

            if isinstance(result, dict):
                delay = result.get("delay")

            return True, delay, r.status_code, result

        return False, None, r.status_code, result

    except Exception as e:
        return False, None, None, str(e)


print("=" * 90)
print("VIP 节点对照诊断")
print("=" * 90)


# ============================================================
# 读取源文件
# ============================================================

print("\n# 读取 source.yaml")

try:
    with open(SOURCE, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
except Exception as e:
    print(f"❌ 读取 source.yaml 失败: {e}")
    sys.exit(1)


proxies = data.get("proxies", [])

print(f"# 原始节点: {len(proxies)}")


# ============================================================
# 实验性节点
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
# 高级节点
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
# 14 个 VIP 节点
# ============================================================

vip_candidates = experimental + advanced


print("\n" + "=" * 80)
print("VIP 候选节点")
print("=" * 80)

for i, item in enumerate(vip_candidates, 1):

    p = item["proxy"]

    print(
        f"[VIP {i:02d}] "
        f"{item['category']} | "
        f"{item['region']} | "
        f"{item['original_name']} | "
        f"type={proxy_type(p)} | "
        f"server={proxy_server(p)} | "
        f"port={proxy_port(p)}"
    )


print(f"\nVIP 候选总数: {len(vip_candidates)}")


# ============================================================
# 普通节点对照组
#
# 排除：
# 实验性
# 高级
# 基础
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


# ============================================================
# 尽量选择不同地区的普通节点
# ============================================================

control = []

used_regions = set()

for item in control_candidates:

    if len(control) >= 5:
        break

    if item["region"] in used_regions:
        continue

    control.append(item)
    used_regions.add(item["region"])


# 不足5个时继续补
if len(control) < 5:

    selected_names = {
        x["original_name"]
        for x in control
    }

    for item in control_candidates:

        if len(control) >= 5:
            break

        if item["original_name"] in selected_names:
            continue

        control.append(item)


print("\n" + "=" * 80)
print("普通节点对照组")
print("=" * 80)

for i, item in enumerate(control, 1):

    p = item["proxy"]

    print(
        f"[普通 {i:02d}] "
        f"{item['region']} | "
        f"{item['original_name']} | "
        f"type={proxy_type(p)} | "
        f"server={proxy_server(p)} | "
        f"port={proxy_port(p)}"
    )


print(f"\n普通对照总数: {len(control)}")


# ============================================================
# 合并
# ============================================================

all_candidates = vip_candidates + control


print("\n" + "=" * 90)
print("建立 Mihomo 测试配置")
print("=" * 90)


test_proxies = []
seen_names = set()

for item in all_candidates:

    proxy = dict(item["proxy"])
    name = item["original_name"]

    if name in seen_names:
        print(f"⚠️ 重复节点名称，跳过: {name}")
        continue

    seen_names.add(name)

    # 完全保持原始名称
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
            "proxies": [
                p["name"]
                for p in test_proxies
            ]
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


print(f"测试配置节点数: {len(test_proxies)}")


# ============================================================
# 清理旧 Mihomo
# ============================================================

print("\n关闭旧 Mihomo...")

subprocess.run(
    ["pkill", "-9", "mihomo"],
    stdout=subprocess.DEVNULL,
    stderr=subprocess.DEVNULL
)

time.sleep(2)


# ============================================================
# 启动 Mihomo
# ============================================================

print("启动 Mihomo...")


mihomo = subprocess.Popen(
    ["./mihomo", "-f", "test.yaml"],
    stdout=subprocess.PIPE,
    stderr=subprocess.STDOUT,
    text=True,
    bufsize=1
)


# ============================================================
# 等待 API
# ============================================================

print("等待 Mihomo API 启动...")


started = False

for i in range(30):

    time.sleep(1)

    try:

        r = requests.get(
            f"{API}/proxies",
            timeout=2
        )

        if r.status_code == 200:

            started = True
            print(f"✅ Mihomo API 已启动（等待 {i + 1} 秒）")
            break

    except requests.RequestException:
        pass


if not started:

    print("\n❌ Mihomo 启动失败")

    print("\n========== Mihomo 日志 ==========")

    try:

        output, _ = mihomo.communicate(timeout=3)

        if output:
            print(output[-10000:])

    except Exception as e:

        print(f"读取 Mihomo 日志失败: {e}")

        try:
            mihomo.kill()
        except Exception:
            pass

    sys.exit(1)


# ============================================================
# 获取 Mihomo 当前代理列表
# ============================================================

try:

    response = requests.get(
        f"{API}/proxies",
        timeout=5
    )

    api_proxies = response.json().get("proxies", {})

    print(
        f"✅ Mihomo 已加载代理: "
        f"{len(api_proxies)} 个"
    )

except Exception as e:

    print(f"❌ 获取 Mihomo 代理列表失败: {e}")

    mihomo.kill()
    sys.exit(1)


# ============================================================
# 检查候选节点是否真的进入 Mihomo
# ============================================================

print("\n" + "=" * 90)
print("检查候选节点")
print("=" * 90)


missing = []

for item in all_candidates:

    name = item["original_name"]

    if name not in api_proxies:

        missing.append(name)

        print(
            f"⚠️ Mihomo 中不存在: {name}"
        )


if not missing:

    print("✅ 所有候选节点均已进入 Mihomo")

else:

    print(
        f"⚠️ 有 {len(missing)} 个节点没有进入 Mihomo"
    )


# ============================================================
# 开始测速
# ============================================================

vip_success = []
vip_failed = []

control_success = []
control_failed = []


print("\n" + "=" * 90)
print("开始测速")
print("=" * 90)


total = len(all_candidates)


for i, item in enumerate(all_candidates, 1):

    name = item["original_name"]
    p = item["proxy"]

    print(
        f"\n[{i}/{total}] "
        f"{item['category']} | "
        f"{item['region']} | "
        f"{name}"
    )

    print(
        f"协议: {proxy_type(p)} | "
        f"服务器: {proxy_server(p)} | "
        f"端口: {proxy_port(p)}"
    )


    if name not in api_proxies:

        print("❌ 节点未被 Mihomo 加载")

        if item["category"] == "普通对照":
            control_failed.append(item)
        else:
            vip_failed.append(item)

        continue


    success, delay, status, result = test_node(name)


    if success:

        print(
            f"✅ 成功 | "
            f"HTTP {status} | "
            f"延迟: {delay} ms"
        )

        if item["category"] == "普通对照":

            control_success.append(item)

        else:

            vip_success.append(item)

    else:

        print(
            f"❌ 失败 | "
            f"HTTP {status} | "
            f"返回: {str(result)[:300]}"
        )

        if item["category"] == "普通对照":

            control_failed.append(item)

        else:

            vip_failed.append(item)


# ============================================================
# 结果
# ============================================================

print("\n" + "=" * 90)
print("最终诊断结果")
print("=" * 90)


print(
    f"\nVIP 实验性/高级:"
    f" {len(vip_success)}/{len(vip_candidates)} 成功"
)


print(
    f"普通节点对照:"
    f" {len(control_success)}/{len(control)} 成功"
)


# ============================================================
# VIP 成功
# ============================================================

print("\n" + "-" * 80)
print("VIP 成功节点")
print("-" * 80)


if vip_success:

    for item in vip_success:

        p = item["proxy"]

        print(
            f"✅ {item['region']} | "
            f"{item['original_name']} | "
            f"{proxy_type(p)} | "
            f"{proxy_server(p)}:{proxy_port(p)}"
        )

else:

    print("无")


# ============================================================
# 普通成功
# ============================================================

print("\n" + "-" * 80)
print("普通对照成功节点")
print("-" * 80)


if control_success:

    for item in control_success:

        p = item["proxy"]

        print(
            f"✅ {item['region']} | "
            f"{item['original_name']} | "
            f"{proxy_type(p)} | "
            f"{proxy_server(p)}:{proxy_port(p)}"
        )

else:

    print("无")


# ============================================================
# VIP失败
# ============================================================

print("\n" + "-" * 80)
print("VIP 失败节点")
print("-" * 80)


for item in vip_failed:

    p = item["proxy"]

    print(
        f"❌ {item['region']} | "
        f"{item['original_name']} | "
        f"{proxy_type(p)} | "
        f"{proxy_server(p)}:{proxy_port(p)}"
    )


# ============================================================
# 普通失败
# ============================================================

print("\n" + "-" * 80)
print("普通对照失败节点")
print("-" * 80)


for item in control_failed:

    p = item["proxy"]

    print(
        f"❌ {item['region']} | "
        f"{item['original_name']} | "
        f"{proxy_type(p)} | "
        f"{proxy_server(p)}:{proxy_port(p)}"
    )


print("\n" + "=" * 90)
print("诊断完成")
print("=" * 90)


print(
    "\n本次运行不会生成 cleanvip.yaml。"
)

print(
    "只用于确认："
    "VIP 实验性/高级节点与普通节点在 GitHub Actions 中的连通性差异。"
)


# ============================================================
# 关闭 Mihomo
# ============================================================

try:

    mihomo.terminate()
    mihomo.wait(timeout=5)

except Exception:

    try:
        mihomo.kill()
    except Exception:
        pass
