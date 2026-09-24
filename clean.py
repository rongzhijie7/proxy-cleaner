import requests
import yaml
import sys


VIP_URL = (
    "https://gist.githubusercontent.com/"
    "rongzhijie7/76ce5d8efc7e0f92cda3b59a82536532/"
    "raw/VIP"
)

INPUT_FILE = "vip.yaml"
OUTPUT_FILE = "clean.yaml"


def download_vip():
    print("正在下载 VIP...")

    response = requests.get(
        VIP_URL,
        timeout=60,
    )

    print("HTTP:", response.status_code)
    print("Size:", len(response.content))

    if response.status_code != 200:
        raise RuntimeError(
            f"VIP 下载失败: HTTP {response.status_code}"
        )

    with open(INPUT_FILE, "wb") as f:
        f.write(response.content)

    print("VIP 下载成功")


def load_vip():

    with open(
        INPUT_FILE,
        "r",
        encoding="utf-8"
    ) as f:

        data = yaml.safe_load(f)

    if not isinstance(data, dict):
        raise RuntimeError(
            "VIP YAML 格式错误"
        )

    proxies = data.get("proxies", [])

    if not isinstance(proxies, list):
        raise RuntimeError(
            "VIP 中没有找到 proxies"
        )

    return data, proxies


def main():

    download_vip()

    data, proxies = load_vip()

    print()
    print("=" * 50)
    print("VIP 节点数量:", len(proxies))
    print("=" * 50)

    for index, proxy in enumerate(
        proxies,
        start=1
    ):

        name = proxy.get(
            "name",
            f"Node-{index}"
        )

        protocol = proxy.get(
            "type",
            "unknown"
        )

        server = proxy.get(
            "server",
            ""
        )

        port = proxy.get(
            "port",
            ""
        )

        print(
            f"{index:03d} | "
            f"{protocol:12} | "
            f"{server}:{port} | "
            f"{name}"
        )

    # 暂时原样输出
    output = {
        "proxies": proxies
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

    print()
    print(
        "已生成:",
        OUTPUT_FILE
    )


if __name__ == "__main__":
    main()
