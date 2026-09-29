import copy
import gzip
import os
import shutil
import subprocess
import time
from collections import defaultdict

import requests
import yaml


# ============================================================
# 基本配置
# ============================================================

GIST_URL = (
    "https://gist.githubusercontent.com/rongzhijie7/"
    "76ce5d8efc7e0f92cda3b59a82536532/raw/VIP"
)

OUTPUT_FILE = "cleanvip.yaml"

MIHOMO_VERSION = "v1.19.31"

# 用百度进行连通性/延迟测试
TEST_URL = "https://www.baidu.com/"
TEST_TIMEOUT = 5000

# 高级：每个地区最多保留 2 条
MAX_BACKUP_PER_REGION = 2

# PR：每个地区最多保留 2 条
MAX_RELAY_PER_REGION = 2


# ============================================================
# 只允许这 6 个地区
# ISO 3166-1 alpha-2
# ============================================================

REGIONS = {
    "香港": "HK",
    "🇭🇰": "HK",

    "日本": "JP",
    "🇯🇵": "JP",

    "韩国": "KR",
    "韓國": "KR",
    "🇰🇷": "KR",

    "新加坡": "SG",
    "狮城": "SG",
    "獅城": "SG",
    "🇸🇬": "SG",

    "美国": "US",
    "美國": "US",
    "🇺🇸": "US",

    "英国": "GB",
    "英國": "GB",
    "🇬🇧": "GB",
}


# ============================================================
# 日志
# ============================================================

def log(text):
    print(text, flush=True)


# ============================================================
# 获取 VIP Gist
# ============================================================

def get_vip():
    log("=" * 60)
    log("获取 VIP Gist")
    log("=" * 60)

    headers = {
        "User-Agent": "Mozilla/5.0"
    }

    response = requests.get(
        GIST_URL,
        headers=headers,
        timeout=30
    )

    response.raise_for_status()

    log(f"Gist 状态: {response.status_code}")
    log(f"内容大小: {len(response.text)}")

    return response.text


# ============================================================
# 解析节点
# ============================================================

def parse_nodes(content):
    data = yaml.safe_load(content)

    if not isinstance(data, dict):
        raise ValueError("Gist YAML 格式错误")

    proxies = data.get("proxies")

    if not isinstance(proxies, list):
        raise ValueError("Gist 中没有找到 proxies")

    nodes = []

    for proxy in proxies:
        if not isinstance(proxy, dict):
            continue

        if not proxy.get("name"):
            continue

        nodes.append(proxy)

    log(f"原始节点数量: {len(nodes)}")

    return nodes


# ============================================================
# 判断地区
# ============================================================

def get_region(name):
    name_lower = name.lower()

    # 长关键词优先
    keywords = sorted(
        REGIONS.items(),
        key=lambda x: len(x[0]),
        reverse=True
    )

    for keyword, region in keywords:
        if keyword.lower() in name_lower:
            return region

    return None


# ============================================================
# 判断节点类型
#
# 实验性 = 专线
# 高级   = 备用
# PR     = 中转
# ============================================================

def get_node_type(name):
    name_lower = name.lower()

    if "实验性" in name:
        return "dedicated"

    if "高级" in name:
        return "backup"

    if "pr" in name_lower:
        return "relay"

    return None


# ============================================================
# 分类节点
# ============================================================

def filter_nodes(nodes):

    dedicated = defaultdict(list)
    backup = defaultdict(list)
    relay = defaultdict(list)

    ignored_region = 0
    ignored_keyword = 0

    for node in nodes:

        name = str(node.get("name", ""))

        region = get_region(name)

        if not region:
            ignored_region += 1
            continue

        node_type = get_node_type(name)

        if node_type == "dedicated":
            dedicated[region].append(node)

        elif node_type == "backup":
            backup[region].append(node)

        elif node_type == "relay":
            relay[region].append(node)

        else:
            ignored_keyword += 1

    log("")
    log("=" * 60)
    log("节点分类")
    log("=" * 60)

    log(f"实验性节点: {sum(len(v) for v in dedicated.values())}")
    log(f"高级节点:   {sum(len(v) for v in backup.values())}")
    log(f"PR节点:      {sum(len(v) for v in relay.values())}")
    log(f"地区不匹配:  {ignored_region}")
    log(f"关键词不匹配: {ignored_keyword}")

    return dedicated, backup, relay


# ============================================================
# 实验性节点
#
# 每个地区只保留 1 条
# 不测速
# ============================================================

def select_dedicated(dedicated):

    selected = []

    log("")
    log("=" * 60)
    log("处理实验性节点 → 专线")
    log("=" * 60)

    for region in ["HK", "JP", "KR", "SG", "US", "GB"]:

        nodes = dedicated.get(region, [])

        if not nodes:
            log(f"{region}: 没有实验性节点")
            continue

        node = copy.deepcopy(nodes[0])

        selected.append({
            "node": node,
            "region": region,
            "delay": None,
        })

        log(
            f"{region}: 保留 {node.get('name')} "
            f"(不测速)"
        )

    return selected


# ============================================================
# 下载 Mihomo
# ============================================================

def download_mihomo():

    binary = "./mihomo"

    if os.path.exists(binary):
        log("发现已有 Mihomo，直接使用")
        return binary

    log("")
    log("=" * 60)
    log("下载 Mihomo")
    log("=" * 60)

    filename = (
        f"mihomo-linux-amd64-v3-{MIHOMO_VERSION}.gz"
    )

    url = (
        f"https://github.com/MetaCubeX/mihomo/releases/"
        f"download/{MIHOMO_VERSION}/{filename}"
    )

    gz_file = "mihomo.gz"

    log(f"下载: {url}")

    response = requests.get(
        url,
        timeout=60
    )

    response.raise_for_status()

    with open(gz_file, "wb") as f:
        f.write(response.content)

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

def start_mihomo(binary, nodes):

    workdir = ".mihomo_test"

    if os.path.exists(workdir):
        shutil.rmtree(workdir)

    os.makedirs(workdir)

    config_file = os.path.join(
        workdir,
        "config.yaml"
    )

    proxies = []

    for node in nodes:
        proxy = copy.deepcopy(node)

        proxies.append(proxy)

    proxy_names = [
        str(proxy["name"])
        for proxy in proxies
    ]

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
                "proxies": proxy_names,
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

    log("启动 Mihomo...")

    process = subprocess.Popen(
        [
            binary,
            "-d",
            workdir,
            "-f",
            config_file,
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        text=True,
    )

    controller = "http://127.0.0.1:9090"

    for _ in range(30):

        if process.poll() is not None:
            stderr = process.stderr.read()

            log("Mihomo 启动失败:")
            log(stderr[-3000:])

            raise RuntimeError(
                "Mihomo 启动失败"
            )

        try:
            response = requests.get(
                controller,
                timeout=2
            )

            if response.status_code == 200:
                log("Mihomo 已启动")
                return process

        except Exception:
            pass

        time.sleep(1)

    process.terminate()

    raise RuntimeError(
        "Mihomo 启动超时"
    )


# ============================================================
# 停止 Mihomo
# ============================================================

def stop_mihomo(process):

    if not process:
        return

    try:
        process.terminate()
        process.wait(timeout=5)

    except Exception:

        try:
            process.kill()
        except Exception:
            pass


# ============================================================
# 测试单个节点
#
# 正确 API：
# /proxies/{name}/delay
# ============================================================

def test_node(name):

    encoded_name = requests.utils.quote(
        name,
        safe=""
    )

    url = (
        "http://127.0.0.1:9090/proxies/"
        + encoded_name
        + "/delay"
    )

    try:

        response = requests.get(
            url,
            params={
                "url": TEST_URL,
                "timeout": TEST_TIMEOUT,
            },
            timeout=10,
        )

        if response.status_code != 200:
            return None

        data = response.json()

        delay = data.get("delay")

        if delay is None:
            return None

        delay = int(delay)

        if delay <= 0:
            return None

        return delay

    except Exception:
        return None


# ============================================================
# 测试节点
#
# 高级 + PR 一起测速
# ============================================================

def test_nodes(backup, relay):

    all_candidates = []

    # --------------------------------------------------------
    # 高级节点
    # --------------------------------------------------------

    for region, nodes in backup.items():

        for node in nodes:

            all_candidates.append({
                "node": copy.deepcopy(node),
                "region": region,
                "type": "backup",
            })

    # --------------------------------------------------------
    # PR 节点
    # --------------------------------------------------------

    for region, nodes in relay.items():

        for node in nodes:

            all_candidates.append({
                "node": copy.deepcopy(node),
                "region": region,
                "type": "relay",
            })

    if not all_candidates:
        log("")
        log("没有需要测速的高级/PR节点")
        return []

    log("")
    log("=" * 60)
    log("开始测试高级 + PR 节点")
    log("=" * 60)

    # --------------------------------------------------------
    # 给 Mihomo 使用临时唯一名称
    # --------------------------------------------------------

    test_nodes_list = []

    for index, item in enumerate(
        all_candidates,
        start=1
    ):

        original_name = item["node"]["name"]

        temporary_name = (
            f"__VIP_TEST_{index:04d}__"
        )

        item["original_name"] = original_name
        item["test_name"] = temporary_name

        item["node"]["name"] = temporary_name

        test_nodes_list.append(
            item["node"]
        )

    binary = download_mihomo()

    process = None

    passed = []

    try:

        process = start_mihomo(
            binary,
            test_nodes_list
        )

        for index, item in enumerate(
            all_candidates,
            start=1
        ):

            region = item["region"]
            node_type = item["type"]
            original_name = item["original_name"]
            test_name = item["test_name"]

            delay = test_node(test_name)

            type_text = (
                "备用"
                if node_type == "backup"
                else "中转"
            )

            if delay is not None:

                item["delay"] = delay

                passed.append(item)

                log(
                    f"[通过] {index:02d} "
                    f"{region} "
                    f"{type_text} "
                    f"{original_name} "
                    f"{delay}ms"
                )

            else:

                log(
                    f"[失败] {index:02d} "
                    f"{region} "
                    f"{type_text} "
                    f"{original_name}"
                )

    finally:

        stop_mihomo(process)

    return passed


# ============================================================
# 选择高级节点
#
# 每个地区：
# 测速通过 → 按延迟排序 → 最快 2 条
# ============================================================

def select_backups(passed):

    grouped = defaultdict(list)

    for item in passed:

        if item["type"] == "backup":
            grouped[item["region"]].append(item)

    selected = []

    log("")
    log("=" * 60)
    log("筛选高级节点 → 备用")
    log("=" * 60)

    for region in [
        "HK",
        "JP",
        "KR",
        "SG",
        "US",
        "GB",
    ]:

        nodes = grouped.get(region, [])

        nodes.sort(
            key=lambda x: x["delay"]
        )

        nodes = nodes[
            :MAX_BACKUP_PER_REGION
        ]

        selected.extend(nodes)

        if nodes:

            log(
                f"{region}: 保留 {len(nodes)} 条"
            )

            for item in nodes:

                log(
                    f"  {item['original_name']} "
                    f"{item['delay']}ms"
                )

        else:

            log(
                f"{region}: 没有可用备用节点"
            )

    return selected


# ============================================================
# 选择 PR 节点
#
# 每个地区：
# 测速通过 → 按延迟排序 → 最快 2 条
# ============================================================

def select_relays(passed):

    grouped = defaultdict(list)

    for item in passed:

        if item["type"] == "relay":
            grouped[item["region"]].append(item)

    selected = []

    log("")
    log("=" * 60)
    log("筛选 PR 节点 → 中转")
    log("=" * 60)

    for region in [
        "HK",
        "JP",
        "KR",
        "SG",
        "US",
        "GB",
    ]:

        nodes = grouped.get(region, [])

        nodes.sort(
            key=lambda x: x["delay"]
        )

        nodes = nodes[
            :MAX_RELAY_PER_REGION
        ]

        selected.extend(nodes)

        if nodes:

            log(
                f"{region}: 保留 {len(nodes)} 条"
            )

            for item in nodes:

                log(
                    f"  {item['original_name']} "
                    f"{item['delay']}ms"
                )

        else:

            log(
                f"{region}: 没有可用中转节点"
            )

    return selected


# ============================================================
# 最终重命名
# ============================================================

def rename_nodes(
    dedicated,
    backups,
    relays
):

    final_nodes = []

    # --------------------------------------------------------
    # 实验性 → 专线
    # --------------------------------------------------------

    dedicated_count = defaultdict(int)

    for item in dedicated:

        region = item["region"]

        dedicated_count[region] += 1

        node = copy.deepcopy(
            item["node"]
        )

        node["name"] = (
            f"{region}专线"
            f"{dedicated_count[region]:02d}"
        )

        final_nodes.append(node)

    # --------------------------------------------------------
    # 高级 → 备用
    # --------------------------------------------------------

    backup_count = defaultdict(int)

    for item in backups:

        region = item["region"]

        backup_count[region] += 1

        node = copy.deepcopy(
            item["node"]
        )

        node["name"] = (
            f"{region}备用"
            f"{backup_count[region]:02d}"
        )

        final_nodes.append(node)

    # --------------------------------------------------------
    # PR → 中转
    # --------------------------------------------------------

    relay_count = defaultdict(int)

    for item in relays:

        region = item["region"]

        relay_count[region] += 1

        node = copy.deepcopy(
            item["node"]
        )

        node["name"] = (
            f"{region}中转"
            f"{relay_count[region]:02d}"
        )

        final_nodes.append(node)

    return final_nodes


# ============================================================
# 保存 cleanvip.yaml
# ============================================================

def save_output(nodes):

    data = {
        "proxies": nodes
    }

    with open(
        OUTPUT_FILE,
        "w",
        encoding="utf-8"
    ) as f:

        yaml.safe_dump(
            data,
            f,
            allow_unicode=True,
            sort_keys=False
        )

    log("")
    log("=" * 60)
    log("生成完成")
    log("=" * 60)

    log(
        f"最终节点数量: {len(nodes)}"
    )

    log(
        f"输出文件: {OUTPUT_FILE}"
    )


# ============================================================
# 主程序
# ============================================================

def main():

    # --------------------------------------------------------
    # 1. 获取 VIP
    # --------------------------------------------------------

    content = get_vip()

    # --------------------------------------------------------
    # 2. 解析
    # --------------------------------------------------------

    nodes = parse_nodes(content)

    # --------------------------------------------------------
    # 3. 分类
    # --------------------------------------------------------

    dedicated, backup, relay = filter_nodes(
        nodes
    )

    # --------------------------------------------------------
    # 4. 实验性 → 专线
    #    不测速
    # --------------------------------------------------------

    selected_dedicated = select_dedicated(
        dedicated
    )

    # --------------------------------------------------------
    # 5. 高级 + PR → 一起测速
    # --------------------------------------------------------

    passed = test_nodes(
        backup,
        relay
    )

    # --------------------------------------------------------
    # 6. 高级 → 备用
    # --------------------------------------------------------

    selected_backups = select_backups(
        passed
    )

    # --------------------------------------------------------
    # 7. PR → 中转
    # --------------------------------------------------------

    selected_relays = select_relays(
        passed
    )

    # --------------------------------------------------------
    # 8. 最终重命名
    # --------------------------------------------------------

    final_nodes = rename_nodes(
        selected_dedicated,
        selected_backups,
        selected_relays
    )

    # --------------------------------------------------------
    # 9. 保存
    # --------------------------------------------------------

    save_output(
        final_nodes
    )


if __name__ == "__main__":
    main()
