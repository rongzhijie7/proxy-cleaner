import os
import sys
import time
import yaml
import requests
import subprocess
import urllib.parse

# ============================================================
# 基本配置
# ============================================================

VIP_URL = (
    "https://gist.githubusercontent.com/"
    "rongzhijie7/76ce5d8efc7e0f92cda3b59a82536532/"
    "raw/VIP"
)

OUTPUT_FILE = "cleanvip.yaml"

MIHOMO_BIN = "./mihomo"
MIHOMO_CONFIG = "/tmp/mihomo_test.yaml"
MIHOMO_LOG = "/tmp/mihomo.log"

MIHOMO_API = "http://127.0.0.1:9090"

# Mihomo 混合端口
MIHOMO_PORT = 7890

# 单节点测速超时
TEST_TIMEOUT = 15000

# 基础 HTTPS 测试
BASIC_TEST_URL = "https://www.gstatic.com/generate_204"

# YouTube 测试
YOUTUBE_TEST_URL = "https://www.youtube.com/generate_204"

# 只保留这些地区
REGIONS = [
    "香港",
    "台湾",
    "日本",
    "新加坡",
    "美国",
    "英国",
    "韩国",
]


# ============================================================
# 下载 VIP
# ============================================================

def download_vip():

    print("======================================")
    print("下载 VIP")
    print("======================================")

    try:
        response = requests.get(
            VIP_URL,
            timeout=60,
            headers={
                "User-Agent": "Mozilla/5.0"
            },
        )

    except Exception as e:

        print("❌ VIP 下载失败:")
        print(e)
        sys.exit(1)

    print("HTTP:", response.status_code)
    print("Size:", len(response.content))

    if response.status_code != 200:

        print("❌ VIP HTTP 状态异常")
        print(response.text[:500])
        sys.exit(1)

    if not response.text.strip():

        print("❌ VIP 内容为空")
        sys.exit(1)

    return response.text


# ============================================================
# 地区识别
# ============================================================

def get_region(name):

    name = str(name)

    # 狮城 = 新加坡
    if "狮城" in name:
        return "新加坡"

    # 中文地区
    for region in REGIONS:

        if region in name:
            return region

    # 英文地区
    lower = name.lower()

    if "hong kong" in lower:
        return "香港"

    if "taiwan" in lower:
        return "台湾"

    if "japan" in lower:
        return "日本"

    if "singapore" in lower:
        return "新加坡"

    if "united states" in lower:
        return "美国"

    if "usa" in lower:
        return "美国"

    if "america" in lower:
        return "美国"

    if "united kingdom" in lower:
        return "英国"

    if "uk" in lower:
        return "英国"

    if "korea" in lower:
        return "韩国"

    return None


# ============================================================
# 清理节点名称
# ============================================================

def clean_name(name):

    name = str(name)

    replacements = {
        "&#x5b;": "[",
        "&#x5d;": "]",
        "&#91;": "[",
        "&#93;": "]",
    }

    for old, new in replacements.items():
        name = name.replace(old, new)

    return name.strip()


# ============================================================
# 筛选候选节点
#
# 重要：
# 这里只允许：
#   实验性
#   高级
#
# [基础]、普通节点以及其它节点全部直接跳过。
# ============================================================

def collect_candidates(data):

    proxies = data.get("proxies", [])

    if not isinstance(proxies, list):

        print("❌ VIP YAML 中没有有效的 proxies")
        sys.exit(1)

    experimental = []
    advanced = []

    print()
    print("======================================")
    print("开始筛选节点")
    print("======================================")

    # --------------------------------------------------------
    # 第一轮：收集
    # --------------------------------------------------------

    for proxy in proxies:

        # 防止异常 YAML 项
        if not isinstance(proxy, dict):
            continue

        original_name = proxy.get("name")

        if not original_name:
            continue

        original_name = clean_name(original_name)

        # ====================================================
        # 实验性
        # ====================================================

        if "实验性" in original_name:

            region = get_region(original_name)

            if not region:

                print(
                    "[跳过] 实验性节点无法识别地区:",
                    original_name
                )

                continue

            new_proxy = proxy.copy()

            new_proxy["_region"] = region
            new_proxy["_original_name"] = original_name

            experimental.append(new_proxy)

            continue

        # ====================================================
        # 高级
        # ====================================================

        if "高级" in original_name:

            region = get_region(original_name)

            if not region:

                print(
                    "[跳过] 高级节点无法识别地区:",
                    original_name
                )

                continue

            new_proxy = proxy.copy()

            new_proxy["_region"] = region
            new_proxy["_original_name"] = original_name

            advanced.append(new_proxy)

            continue

        # ====================================================
        # 其它所有节点
        #
        # 包括：
        # [基础]
        # 普通节点
        # 免费节点
        # 其它标签
        #
        # 全部不处理。
        # ====================================================

        continue

    result = []

    # ========================================================
    # 实验性 → 专线
    # ========================================================

    print()
    print("实验性节点:")

    for proxy in experimental:

        region = proxy["_region"]

        proxy["name"] = f"{region}专线"

        result.append(proxy)

        print(
            f"  {proxy['_original_name']} "
            f"-> {proxy['name']}"
        )

    # ========================================================
    # 高级 → 备用
    #
    # 每个地区最多 2 个。
    # 先按地区收集，再取前两个。
    # ========================================================

    advanced_by_region = {
        region: []
        for region in REGIONS
    }

    for proxy in advanced:

        region = proxy["_region"]

        if region in advanced_by_region:

            advanced_by_region[region].append(proxy)

    print()
    print("高级备用节点:")

    for region in REGIONS:

        nodes = advanced_by_region[region][:2]

        for index, proxy in enumerate(
            nodes,
            start=1
        ):

            if index == 1:
                proxy["name"] = f"{region}备用"

            else:
                proxy["name"] = (
                    f"{region}备用-{index}"
                )

            result.append(proxy)

            print(
                f"  {proxy['_original_name']} "
                f"-> {proxy['name']}"
            )

    # ========================================================
    # 删除内部字段
    # ========================================================

    for proxy in result:

        proxy.pop("_region", None)
        proxy.pop("_original_name", None)

    print()
    print("======================================")
    print("筛选完成")
    print("======================================")

    print("实验性:", len(experimental))
    print("高级:", len(advanced))
    print("最终候选:", len(result))

    return result


# ============================================================
# 创建 Mihomo 测试配置
# ============================================================

def create_mihomo_config(proxies):

    proxy_names = [
        proxy["name"]
        for proxy in proxies
    ]

    config = {

        "mixed-port": MIHOMO_PORT,

        "allow-lan": False,

        "mode": "rule",

        "log-level": "debug",

        "ipv6": False,

        "external-controller":
            "127.0.0.1:9090",

        "unified-delay": True,

        "tcp-concurrent": True,

        "dns": {

            "enable": True,

            "ipv6": False,

            "enhanced-mode": "redir-host",

            "nameserver": [
                "system",
            ],
        },

        "proxies": proxies,

        "proxy-groups": [

            {
                "name": "TEST",
                "type": "select",
                "proxies": proxy_names,
            }

        ],

        "rules": [
            "MATCH,TEST"
        ],
    }

    return config


# ============================================================
# 启动 Mihomo
# ============================================================

def start_mihomo(proxies):

    config = create_mihomo_config(proxies)

    with open(
        MIHOMO_CONFIG,
        "w",
        encoding="utf-8",
    ) as f:

        yaml.safe_dump(
            config,
            f,
            allow_unicode=True,
            sort_keys=False,
        )

    print()
    print("======================================")
    print("启动 Mihomo")
    print("======================================")

    log = open(
        MIHOMO_LOG,
        "w",
        encoding="utf-8",
    )

    process = subprocess.Popen(
        [
            MIHOMO_BIN,
            "-f",
            MIHOMO_CONFIG,
        ],
        stdout=log,
        stderr=subprocess.STDOUT,
        text=True,
    )

    # --------------------------------------------------------
    # 等待 API
    # --------------------------------------------------------

    for _ in range(40):

        if process.poll() is not None:

            log.close()

            print("❌ Mihomo 进程提前退出")

            show_mihomo_log()

            sys.exit(1)

        try:

            response = requests.get(
                f"{MIHOMO_API}/proxies",
                timeout=1,
            )

            if response.status_code == 200:

                print("✅ Mihomo API 已启动")

                return process, log

        except Exception:
            pass

        time.sleep(0.5)

    print("❌ Mihomo API 启动超时")

    try:
        process.terminate()
    except Exception:
        pass

    log.close()

    show_mihomo_log()

    sys.exit(1)


# ============================================================
# 获取 Mihomo 节点列表
# ============================================================

def get_loaded_proxies():

    try:

        response = requests.get(
            f"{MIHOMO_API}/proxies",
            timeout=5,
        )

        if response.status_code != 200:

            print(
                "❌ 无法读取 Mihomo 节点列表"
            )

            return {}

        data = response.json()

        return data.get(
            "proxies",
            {}
        )

    except Exception as e:

        print(
            "❌ 读取 Mihomo 节点失败:",
            e
        )

        return {}


# ============================================================
# 单节点 API 测试
# ============================================================

def test_single_node(
    name,
    test_url,
    expected,
):

    encoded_name = urllib.parse.quote(
        name,
        safe=""
    )

    api_url = (
        f"{MIHOMO_API}/proxies/"
        f"{encoded_name}/delay"
    )

    params = {
        "url": test_url,
        "timeout": TEST_TIMEOUT,
        "expected": expected,
    }

    try:

        response = requests.get(
            api_url,
            params=params,
            timeout=(TEST_TIMEOUT / 1000) + 5,
        )

        if response.status_code != 200:
            return None

        try:
            data = response.json()
        except Exception:
            return None

        delay = data.get("delay")

        if delay:
            return int(delay)

        return None

    except Exception:
        return None


# ============================================================
# 测试全部节点
# ============================================================

def test_all_nodes(proxies):

    print()
    print("======================================")
    print("开始实际节点测试")
    print("======================================")

    print("基础测试:", BASIC_TEST_URL)
    print("YouTube测试:", YOUTUBE_TEST_URL)
    print(
        "单项超时:",
        f"{TEST_TIMEOUT / 1000:.0f} 秒"
    )

    print("======================================")

    loaded = get_loaded_proxies()

    print()
    print(
        "Mihomo 已加载节点:",
        len(loaded)
    )

    if not loaded:

        print(
            "❌ Mihomo 没有加载任何节点"
        )

        return []

    working = []

    total = len(proxies)

    for index, proxy in enumerate(
        proxies,
        start=1
    ):

        name = proxy["name"]

        print()
        print(
            f"[{index}/{total}] {name}"
        )

        # ----------------------------------------------------
        # 硬性检查
        # ----------------------------------------------------

        if name not in loaded:

            print(
                "    ❌ Mihomo 未加载此节点"
            )

            continue

        # ----------------------------------------------------
        # 基础 HTTPS
        # ----------------------------------------------------

        print(
            "    [1/2] 基础 HTTPS..."
        )

        basic_delay = test_single_node(
            name,
            BASIC_TEST_URL,
            "204"
        )

        if basic_delay:

            print(
                f"    ✅ 基础 HTTPS "
                f"{basic_delay} ms"
            )

        else:

            print(
                "    ❌ 基础 HTTPS 失败"
            )

            continue

        # ----------------------------------------------------
        # YouTube
        # ----------------------------------------------------

        print(
            "    [2/2] YouTube..."
        )

        youtube_delay = test_single_node(
            name,
            YOUTUBE_TEST_URL,
            "200-399"
        )

        if youtube_delay:

            print(
                f"    ✅ YouTube "
                f"{youtube_delay} ms"
            )

        else:

            print(
                "    ❌ YouTube 失败"
            )

            continue

        # ----------------------------------------------------
        # 通过
        # ----------------------------------------------------

        new_proxy = proxy.copy()

        new_proxy["_basic_delay"] = basic_delay
        new_proxy["_youtube_delay"] = youtube_delay

        working.append(new_proxy)

        print(
            "    ⭐ 节点最终通过"
        )

    return working


# ============================================================
# 清理测试字段
# ============================================================

def clean_output_proxies(proxies):

    for proxy in proxies:

        proxy.pop(
            "_basic_delay",
            None
        )

        proxy.pop(
            "_youtube_delay",
            None
        )

        # 双保险：
        # 内部字段绝不输出
        proxy.pop(
            "_region",
            None
        )

        proxy.pop(
            "_original_name",
            None
        )


# ============================================================
# 保存 cleanvip.yaml
# ============================================================

def save_yaml(proxies):

    output = {
        "proxies": proxies
    }

    temp_file = (
        OUTPUT_FILE + ".tmp"
    )

    with open(
        temp_file,
        "w",
        encoding="utf-8",
    ) as f:

        yaml.safe_dump(
            output,
            f,
            allow_unicode=True,
            sort_keys=False,
        )

    os.replace(
        temp_file,
        OUTPUT_FILE,
    )


# ============================================================
# 输出 Mihomo 日志
# ============================================================

def show_mihomo_log():

    print()
    print("======================================")
    print("Mihomo 日志")
    print("======================================")

    if not os.path.exists(
        MIHOMO_LOG
    ):

        print(
            "没有找到 Mihomo 日志"
        )

        return

    try:

        with open(
            MIHOMO_LOG,
            "r",
            encoding="utf-8",
            errors="ignore",
        ) as f:

            lines = f.readlines()

        if not lines:

            print(
                "Mihomo 日志为空"
            )

            return

        for line in lines[-100:]:

            print(
                line.rstrip()
            )

    except Exception as e:

        print(
            "读取 Mihomo 日志失败:",
            e
        )


# ============================================================
# 停止 Mihomo
# ============================================================

def stop_mihomo(
    process,
    log,
):

    print()
    print("停止 Mihomo")

    try:

        process.terminate()

        process.wait(
            timeout=5
        )

    except Exception:

        try:
            process.kill()
        except Exception:
            pass

    try:
        log.close()
    except Exception:
        pass


# ============================================================
# 主程序
# ============================================================

def main():

    print()
    print("======================================")
    print("VIP 节点自动清洗")
    print("======================================")

    # --------------------------------------------------------
    # 检查 Mihomo
    # --------------------------------------------------------

    if not os.path.exists(
        MIHOMO_BIN
    ):

        print(
            "❌ 找不到 Mihomo:",
            MIHOMO_BIN
        )

        sys.exit(1)

    # --------------------------------------------------------
    # 下载 VIP
    # --------------------------------------------------------

    vip_text = download_vip()

    # --------------------------------------------------------
    # YAML
    # --------------------------------------------------------

    try:

        data = yaml.safe_load(
            vip_text
        )

    except Exception as e:

        print(
            "❌ YAML 解析失败:",
            e
        )

        sys.exit(1)

    if not isinstance(
        data,
        dict
    ):

        print(
            "❌ VIP YAML 格式错误"
        )

        sys.exit(1)

    # --------------------------------------------------------
    # 筛选
    # --------------------------------------------------------

    candidates = collect_candidates(
        data
    )

    if not candidates:

        print(
            "❌ 筛选后没有节点"
        )

        sys.exit(1)

    # --------------------------------------------------------
    # 启动 Mihomo
    # --------------------------------------------------------

    mihomo, mihomo_log = start_mihomo(
        candidates
    )

    try:

        working = test_all_nodes(
            candidates
        )

    finally:

        stop_mihomo(
            mihomo,
            mihomo_log
        )

    # --------------------------------------------------------
    # 结果
    # --------------------------------------------------------

    print()
    print("======================================")
    print("测试完成")
    print("======================================")

    print(
        "候选节点:",
        len(candidates)
    )

    print(
        "可用节点:",
        len(working)
    )

    print(
        "失效节点:",
        len(candidates) - len(working)
    )

    # --------------------------------------------------------
    # 全部失败
    #
    # 不覆盖旧 cleanvip.yaml
    # --------------------------------------------------------

    if not working:

        print()
        print(
            "⚠️ 本轮没有测试通过的节点"
        )

        print(
            f"⚠️ 保留旧的 {OUTPUT_FILE}"
        )

        print(
            "✅ 本轮任务正常结束"
        )

        return

    # --------------------------------------------------------
    # 清理内部字段
    # --------------------------------------------------------

    clean_output_proxies(
        working
    )

    # --------------------------------------------------------
    # 保存
    # --------------------------------------------------------

    save_yaml(
        working
    )

    # --------------------------------------------------------
    # 最终结果
    # --------------------------------------------------------

    print()
    print("======================================")
    print(
        f"✅ {OUTPUT_FILE} 生成成功"
    )
    print("======================================")

    for proxy in working:

        print(
            f"- {proxy['name']} "
            f"[{proxy.get('type', '')}]"
        )

    print()
    print(
        f"最终保留 {len(working)} 个节点"
    )


if __name__ == "__main__":
    main()
