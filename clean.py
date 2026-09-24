import requests
import yaml
import subprocess
import time
import os
import signal
import sys
import socket
import threading
import re

# =========================================================
# 配置
# =========================================================

VIP_URL = (
    "https://gist.githubusercontent.com/"
    "rongzhijie7/76ce5d8efc7e0f92cda3b59a82536532/"
    "raw/VIP"
)

OUTPUT_FILE = "clean.yaml"

MIHOMO_BIN = "./mihomo"

MIHOMO_PORT = 7890
MIHOMO_API_PORT = 9090

# YouTube 测试地址
TEST_URL = "https://www.youtube.com/generate_204"

# 单个节点最大测试时间
TEST_TIMEOUT = 12

# Mihomo 启动等待时间
MIHOMO_START_WAIT = 3

REGIONS = [
    "香港",
    "台湾",
    "日本",
    "新加坡",
    "美国",
    "英国",
    "韩国",
]


# =========================================================
# 下载 VIP
# =========================================================

def download_vip():

    print("======================================")
    print("下载 VIP")
    print("======================================")

    try:
        r = requests.get(
            VIP_URL,
            timeout=60,
            headers={
                "User-Agent": "Mozilla/5.0"
            }
        )
    except Exception as e:
        print("VIP 下载失败：", e)
        sys.exit(1)

    print("HTTP:", r.status_code)
    print("Size:", len(r.content))

    if r.status_code != 200:
        print(r.text[:500])
        sys.exit(1)

    return r.text


# =========================================================
# 判断地区
# =========================================================

def get_region(name):

    name = str(name)

    # 狮城 = 新加坡
    if "狮城" in name:
        return "新加坡"

    for region in REGIONS:

        if region in name:
            return region

    lower_name = name.lower()

    if "hong kong" in lower_name:
        return "香港"

    if "taiwan" in lower_name:
        return "台湾"

    if "japan" in lower_name:
        return "日本"

    if "singapore" in lower_name:
        return "新加坡"

    if "united states" in lower_name:
        return "美国"

    if "usa" in lower_name:
        return "美国"

    if "america" in lower_name:
        return "美国"

    if "united kingdom" in lower_name:
        return "英国"

    if re.search(r"\buk\b", lower_name):
        return "英国"

    if "korea" in lower_name:
        return "韩国"

    return None


# =========================================================
# 名称清理
# =========================================================

def clean_original_name(name):

    name = str(name)

    name = name.replace("&#x5b;", "[")
    name = name.replace("&#x5d;", "]")
    name = name.replace("&#91;", "[")
    name = name.replace("&#93;", "]")

    return name.strip()


# =========================================================
# 重复名称编号
# =========================================================

def unique_name(base_name, counters):

    if base_name not in counters:

        counters[base_name] = 1

        return base_name

    counters[base_name] += 1

    return f"{base_name}-{counters[base_name]}"


# =========================================================
# 筛选节点
# =========================================================

def filter_nodes(data):

    proxies = data.get("proxies", [])

    if not isinstance(proxies, list):

        print("VIP 中没有 proxies")

        sys.exit(1)

    result = []

    name_counters = {}

    # 高级备用每地区最多 2 条
    advanced_count = {
        region: 0
        for region in REGIONS
    }

    experimental_count = 0
    advanced_total = 0

    print()
    print("======================================")
    print("开始筛选节点")
    print("======================================")

    for proxy in proxies:

        if not isinstance(proxy, dict):
            continue

        original_name = proxy.get("name")

        if not original_name:
            continue

        original_name = clean_original_name(
            original_name
        )

        # =================================================
        # 规则 1：实验性 → 区域专线
        # =================================================

        if "实验性" in original_name:

            region = get_region(original_name)

            if not region:

                print(
                    "[跳过] 无法识别地区:",
                    original_name
                )

                continue

            new_name = f"{region}专线"

            new_name = unique_name(
                new_name,
                name_counters
            )

            new_proxy = proxy.copy()

            new_proxy["name"] = new_name

            result.append(new_proxy)

            experimental_count += 1

            print(
                f"[专线] {original_name}"
                f" -> {new_name}"
            )

            continue

        # =================================================
        # 规则 2：高级 → 区域备用
        # 每地区最多 2 条
        # =================================================

        if "高级" in original_name:

            region = get_region(original_name)

            if not region:

                print(
                    "[跳过] 无法识别地区:",
                    original_name
                )

                continue

            if advanced_count[region] >= 2:

                print(
                    f"[跳过] {original_name}"
                    f" -> {region}备用已经达到2条"
                )

                continue

            advanced_count[region] += 1

            new_name = f"{region}备用"

            new_name = unique_name(
                new_name,
                name_counters
            )

            new_proxy = proxy.copy()

            new_proxy["name"] = new_name

            result.append(new_proxy)

            advanced_total += 1

            print(
                f"[备用] {original_name}"
                f" -> {new_name}"
            )

            continue

    print()
    print("筛选完成")
    print("实验性专线:", experimental_count)
    print("高级备用:", advanced_total)
    print("待测试:", len(result))

    return result


# =========================================================
# 创建 Mihomo 测试配置
# =========================================================

def create_mihomo_config(proxy):

    config = {
        "mixed-port": MIHOMO_PORT,

        "allow-lan": False,

        "mode": "rule",

        "log-level": "error",

        "dns": {
            "enable": True,
            "ipv6": False,
            "enhanced-mode": "fake-ip",
            "nameserver": [
                "1.1.1.1",
                "8.8.8.8"
            ]
        },

        "proxies": [
            proxy
        ],

        "proxy-groups": [
            {
                "name": "TEST",
                "type": "select",
                "proxies": [
                    proxy["name"]
                ]
            }
        ],

        "rules": [
            "MATCH,TEST"
        ]
    }

    return config


# =========================================================
# 启动 Mihomo
# =========================================================

def start_mihomo(proxy, config_file):

    config = create_mihomo_config(proxy)

    with open(
        config_file,
        "w",
        encoding="utf-8"
    ) as f:

        yaml.safe_dump(
            config,
            f,
            allow_unicode=True,
            sort_keys=False
        )

    process = subprocess.Popen(
        [
            MIHOMO_BIN,
            "-f",
            config_file
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )

    # 等待 Mihomo 启动
    for _ in range(30):

        if process.poll() is not None:

            return None

        try:

            with socket.create_connection(
                ("127.0.0.1", MIHOMO_PORT),
                timeout=0.2
            ):

                return process

        except Exception:

            time.sleep(0.2)

    try:
        process.kill()
    except Exception:
        pass

    return None


# =========================================================
# 测试节点
# =========================================================

def test_proxy(proxy, index, total):

    name = proxy.get("name", "UNKNOWN")

    print(
        f"[{index}/{total}] 测试: {name}"
    )

    config_file = f"/tmp/mihomo_test_{index}.yaml"

    process = None

    try:

        process = start_mihomo(
            proxy,
            config_file
        )

        if not process:

            print(
                f"    ❌ Mihomo 启动失败"
            )

            return False

        time.sleep(
            MIHOMO_START_WAIT
        )

        proxies = {
            "http": f"http://127.0.0.1:{MIHOMO_PORT}",
            "https": f"http://127.0.0.1:{MIHOMO_PORT}",
        }

        start = time.time()

        r = requests.get(
            TEST_URL,
            proxies=proxies,
            timeout=TEST_TIMEOUT,
            headers={
                "User-Agent": "Mozilla/5.0"
            }
        )

        elapsed = time.time() - start

        # 200 / 204 都算成功
        if r.status_code in (200, 204):

            print(
                f"    ✅ 可用"
                f"  HTTP {r.status_code}"
                f"  {elapsed:.2f}s"
            )

            return True

        print(
            f"    ❌ HTTP {r.status_code}"
        )

        return False

    except Exception as e:

        print(
            f"    ❌ 失败: {str(e)[:120]}"
        )

        return False

    finally:

        if process:

            try:

                process.terminate()

                process.wait(
                    timeout=2
                )

            except Exception:

                try:
                    process.kill()
                except Exception:
                    pass

        try:
            os.remove(config_file)
        except Exception:
            pass


# =========================================================
# 测试所有节点
# =========================================================

def test_all_nodes(proxies):

    print()
    print("======================================")
    print("开始实际代理测试")
    print("测试目标：YouTube")
    print("======================================")
    print()

    working = []

    total = len(proxies)

    for index, proxy in enumerate(
        proxies,
        start=1
    ):

        if test_proxy(
            proxy,
            index,
            total
        ):

            working.append(proxy)

    print()
    print("======================================")
    print("测试完成")
    print("======================================")

    print(
        "测试节点:",
        total
    )

    print(
        "可用节点:",
        len(working)
    )

    print(
        "失效节点:",
        total - len(working)
    )

    return working


# =========================================================
# 写入 clean.yaml
# =========================================================

def save_yaml(proxies):

    output = {
        "proxies": proxies
    }

    with open(
        OUTPUT_FILE,
        "w",
        encoding="utf-8"
    ) as f:

        yaml.safe_dump(
            output,
            f,
            allow_unicode=True,
            sort_keys=False
        )


# =========================================================
# 主程序
# =========================================================

def main():

    # -----------------------------------------------------
    # 检查 Mihomo
    # -----------------------------------------------------

    if not os.path.exists(MIHOMO_BIN):

        print(
            "错误：找不到 Mihomo:"
            f" {MIHOMO_BIN}"
        )

        sys.exit(1)

    # -----------------------------------------------------
    # 下载 VIP
    # -----------------------------------------------------

    vip_text = download_vip()

    # -----------------------------------------------------
    # 解析 YAML
    # -----------------------------------------------------

    try:

        data = yaml.safe_load(
            vip_text
        )

    except Exception as e:

        print(
            "YAML 解析失败:",
            e
        )

        sys.exit(1)

    if not isinstance(data, dict):

        print("VIP YAML 格式错误")

        sys.exit(1)

    # -----------------------------------------------------
    # 筛选
    # -----------------------------------------------------

    candidates = filter_nodes(data)

    if not candidates:

        print(
            "错误：筛选后没有节点"
        )

        sys.exit(1)

    # -----------------------------------------------------
    # 实际测试
    # -----------------------------------------------------

    working = test_all_nodes(
        candidates
    )

    # -----------------------------------------------------
    # 防止所有节点失效
    # -----------------------------------------------------

    if not working:

        print()
        print(
            "错误：所有节点测试失败！"
        )

        print(
            "为了防止覆盖正常的 clean.yaml，"
            "本次任务不会生成空订阅。"
        )

        sys.exit(1)

    # -----------------------------------------------------
    # 写入
    # -----------------------------------------------------

    save_yaml(
        working
    )

    print()
    print("======================================")
    print("clean.yaml 生成成功")
    print("======================================")

    for proxy in working:

        print(
            f"- {proxy.get('name')}"
            f" [{proxy.get('type')}]"
        )


if __name__ == "__main__":

    main()
