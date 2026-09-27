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

        files = data.get("files", {})

        print("Gist files:", list(files.keys()))

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
        print("size:", vip.get("size"))

        content = vip.get("content")

        if content and not vip.get("truncated", False):
            print("Using Gist API content")
            return content

        raw_url = vip.get("raw_url")

        if not raw_url:
            raise RuntimeError(
                "VIP raw_url not found"
            )

        print("Using Gist raw_url:")
        print(raw_url)

        response = session.get(
            raw_url,
            timeout=60
        )

        print("Raw status:", response.status_code)

        response.raise_for_status()

        if not response.text.strip():
            raise RuntimeError(
                "VIP raw content is empty"
            )

        return response.text

    except Exception as error:
        print()
        print("Gist API failed:")
        print(str(error))
        print()
        print("Trying direct VIP Raw URL...")

        response = session.get(
            GIST_RAW_URL,
            timeout=60
        )

        print("Direct Raw status:", response.status_code)

        response.raise_for_status()

        if not response.text.strip():
            raise RuntimeError(
                "Direct VIP Raw content is empty"
            )

        return response.text


def get_region(name):
    regions = [
        ("香港", "香港"),
        ("澳门", "澳门"),
        ("台湾", "台湾"),
        ("新加坡", "新加坡"),
        ("狮城", "新加坡"),
        ("日本", "日本"),
        ("韩国", "韩国"),
        ("美国", "美国"),
        ("英国", "英国"),
        ("德国", "德国"),
        ("法国", "法国"),
        ("加拿大", "加拿大"),
        ("澳大利亚", "澳大利亚"),
        ("印度", "印度"),
        ("土耳其", "土耳其"),
        ("意大利", "意大利"),
        ("泰国", "泰国"),
        ("墨西哥", "墨西哥"),
        ("巴西", "巴西")
    ]

    for keyword, region in regions:
        if keyword in name:
            return region

    return None


def clean_vip(content):
    print()
    print("================================")
    print("解析 VIP")
    print("================================")

    data = yaml.safe_load(content)

    if not isinstance(data, dict):
        raise RuntimeError(
            "VIP YAML top level is not a dictionary"
        )

    proxies = data.get("proxies", [])

    if not isinstance(proxies, list):
        raise RuntimeError(
            "VIP YAML does not contain proxies"
        )

    print("原始节点数量:", len(proxies))

    if not proxies:
        raise RuntimeError(
            "VIP proxies is empty"
        )

    print()
    print("原始节点名称:")
    print("--------------------------------")

    for index, proxy in enumerate(proxies, 1):
        if isinstance(proxy, dict):
            print(
                str(index).zfill(3)
                + ". "
                + str(proxy.get("name", "<无名称>"))
            )

    print("--------------------------------")

    experimental = []
    basic = []

    basic_regions = {
        "香港",
        "台湾",
        "新加坡",
        "日本",
        "美国"
    }

    for proxy in proxies:

        if not isinstance(proxy, dict):
            continue

        name = str(
            proxy.get("name", "")
        ).strip()

        if not name:
            continue

        if not proxy.get("server"):
            continue

        region = get_region(name)

        if not region:
            continue

        if "实验性" in name:

            if region in {
                "香港",
                "日本",
                "新加坡",
                "美国"
            }:
                new_proxy = proxy.copy()

                new_proxy["name"] = (
                    region + "专线"
                )

                experimental.append(
                    new_proxy
                )

        elif "基础" in name:

            if region in basic_regions:

                new_proxy = proxy.copy()

                new_proxy["_region"] = region

                basic.append(
                    new_proxy
                )

    print()
    print("实验性节点:", len(experimental))
    print("基础节点:", len(basic))

    result = []

    used_experimental = set()

    for proxy in experimental:

        name = proxy["name"]

        region = name.replace(
            "专线",
            ""
        )

        if region in used_experimental:
            continue

        used_experimental.add(region)

        result.append(proxy)

    basic_count = {}

    for proxy in basic:

        region = proxy.pop(
            "_region",
            None
        )

        if not region:
            continue

        basic_count[region] = (
            basic_count.get(region, 0) + 1
        )

        count = basic_count[region]

        if count == 1:
            proxy["name"] = (
                region + "备用"
            )
        else:
            proxy["name"] = (
                region
                + "备用-"
                + str(count)
            )

        result.append(proxy)

    return result


def save_output(proxies):

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
    print("最终节点数量:", len(proxies))

    print()
    print("最终节点:")

    for index, proxy in enumerate(
        proxies,
        1
    ):
        print(
            str(index).zfill(2)
            + ". "
            + str(proxy.get("name", ""))
        )

    print()
    print("生成完成:", OUTPUT_FILE)


def main():

    print()
    print("================================")
    print("CleanVIP")
    print("================================")

    content = get_vip_content()

    proxies = clean_vip(content)

    if not proxies:
        raise RuntimeError(
            "筛选后没有节点"
        )

    save_output(proxies)


if __name__ == "__main__":
    main()
