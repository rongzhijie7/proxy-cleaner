import os
import gzip
import shutil
import subprocess
import time
from collections import defaultdict

import requests
import yaml


# ============================================================
# 配置
# ============================================================

GIST_URL = (
    "https://gist.githubusercontent.com/"
    "rongzhijie7/76ce5d8efc7e0f92cda3b59a82536532/raw/VIP"
)

OUTPUT_FILE = "cleanvip.yaml"

MIHOMO_VERSION = "v1.19.31"

TEST_URL = "https://www.gstatic.com/generate_204"

TEST_TIMEOUT = 5000

MAX_BACKUP_PER_REGION = 2


# ============================================================
# ISO 3166-1 alpha-2 地区识别
# ============================================================

REGIONS = {
    "香港": "HK",
    "🇭🇰": "HK",

    "台湾": "TW",
    "台灣": "TW",
    "🇹🇼": "TW",

    "美国": "US",
    "美國": "US",
    "🇺🇸": "US",

    "新加坡": "SG",
    "狮城": "SG",
    "獅城": "SG",
    "🇸🇬": "SG",

    "日本": "JP",
    "🇯🇵": "JP",

    "英国": "GB",
    "英國": "GB",
    "🇬🇧": "GB",

    "韩国": "KR",
    "韓國": "KR",
    "🇰🇷": "KR",
}


# ============================================================
# 输出日志
# ============================================================

def log(text):
    print(text, flush=True)


# ============================================================
# 1. 从 VIP Gist 获取原始节点
# ============================================================

def download_vip():

    log("=" * 60)
    log("1. 获取 VIP Gist")
    log("=" * 60)

    response = requests.get(
        GIST_URL,
        timeout=30,
        headers={
            "User-Agent": "Mozilla/5.0"
        }
    )

    log(f"Gist HTTP 状态: {response.status_code}")

    response.raise_for_status()

    content = response.text

    log(f"原始内容大小: {len(content)}")

    return content


# ============================================================
# 2. 解析 YAML
# ============================================================

def parse_vip(content):

    log("=" * 60)
    log("2. 解析 VIP 节点")
    log("=" * 60)

    data = yaml.safe_load(content)

    if not isinstance(data, dict):
        raise RuntimeError("VIP Gist 不是有效 YAML")

    proxies = data.get("proxies")

    if not isinstance(proxies, list):
        raise RuntimeError("VIP Gist 中没有 proxies")

    log(f"原始节点数量: {len(proxies)}")

    return proxies


# ============================================================
# 地区识别
# ============================================================

def detect_region(name):

    for keyword in sorted(
        REGIONS,
        key=len,
        reverse=True
    ):
        if keyword.lower() in name.lower():
            return REGIONS[keyword]

    return None


# ============================================================
# 节点类型识别
# ============================================================

def detect_type(name):

    # 实验性 = 专线
    if "实验性" in name:
        return "dedicated"

    # 高级 = 备用
    if "高级" in name:
        return "backup"

    return None


# ============================================================
# 3. 筛选节点
# ============================================================

def filter_nodes(proxies):

    log("=" * 60)
    log("3. 筛选节点")
    log("=" * 60)

    dedicated = []
    backup = []

    ignored_region = 0
    ignored_keyword = 0

    for proxy in proxies:

        if not isinstance(proxy, dict):
            continue

        name = str(proxy.get("name", ""))

        if not name:
            continue

        region = detect_region(name)

        if not region:
            ignored_region += 1
            continue

        node_type = detect_type(name)

        if node_type == "dedicated":

            dedicated.append({
                "proxy": proxy,
                "region": region,
                "type": "dedicated",
                "original_name": name,
            })

        elif node_type == "backup":

            backup.append({
                "proxy": proxy,
                "region": region,
                "type": "backup",
                "original_name": name,
            })

        else:

            ignored_keyword += 1

    log(f"专线候选: {len(dedicated)}")
    log(f"备用候选: {len(backup)}")
    log(f"地区不匹配: {ignored_region}")
    log(f"关键词不匹配: {ignored_keyword}")

    return dedicated, backup


# ============================================================
# 下载 Mihomo
# ============================================================

def download_mihomo():

    binary = "./mihomo"

    if os.path.exists(binary):

        log("使用已有 Mihomo")

        os.chmod(binary, 0o755)

        return binary

    log("=" * 60)
    log("下载 Mihomo")
    log("=" * 60)

    url = (
        "https://github.com/MetaCubeX/mihomo/releases/download/"
        f"{MIHOMO_VERSION}/"
        f"mihomo-linux-amd64-v3-{MIHOMO_VERSION}.gz"
    )

    response = requests.get(
        url,
        timeout=60,
        stream=True
    )

    response.raise_for_status()

    gz_file = "mihomo.gz"

    with open(gz_file, "wb") as f:

        for chunk in response.iter_content(
            chunk_size=1024 * 64
        ):

            if chunk:
                f.write(chunk)

    with gzip.open(gz_file, "rb") as src:

        with open(binary, "wb") as dst:
            shutil.copyfileobj(src, dst)

    os.chmod(binary, 0o755)

    os.remove(gz_file)

    log("Mihomo 下载完成")

    return binary


# ============================================================
# 启动 Mihomo
# ============================================================

def start_mihomo(binary, proxies):

    workdir = ".mihomo_test"

    os.makedirs(workdir, exist_ok=True)

    config_file = os.path.join(
        workdir,
        "config.yaml"
    )

    config = {
        "mixed-port": 7890,
        "allow-lan": False,
        "mode": "rule",
        "log-level": "error",

        "external-controller": "127.0.0.1:9090",

        "proxies": proxies,

        "proxy-groups": [
            {
                "name": "TEST",
                "type": "select",
                "proxies": [
                    proxy["name"]
                    for proxy in proxies
                ],
            }
        ],

        "rules": [
            "MATCH,TEST"
        ],
    }

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
            binary,
            "-d",
            workdir,
            "-f",
            config_file
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )

    log("等待 Mihomo 启动...")

    for _ in range(30):

        try:

            response = requests.get(
                "http://127.0.0.1:9090",
                timeout=1
            )

            if response.status_code < 500:
                log("Mihomo 已启动")
                return process

        except Exception:
            pass

        time.sleep(1)

    process.kill()

    raise RuntimeError("Mihomo 启动失败")


# ============================================================
# 测试单个节点
# ============================================================

def test_proxy(name):

    api_url = (
        "http://127.0.0.1:9090/proxies/"
        + requests.utils.quote(
            name,
            safe=""
        )
    )

    try:

        response = requests.get(
            api_url,
            params={
                "url": TEST_URL,
                "timeout": TEST_TIMEOUT,
            },
            timeout=10
        )

        if response.status_code != 200:
            return None

        data = response.json()

        delay = data.get("delay")

        if delay is None:
            return None

        return int(delay)

    except Exception:
        return None


# ============================================================
# 4. 测速
# ============================================================

def speed_test(nodes):

    if not nodes:
        return []

    log("=" * 60)
    log("4. 开始测速")
    log("=" * 60)

    mihomo_binary = download_mihomo()

    # 为了避免 VIP 原始节点重名，
    # 测速时临时使用唯一名称。
    test_proxies = []

    for index, item in enumerate(nodes):

        proxy = dict(item["proxy"])

        test_name = f"__VIP_TEST_{index:04d}__"

        proxy["name"] = test_name

        item["test_name"] = test_name

        test_proxies.append(proxy)

    process = None

    passed = []

    try:

        process = start_mihomo(
            mihomo_binary,
            test_proxies
        )

        for index, item in enumerate(nodes):

            delay = test_proxy(
                item["test_name"]
            )

            if delay is not None:

                item["delay"] = delay

                passed.append(item)

                log(
                    f"[通过] "
                    f"{item['original_name']} "
                    f"{delay} ms"
                )

            else:

                log(
                    f"[失败] "
                    f"{item['original_name']}"
                )

    finally:

        if process:

            try:
                process.terminate()
                process.wait(timeout=5)
            except Exception:
                try:
                    process.kill()
                except Exception:
                    pass

    log("")
    log(f"测速通过: {len(passed)} / {len(nodes)}")

    return passed


# ============================================================
# 5. 备用节点每地区最多保留 2 个
# ============================================================

def limit_backup(nodes):

    grouped = defaultdict(list)

    for item in nodes:

        grouped[
            item["region"]
        ].append(item)

    result = []

    log("=" * 60)
    log("5. 筛选备用节点")
    log("=" * 60)

    for region in sorted(grouped):

        items = grouped[region]

        # 延迟从低到高
        items.sort(
            key=lambda item: item["delay"]
        )

        selected = items[
            :MAX_BACKUP_PER_REGION
        ]

        result.extend(selected)

        log(
            f"{region}: "
            f"{len(items)} 个测速通过 → "
            f"保留 {len(selected)} 个"
        )

    return result


# ============================================================
# 6. 最终命名
# ============================================================

def rename_nodes(dedicated, backup):

    log("=" * 60)
    log("6. 按 ISO 3166-1 alpha-2 重新命名")
    log("=" * 60)

    counters = defaultdict(int)

    final_nodes = []

    # 专线
    for item in dedicated:

        region = item["region"]

        key = f"{region}专线"

        counters[key] += 1

        number = counters[key]

        new_name = f"{key}{number:02d}"

        proxy = dict(item["proxy"])

        proxy["name"] = new_name

        final_nodes.append(proxy)

        log(
            f"{item['original_name']} "
            f"→ {new_name} "
            f"({item['delay']} ms)"
        )

    # 备用
    for item in backup:

        region = item["region"]

        key = f"{region}备用"

        counters[key] += 1

        number = counters[key]

        new_name = f"{key}{number:02d}"

        proxy = dict(item["proxy"])

        proxy["name"] = new_name

        final_nodes.append(proxy)

        log(
            f"{item['original_name']} "
            f"→ {new_name} "
            f"({item['delay']} ms)"
        )

    return final_nodes


# ============================================================
# 7. 生成 cleanvip.yaml
# ============================================================

def save_yaml(proxies):

    log("=" * 60)
    log("7. 生成 cleanvip.yaml")
    log("=" * 60)

    output = {
        "proxies": proxies
    }

    # 直接覆盖旧文件
    with open(
        OUTPUT_FILE,
        "w",
        encoding="utf-8"
    ) as f:

        yaml.safe_dump(
            output,
            f,
            allow_unicode=True,
            sort_keys=False,
            default_flow_style=False
        )

    log(
        f"最终节点数量: {len(proxies)}"
    )

    log(
        f"文件已生成: {OUTPUT_FILE}"
    )


# ============================================================
# 主程序
# ============================================================

def main():

    log("")
    log("=" * 60)
    log("CleanVIP")
    log("VIP Gist → 筛选 → 测速 → ISO命名 → cleanvip.yaml")
    log("=" * 60)
    log("")

    # --------------------------------------------------------
    # 1. 只从 VIP Gist 获取源节点
    # --------------------------------------------------------

    content = download_vip()

    # --------------------------------------------------------
    # 2. 解析原始 YAML
    # --------------------------------------------------------

    proxies = parse_vip(content)

    # --------------------------------------------------------
    # 3. 筛选
    # --------------------------------------------------------

    dedicated, backup = filter_nodes(
        proxies
    )

    candidates = dedicated + backup

    if not candidates:

        raise RuntimeError(
            "筛选后没有符合条件的节点"
        )

    # --------------------------------------------------------
    # 4. 测速
    # --------------------------------------------------------

    passed = speed_test(
        candidates
    )

    if not passed:

        raise RuntimeError(
            "测速后没有可用节点"
        )

    # --------------------------------------------------------
    # 5. 分离专线 / 备用
    # --------------------------------------------------------

    passed_dedicated = [
        item
        for item in passed
        if item["type"] == "dedicated"
    ]

    passed_backup = [
        item
        for item in passed
        if item["type"] == "backup"
    ]

    # --------------------------------------------------------
    # 6. 备用每地区最多 2 个
    # --------------------------------------------------------

    passed_backup = limit_backup(
        passed_backup
    )

    # --------------------------------------------------------
    # 7. 最终命名
    # --------------------------------------------------------

    final_proxies = rename_nodes(
        passed_dedicated,
        passed_backup
    )

    # --------------------------------------------------------
    # 8. 生成全新的 cleanvip.yaml
    # --------------------------------------------------------

    save_yaml(
        final_proxies
    )

    log("")
    log("=" * 60)
    log("CleanVIP 执行完成")
    log("=" * 60)


if __name__ == "__main__":
    main()
