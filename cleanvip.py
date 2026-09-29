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
# VIP Gist → 筛选 → 高级节点测速 → 保留 → ISO命名 → cleanvip.yaml
# ============================================================

GIST_URL = (
    "https://gist.githubusercontent.com/"
    "rongzhijie7/76ce5d8efc7e0f92cda3b59a82536532/raw/VIP"
)

OUTPUT_FILE = "cleanvip.yaml"

MIHOMO_VERSION = "v1.19.31"

# 高级节点测速目标
TEST_URL = "https://www.baidu.com/"

# Mihomo delay timeout，单位毫秒
TEST_TIMEOUT = 5000

# 每个地区最多保留 2 个高级节点
MAX_BACKUP_PER_REGION = 2


# ============================================================
# 地区 → ISO 3166-1 alpha-2
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


def log(text):
    print(text, flush=True)


# ============================================================
# 1. 获取 VIP Gist
# ============================================================

def get_vip():

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

    log(
        f"Gist HTTP 状态: "
        f"{response.status_code}"
    )

    response.raise_for_status()

    return response.text


# ============================================================
# 2. 解析节点
# ============================================================

def parse_nodes(content):

    log("=" * 60)
    log("2. 解析 VIP 节点")
    log("=" * 60)

    try:
        data = yaml.safe_load(content)

    except yaml.YAMLError as e:

        raise RuntimeError(
            f"YAML 解析失败: {e}"
        )

    if not isinstance(data, dict):

        raise RuntimeError(
            "VIP Gist 格式错误"
        )

    proxies = data.get("proxies")

    if not isinstance(proxies, list):

        raise RuntimeError(
            "VIP Gist 中没有 proxies"
        )

    nodes = []

    for proxy in proxies:

        if not isinstance(proxy, dict):
            continue

        if not proxy.get("name"):
            continue

        nodes.append(proxy)

    log(
        f"原始节点数量: {len(nodes)}"
    )

    return nodes


# ============================================================
# 3. 识别地区
# ============================================================

def get_region(name):

    for keyword in sorted(
        REGIONS,
        key=len,
        reverse=True
    ):

        if keyword.lower() in name.lower():

            return REGIONS[keyword]

    return None


# ============================================================
# 4. 第一次筛选
#
# 实验性 = 专线
# 高级   = 备用
# ============================================================

def filter_nodes(nodes):

    log("=" * 60)
    log("3. 筛选节点")
    log("=" * 60)

    dedicated_by_region = defaultdict(list)
    backup_by_region = defaultdict(list)

    ignored_region = 0
    ignored_keyword = 0

    for node in nodes:

        name = str(
            node.get("name", "")
        )

        region = get_region(name)

        if region is None:

            ignored_region += 1
            continue

        # 实验性 = 专线
        if "实验性" in name:

            dedicated_by_region[
                region
            ].append(node)

            continue

        # 高级 = 备用
        if "高级" in name:

            backup_by_region[
                region
            ].append(node)

            continue

        ignored_keyword += 1

    log(
        "专线地区数量: "
        f"{len(dedicated_by_region)}"
    )

    log(
        "备用候选地区数量: "
        f"{len(backup_by_region)}"
    )

    log(
        f"地区不匹配: {ignored_region}"
    )

    log(
        f"关键词不匹配: {ignored_keyword}"
    )

    return (
        dedicated_by_region,
        backup_by_region
    )


# ============================================================
# 5. 实验性节点
#
# 每个地区只取 1 条
# 不测速
# ============================================================

def select_dedicated(
    dedicated_by_region
):

    log("=" * 60)
    log("4. 选择实验性专线")
    log("=" * 60)

    selected = []

    for region in sorted(
        dedicated_by_region
    ):

        nodes = dedicated_by_region[
            region
        ]

        # 正常情况下每个地区只有一条。
        # 如果 Gist 将来出现多条，只取第一条。
        node = nodes[0]

        selected.append({
            "node": dict(node),
            "region": region,
            "type": "dedicated",
            "delay": None
        })

        log(
            f"{region}: "
            f"{node['name']} → 保留"
        )

        if len(nodes) > 1:

            log(
                f"{region}: "
                f"发现 {len(nodes)} 条实验性节点，"
                "按规则只取 1 条，不测速"
            )

    return selected


# ============================================================
# 6. 下载 Mihomo
# ============================================================

def download_mihomo():

    binary = "./mihomo"

    if os.path.exists(binary):

        os.chmod(
            binary,
            0o755
        )

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

    os.remove(
        gz_file
    )

    os.chmod(
        binary,
        0o755
    )

    log(
        "Mihomo 下载完成"
    )

    return binary


# ============================================================
# 7. 启动 Mihomo
# ============================================================

def start_mihomo(
    binary,
    nodes
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

        "proxies": nodes,

        "proxy-groups": [
            {
                "name": "TEST",
                "type": "select",
                "proxies": [
                    node["name"]
                    for node in nodes
                ]
            }
        ],

        "rules": [
            "MATCH,TEST"
        ]
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
        stderr=subprocess.PIPE,
        text=True
    )

    log(
        "等待 Mihomo 启动..."
    )

    for _ in range(30):

        try:

            response = requests.get(
                "http://127.0.0.1:9090",
                timeout=1
            )

            if response.status_code < 500:

                log(
                    "Mihomo 已启动"
                )

                return process

        except requests.RequestException:

            pass

        time.sleep(1)

    try:

        process.terminate()

        error = process.communicate(
            timeout=5
        )[1]

    except Exception:

        process.kill()

        error = ""

    if error:

        log(
            "Mihomo 错误:"
        )

        log(
            error[-3000:]
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

        except Exception:

            pass


# ============================================================
# 9. 测试一个高级节点
# ============================================================

def test_node(name):

    encoded = requests.utils.quote(
        name,
        safe=""
    )

    url = (
        "http://127.0.0.1:9090/proxies/"
        + encoded
        + "/delay"
    )

    try:

        response = requests.get(
            url,
            params={
                "url": TEST_URL,
                "timeout": TEST_TIMEOUT
            },
            timeout=10
        )

        if response.status_code != 200:

            log(
                f"[失败] {name} "
                f"HTTP {response.status_code}"
            )

            return None

        try:

            data = response.json()

        except ValueError:

            log(
                f"[失败] {name} "
                "返回内容不是 JSON"
            )

            return None

        delay = data.get(
            "delay"
        )

        if delay is None:

            log(
                f"[失败] {name}: "
                f"{data}"
            )

            return None

        delay = int(delay)

        log(
            f"[通过] {name} "
            f"→ {delay} ms"
        )

        return delay

    except requests.Timeout:

        log(
            f"[超时] {name}"
        )

        return None

    except Exception as e:

        log(
            f"[失败] {name}: {e}"
        )

        return None


# ============================================================
# 10. 测试高级节点
# ============================================================

def test_backups(
    backup_by_region
):

    log("=" * 60)
    log("5. 测试高级备用节点")
    log("=" * 60)

    candidates = []

    # 临时名称，避免原始名称重复
    index = 0

    for region in sorted(
        backup_by_region
    ):

        for node in backup_by_region[
            region
        ]:

            index += 1

            test_name = (
                f"__VIP_BACKUP_{index:04d}__"
            )

            proxy = dict(node)

            proxy["name"] = test_name

            candidates.append({
                "node": proxy,
                "original_name": node["name"],
                "region": region,
                "type": "backup",
                "test_name": test_name
            })

    if not candidates:

        log(
            "没有高级备用节点需要测速"
        )

        return []

    mihomo = download_mihomo()

    process = None

    passed = []

    try:

        process = start_mihomo(
            mihomo,
            [
                item["node"]
                for item in candidates
            ]
        )

        for item in candidates:

            delay = test_node(
                item["test_name"]
            )

            if delay is None:

                continue

            item["delay"] = delay

            passed.append(
                item
            )

    finally:

        stop_mihomo(
            process
        )

    log("")
    log(
        f"高级节点测速通过: "
        f"{len(passed)} / "
        f"{len(candidates)}"
    )

    return passed


# ============================================================
# 11. 每地区保留最快 2 个高级节点
# ============================================================

def select_backups(
    passed
):

    log("=" * 60)
    log("6. 选择高级备用节点")
    log("=" * 60)

    grouped = defaultdict(list)

    for item in passed:

        grouped[
            item["region"]
        ].append(item)

    selected = []

    for region in sorted(
        grouped
    ):

        nodes = grouped[
            region
        ]

        nodes.sort(
            key=lambda x: x["delay"]
        )

        keep = nodes[
            :MAX_BACKUP_PER_REGION
        ]

        selected.extend(
            keep
        )

        log(
            f"{region}: "
            f"测速通过 {len(nodes)} "
            f"→ 保留 {len(keep)}"
        )

    return selected


# ============================================================
# 12. 最终命名
# ============================================================

def rename_nodes(
    dedicated,
    backups
):

    log("=" * 60)
    log("7. 最终节点命名")
    log("=" * 60)

    counters = defaultdict(int)

    final = []

    # --------------------------------------------------------
    # 专线
    # --------------------------------------------------------

    for item in dedicated:

        region = item["region"]

        key = (
            region + "专线"
        )

        counters[key] += 1

        name = (
            key
            + f"{counters[key]:02d}"
        )

        node = dict(
            item["node"]
        )

        node["name"] = name

        final.append(
            node
        )

        log(
            f"{item['node']['name']} "
            f"→ {name}"
        )

    # --------------------------------------------------------
    # 备用
    # --------------------------------------------------------

    for item in backups:

        region = item["region"]

        key = (
            region + "备用"
        )

        counters[key] += 1

        name = (
            key
            + f"{counters[key]:02d}"
        )

        # 测速时用了临时名称，
        # 这里恢复原始节点配置后再命名。
        node = dict(
            item["node"]
        )

        node["name"] = name

        # item["node"] 里的 name 是临时名称，
        # 这里只改变 name，其他字段全部保留。
        final.append(
            node
        )

        log(
            f"{item['original_name']} "
            f"→ {name} "
            f"({item['delay']} ms)"
        )

    return final


# ============================================================
# 13. 保存 cleanvip.yaml
# ============================================================

def save_output(nodes):

    log("=" * 60)
    log("8. 生成 cleanvip.yaml")
    log("=" * 60)

    output = {
        "proxies": nodes
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
            sort_keys=False,
            default_flow_style=False
        )

    log(
        f"最终节点数量: {len(nodes)}"
    )

    log(
        f"已生成: {OUTPUT_FILE}"
    )


# ============================================================
# 主程序
# ============================================================

def main():

    log("")
    log("=" * 60)
    log("CleanVIP")
    log(
        "VIP Gist → 筛选 → "
        "高级测速 → 保留 → ISO命名"
    )
    log("=" * 60)
    log("")

    # --------------------------------------------------------
    # 1. 只从 VIP Gist 读取
    # --------------------------------------------------------

    content = get_vip()

    # --------------------------------------------------------
    # 2. 解析
    # --------------------------------------------------------

    nodes = parse_nodes(
        content
    )

    # --------------------------------------------------------
    # 3. 筛选
    # --------------------------------------------------------

    (
        dedicated_by_region,
        backup_by_region
    ) = filter_nodes(
        nodes
    )

    # --------------------------------------------------------
    # 4. 实验性：
    # 每地区只取一条，不测速
    # --------------------------------------------------------

    dedicated = select_dedicated(
        dedicated_by_region
    )

    # --------------------------------------------------------
    # 5. 高级：
    # 测速
    # --------------------------------------------------------

    passed_backup = test_backups(
        backup_by_region
    )

    # --------------------------------------------------------
    # 6. 高级：
    # 每地区最快 2 条
    # --------------------------------------------------------

    backups = select_backups(
        passed_backup
    )

    # --------------------------------------------------------
    # 7. 最后统一命名
    # --------------------------------------------------------

    final_nodes = rename_nodes(
        dedicated,
        backups
    )

    if not final_nodes:

        raise RuntimeError(
            "最终没有可用节点"
        )

    # --------------------------------------------------------
    # 8. 输出
    # --------------------------------------------------------

    save_output(
        final_nodes
    )

    log("")
    log("=" * 60)
    log("CleanVIP 执行完成")
    log("=" * 60)


if __name__ == "__main__":
    main()
