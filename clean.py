import requests
import yaml
import re
import time
import subprocess


SOURCE_URL = "https://gist.githubusercontent.com/rongzhijie7/76ce5d8efc7e0f92cda3b59a82536532/raw/VIP"

OUTPUT_FILE = "cleanvip.yaml"
TEST_FILE = "test.yaml"

MIHOMO = "./mihomo"
MIHOMO_API = "http://127.0.0.1:9090"

TEST_URL = "https://www.gstatic.com/generate_204"
TEST_TIMEOUT = 5000


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
    return {
        key: normalize_value(value)
        for key, value in proxy.items()
    }


def get_region(name):

    for region in REGIONS:

        if region in name:

            if region == "狮城":
                return "新加坡"

            return region

    lower_name = name.lower()

    for alias, region in REGION_ALIASES.items():

        if alias in lower_name:
            return region

    return None


# ============================================================
# 下载 VIP
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
            print("❌ VIP 文件格式错误")
            return None

        proxies = config.get("proxies", [])

        print("原始节点:", len(proxies))

        return proxies

    except Exception as e:

        print("❌ 下载失败:", repr(e))

        return None


# ============================================================
# 清洗节点
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

        name = str(proxy.get("name", ""))

        if not name:
            continue

        if not proxy.get("server"):
            continue

        if not proxy.get("type"):
            continue

        # ----------------------------------------------------
        # 实验性
        # ----------------------------------------------------

        if "实验性" in name:

            region = get_region(name)

            if not region:
                continue

            if region not in experimental:

                proxy["name"] = f"{region}专线"

                experimental[region] = proxy

        # ----------------------------------------------------
        # 高级
        # ----------------------------------------------------

        elif "高级" in name:

            region = get_region(name)

            if not region:

                print(
                    "跳过高级节点（地区未知）:",
                    name
                )

                continue

            advanced.setdefault(
                region,
                []
            ).append(proxy)

        # ----------------------------------------------------
        # 其他节点全部忽略
        # ----------------------------------------------------

    result = []

    # ========================================================
    # 实验性
    # ========================================================

    print()
    print("实验性节点:")

    for region, proxy in experimental.items():

        result.append(proxy)

        print(
            " ",
            proxy["name"],
            "<-",
            proxy.get("server")
        )

    # ========================================================
    # 高级
    # ========================================================

    print()
    print("高级节点:")

    for region, proxies in advanced.items():

        selected = proxies[:2]

        for index, proxy in enumerate(
            selected,
            start=1
        ):

            if index == 1:
                proxy["name"] = f"{region}备用"
            else:
                proxy["name"] = f"{region}备用-{index}"

            result.append(proxy)

            print(
                " ",
                proxy["name"],
                "<-",
                proxy.get("server")
            )

        if len(proxies) > 2:

            print(
                f"  {region}: "
                f"原有 {len(proxies)} 个高级节点，"
                f"仅保留前 2 个"
            )

    print()
    print("最终候选节点:", len(result))

    return result


# ============================================================
# 生成 Mihomo 测试配置
# ============================================================

def create_test_config(proxies):

    names = [
        proxy["name"]
        for proxy in proxies
    ]

    config = {

        "mixed-port": 7890,

        "external-controller":
            "127.0.0.1:9090",

        "proxies":
            proxies,

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
            config,
            f,
            allow_unicode=True,
            sort_keys=False
        )


# ============================================================
# 等待 Mihomo
# ============================================================

def wait_mihomo():

    print()
    print("等待 Mihomo 启动...")

    for _ in range(20):

        try:

            r = requests.get(
                f"{MIHOMO_API}/proxies",
                timeout=2
            )

            if r.status_code == 200:

                print("Mihomo API 已启动")

                # 和之前成功脚本保持一致
                time.sleep(5)

                return True

        except Exception:
            pass

        time.sleep(1)

    print("❌ Mihomo API 启动失败")

    return False


# ============================================================
# 测试节点
#
# 注意：
# 这里只检测，不删除
# ============================================================

def test_node(name):

    try:

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

        if r.status_code != 200:

            print(
                f"    ❌ HTTP {r.status_code}"
            )

            try:
                print(
                    "    返回:",
                    r.text[:300]
                )
            except Exception:
                pass

            return None

        try:

            data = r.json()

        except Exception:

            print("    ❌ 返回不是 JSON")

            return None

        if "delay" not in data:

            print(
                "    ❌ 没有 delay:",
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
# 节点检测
# ============================================================

def check_nodes(proxies):

    print()
    print("======================================")
    print("开始节点存活检测")
    print("注意：检测失败不会删除节点")
    print("======================================")

    success = 0
    failed = 0

    for index, proxy in enumerate(
        proxies,
        start=1
    ):

        name = proxy["name"]

        print(
            f"[{index}/{len(proxies)}] {name}"
        )

        delay = test_node(name)

        if delay is not None:

            print(
                f"    ✅ 可用 {delay} ms"
            )

            success += 1

        else:

            print(
                "    ❌ 检测失败"
            )

            failed += 1

    print()
    print("======================================")
    print("节点检测完成")
    print("======================================")

    print("检测节点:", len(proxies))
    print("检测成功:", success)
    print("检测失败:", failed)

    print()
    print("⚠️ 检测结果仅供参考")
    print("⚠️ 本轮不会删除任何节点")


# ============================================================
# 输出 cleanvip.yaml
# ============================================================

def save_output(proxies):

    output = {
        "proxies": proxies
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
    print("清洗完成")
    print("======================================")

    print(
        "最终节点:",
        len(proxies)
    )

    print(
        "输出文件:",
        OUTPUT_FILE
    )


# ============================================================
# 主程序
# ============================================================

def main():

    print()
    print("======================================")
    print("VIP 节点自动清洗 + 存活检测")
    print("======================================")

    raw_proxies = download_source()

    if not raw_proxies:
        return

    candidates = collect_candidates(
        raw_proxies
    )

    if not candidates:
        print("❌ 没有符合条件的节点")
        return

    # --------------------------------------------------------
    # 先生成最终订阅
    # --------------------------------------------------------

    save_output(candidates)

    # --------------------------------------------------------
    # 再进行存活检测
    # --------------------------------------------------------

    create_test_config(
        candidates
    )

    process = None

    try:

        print()
        print("启动 Mihomo...")

        process = subprocess.Popen(
            [
                MIHOMO,
                "-f",
                TEST_FILE
            ]
        )

        if wait_mihomo():

            check_nodes(
                candidates
            )

    finally:

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
