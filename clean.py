import yaml
import requests
import time
import subprocess
import urllib.parse


# ============================================================
# 配置
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
    "united states": "美国",
    "usa": "美国",
    "america": "美国",
    "united kingdom": "英国",
    "uk": "英国",
    "korea": "韩国",
}


# ============================================================
# 地区识别
# ============================================================

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
# 读取 VIP
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
# 收集实验性节点
#
# 注意：
# 这里完全保留原始 proxy
# 不 normalize
# 不修改任何字段
# ============================================================

def collect_experimental(raw_proxies):

    experimental = {}

    for proxy in raw_proxies:

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

        if region in experimental:
            continue

        experimental[region] = proxy

    return experimental


# ============================================================
# 收集高级节点
#
# 注意：
# 完全保留原始 proxy
# ============================================================

def collect_advanced(raw_proxies):

    advanced = {}

    for proxy in raw_proxies:

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
# 筛选 14 个候选
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

    candidates = []


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

        candidates.append({
            "proxy": proxy,
            "region": region,
            "category": "experimental",
            "original_name": proxy["name"]
        })

        print(
            region,
            "<-",
            proxy["name"]
        )


    # --------------------------------------------------------
    # 高级
    # --------------------------------------------------------

    print()
    print("【高级节点】")

    for region in REGIONS:

        if region == "狮城":
            continue

        nodes = advanced.get(
            region,
            []
        )

        if not nodes:
            continue

        selected = nodes[:2]

        for index, proxy in enumerate(
            selected,
            start=1
        ):

            candidates.append({
                "proxy": proxy,
                "region": region,
                "category": "advanced",
                "index": index,
                "original_name": proxy["name"]
            })

            print(
                region,
                f"备用-{index}",
                "<-",
                proxy["name"]
            )

        if len(nodes) > 2:

            print(
                f"{region}: 原有 {len(nodes)} "
                f"个高级节点，仅测试前 2 个"
            )


    print()
    print("======================================")
    print("候选节点统计")
    print("======================================")

    print(
        "候选节点:",
        len(candidates)
    )

    return candidates


# ============================================================
# 生成测试配置
#
# 最重要：
# 使用原始节点名称
# 不修改 proxy 内任何字段
# ============================================================

def create_test_config(candidates):

    proxies = []

    names = []

    for item in candidates:

        proxy = item["proxy"]

        original_name = item["original_name"]

        # 创建副本，只保证不会污染原始数据
        proxy_copy = dict(proxy)

        # 测试阶段使用原始名称
        proxy_copy["name"] = original_name

        proxies.append(proxy_copy)

        names.append(original_name)


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
    print(
        "test.yaml 已生成"
    )


# ============================================================
# 等待 Mihomo
# ============================================================

def wait_mihomo():

    print()
    print(
        "等待 Mihomo API..."
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

    return False


# ============================================================
# 测试节点
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

        data = r.json()

        if "delay" not in data:
            return None

        return int(
            data["delay"]
        )

    except Exception as e:

        print(
            "    异常:",
            repr(e)
        )

        return None


# ============================================================
# 主程序
# ============================================================

def main():

    raw_proxies = load_source()

    if not raw_proxies:
        return


    candidates = collect_candidates(
        raw_proxies
    )

    if not candidates:
        return


    create_test_config(
        candidates
    )


    process = None

    try:

        print()
        print(
            "======================================"
        )
        print(
            "启动 Mihomo"
        )
        print(
            "======================================"
        )

        process = subprocess.Popen(
            [
                MIHOMO,
                "-f",
                TEST_FILE
            ]
        )


        if not wait_mihomo():

            print(
                "❌ Mihomo 启动失败"
            )

            return


        # ====================================================
        # 测试
        # ====================================================

        print()
        print(
            "======================================"
        )
        print(
            "开始节点测速"
        )
        print(
            "======================================"
        )


        alive = []


        for index, item in enumerate(
            candidates,
            start=1
        ):

            original_name = item[
                "original_name"
            ]

            print()
            print(
                f"[{index}/{len(candidates)}] "
                f"{original_name}"
            )


            delay = test_node(
                original_name
            )


            if delay is not None:

                print(
                    f"    ✅ 可用 {delay} ms"
                )

                alive.append(item)

            else:

                print(
                    "    ❌ 测速失败"
                )


        # ====================================================
        # 输出
        #
        # 只有这里才修改名称
        # ====================================================

        clean = []


        for item in alive:

            proxy = dict(
                item["proxy"]
            )

            region = item["region"]

            if item["category"] == "experimental":

                proxy["name"] = (
                    f"{region}专线"
                )

            else:

                index = item["index"]

                if index == 1:

                    proxy["name"] = (
                        f"{region}备用"
                    )

                else:

                    proxy["name"] = (
                        f"{region}备用-{index}"
                    )

            clean.append(
                proxy
            )


        # ====================================================
        # 保存
        # ====================================================

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
        print(
            "======================================"
        )
        print(
            "测速完成"
        )
        print(
            "======================================"
        )

        print(
            "候选节点:",
            len(candidates)
        )

        print(
            "测速成功:",
            len(alive)
        )

        print(
            "测速失败:",
            len(candidates) - len(alive)
        )

        print()
        print(
            "最终 cleanvip.yaml:",
            len(clean)
        )


        for proxy in clean:

            print(
                "  ✅",
                proxy["name"]
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


if __name__ == "__main__":
    main()
