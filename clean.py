import os
import re
import time
import subprocess
import requests
import yaml


# ============================================================
# 基本配置
# ============================================================

SOURCE_URL = (
    "https://gist.githubusercontent.com/"
    "rongzhijie7/76ce5d8efc7e0f92cda3b59a82536532/"
    "raw/VIP"
)

OUTPUT_FILE = "cleanvip.yaml"
TEST_FILE = "test.yaml"

MIHOMO = "./mihomo"
MIHOMO_API = "http://127.0.0.1:9090"

TEST_URL = "https://www.gstatic.com/generate_204"
TEST_TIMEOUT = 5000


# ============================================================
# 地区
# ============================================================

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


# ============================================================
# 数据标准化
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
# 获取地区
# ============================================================

def get_region(name):
    if not name:
        return None

    # 中文优先
    for region in REGIONS:
        if region in name:
            if region == "狮城":
                return "新加坡"
            return region

    # 英文地区
    lower_name = name.lower()

    for alias, region in REGION_ALIASES.items():
        if alias in lower_name:
            return region

    return None


# ============================================================
# 下载 VIP Gist
# ============================================================

def download_source():
    print("======================================")
    print("下载 VIP Gist")
    print("======================================")

    try:
        r = requests.get(
            SOURCE_URL,
            timeout=30,
            headers={
                "User-Agent": "Mozilla/5.0"
            }
        )

        print("HTTP状态:", r.status_code)
        print("文件大小:", len(r.content))

        r.raise_for_status()

        config = yaml.safe_load(r.text)

        if not isinstance(config, dict):
            print("❌ VIP 文件不是有效 YAML")
            return None

        proxies = config.get("proxies", [])

        print("原始节点:", len(proxies))

        return proxies

    except Exception as e:
        print("❌ 下载 VIP 失败:", repr(e))
        return None


# ============================================================
# 筛选候选节点
#
# 规则：
#
# 1. 实验性
#    每个地区保留
#    名称统一改成：
#    香港专线
#    日本专线
#    ...
#
# 2. 高级
#    每个地区最多保留 2 个
#    香港备用
#    香港备用-2
#
# 3. [基础] 永远不进入最终结果
# ============================================================

def collect_candidates(raw_proxies):

    experimental = {}
    advanced = {}

    print()
    print("======================================")
    print("开始筛选 VIP 节点")
    print("======================================")

    for raw_proxy in raw_proxies:

        proxy = normalize_proxy(raw_proxy)

        old_name = str(proxy.get("name", ""))

        if not old_name:
            continue

        if not proxy.get("server"):
            continue

        if not proxy.get("type"):
            continue

        # ----------------------------------------------------
        # 实验性
        # ----------------------------------------------------

        if "实验性" in old_name:

            region = get_region(old_name)

            if not region:
                print("跳过实验性节点（地区未知）:", old_name)
                continue

            # 每个地区只保留一个实验性
            if region not in experimental:

                proxy["name"] = f"{region}专线"

                experimental[region] = proxy

            continue

        # ----------------------------------------------------
        # 高级
        # ----------------------------------------------------

        if "高级" in old_name:

            region = get_region(old_name)

            if not region:
                print("跳过高级节点（地区未知）:", old_name)
                continue

            if region not in advanced:
                advanced[region] = []

            # 先全部收集
            advanced[region].append(proxy)

            continue

        # ----------------------------------------------------
        # 其他节点全部忽略
        # 包括 [基础]
        # ----------------------------------------------------

    # ========================================================
    # 输出实验性
    # ========================================================

    candidates = []

    print()
    print("实验性节点:")

    for region, proxy in experimental.items():

        print(
            f"  {proxy.get('name')} "
            f"<- {proxy.get('server')}"
        )

        candidates.append(proxy)

    # ========================================================
    # 输出高级
    # 每个地区最多两个
    # ========================================================

    print()
    print("高级节点:")

    for region, proxy_list in advanced.items():

        # 最多两个
        selected = proxy_list[:2]

        for index, proxy in enumerate(selected, start=1):

            if index == 1:
                new_name = f"{region}备用"
            else:
                new_name = f"{region}备用-{index}"

            proxy["name"] = new_name

            print(
                f"  {new_name} "
                f"<- {proxy.get('server')}"
            )

            candidates.append(proxy)

        if len(proxy_list) > 2:
            print(
                f"  {region}: 原有 {len(proxy_list)} 个高级节点，"
                f"仅保留前 2 个"
            )

    print()
    print("最终候选节点:", len(candidates))

    for proxy in candidates:
        print(" ", proxy["name"])

    return candidates


# ============================================================
# 创建 Mihomo 测试配置
#
# 尽量保持与你那个已经能正常测速的脚本一致
# ============================================================

def create_test_config(proxies):

    names = [p["name"] for p in proxies]

    test_config = {
        "mixed-port": 7890,

        "external-controller": "127.0.0.1:9090",

        "proxies": proxies,

        "proxy-groups": [
            {
                "name": "TEST",
                "type": "url-test",
                "proxies": names,
                "url": TEST_URL,
                "interval": 300
            }
        ]
    }

    with open(
        TEST_FILE,
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
    print("测试配置已生成:", TEST_FILE)


# ============================================================
# 等待 Mihomo API
# ============================================================

def wait_mihomo():

    print()
    print("等待 Mihomo 启动...")

    for i in range(20):

        try:

            r = requests.get(
                f"{MIHOMO_API}/proxies",
                timeout=2
            )

            if r.status_code == 200:

                print("Mihomo API 已启动")

                # 完全按照参考脚本，
                # API启动后再额外等待几秒
                time.sleep(5)

                return True

        except Exception:
            pass

        time.sleep(1)

    print("❌ Mihomo API 启动失败")

    return False


# ============================================================
# 测试单个节点
# ============================================================

def test_node(name):

    try:

        # 这里故意保持和你原来能成功的脚本一致：
        #
        # /proxies/{name}/delay
        #
        # 不自己做复杂编码

        url = (
            f"{MIHOMO_API}/proxies/"
            f"{name}/delay"
        )

        r = requests.get(
            url,
            params={
                "timeout": TEST_TIMEOUT,
                "url": TEST_URL
            },
            timeout=8
        )

        # ----------------------------------------------------
        # HTTP错误
        # ----------------------------------------------------

        if r.status_code != 200:

            print(
                f"    ❌ HTTP {r.status_code}"
            )

            try:
                print(
                    "    返回:",
                    r.text[:500]
                )
            except Exception:
                pass

            return None

        # ----------------------------------------------------
        # JSON
        # ----------------------------------------------------

        try:

            data = r.json()

        except Exception:

            print("    ❌ 返回不是 JSON")

            print(
                "    返回:",
                r.text[:500]
            )

            return None

        # ----------------------------------------------------
        # delay
        # ----------------------------------------------------

        if "delay" not in data:

            print("    ❌ 没有 delay")

            print(
                "    返回:",
                data
            )

            return None

        delay = data["delay"]

        try:
            delay = int(delay)
        except Exception:
            pass

        return delay

    except Exception as e:

        print(
            "    ❌ 请求异常:",
            repr(e)
        )

        return None


# ============================================================
# 测试全部节点
# ============================================================

def test_nodes(proxies):

    print()
    print("======================================")
    print("开始实际节点测试")
    print("======================================")

    alive = []

    for index, proxy in enumerate(
        proxies,
        start=1
    ):

        name = proxy["name"]

        print(
            f"[{index}/{len(proxies)}] "
            f"{name}"
        )

        delay = test_node(name)

        if delay is not None:

            print(
                f"    ✅ {delay} ms"
            )

            alive.append(
                (proxy, delay)
            )

        else:

            print(
                "    ❌ FAIL"
            )

    print()
    print("======================================")
    print("测速完成")
    print("======================================")

    print(
        "候选节点:",
        len(proxies)
    )

    print(
        "可用节点:",
        len(alive)
    )

    return alive


# ============================================================
# 保存结果
# ============================================================

def save_output(alive):

    if not alive:

        print()
        print("======================================")
        print("本轮没有可用节点")
        print("不覆盖旧的 cleanvip.yaml")
        print("======================================")

        return False

    clean = []

    for proxy, delay in alive:

        clean.append(proxy)

    output = {
        "proxies": clean
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
    print(
        f"{OUTPUT_FILE} 生成完成"
    )
    print(
        "可用节点:",
        len(clean)
    )
    print("======================================")

    return True


# ============================================================
# 主程序
# ============================================================

def main():

    print()
    print("======================================")
    print("VIP 节点自动清洗")
    print("======================================")

    # --------------------------------------------------------
    # 1. 下载
    # --------------------------------------------------------

    raw_proxies = download_source()

    if not raw_proxies:

        print("❌ 没有获取到 VIP 节点")

        return

    # --------------------------------------------------------
    # 2. 筛选
    # --------------------------------------------------------

    candidates = collect_candidates(
        raw_proxies
    )

    if not candidates:

        print("❌ 没有符合条件的候选节点")

        return

    # --------------------------------------------------------
    # 3. 创建测试配置
    # --------------------------------------------------------

    create_test_config(
        candidates
    )

    # --------------------------------------------------------
    # 4. 启动 Mihomo
    # --------------------------------------------------------

    print()
    print("======================================")
    print("启动 Mihomo")
    print("======================================")

    process = None

    try:

        process = subprocess.Popen(
            [
                MIHOMO,
                "-f",
                TEST_FILE
            ]
        )

        # ----------------------------------------------------
        # 5. 等待 Mihomo
        # ----------------------------------------------------

        if not wait_mihomo():

            return

        # ----------------------------------------------------
        # 6. 测速
        # ----------------------------------------------------

        alive = test_nodes(
            candidates
        )

        # ----------------------------------------------------
        # 7. 保存
        # ----------------------------------------------------

        save_output(
            alive
        )

    finally:

        # ----------------------------------------------------
        # 8. 关闭 Mihomo
        # ----------------------------------------------------

        if process:

            print()
            print("关闭 Mihomo")

            try:
                process.kill()
                process.wait(timeout=5)
            except Exception:
                pass

    print()
    print("======================================")
    print("本轮任务结束")
    print("======================================")


if __name__ == "__main__":
    main()
