import requests
import yaml

# ============================================================
# 筛选规则
# ============================================================

# 实验性 = 专线
DEDICATED_KEYWORDS = [
    "实验性",
]

# 高级 = 备用
BACKUP_KEYWORDS = [
    "高级",
]

# 只处理这些地区
# ISO 3166-1 alpha-2
REGIONS = {
    "香港": "HK",
    "台湾": "TW",
    "美国": "US",
    "新加坡": "SG",
    "日本": "JP",
    "英国": "GB",
    "韩国": "KR",
}

# 地区别名
REGION_ALIASES = {
    "香港": "香港",
    "🇭🇰": "香港",

    "台湾": "台湾",
    "台灣": "台湾",
    "🇹🇼": "台湾",

    "美国": "美国",
    "🇺🇸": "美国",

    "新加坡": "新加坡",
    "狮城": "新加坡",
    "🇸🇬": "新加坡",

    "日本": "日本",
    "🇯🇵": "日本",

    "英国": "英国",
    "英國": "英国",
    "🇬🇧": "英国",

    "韩国": "韩国",
    "韓國": "韩国",
    "🇰🇷": "韩国",
}

# ============================================================
# Gist
# ============================================================

GIST_ID = "76ce5d8efc7e0f92cda3b59a82536532"
GIST_FILE = "VIP"

GIST_API_URL = f"https://api.github.com/gists/{GIST_ID}"

GIST_RAW_URL = (
    f"https://gist.githubusercontent.com/"
    f"rongzhijie7/{GIST_ID}/raw/VIP"
)

OUTPUT_FILE = "cleanvip.yaml"


# ============================================================
# 获取 Gist
# ============================================================

def get_source():

    print("================================")
    print("获取 Gist")
    print("================================")

    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "github-actions-cleanvip",
    }

    try:

        response = requests.get(
            GIST_API_URL,
            headers=headers,
            timeout=30,
        )

        print("Gist API 状态:", response.status_code)

        if response.status_code == 200:

            data = response.json()

            files = data.get("files", {})

            print("Gist 文件:", list(files.keys()))

            if GIST_FILE in files:

                file_info = files[GIST_FILE]

                content = file_info.get("content")

                if content:

                    print("找到 VIP 文件")
                    print("内容大小:", len(content))

                    return content

                raw_url = file_info.get("raw_url")

                if raw_url:

                    print("使用 Gist raw_url")

                    r = requests.get(
                        raw_url,
                        timeout=30,
                    )

                    r.raise_for_status()

                    return r.text

    except Exception as e:

        print("Gist API 获取失败:", e)

    print("尝试 Gist Raw")

    response = requests.get(
        GIST_RAW_URL,
        timeout=30,
    )

    response.raise_for_status()

    print("Raw 获取成功")

    return response.text


# ============================================================
# 地区识别
# ============================================================

def get_region(name):

    for keyword, region in REGION_ALIASES.items():

        if keyword in name:

            return region

    return None


# ============================================================
# 节点类型
# ============================================================

def is_dedicated(name):

    return any(
        keyword in name
        for keyword in DEDICATED_KEYWORDS
    )


def is_backup(name):

    return any(
        keyword in name
        for keyword in BACKUP_KEYWORDS
    )


# ============================================================
# 主程序
# ============================================================

def main():

    content = get_source()

    config = yaml.safe_load(content)

    if not isinstance(config, dict):

        raise RuntimeError(
            "Gist 内容不是有效 YAML"
        )

    proxies = config.get("proxies", [])

    if not proxies:

        raise RuntimeError(
            "Gist 中没有找到 proxies"
        )

    print("")
    print("原始节点数量:", len(proxies))

    # ========================================================
    # 按地区分别保存
    # ========================================================

    dedicated = {}
    backup = {}

    # 初始化地区
    for region in REGIONS:

        dedicated[region] = []
        backup[region] = []

    # ========================================================
    # 筛选
    # ========================================================

    for proxy in proxies:

        name = str(
            proxy.get("name", "")
        ).strip()

        if not name:
            continue

        region = get_region(name)

        # 没识别出地区，直接丢弃
        if region is None:
            print("跳过（未知地区）:", name)
            continue

        # ----------------------------------------------------
        # 实验性 → 专线
        # ----------------------------------------------------

        if is_dedicated(name):

            dedicated[region].append(proxy)

            print(
                "专线:",
                name,
                "→",
                REGIONS[region] + "专线",
            )

            continue

        # ----------------------------------------------------
        # 高级 → 备用
        # ----------------------------------------------------

        if is_backup(name):

            backup[region].append(proxy)

            print(
                "备用:",
                name,
                "→",
                REGIONS[region] + "备用",
            )

            continue

        # ----------------------------------------------------
        # 其他类型全部丢弃
        # ----------------------------------------------------

        print("跳过:", name)

    # ========================================================
    # 生成最终节点
    # ========================================================

    final_proxies = []

    # ========================================================
    # 专线
    # 每个地区只保留一个
    # ========================================================

    for region, nodes in dedicated.items():

        if not nodes:
            continue

        proxy = nodes[0].copy()

        proxy["name"] = (
            f"{REGIONS[region]}专线"
        )

        final_proxies.append(proxy)

    # ========================================================
    # 备用
    # 每个地区最多两个
    # ========================================================

    for region, nodes in backup.items():

        for index, proxy in enumerate(
            nodes[:2],
            start=1,
        ):

            proxy = proxy.copy()

            proxy["name"] = (
                f"{REGIONS[region]}"
                f"备用"
                f"{index:02d}"
            )

            final_proxies.append(proxy)

    # ========================================================
    # 检查
    # ========================================================

    if not final_proxies:

        raise RuntimeError(
            "筛选后没有节点，请检查关键词和地区名称"
        )

    # ========================================================
    # 输出
    # ========================================================

    output = {
        "proxies": final_proxies
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

    # ========================================================
    # 输出统计
    # ========================================================

    print("")
    print("================================")
    print("筛选完成")
    print("================================")

    print(
        "最终节点数量:",
        len(final_proxies),
    )

    print("")
    print("最终节点:")

    for proxy in final_proxies:

        print(
            " -",
            proxy["name"],
        )

    print("")
    print("输出文件:", OUTPUT_FILE)


if __name__ == "__main__":
    main()
