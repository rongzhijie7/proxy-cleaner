import requests
import yaml

GIST_ID = "76ce5d8efc7e0f92cda3b59a82536532"

GIST_API_URL = "https://api.github.com/gists/" + GIST_ID

GIST_RAW_URL = "https://gist.githubusercontent.com/rongzhijie7/76ce5d8efc7e0f92cda3b59a82536532/raw/VIP"

OUTPUT_FILE = "cleanvip.yaml"


session = requests.Session()

session.headers.update({
    "User-Agent": "CleanVIP-GitHub-Actions",
    "Accept": "application/vnd.github+json"
})


# ============================================================
# 获取 VIP Gist
# ============================================================

def get_vip_content():

    print("================================")
    print("获取 VIP Gist")
    print("================================")

    print("Gist API:")
    print(GIST_API_URL)

    try:

        response = session.get(
            GIST_API_URL,
            timeout=30
        )

        print("API status:", response.status_code)

        response.raise_for_status()

        data = response.json()

        files = data.get(
            "files",
            {}
        )

        print(
            "Gist files:",
            list(files.keys())
        )

        vip = None

        for filename, info in files.items():

            if filename.lower() == "vip":

                vip = info

                break

        if vip is None:

            raise RuntimeError(
                "VIP file not found in Gist"
            )

        print("VIP file found")

        print(
            "size:",
            vip.get("size")
        )

        content = vip.get("content")

        if content and not vip.get(
            "truncated",
            False
        ):

            print(
                "Using Gist API content"
            )

            return content

        raw_url = vip.get(
            "raw_url"
        )

        if not raw_url:

            raise RuntimeError(
                "VIP raw_url not found"
            )

        print(
            "Using Gist raw_url:"
        )

        print(raw_url)

        response = session.get(
            raw_url,
            timeout=60
        )

        print(
            "Raw status:",
            response.status_code
        )

        response.raise_for_status()

        if not response.text.strip():

            raise RuntimeError(
                "VIP raw content is empty"
            )

        return response.text

    except Exception as error:

        print()
        print(
            "Gist API failed:"
        )

        print(
            str(error)
        )

        print()
        print(
            "Trying direct VIP Raw URL..."
        )

        response = session.get(
            GIST_RAW_URL,
            timeout=60
        )

        print(
            "Direct Raw status:",
            response.status_code
        )

        response.raise_for_status()

        if not response.text.strip():

            raise RuntimeError(
                "Direct VIP Raw content is empty"
            )

        return response.text


# ============================================================
# 识别地区
# ============================================================

def get_region(name):

    if "香港" in name:
        return "香港"

    if "台湾" in name:
        return "台湾"

    if "狮城" in name:
        return "新加坡"

    if "新加坡" in name:
        return "新加坡"

    if "日本" in name:
        return "日本"

    if "美国" in name:
        return "美国"

    return None


# ============================================================
# 判断是不是专线
# ============================================================

def is_dedicated(name):

    return name.endswith(
        "专线"
    )


# ============================================================
# 判断是不是备用节点
# ============================================================

def is_backup(name):

    patterns = [
        "02O-",
        "02B",
        "03O-",
        "03B"
    ]

    for pattern in patterns:

        if pattern in name:

            return True

    return False


# ============================================================
# 处理 VIP
# ============================================================

def clean_vip(content):

    print()
    print("================================")
    print("解析 VIP")
    print("================================")

    try:

        data = yaml.safe_load(
            content
        )

    except Exception as error:

        raise RuntimeError(
            "YAML 解析失败: "
            + str(error)
        )

    if not isinstance(
        data,
        dict
    ):

        raise RuntimeError(
            "VIP YAML 顶层不是字典"
        )

    proxies = data.get(
        "proxies",
        []
    )

    if not isinstance(
        proxies,
        list
    ):

        raise RuntimeError(
            "VIP YAML 没有 proxies"
        )

    print(
        "原始节点数量:",
        len(proxies)
    )

    print()
    print("原始节点名称:")
    print("--------------------------------")

    for index, proxy in enumerate(
        proxies,
        1
    ):

        if isinstance(
            proxy,
            dict
        ):

            print(
                str(index).zfill(3)
                + ". "
                + str(
                    proxy.get(
                        "name",
                        "<无名称>"
                    )
                )
            )

    print("--------------------------------")

    # ========================================================
    # 第一阶段：筛选
    # ========================================================

    dedicated = []
    backup = []

    for proxy in proxies:

        if not isinstance(
            proxy,
            dict
        ):
            continue

        name = str(
            proxy.get(
                "name",
                ""
            )
        ).strip()

        if not name:
            continue

        if not proxy.get(
            "server"
        ):
            continue

        region = get_region(
            name
        )

        if not region:
            continue

        # ------------------------------
        # 专线
        # ------------------------------

        if is_dedicated(
            name
        ):

            # 狮城统一改成新加坡
            new_proxy = proxy.copy()

            new_proxy["name"] = (
                region
                + "专线"
            )

            dedicated.append(
                new_proxy
            )

            continue

        # ------------------------------
        # 备用
        # ------------------------------

        if is_backup(
            name
        ):

            # 只保留指定地区
            if region in {
                "台湾",
                "新加坡",
                "日本",
                "美国"
            }:

                new_proxy = proxy.copy()

                new_proxy["_region"] = (
                    region
                )

                backup.append(
                    new_proxy
                )


    print()
    print(
        "专线节点:",
        len(dedicated)
    )

    print(
        "备用节点:",
        len(backup)
    )


    # ========================================================
    # 第二阶段：专线去重
    # ========================================================

    result = []

    dedicated_regions = set()

    for proxy in dedicated:

        name = proxy.get(
            "name",
            ""
        )

        region = name.replace(
            "专线",
            ""
        )

        if region in dedicated_regions:

            continue

        dedicated_regions.add(
            region
        )

        result.append(
            proxy
        )


    # ========================================================
    # 第三阶段：备用节点编号
    # ========================================================

    backup_count = {}

    for proxy in backup:

        region = proxy.pop(
            "_region",
            None
        )

        if not region:
            continue

        backup_count[
            region
        ] = (
            backup_count.get(
                region,
                0
            )
            + 1
        )

        count = backup_count[
            region
        ]

        if count == 1:

            proxy["name"] = (
                region
                + "备用"
            )

        else:

            proxy["name"] = (
                region
                + "备用-"
                + str(count)
            )

        result.append(
            proxy
        )


    return result


# ============================================================
# 输出 cleanvip.yaml
# ============================================================

def save_output(
    proxies
):

    print()
    print("================================")
    print("生成 cleanvip.yaml")
    print("================================")

    output = {
        "proxies": proxies
    }

    with open(
        OUTPUT_FILE,
        "w",
        encoding="utf-8"
    ) as file:

        yaml.safe_dump(
            output,
            file,
            allow_unicode=True,
            sort_keys=False
        )

    print()
    print(
        "最终节点数量:",
        len(proxies)
    )

    print()
    print("最终节点:")
    print("--------------------------------")

    for index, proxy in enumerate(
        proxies,
        1
    ):

        print(
            str(index).zfill(2)
            + ". "
            + str(
                proxy.get(
                    "name",
                    ""
                )
            )
        )

    print("--------------------------------")

    print()
    print(
        "生成完成:",
        OUTPUT_FILE
    )


# ============================================================
# Main
# ============================================================

def main():

    print()
    print("================================")
    print("CleanVIP")
    print("================================")
    print()

    content = get_vip_content()

    proxies = clean_vip(
        content
    )

    if not proxies:

        raise RuntimeError(
            "筛选后没有节点"
        )

    save_output(
        proxies
    )


if __name__ == "__main__":

    main()
