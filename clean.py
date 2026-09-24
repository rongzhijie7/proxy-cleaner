import requests
import yaml
import subprocess
import time
import os
import sys
import urllib.parse

VIP_URL = (
    "https://gist.githubusercontent.com/"
    "rongzhijie7/76ce5d8efc7e0f92cda3b59a82536532/"
    "raw/VIP"
)

# 最终输出文件
OUTPUT_FILE = "cleanvip.yaml"

# Mihomo
MIHOMO_BIN = "./mihomo"
MIHOMO_PORT = 7890
MIHOMO_API = "http://127.0.0.1:9090"

# YouTube 测试地址
TEST_URL = "https://www.youtube.com/generate_204"

# 单节点测试超时：15 秒
TEST_TIMEOUT = 15000

# Mihomo 启动等待
START_WAIT = 3

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

        # ==========================
        # 实验性 → 专线
        # ==========================
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

        # ==========================
        # 高级 → 备用
        # ==========================
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

    # ==========================
    # 最终候选节点
    # ==========================
    result = []

    # ==========================
    # 实验性节点
    # ==========================
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

    # ==========================
    # 高级节点按地区归类
    # 每个地区最多 2 个
    # ==========================
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

        # 每个地区最多保留 2 个
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

    # ==========================
    # 删除内部字段
    # ==========================
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

        "log-level": "info",

        "external-controller":
            "127.0.0.1:9090",

        "unified-delay": True,

        "tcp-concurrent": True,

        "dns": {
            "enable": True,
            "ipv6": False,
            "enhanced-mode": "fake-ip",
            "nameserver": [
                "1.1.1.1",
                "8.8.8.8",
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

    process = subprocess.Popen(
        [
            MIHOMO_BIN,
            "-f",
            config_file,
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )

    # 等待 API 启动
    for i in range(40):

        if process.poll() is not None:

            output = process.stdout.read()

            print(output)

            print("Mihomo 启动失败")

            sys.exit(1)

        try:

            r = requests.get(
                f"{MIHOMO_API}/proxies",
                timeout=1,
            )

            if r.status_code == 200:

                print("Mihomo API 已启动")

                return process

        except Exception:
            pass

        time.sleep(0.5)

    print("Mihomo API 启动超时")

    try:
        process.terminate()
    except Exception:
        pass

    sys.exit(1)


def test_node(name):

    encoded_name = urllib.parse.quote(
        name,
        safe="",
    )

    url = (
        f"{MIHOMO_API}/proxies/"
        f"{encoded_name}/delay"
    )

    params = {
        "url": TEST_URL,

        "timeout": TEST_TIMEOUT,

        # 接受 200 或 204
        "expected": "200/204",
    }

    try:

        r = requests.get(
            url,
            params=params,
            timeout=(TEST_TIMEOUT / 1000) + 5,
        )

        # ==========================
        # 成功
        # ==========================
        if r.status_code == 200:

            try:
                data = r.json()
            except Exception:

                print(
                    f"    ❌ {name} "
                    f"返回内容不是 JSON"
                )

                print(
                    "       ",
                    r.text[:300],
                )

                return False

            delay = data.get("delay", 0)

            if delay:

                print(
                    f"    ✅ {name}  "
                    f"{delay} ms"
                )

                return True

            print(
                f"    ❌ {name}  "
                f"无有效延迟"
            )

            print(
                "       ",
                data,
            )

            return False

        # ==========================
        # Mihomo 超时
        # ==========================
        if r.status_code == 504:

            print(
                f"    ❌ {name}  "
                f"Mihomo 测试超时"
            )

            print(
                "       ",
                r.text[:300],
            )

            return False

        # ==========================
        # 其他 API 错误
        # ==========================
        print(
            f"    ❌ {name}  "
            f"API HTTP {r.status_code}"
        )

        print(
            "       ",
            r.text[:300],
        )

        return False

    except requests.exceptions.Timeout:

        print(
            f"    ❌ {name}  "
            f"Python 请求超时"
        )

        return False

    except Exception as e:

        print(
            f"    ❌ {name}  "
            f"{str(e)[:200]}"
        )

        return False


def test_all_nodes(proxies):

    print()
    print("======================================")
    print("开始实际节点测试")
    print("======================================")

    print("测试地址:")
    print(TEST_URL)

    print("单节点超时:")
    print(f"{TEST_TIMEOUT / 1000:.0f} 秒")

    print("======================================")
    print()

    working = []

    total = len(proxies)

    for index, proxy in enumerate(
        proxies,
        start=1,
    ):

        name = proxy["name"]

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


def main():

    if not os.path.exists(MIHOMO_BIN):

        print(
            "错误：找不到 Mihomo:",
            MIHOMO_BIN,
        )

        sys.exit(1)

    # ==========================
    # 下载
    # ==========================
    vip_text = download_vip()

    # ==========================
    # YAML
    # ==========================
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

    # ==========================
    # 筛选
    # ==========================
    candidates = collect_candidates(
        data
    )

    if not candidates:

        print(
            "筛选后没有节点"
        )

        sys.exit(1)

    # ==========================
    # 启动 Mihomo
    # ==========================
    mihomo = start_mihomo(
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

    # ==========================
    # 结果
    # ==========================
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

    # ==========================
    # 全部失败
    # 不覆盖旧文件
    # ==========================
    if not working:

        print()
        print(
            "❌ 所有节点测试失败"
        )

        print(
            f"本次不覆盖 {OUTPUT_FILE}"
        )

        sys.exit(1)

    # ==========================
    # 保存
    # ==========================
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
