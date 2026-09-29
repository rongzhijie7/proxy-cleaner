import gzip
import os
import shutil
import subprocess
import time
from collections import defaultdict

import requests
import yaml


# ============================================================
# CleanVIP
# VIP Gist → 筛选 → 测速 → ISO命名 → cleanvip.yaml
# ============================================================

GIST_URL = (
    "https://gist.githubusercontent.com/"
    "rongzhijie7/76ce5d8efc7e0f92cda3b59a82536532/raw/VIP"
)

OUTPUT_FILE = "cleanvip.yaml"

MIHOMO_VERSION = "v1.19.31"

# YouTube 测速地址
TEST_URL = "https://www.youtube.com/generate_204"

# Mihomo delay API 超时时间，单位毫秒
TEST_TIMEOUT = 5000

# 高级节点每个地区最多保留 2 个
MAX_BACKUP_PER_REGION = 2


# ============================================================
# ISO 3166-1 alpha-2 地区
# ============================================================

REGIONS = {
    "香港": "HK",
    "🇭🇰": "HK",

    "台湾": "TW",
    "台灣": "TW",
    "🇹🇼": "TW",

    "中国台湾": "TW",
    "中國台灣": "TW",

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


def log(message):
    print(message, flush=True)


# ============================================================
# 1. 获取 VIP Gist
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

    try:
        data = yaml.safe_load(content)

    except yaml.YAMLError as e:
        raise RuntimeError(
            f"VIP Gist YAML 解析失败: {e}"
        )

    if not isinstance(data, dict):
        raise RuntimeError(
            "VIP Gist 不是有效的 YAML 配置"
        )

    proxies = data.get("proxies")

    if not isinstance(proxies, list):
        raise RuntimeError(
            "VIP Gist 中没有有效的 proxies"
        )

    valid = []

    for proxy in proxies:

        if not isinstance(proxy, dict):
            continue

        if not proxy.get("name"):
            continue

        valid.append(proxy)

    log(f"原始节点数量: {len(valid)}")

    return valid


# ============================================================
# 3. 地区识别
# ============================================================

def detect_region(name):

    for keyword in sorted(
        REGIONS.keys(),
        key=len,
        reverse=True
    ):

        if keyword.lower() in name.lower():
            return REGIONS[keyword]

    return None


# ============================================================
# 4. 类型识别
#
# 实验性 = 专线
# 高级   = 备用
# ============================================================

def detect_type(name):

    if "实验性" in name:
        return "dedicated"

    if "高级" in name:
        return "backup"

    return None


# ============================================================
# 5. 筛选节点
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

        original_name = str(
            proxy.get("name", "")
        )

        # 先识别地区
        region = detect_region(
            original_name
        )

        if region is None:

            ignored_region += 1

            continue

        # 再识别类型
        node_type = detect_type(
            original_name
        )

        if node_type is None:

            ignored_keyword += 1

            continue

        item = {
            "proxy": dict(proxy),
            "region": region,
            "type": node_type,
            "original_name": original_name,
        }

        if node_type == "dedicated":

            dedicated.append(item)

        else:

            backup.append(item)

    log(
        f"专线候选: {len(dedicated)}"
    )

    log(
        f"备用候选: {len(backup)}"
    )

    log(
        f"地区不匹配: {ignored_region}"
    )

    log(
        f"关键词不匹配: {ignored_keyword}"
    )

    return dedicated, backup


# ============================================================
# 6. 下载 Mihomo
# ============================================================

def download_mihomo():

    binary = "./mihomo"

    if os.path.isfile(binary):

        os.chmod(binary, 0o755)

        log("使用已有 Mihomo")

        return binary

    log("=" * 60)
    log("下载 Mihomo")
    log("=" * 60)

    url = (
        "https://github.com/MetaCubeX/mihomo/releases/download/"
        f"{MIHOMO_VERSION}/"
        f"mihomo-linux-amd64-v3-{MIHOMO_VERSION}.gz"
    )

    log(f"下载地址: {url}")

    response = requests.get(
        url,
        timeout=60,
        stream=True,
        headers={
            "User-Agent": "Mozilla/5.0"
        }
    )

    response.raise_for_status()

    gz_file = "mihomo.gz"

    with open(
        gz_file,
        "wb"
    ) as f:

        for chunk in response.iter_content(
            chunk_size=65536
        ):

            if chunk:
                f.write(chunk)

    with gzip.open(
        gz_file,
        "rb"
    ) as source:

        with open(
            binary,
            "wb"
        ) as target:

            shutil.copyfileobj(
                source,
                target
            )

    os.chmod(
        binary,
        0o755
    )

    os.remove(
        gz_file
    )

    log("Mihomo 下载完成")

    return binary


# ============================================================
# 7. 启动 Mihomo
# ============================================================

def start_mihomo(
    binary,
    proxies
):

    workdir = os.path.abspath(
        ".mihomo_test"
    )

    os.makedirs(
        workdir,
        exist_ok=True
    )

    config_file = os.path.join(
        workdir,
        "config.yaml"
    )

    config = {

        "mixed-port": 7890,

        "allow-lan": False,

        "mode": "rule",

        "log-level": "error",

        "external-controller":
            "127.0.0.1:9090",

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
            sort_keys=False,
            default_flow_style=False
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
        stderr=subprocess.PIPE,
        text=True
    )

    log("等待 Mihomo 启动...")

    controller = (
        "http://127.0.0.1:9090"
    )

    for _ in range(30):

        try:

            response = requests.get(
                controller,
                timeout=1
            )

            if response.status_code < 500:

                log("Mihomo 已启动")

                return process

        except requests.RequestException:

            pass

        time.sleep(1)

    # 启动失败，读取错误
    try:

        process.terminate()

        stderr = process.communicate(
            timeout=5
        )[1]

    except Exception:

        process.kill()

        stderr = ""

    if stderr:

        log("Mihomo 错误:")

        log(
            stderr[-5000:]
        )

    raise RuntimeError(
        "Mihomo 启动失败"
    )


# ============================================================
# 8. 停止 Mihomo
# ============================================================

def stop_mihomo(process):

    if process is None:
        return

    if process.poll() is not None:
        return

    try:

        process.terminate()

        process.wait(
            timeout=5
        )

    except Exception:

        try:

            process.kill()

            process.wait(
                timeout=3
            )

        except Exception:

            pass


# ============================================================
# 9. Mihomo 节点测速
#
# 正确 API：
#
# /proxies/{节点名称}/delay
#
# 而不是：
#
# /proxies/{节点名称}
# ============================================================

def test_proxy(name):

    encoded_name = requests.utils.quote(
        name,
        safe=""
    )

    api_url = (
        "http://127.0.0.1:9090/proxies/"
        + encoded_name
        + "/delay"
    )

    try:

        response = requests.get(
            api_url,
            params={
                "url": TEST_URL,
                "timeout": TEST_TIMEOUT
            },
            timeout=10
        )

        if response.status_code != 200:

            log(
                f"[API错误] {name} "
                f"HTTP {response.status_code}: "
                f"{response.text[:500]}"
            )

            return None

        try:

            data = response.json()

        except ValueError:

            log(
                f"[API错误] {name}: "
                "返回内容不是 JSON"
            )

            return None

        delay = data.get(
            "delay"
        )

        if delay is None:

            log(
                f"[测速失败] {name}: "
                f"{data}"
            )

            return None

        try:

            delay = int(delay)

        except (
            TypeError,
            ValueError
        ):

            log(
                f"[测速失败] {name}: "
                f"delay={delay}"
            )

            return None

        return delay

    except requests.Timeout:

        log(
            f"[超时] {name}"
        )

        return None

    except requests.RequestException as e:

        log(
            f"[网络错误] {name}: {e}"
        )

        return None

    except Exception as e:

        log(
            f"[异常] {name}: {e}"
        )

        return None


# ============================================================
# 10. 批量测速
# ============================================================

def speed_test(nodes):

    if not nodes:

        return []

    log("=" * 60)
    log("4. 开始测速")
    log("=" * 60)

    mihomo = download_mihomo()

    test_proxies = []

    # 给测速节点临时命名
    # 防止 VIP Gist 中原始名称重复
    for index, item in enumerate(nodes):

        proxy = dict(
            item["proxy"]
        )

        test_name = (
            f"__VIP_TEST_{index + 1:04d}__"
        )

        proxy["name"] = test_name

        item["test_name"] = test_name

        test_proxies.append(
            proxy
        )

    process = None

    passed = []

    try:

        process = start_mihomo(
            mihomo,
            test_proxies
        )

        for item in nodes:

            original_name = (
                item["original_name"]
            )

            test_name = (
                item["test_name"]
            )

            delay = test_proxy(
                test_name
            )

            if delay is None:

                log(
                    f"[失败] {original_name}"
                )

                continue

            item["delay"] = delay

            passed.append(
                item
            )

            log(
                f"[通过] {original_name} "
                f"→ {delay} ms"
            )

    finally:

        stop_mihomo(
            process
        )

    log(
        f"测速通过: "
        f"{len(passed)} / "
        f"{len(nodes)}"
    )

    return passed


# ============================================================
# 11. 备用节点筛选
#
# 每个地区最多保留最快的 2 个
# ============================================================

def select_backup(nodes):

    log("=" * 60)
    log("5. 筛选备用节点")
    log("=" * 60)

    grouped = defaultdict(list)

    for item in nodes:

        grouped[
            item["region"]
        ].append(item)

    selected = []

    for region in sorted(
        grouped.keys()
    ):

        items = grouped[
            region
        ]

        # 按测速延迟从低到高
        items.sort(
            key=lambda x: x["delay"]
        )

        keep = items[
            :MAX_BACKUP_PER_REGION
        ]

        selected.extend(
            keep
        )

        log(
            f"{region}: "
            f"测速通过 {len(items)} "
            f"→ 保留 {len(keep)}"
        )

    return selected


# ============================================================
# 12. 最终命名
#
# 专线：
# HK专线01
# HK专线02
#
# 备用：
# HK备用01
# HK备用02
#
# 注意：
# 最终名称不再使用中文地区名。
# ============================================================

def rename_nodes(
    dedicated,
    backup
):

    log("=" * 60)
    log("6. ISO 3166-1 alpha-2 节点命名")
    log("=" * 60)

    counters = defaultdict(int)

    final_proxies = []

    # --------------------------------------------------------
    # 专线
    # --------------------------------------------------------

    # 为了让每个地区内部编号稳定，
    # 按地区 + 延迟排序。
    dedicated.sort(
        key=lambda x: (
            x["region"],
            x["delay"]
        )
    )

    for item in dedicated:

        region = item["region"]

        key = (
            f"{region}专线"
        )

        counters[key] += 1

        new_name = (
            f"{key}"
            f"{counters[key]:02d}"
        )

        proxy = dict(
            item["proxy"]
        )

        proxy["name"] = new_name

        final_proxies.append(
            proxy
        )

        log(
            f"{item['original_name']} "
            f"→ {new_name} "
            f"({item['delay']} ms)"
        )

    # --------------------------------------------------------
    # 备用
    # --------------------------------------------------------

    backup.sort(
        key=lambda x: (
            x["region"],
            x["delay"]
        )
    )

    for item in backup:

        region = item["region"]

        key = (
            f"{region}备用"
        )

        counters[key] += 1

        new_name = (
            f"{key}"
            f"{counters[key]:02d}"
        )

        proxy = dict(
            item["proxy"]
        )

        proxy["name"] = new_name

        final_proxies.append(
            proxy
        )

        log(
            f"{item['original_name']} "
            f"→ {new_name} "
            f"({item['delay']} ms)"
        )

    return final_proxies


# ============================================================
# 13. 生成 cleanvip.yaml
# ============================================================

def save_yaml(proxies):

    log("=" * 60)
    log("7. 生成 cleanvip.yaml")
    log("=" * 60)

    output = {
        "proxies": proxies
    }

    # 直接覆盖旧文件。
    # 不读取旧 cleanvip.yaml。
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
        f"最终节点数量: "
        f"{len(proxies)}"
    )

    log(
        f"文件已生成: "
        f"{OUTPUT_FILE}"
    )


# ============================================================
# 14. 主程序
# ============================================================

def main():

    log("")
    log("=" * 60)
    log("CleanVIP")
    log(
        "VIP Gist → 筛选 → 测速 → "
        "ISO命名 → cleanvip.yaml"
    )
    log("=" * 60)
    log("")

    # ========================================================
    # 第一步：只从 VIP Gist 获取节点
    # ========================================================

    content = download_vip()

    # ========================================================
    # 第二步：解析 VIP Gist
    # ========================================================

    proxies = parse_vip(
        content
    )

    # ========================================================
    # 第三步：筛选
    #
    # 实验性 = 专线
    # 高级   = 备用
    # ========================================================

    dedicated, backup = filter_nodes(
        proxies
    )

    candidates = (
        dedicated + backup
    )

    if not candidates:

        raise RuntimeError(
            "筛选后没有符合条件的节点"
        )

    # ========================================================
    # 第四步：测速
    # ========================================================

    passed = speed_test(
        candidates
    )

    if not passed:

        raise RuntimeError(
            "测速后没有可用节点"
        )

    # ========================================================
    # 第五步：分离专线和备用
    # ========================================================

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

    log("")
    log(
        f"测速通过："
        f"专线 {len(passed_dedicated)}，"
        f"备用 {len(passed_backup)}"
    )

    # ========================================================
    # 第六步：备用每地区只留最快 2 个
    # ========================================================

    selected_backup = select_backup(
        passed_backup
    )

    # ========================================================
    # 第七步：测速完成后再改名字
    # ========================================================

    final_proxies = rename_nodes(
        passed_dedicated,
        selected_backup
    )

    # ========================================================
    # 第八步：覆盖生成 cleanvip.yaml
    # ========================================================

    save_yaml(
        final_proxies
    )

    log("")
    log("=" * 60)
    log("CleanVIP 执行完成")
    log("=" * 60)


# ============================================================
# 程序入口
# ============================================================

if __name__ == "__main__":
    main()
