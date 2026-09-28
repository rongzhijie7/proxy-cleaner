import os
import subprocess
import tempfile
import time
import requests
import yaml

SOURCE_URL = (
    "https://gist.githubusercontent.com/rongzhijie7/"
    "76ce5d8efc7e0f92cda3b59a82536532/raw/Spare"
)

OUTPUT_FILE = "spare.yaml"

# 测速地址
TEST_URL = "https://www.gstatic.com/generate_204"

# 单节点测速超时时间
TIMEOUT = 5000

# 每个地区保留数量
KEEP_PER_REGION = 2


# ============================================================
# ISO 3166-1 Alpha-2
# ============================================================

REGIONS = {
    "香港": "HK",
    "台湾": "TW",
    "狮城": "SG",
    "新加坡": "SG",
    "日本": "JP",
    "韩国": "KR",
    "美国": "US",
    "英国": "GB",
    "俄罗斯": "RU",
    "土耳其": "TR",
    "德国": "DE",
    "瑞士": "CH",
    "菲律宾": "PH",
    "印度": "IN",
    "马来西亚": "MY",
    "尼日利亚": "NG",
    "南非": "ZA",
    "阿根廷": "AR",
    "加拿大": "CA",
    "澳大利亚": "AU",
    "法国": "FR",
    "荷兰": "NL",
    "意大利": "IT",
    "西班牙": "ES",
    "巴西": "BR",
}


# ============================================================
# 下载 Spare
# ============================================================

def download_source():

    print("正在下载 Spare...")

    response = requests.get(
        SOURCE_URL,
        timeout=30,
        headers={
            "User-Agent": "Mozilla/5.0"
        }
    )

    response.raise_for_status()

    data = yaml.safe_load(response.text)

    if not isinstance(data, dict):
        raise ValueError("Spare 不是有效的 YAML")

    proxies = data.get("proxies", [])

    if not isinstance(proxies, list):
        raise ValueError("Spare 中不存在有效的 proxies")

    print(f"源节点数量：{len(proxies)}")

    return proxies


# ============================================================
# 地区识别
# ============================================================

def get_region(name):

    name = str(name)

    for region, iso in REGIONS.items():

        if region in name:
            return region, iso

    return None, None


# ============================================================
# 创建 Mihomo 临时配置
# ============================================================

def create_mihomo_config(proxies):

    names = [
        proxy["name"]
        for proxy in proxies
        if "name" in proxy
    ]

    config = {
        "mixed-port": 7890,

        "allow-lan": False,

        "mode": "rule",

        "log-level": "silent",

        "external-controller": "127.0.0.1:9090",

        "proxies": proxies,

        "proxy-groups": [
            {
                "name": "TEST",
                "type": "select",
                "proxies": names,
            }
        ],

        "rules": [
            "MATCH,TEST"
        ],
    }

    fd, path = tempfile.mkstemp(
        prefix="mihomo-",
        suffix=".yaml"
    )

    os.close(fd)

    with open(
        path,
        "w",
        encoding="utf-8"
    ) as f:

        yaml.safe_dump(
            config,
            f,
            allow_unicode=True,
            sort_keys=False
        )

    return path


# ============================================================
# 启动 Mihomo
# ============================================================

def start_mihomo(config_file):

    print("启动 Mihomo...")

    process = subprocess.Popen(
        [
            "./mihomo",
            "-f",
            config_file
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )

    for _ in range(30):

        try:

            response = requests.get(
                "http://127.0.0.1:9090/version",
                timeout=1
            )

            if response.status_code == 200:

                print("Mihomo 已启动")

                return process

        except Exception:
            pass

        time.sleep(1)

    process.kill()

    raise RuntimeError("Mihomo 启动失败")


# ============================================================
# 单节点测速
# ============================================================

def test_proxy(name):

    proxy_name = requests.utils.quote(
        name,
        safe=""
    )

    url = (
        "http://127.0.0.1:9090/proxies/"
        f"{proxy_name}/delay"
    )

    params = {
        "url": TEST_URL,
        "timeout": TIMEOUT
    }

    try:

        response = requests.get(
            url,
            params=params,
            timeout=(TIMEOUT / 1000) + 3
        )

        if response.status_code != 200:
            return None

        data = response.json()

        delay = data.get("delay")

        if isinstance(delay, int) and delay > 0:
            return delay

    except Exception:
        pass

    return None


# ============================================================
# 主程序
# ============================================================

def main():

    proxies = download_source()

    # --------------------------------------------------------
    # 识别地区
    # --------------------------------------------------------

    valid = []

    for proxy in proxies:

        if not isinstance(proxy, dict):
            continue

        if "name" not in proxy:
            continue

        region, iso = get_region(
            proxy["name"]
        )

        if not region:
            print(
                f"跳过未知地区："
                f"{proxy['name']}"
            )
            continue

        item = proxy.copy()

        item["_region"] = region
        item["_iso"] = iso

        valid.append(item)

    print(
        f"识别到有效地区节点："
        f"{len(valid)}"
    )

    if not valid:
        raise RuntimeError(
            "没有找到有效地区节点"
        )

    # --------------------------------------------------------
    # Mihomo 配置
    # --------------------------------------------------------

    mihomo_proxies = []

    for proxy in valid:

        item = proxy.copy()

        item.pop("_region", None)
        item.pop("_iso", None)

        mihomo_proxies.append(item)

    config_file = create_mihomo_config(
        mihomo_proxies
    )

    process = None

    try:

        process = start_mihomo(
            config_file
        )

        # ----------------------------------------------------
        # 测速
        # ----------------------------------------------------

        results = []

        print("")
        print("开始测速...")
        print("=" * 60)

        for index, proxy in enumerate(
            valid,
            start=1
        ):

            name = proxy["name"]

            delay = test_proxy(name)

            if delay is None:

                print(
                    f"[{index}/{len(valid)}] "
                    f"{name} -> FAILED"
                )

                continue

            print(
                f"[{index}/{len(valid)}] "
                f"{name} -> {delay} ms"
            )

            item = proxy.copy()

            item["_delay"] = delay

            results.append(item)

        print("=" * 60)

        # ----------------------------------------------------
        # 按地区分组
        # ----------------------------------------------------

        grouped = {}

        for proxy in results:

            region = proxy["_region"]

            grouped.setdefault(
                region,
                []
            ).append(proxy)

        # ----------------------------------------------------
        # 每个地区取最快 2 个
        # ----------------------------------------------------

        final_proxies = []

        for region, nodes in grouped.items():

            nodes.sort(
                key=lambda x: x["_delay"]
            )

            nodes = nodes[
                :KEEP_PER_REGION
            ]

            iso = REGIONS[region]

            for index, proxy in enumerate(
                nodes,
                start=1
            ):

                item = proxy.copy()

                delay = item.pop(
                    "_delay"
                )

                item.pop(
                    "_region",
                    None
                )

                item.pop(
                    "_iso",
                    None
                )

                # ISO 3166-1 Alpha-2 + 两位序号
                item["name"] = (
                    f"{iso}{index:02d}"
                )

                final_proxies.append(
                    item
                )

                print(
                    f"保留 {item['name']} "
                    f"← {delay} ms"
                )

        # ----------------------------------------------------
        # 输出 spare.yaml
        # ----------------------------------------------------

        output = {
            "proxies": final_proxies
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

        print("")
        print(
            f"最终节点数量："
            f"{len(final_proxies)}"
        )

        print(
            f"已生成："
            f"{OUTPUT_FILE}"
        )

    finally:

        if process:

            process.terminate()

            try:
                process.wait(
                    timeout=5
                )
            except Exception:
                process.kill()

        if os.path.exists(
            config_file
        ):
            os.remove(
                config_file
            )


if __name__ == "__main__":
    main()
