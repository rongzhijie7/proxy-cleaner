import requests
import yaml
import subprocess
import time
import os
import sys
import urllib.parse
import threading

VIP_URL = (
    "https://gist.githubusercontent.com/"
    "rongzhijie7/76ce5d8efc7e0f92cda3b59a82536532/"
    "raw/VIP"
)

OUTPUT_FILE = "cleanvip.yaml"

MIHOMO_BIN = "./mihomo"
MIHOMO_PORT = 7890
MIHOMO_API = "http://127.0.0.1:9090"

# 基础 HTTPS 测试
BASIC_TEST_URL = "https://www.gstatic.com/generate_204"

# YouTube 测试
YOUTUBE_TEST_URL = "https://www.youtube.com/generate_204"

# 单次测试 15 秒
TEST_TIMEOUT = 15000

REGIONS = [
    "香港",
    "台湾",
    "日本",
    "新加坡",
    "美国",
    "英国",
    "韩国",
]


def download_vip():
    print("======================================")
    print("下载 VIP")
    print("======================================")

    try:
        r = requests.get(
            VIP_URL,
            timeout=60,
            headers={"User-Agent": "Mozilla/5.0"},
        )
    except Exception as e:
        print("VIP 下载失败:", e)
        sys.exit(1)

    print("HTTP:", r.status_code)
    print("Size:", len(r.content))

    if r.status_code != 200:
        print(r.text[:500])
        sys.exit(1)

    if not r.text.strip():
        print("VIP 内容为空")
        sys.exit(1)

    return r.text


def get_region(name):
    name = str(name)

    if "狮城" in name:
        return "新加坡"

    for region in REGIONS:
        if region in name:
            return region

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


def collect_candidates(data):

    proxies = data.get("proxies", [])

    if not isinstance(proxies, list):
        print("VIP YAML 中没有有效的 proxies")
        sys.exit(1)

    experimental = []
    advanced = []

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

        original_name = clean_name(original_name)

        # ==============================
        # 实验性 → 专线
        # ==============================
        if "实验性" in original_name:

            region = get_region(original_name)

            if not region:
                print(
                    "[跳过] 实验性节点无法识别地区:",
                    original_name,
                )
                continue

            new_proxy = proxy.copy()

            new_proxy["_region"] = region
            new_proxy["_category"] = "专线"
            new_proxy["_original_name"] = original_name

            experimental.append(new_proxy)

            continue

        # ==============================
        # 高级 → 备用
        # ==============================
        if "高级" in original_name:

            region = get_region(original_name)

            if not region:
                print(
                    "[跳过] 高级节点无法识别地区:",
                    original_name,
                )
                continue

            new_proxy = proxy.copy()

            new_proxy["_region"] = region
            new_proxy["_category"] = "备用"
            new_proxy["_original_name"] = original_name

            advanced.append(new_proxy)

    result = []

    # ==============================
    # 实验性
    # ==============================
    print()
    print("实验性节点:")

    for proxy in experimental:

        region = proxy["_region"]

        proxy["name"] = f"{region}专线"

        result.append(proxy)

        print(
            f"  {proxy['_original_name']} -> "
            f"{proxy['name']}"
        )

    # ==============================
    # 高级
    # 每地区最多 2 个
    # ==============================
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
            start=1,
        ):

            if index == 1:
                proxy["name"] = f"{region}备用"
            else:
                proxy["name"] = f"{region}备用-{index}"

            result.append(proxy)

            print(
                f"  {proxy['_original_name']} -> "
                f"{proxy['name']}"
            )

    # 删除内部字段
    for proxy in result:

        proxy.pop("_region", None)
        proxy.pop("_category", None)
        proxy.pop("_original_name", None)

    print()
    print("======================================")
    print("筛选完成")
    print("======================================")

    print("实验性:", len(experimental))
    print("高级:", len(advanced))
    print("最终候选:", len(result))

    return result


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

        # ==============================
        # 关键修改：
        # 使用系统 DNS
        # 不再使用 1.1.1.1 / 8.8.8.8
        # ==============================
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


def start_mihomo(proxies):

    config_file = "/tmp/mihomo_test.yaml"
    log_file = "/tmp/mihomo.log"

    config = create_mihomo_config(proxies)

    with open(
        config_file,
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
        log_file,
        "w",
        encoding="utf-8",
    )

    process = subprocess.Popen(
        [
            MIHOMO_BIN,
            "-f",
            config_file,
        ],
        stdout=log,
        stderr=subprocess.STDOUT,
        text=True,
    )

    # 等待 API
    for i in range(40):

        if process.poll() is not None:

            log.close()

            with open(
                log_file,
                "r",
                encoding="utf-8",
                errors="ignore",
            ) as f:
                print(f.read())

            print("Mihomo 启动失败")

            sys.exit(1)

        try:

            r = requests.get(
                f"{MIHOMO_API}/proxies",
                timeout=1,
            )

            if r.status_code == 200:

                print("Mihomo API 已启动")

                return process, log

        except Exception:
            pass

        time.sleep(0.5)

    print("Mihomo API 启动超时")

    try:
        process.terminate()
    except Exception:
        pass

    log.close()

    sys.exit(1)


def test_mihomo_node(
    name,
    test_url,
    expected,
):

    encoded_name = urllib.parse.quote(
        name,
        safe="",
    )

    url = (
        f"{MIHOMO_API}/proxies/"
        f"{encoded_name}/delay"
    )

    params = {
        "url": test_url,
        "timeout": TEST_TIMEOUT,
        "expected": expected,
    }

    try:

        r = requests.get(
            url,
            params=params,
            timeout=(TEST_TIMEOUT / 1000) + 5,
        )

        if r.status_code == 200:

            try:
                data = r.json()
            except Exception:
                return None

            delay = data.get("delay", 0)

            if delay:
                return delay

            return None

        return None

    except Exception:
        return None


def test_node(name):

    print()
    print(f"    节点: {name}")

    # ==============================
    # 第一关：
    # 基础 HTTPS
    # ==============================
    print("    [1/2] 基础 HTTPS 测试")

    basic_delay = test_mihomo_node(
        name,
        BASIC_TEST_URL,
        "204",
    )

    if basic_delay:

        print(
            f"    ✅ 基础 HTTPS: "
            f"{basic_delay} ms"
        )

    else:

        print(
            "    ❌ 基础 HTTPS: 超时/失败"
        )

        return False

    # ==============================
    # 第二关：
    # YouTube
    # ==============================
    print("    [2/2] YouTube 测试")

    youtube_delay = test_mihomo_node(
        name,
        YOUTUBE_TEST_URL,
        "200-399",
    )

    if youtube_delay:

        print(
            f"    ✅ YouTube: "
            f"{youtube_delay} ms"
        )

        return True

    print(
        "    ❌ YouTube: 超时/失败"
    )

    return False


def test_all_nodes(proxies):

    print()
    print("======================================")
    print("开始实际节点测试")
    print("======================================")

    print(
        "基础测试:",
        BASIC_TEST_URL
    )

    print(
        "YouTube测试:",
        YOUTUBE_TEST_URL
    )

    print(
        "单次超时:",
        f"{TEST_TIMEOUT / 1000:.0f} 秒"
    )

    print("======================================")

    working = []

    total = len(proxies)

    for index, proxy in enumerate(
        proxies,
        start=1,
    ):

        name = proxy["name"]

        print()
        print(
            f"[{index}/{total}]"
        )

        if test_node(name):

            working.append(proxy)

    return working


def save_yaml(proxies):

    output = {
        "proxies": proxies
    }

    with open(
        OUTPUT_FILE,
        "w",
        encoding="utf-8",
    ) as f:

        yaml.safe_dump(
            output,
            f,
            allow_unicode=True,
            sort_keys=False,
        )


def show_mihomo_log():

    log_file = "/tmp/mihomo.log"

    print()
    print("======================================")
    print("Mihomo 最近日志")
    print("======================================")

    if not os.path.exists(log_file):

        print("没有找到 Mihomo 日志")

        return

    try:

        with open(
            log_file,
            "r",
            encoding="utf-8",
            errors="ignore",
        ) as f:

            lines = f.readlines()

        # 只打印最后 120 行
        for line in lines[-120:]:
            print(line.rstrip())

    except Exception as e:

        print(
            "读取 Mihomo 日志失败:",
            e,
        )


def main():

    if not os.path.exists(MIHOMO_BIN):

        print(
            "错误：找不到 Mihomo:",
            MIHOMO_BIN,
        )

        sys.exit(1)

    # ==============================
    # 下载 VIP
    # ==============================
    vip_text = download_vip()

    # ==============================
    # 解析 YAML
    # ==============================
    try:

        data = yaml.safe_load(
            vip_text
        )

    except Exception as e:

        print(
            "YAML 解析失败:",
            e,
        )

        sys.exit(1)

    if not isinstance(data, dict):

        print(
            "VIP YAML 格式错误"
        )

        sys.exit(1)

    # ==============================
    # 筛选
    # ==============================
    candidates = collect_candidates(
        data
    )

    if not candidates:

        print(
            "筛选后没有节点"
        )

        sys.exit(1)

    # ==============================
    # 启动 Mihomo
    # ==============================
    mihomo, mihomo_log = start_mihomo(
        candidates
    )

    try:

        working = test_all_nodes(
            candidates
        )

    finally:

        print()
        print("停止 Mihomo")

        try:

            mihomo.terminate()

            mihomo.wait(
                timeout=5
            )

        except Exception:

            try:
                mihomo.kill()
            except Exception:
                pass

        try:
            mihomo_log.close()
        except Exception:
            pass

    # ==============================
    # 打印 Mihomo 日志
    # ==============================
    show_mihomo_log()

    # ==============================
    # 结果
    # ==============================
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

    # ==============================
    # 全部失败
    # ==============================
    if not working:

        print()
        print(
            "❌ 所有节点测试失败"
        )

        print(
            f"本次不覆盖 {OUTPUT_FILE}"
        )

        sys.exit(1)

    # ==============================
    # 保存
    # ==============================
    save_yaml(working)

    print()
    print("======================================")
    print(
        f"{OUTPUT_FILE} 生成成功"
    )
    print("======================================")

    for proxy in working:

        print(
            f"- {proxy['name']} "
            f"[{proxy.get('type', '')}]"
        )


if __name__ == "__main__":
    main()
