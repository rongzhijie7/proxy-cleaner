import yaml
import requests
import time
import subprocess
import re
import urllib.parse


# ============================================================
# 基本配置
# ============================================================

SOURCE_FILE = "source.yaml"
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
# YAML 类型规范化
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

    # 中文地区
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
# 下载/读取
# ============================================================

def load_source():

    print()
    print("======================================")
    print("读取 source.yaml")
    print("======================================")

    with open(
        SOURCE_FILE,
        "r",
        encoding="utf-8"
    ) as f:

        config = yaml.safe_load(f)

    if not isinstance(config, dict):

        raise RuntimeError(
            "source.yaml 格式错误"
        )

    raw_proxies = config.get(
        "proxies",
        []
    )

    print(
        "原始节点:",
        len(raw_proxies)
    )

    return raw_proxies


# ============================================================
# 筛选实验性
# ============================================================

def collect_experimental(raw_proxies):

    experimental = {}

    for raw_proxy in raw_proxies:

        proxy = normalize_proxy(raw_proxy)

        name = str(
            proxy.get(
                "name",
                ""
            )
        )

        if not name:
            continue

        if not proxy.get("server"):
            continue

        if not proxy.get("type"):
            continue

        if "实验性" not in name:
            continue

        region = get_region(name)

        if not region:
            continue

        # 每个地区只保留一个
        if region in experimental:
            continue

        proxy["name"] = f"{region}专线"

        experimental[region] = proxy

    return experimental


# ============================================================
# 筛选高级
# ============================================================

def collect_advanced(raw_proxies):

    advanced = {}

    for raw_proxy in raw_proxies:

        proxy = normalize_proxy(raw_proxy)

        name = str(
            proxy.get(
                "name",
                ""
            )
        )

        if not name:
            continue

        if not proxy.get("server"):
            continue

        if not proxy.get("type"):
            continue

        if "高级" not in name:
            continue

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

    return advanced


# ============================================================
# 生成最终候选节点
# ============================================================

def collect_candidates(raw_proxies):

    print()
    print("======================================")
    print("开始筛选 VIP 节点")
    print("======================================")

    experimental = collect_experimental(
        raw_proxies
    )

    advanced = collect_advanced(
        raw_proxies
    )

    result = []

    # --------------------------------------------------------
    # 实验性
    # --------------------------------------------------------

    print()
    print("【实验性节点】")

    for region in REGIONS:

        if region == "狮城":
            continue

        proxy = experimental.get(region)

        if not proxy:
            continue

        result.append(proxy)

        print(
            f"  {proxy['name']} <- "
            f"{proxy.get('server')}"
        )

    # --------------------------------------------------------
    # 高级
    # --------------------------------------------------------

    print()
    print("【高级节点】")

    for region in REGIONS:

        if region == "狮城":
            continue

        proxies = advanced.get(
            region,
            []
        )

        if not proxies:
            continue

        selected = proxies[:2]

        for index, proxy in enumerate(
            selected,
            start=1
        ):

            if index == 1:

                proxy["name"] = (
                    f"{region}备用"
                )

            else:

                proxy["name"] = (
                    f"{region}备用-{index}"
                )

            result.append(proxy)

            print(
                f"  {proxy['name']} <- "
                f"{proxy.get('server')}"
            )

        if len(proxies) > 2:

            print(
                f"  {region}: "
                f"原有 {len(proxies)} 个高级节点，"
                f"仅保留前 2 个"
            )

    print()
    print("======================================")
    print("筛选完成")
    print("======================================")

    print(
        "最终候选节点:",
        len(result)
    )

    return result


# ============================================================
# 创建 Mihomo 测试配置
# ============================================================

def create_test_config(proxies):

    names = [
        proxy["name"]
        for proxy in proxies
    ]

    test_config = {

        "mixed-port": 7890,

        "external-controller":
            "127.0.0.1:9090",

        "proxies":
            proxies,

        "proxy-groups": [

            {
                "name": "TEST",

                "type": "url-test",

                "proxies":
                    names,

                "url":
                    TEST_URL,

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
    print(
        "test.yaml 已生成"
    )


# ============================================================
# 等待 Mihomo
# ============================================================

def wait_mihomo():

    print()
    print(
        "等待 Mihomo API 启动..."
    )

    for _ in range(30):

        try:

            r = requests.get(
                f"{MIHOMO_API}/proxies",
                timeout=2
            )

            if r.status_code == 200:

                print(
                    "Mihomo API 已启动"
                )

                time.sleep(3)

                return True

        except Exception:
            pass

        time.sleep(1)

    print(
        "❌ Mihomo API 启动失败"
    )

    return False


# ============================================================
# 测试单个节点
# ============================================================

def test_node(name):

    encoded_name = urllib.parse.quote(
        name,
        safe=""
    )

    url = (
        f"{MIHOMO_API}/proxies/"
        f"{encoded_name}/delay"
    )

    try:

        r = requests.get(

            url,

            params={
                "timeout": TEST_TIMEOUT,
                "url": TEST_URL
            },

            timeout=8
        )

        print(
            "    HTTP:",
            r.status_code
        )

        print(
            "    返回:",
            r.text[:500]
        )

        if r.status_code != 200:

            return None

        try:

            data = r.json()

        except Exception:

            print(
                "    ❌ 返回不是 JSON"
            )

            return None

        if "delay" not in data:

            print(
                "    ❌ 没有 delay"
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

def check_nodes(proxies):

    print()
    print("======================================")
    print("开始节点存活检测")
    print("======================================")

    alive = []

    for index, proxy in enumerate(
        proxies,
        start=1
    ):

        name = proxy["name"]

        print()
        print(
            f"[{index}/{len(proxies)}] {name}"
        )

        delay = test_node(name)

        if delay is not None:

            print(
                f"    ✅ 可用 {delay} ms"
            )

            alive.append(name)

        else:

            print(
                "    ❌ 节点失效"
            )

    return alive


# ============================================================
# 输出 cleanvip.yaml
# ============================================================

def save_output(proxies, alive):

    alive_set = set(alive)

    clean = []

    for proxy in proxies:

        if proxy["name"] in alive_set:

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
    print("测速完成")
    print("======================================")

    print(
        "候选节点:",
        len(proxies)
    )

    print(
        "测速成功:",
        len(alive)
    )

    print(
        "测速失败:",
        len(proxies) - len(alive)
    )

    print()
    print(
        "======================================"
    )
    print("cleanvip.yaml 已生成")
    print("======================================")

    print(
        "最终节点:",
        len(clean)
    )

    for proxy in clean:

        print(
            "  ✅",
            proxy["name"]
        )


# ============================================================
# 主程序
# ============================================================

def main():

    print()
    print("======================================")
    print("VIP 节点自动清洗")
    print("======================================")

    raw_proxies = load_source()

    if not raw_proxies:

        print(
            "❌ 没有原始节点"
        )

        return

    candidates = collect_candidates(
        raw_proxies
    )

    if not candidates:

        print(
            "❌ 没有符合条件的节点"
        )

        return

    create_test_config(
        candidates
    )

    process = None

    try:

        print()
        print(
            "启动 Mihomo..."
        )

        process = subprocess.Popen(
            [
                MIHOMO,
                "-f",
                TEST_FILE
            ]
        )

        if not wait_mihomo():

            raise RuntimeError(
                "Mihomo 启动失败"
            )

        alive = check_nodes(
            candidates
        )

        save_output(
            candidates,
            alive
        )

    finally:

        if process:

            print()
            print(
                "关闭 Mihomo"
            )

            try:

                process.kill()

                process.wait(
                    timeout=5
                )

            except Exception:

                pass


# ============================================================
# 执行
# ============================================================

if __name__ == "__main__":
    main()
