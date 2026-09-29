import os
import time
import subprocess
from collections import defaultdict
from pathlib import Path
from urllib.parse import quote

import requests
import yaml


# ============================================================
# 基本配置
# ============================================================

GIST_URL = (
    "https://gist.githubusercontent.com/"
    "rongzhijie7/76ce5d8efc7e0f92cda3b59a82536532/raw/VIP"
)

OUTPUT_FILE = "cleanvip.yaml"
MIHOMO_BIN = "./mihomo"

API = "http://127.0.0.1:9090"

# 使用 YouTube 204 页面进行有效性测试
TEST_URL = "https://www.youtube.com/generate_204"

# 单节点最大测速时间
TEST_TIMEOUT_MS = 8000

# Mihomo 启动等待时间
STARTUP_TIMEOUT = 20


# ============================================================
# 地区 -> ISO 3166-1 alpha-2
# ============================================================

REGIONS = {
    "香港": "HK",
    "Hong Kong": "HK",

    "台湾": "TW",
    "台灣": "TW",
    "Taiwan": "TW",

    "日本": "JP",
    "Japan": "JP",

    "新加坡": "SG",
    "狮城": "SG",
    "Singapore": "SG",

    "美国": "US",
    "USA": "US",
    "United States": "US",

    "韩国": "KR",
    "韓國": "KR",
    "Korea": "KR",

    "英国": "GB",
    "英國": "GB",
    "UK": "GB",

    "德国": "DE",
    "德國": "DE",
    "Germany": "DE",

    "意大利": "IT",
    "義大利": "IT",
    "Italy": "IT",

    "印度": "IN",
    "India": "IN",

    "泰国": "TH",
    "泰國": "TH",
    "Thailand": "TH",

    "澳大利亚": "AU",
    "澳洲": "AU",
    "Australia": "AU",

    "墨西哥": "MX",
    "Mexico": "MX",

    "巴西": "BR",
    "Brazil": "BR",

    "加拿大": "CA",
    "Canada": "CA",

    "荷兰": "NL",
    "荷蘭": "NL",
    "Netherlands": "NL",

    "法国": "FR",
    "法國": "FR",
    "France": "FR",

    "西班牙": "ES",
    "Spain": "ES",

    "土耳其": "TR",
    "Turkey": "TR",

    "匈牙利": "HU",
    "Hungary": "HU",

    "乌克兰": "UA",
    "Ukraine": "UA",

    "摩尔多瓦": "MD",
    "Moldova": "MD",

    "阿根廷": "AR",
    "Argentina": "AR",

    "智利": "CL",
    "Chile": "CL",

    "新西兰": "NZ",
    "New Zealand": "NZ",

    "印尼": "ID",
    "印度尼西亚": "ID",
    "Indonesia": "ID",

    "越南": "VN",
    "Vietnam": "VN",

    "巴基斯坦": "PK",
    "Pakistan": "PK",

    "以色列": "IL",
    "Israel": "IL",

    "阿联酋": "AE",
    "United Arab Emirates": "AE",

    "菲律宾": "PH",
    "Philippines": "PH",

    "马来西亚": "MY",
    "Malaysia": "MY",

    "埃及": "EG",
    "Egypt": "EG",

    "尼日利亚": "NG",
    "Nigeria": "NG",
}


# ============================================================
# 根据节点名称识别地区
# ============================================================

def get_region(name):
    # 优先匹配较长名称
    items = sorted(
        REGIONS.items(),
        key=lambda x: len(x[0]),
        reverse=True
    )

    for region_name, code in items:
        if region_name in name:
            return code

    return None


# ============================================================
# 从 VIP Gist 获取节点
# ============================================================

def load_nodes():
    print("=" * 60)
    print("获取 VIP Gist")
    print("=" * 60)

    response = requests.get(
        GIST_URL,
        timeout=30
    )

    response.raise_for_status()

    data = yaml.safe_load(response.text) or {}

    nodes = data.get("proxies", [])

    if not isinstance(nodes, list):
        raise RuntimeError(
            "VIP Gist 中没有找到有效的 proxies 列表"
        )

    print(f"原始节点数量: {len(nodes)}")

    return nodes


# ============================================================
# 筛选 + 重命名
#
# 实验性 -> ISO专线
# 高级   -> ISO备用
#
# 例如：
# 香港实验性 -> HK专线
# 香港高级   -> HK备用
#
# 同地区多个：
# HK专线
# HK专线-2
# HK专线-3
#
# ============================================================

def select_and_rename(nodes):

    selected = []

    for node in nodes:

        if not isinstance(node, dict):
            continue

        original_name = str(
            node.get("name", "")
        )

        # 只处理“实验性”和“高级”
        if (
            "实验性" not in original_name
            and
            "高级" not in original_name
        ):
            continue

        region = get_region(original_name)

        if not region:
            print(
                f"跳过无法识别地区的节点: "
                f"{original_name}"
            )
            continue

        if "实验性" in original_name:
            kind = "专线"
        else:
            kind = "备用"

        new_node = dict(node)

        # 暂存分类
        new_node["_region"] = region
        new_node["_kind"] = kind

        selected.append(new_node)

    print(
        f"符合“实验性/高级”条件: "
        f"{len(selected)}"
    )

    # --------------------------------------------------------
    # 重新命名
    # --------------------------------------------------------

    counters = defaultdict(int)

    result = []

    for node in selected:

        region = node["_region"]
        kind = node["_kind"]

        key = (region, kind)

        counters[key] += 1

        number = counters[key]

        base_name = f"{region}{kind}"

        if number == 1:
            new_name = base_name
        else:
            new_name = f"{base_name}-{number}"

        node["name"] = new_name

        node.pop("_region", None)
        node.pop("_kind", None)

        result.append(node)

        print(
            f"{node['name']}"
        )

    return result


# ============================================================
# 生成 Mihomo 测速配置
# ============================================================

def write_test_config(nodes, config_path):

    config = {
        "mixed-port": 7890,

        "mode": "rule",

        "allow-lan": False,

        "ipv6": False,

        "log-level": "error",

        "external-controller": "127.0.0.1:9090",

        "secret": "",

        "dns": {
            "enable": True,
            "ipv6": False,
            "enhanced-mode": "redir-host",
            "nameserver": [
                "223.5.5.5",
                "1.1.1.1",
            ],
        },

        "proxies": nodes,

        "proxy-groups": [
            {
                "name": "TEST",
                "type": "select",
                "proxies": [
                    node["name"]
                    for node in nodes
                ],
            }
        ],

        "rules": [
            "MATCH,DIRECT"
        ],
    }

    Path(config_path).write_text(
        yaml.safe_dump(
            config,
            allow_unicode=True,
            sort_keys=False,
        ),
        encoding="utf-8",
    )


# ============================================================
# 启动 Mihomo
# ============================================================

def start_mihomo(config_path):

    print("=" * 60)
    print("启动 Mihomo")
    print("=" * 60)

    process = subprocess.Popen(
        [
            MIHOMO_BIN,
            "-f",
            config_path,
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    deadline = time.time() + STARTUP_TIMEOUT

    while time.time() < deadline:

        if process.poll() is not None:
            raise RuntimeError(
                "Mihomo 启动失败"
            )

        try:
            response = requests.get(
                f"{API}/version",
                timeout=3,
            )

            if response.ok:
                print("Mihomo API 已启动")
                return process

        except requests.RequestException:
            pass

        time.sleep(0.5)

    process.terminate()

    raise RuntimeError(
        "Mihomo API 启动超时"
    )


# ============================================================
# 测试单个节点
# ============================================================

def test_node(name):

    encoded_name = quote(
        name,
        safe=""
    )

    url = (
        f"{API}/proxies/"
        f"{encoded_name}/delay"
    )

    params = {
        "url": TEST_URL,
        "timeout": TEST_TIMEOUT_MS,
        "expected": "204",
    }

    try:

        response = requests.get(
            url,
            params=params,
            timeout=(
                TEST_TIMEOUT_MS / 1000
            ) + 3,
        )

        if not response.ok:
            return None

        data = response.json()

        delay = int(
            data.get("delay", 0)
        )

        if delay > 0:
            return delay

    except Exception:
        pass

    return None


# ============================================================
# 主程序
# ============================================================

def main():

    print()
    print("=" * 60)
    print("CleanVIP")
    print("=" * 60)
    print()

    # --------------------------------------------------------
    # 1. 获取 VIP
    # --------------------------------------------------------

    nodes = load_nodes()

    # --------------------------------------------------------
    # 2. 筛选并重命名
    # --------------------------------------------------------

    candidates = select_and_rename(
        nodes
    )

    if not candidates:
        raise RuntimeError(
            "没有找到包含“实验性”或“高级”的节点"
        )

    # --------------------------------------------------------
    # 3. 创建临时 Mihomo 配置
    # --------------------------------------------------------

    test_config = (
        "mihomo-test.yaml"
    )

    write_test_config(
        candidates,
        test_config
    )

    process = None

    alive = []

    try:

        # ----------------------------------------------------
        # 4. 启动 Mihomo
        # ----------------------------------------------------

        process = start_mihomo(
            test_config
        )

        print()
        print("=" * 60)
        print("开始有效性测速")
        print("=" * 60)
        print()

        # ----------------------------------------------------
        # 5. 逐个测速
        # ----------------------------------------------------

        total = len(candidates)

        for index, node in enumerate(
            candidates,
            1
        ):

            name = node["name"]

            delay = test_node(name)

            if delay is not None:

                print(
                    f"[{index}/{total}] "
                    f"✓ {name} "
                    f"{delay} ms"
                )

                alive.append(node)

            else:

                print(
                    f"[{index}/{total}] "
                    f"✗ {name}"
                )

    finally:

        # ----------------------------------------------------
        # 6. 关闭 Mihomo
        # ----------------------------------------------------

        if process:

            process.terminate()

            try:
                process.wait(
                    timeout=5
                )

            except subprocess.TimeoutExpired:

                process.kill()

        try:
            os.remove(
                test_config
            )
        except OSError:
            pass

    # --------------------------------------------------------
    # 7. 防止测速全部失败时覆盖旧文件
    # --------------------------------------------------------

    if not alive:

        raise RuntimeError(
            "所有候选节点测速失败，"
            "拒绝覆盖现有 cleanvip.yaml"
        )

    # --------------------------------------------------------
    # 8. 写入 cleanvip.yaml
    # --------------------------------------------------------

    output = {
        "proxies": alive
    }

    Path(
        OUTPUT_FILE
    ).write_text(
        yaml.safe_dump(
            output,
            allow_unicode=True,
            sort_keys=False,
        ),
        encoding="utf-8",
    )

    print()
    print("=" * 60)
    print("CleanVIP 完成")
    print("=" * 60)
    print(
        f"筛选节点: {len(candidates)}"
    )
    print(
        f"有效节点: {len(alive)}"
    )
    print(
        f"输出文件: {OUTPUT_FILE}"
    )
    print("=" * 60)


if __name__ == "__main__":
    main()
