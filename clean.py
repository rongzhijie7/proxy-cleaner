import os
import sys
import time
import yaml
import requests
import subprocess
import re


# ============================================================
# 基本配置
# ============================================================

VIP_URL = (
    "https://gist.githubusercontent.com/"
    "rongzhijie7/76ce5d8efc7e0f92cda3b59a82536532/"
    "raw/VIP"
)

OUTPUT_FILE = "cleanvip.yaml"

MIHOMO_BIN = "./mihomo"

MIHOMO_CONFIG = "/tmp/mihomo_test.yaml"

MIHOMO_LOG = "/tmp/mihomo.log"

MIHOMO_API = "http://127.0.0.1:9090"

MIHOMO_PORT = 7890

# 单节点测试
TEST_TIMEOUT = 5000

# 测试网址
TEST_URL = "https://www.gstatic.com/generate_204"


# ============================================================
# 只保留这些地区
# ============================================================

REGIONS = [
    "香港",
    "台湾",
    "日本",
    "新加坡",
    "美国",
    "英国",
    "韩国",
]


# ============================================================
# YAML 类型规范化
#
# 某些订阅里可能把 true / false / 数字写成字符串。
# ============================================================

def normalize_value(value):

    if isinstance(value, str):

        if value.lower() == "true":
            return True

        if value.lower() == "false":
            return False

        if re.fullmatch(r"\d+", value):
            return int(value)

    return value


def normalize_proxy(proxy):

    new_proxy = {}

    for key, value in proxy.items():

        new_proxy[key] = normalize_value(value)

    return new_proxy


# ============================================================
# 清理节点名称
# ============================================================

def clean_name(name):

    name = str(name)

    replacements = {

        "&#x5b;": "[",
        "&#x5d;": "]",

        "&#91;": "[",
        "&#93;": "]",

    }

    for old, new in replacements.items():

        name = name.replace(
            old,
            new
        )

    return name.strip()


# ============================================================
# 地区识别
# ============================================================

def get_region(name):

    name = clean_name(name)

    # 狮城 = 新加坡
    if "狮城" in name:

        return "新加坡"

    # 中文地区
    for region in REGIONS:

        if region in name:

            return region

    # 英文地区
    lower = name.lower()

    if "hong kong" in lower:
        return "香港"

    if "taiwan" in lower:
        return "台湾"

    if "japan" in lower:
        return "日本"

    if "singapore" in lower:
        return "新加坡"

    if "united states" in lower:
        return "美国"

    if "usa" in lower:
        return "美国"

    if "america" in lower:
        return "美国"

    if "united kingdom" in lower:
        return "英国"

    if "uk" in lower:
        return "英国"

    if "korea" in lower:
        return "韩国"

    return None


# ============================================================
# 下载 VIP
# ============================================================

def download_vip():

    print()
    print("======================================")
    print("下载 VIP")
    print("======================================")

    try:

        response = requests.get(
            VIP_URL,
            timeout=60,
            headers={
                "User-Agent": "Mozilla/5.0"
            }
        )

    except Exception as e:

        print("❌ VIP 下载失败")
        print(e)

        sys.exit(1)

    print(
        "HTTP:",
        response.status_code
    )

    print(
        "Size:",
        len(response.content)
    )

    if response.status_code != 200:

        print(
            "❌ VIP HTTP 状态异常"
        )

        print(
            response.text[:500]
        )

        sys.exit(1)

    if not response.text.strip():

        print(
            "❌ VIP 内容为空"
        )

        sys.exit(1)

    return response.text


# ============================================================
# 筛选节点
#
# 只允许：
#
#   实验性
#   高级
#
# 其它所有节点：
#
#   基础
#   普通
#   免费
#   其它标签
#
# 全部丢弃。
# ============================================================

def collect_candidates(data):

    raw_proxies = data.get(
        "proxies",
        []
    )

    if not isinstance(
        raw_proxies,
        list
    ):

        print(
            "❌ proxies 格式错误"
        )

        sys.exit(1)

    experimental = []

    advanced = []

    print()
    print("======================================")
    print("开始筛选节点")
    print("======================================")

    # ========================================================
    # 第一轮
    # ========================================================

    for raw_proxy in raw_proxies:

        if not isinstance(
            raw_proxy,
            dict
        ):

            continue

        proxy = normalize_proxy(
            raw_proxy
        )

        old_name = proxy.get(
            "name",
            ""
        )

        if not old_name:

            continue

        old_name = clean_name(
            old_name
        )

        proxy["name"] = old_name

        # ----------------------------------------------------
        # 实验性
        # ----------------------------------------------------

        if "实验性" in old_name:

            region = get_region(
                old_name
            )

            if not region:

                print(
                    "[跳过] 实验性无法识别地区:",
                    old_name
                )

                continue

            proxy["_region"] = region

            proxy["_source_name"] = old_name

            experimental.append(
                proxy
            )

            continue

        # ----------------------------------------------------
        # 高级
        # ----------------------------------------------------

        if "高级" in old_name:

            region = get_region(
                old_name
            )

            if not region:

                print(
                    "[跳过] 高级无法识别地区:",
                    old_name
                )

                continue

            proxy["_region"] = region

            proxy["_source_name"] = old_name

            advanced.append(
                proxy
            )

            continue

        # ----------------------------------------------------
        # 其它全部跳过
        # ----------------------------------------------------

        continue


    result = []


    # ========================================================
    # 实验性 → 专线
    # ========================================================

    print()
    print("实验性节点:")

    for proxy in experimental:

        region = proxy["_region"]

        old_name = proxy["_source_name"]

        proxy["name"] = (
            f"{region}专线"
        )

        result.append(
            proxy
        )

        print(
            f"  {old_name} -> {proxy['name']}"
        )


    # ========================================================
    # 高级 → 备用
    #
    # 每个地区最多 2 个
    # ========================================================

    advanced_by_region = {

        region: []

        for region in REGIONS

    }


    for proxy in advanced:

        region = proxy["_region"]

        if region in advanced_by_region:

            advanced_by_region[
                region
            ].append(proxy)


    print()
    print("高级备用节点:")


    for region in REGIONS:

        nodes = advanced_by_region[
            region
        ][:2]


        for index, proxy in enumerate(
            nodes,
            start=1
        ):

            if index == 1:

                proxy["name"] = (
                    f"{region}备用"
                )

            else:

                proxy["name"] = (
                    f"{region}备用-{index}"
                )

            result.append(
                proxy
            )

            print(
                f"  {proxy['_source_name']} "
                f"-> {proxy['name']}"
            )


    # ========================================================
    # 删除内部字段
    # ========================================================

    for proxy in result:

        proxy.pop(
            "_region",
            None
        )

        proxy.pop(
            "_source_name",
            None
        )


    print()
    print("======================================")
    print("筛选完成")
    print("======================================")

    print(
        "实验性:",
        len(experimental)
    )

    print(
        "高级:",
        len(advanced)
    )

    print(
        "最终候选:",
        len(result)
    )

    return result


# ============================================================
# 创建 Mihomo 测试配置
#
# 这里刻意参考你提供的“能正常测试”的版本。
#
# 不使用：
#   unified-delay
#   tcp-concurrent
#   自定义 DNS
#   expected
#
# 保持最简单的 Mihomo url-test。
# ============================================================

def create_test_config(proxies):

    names = [
        proxy["name"]
        for proxy in proxies
    ]

    config = {

        "mixed-port": MIHOMO_PORT,

        "external-controller":
            "127.0.0.1:9090",

        "proxies":
            proxies,

        "proxy-groups": [

            {
                "name": "TEST",

                "type": "url-test",

                "proxies": names,

                "url":
                    TEST_URL,

                "interval": 300,

            }

        ]

    }

    return config


# ============================================================
# 启动 Mihomo
# ============================================================

def start_mihomo(proxies):

    config = create_test_config(
        proxies
    )

    with open(
        MIHOMO_CONFIG,
        "w",
        encoding="utf-8"
    ) as f:

        yaml.safe_dump(
            config,
            f,
            allow_unicode=True,
            sort_keys=False
        )


    print()
    print("======================================")
    print("启动 Mihomo")
    print("======================================")


    log = open(
        MIHOMO_LOG,
        "w",
        encoding="utf-8"
    )


    process = subprocess.Popen(

        [
            MIHOMO_BIN,
            "-f",
            MIHOMO_CONFIG
        ],

        stdout=log,

        stderr=subprocess.STDOUT,

        text=True
    )


    # ========================================================
    # 等待 API
    # ========================================================

    print(
        "等待 Mihomo API..."
    )


    for _ in range(30):

        if process.poll() is not None:

            log.close()

            print(
                "❌ Mihomo 启动失败"
            )

            show_mihomo_log()

            sys.exit(1)


        try:

            r = requests.get(
                f"{MIHOMO_API}/proxies",
                timeout=1
            )


            if r.status_code == 200:

                print(
                    "✅ Mihomo API 已启动"
                )

                return process, log


        except Exception:

            pass


        time.sleep(0.5)


    print(
        "❌ Mihomo API 启动超时"
    )


    try:

        process.kill()

    except Exception:

        pass


    log.close()

    show_mihomo_log()

    sys.exit(1)


# ============================================================
# 节点测速
#
# 完全参考你提供的可用版本。
# ============================================================

def test_node(name):

    try:

        encoded_name = requests.utils.quote(
            name,
            safe=""
        )

        url = (
            f"{MIHOMO_API}/proxies/"
            f"{encoded_name}/delay"
        )

        r = requests.get(

            url,

            params={
                "timeout": TEST_TIMEOUT,
                "url": TEST_URL,
            },

            timeout=8
        )

        # ====================================================
        # 打印真实返回
        # ====================================================

        if r.status_code != 200:

            print(
                f"  ❌ HTTP {r.status_code}"
            )

            try:

                print(
                    "  返回:",
                    r.text[:500]
                )

            except Exception:

                pass

            return None


        try:

            data = r.json()

        except Exception:

            print(
                "  ❌ 返回不是 JSON:"
            )

            print(
                r.text[:500]
            )

            return None


        if "delay" not in data:

            print(
                "  ❌ 没有 delay"
            )

            print(
                "  返回:",
                data
            )

            return None


        delay = data["delay"]

        if not isinstance(
            delay,
            int
        ):

            delay = int(delay)


        return delay


    except Exception as e:

        print(
            "  ❌ 请求异常:",
            repr(e)
        )

        return None


# ============================================================
# 测试全部节点
# ============================================================

def test_all_nodes(proxies):

    print()
    print("======================================")
    print("开始实际节点测试")
    print("======================================")

    print(
        "测试地址:",
        TEST_URL
    )

    print(
        "单节点超时:",
        TEST_TIMEOUT,
        "ms"
    )

    print("======================================")


    # --------------------------------------------------------
    # 获取 Mihomo 节点
    # --------------------------------------------------------

    try:

        r = requests.get(
            f"{MIHOMO_API}/proxies",
            timeout=5
        )

        loaded = r.json().get(
            "proxies",
            {}
        )

    except Exception as e:

        print(
            "❌ 无法获取 Mihomo 节点列表:",
            e
        )

        return []


    print()
    print(
        "Mihomo 已加载:",
        len(loaded)
    )


    alive = []


    for index, proxy in enumerate(
        proxies,
        start=1
    ):

        name = proxy["name"]


        print()
        print(
            f"[{index}/{len(proxies)}] "
            f"{name}"
        )


        # ----------------------------------------------------
        # 检查是否加载
        # ----------------------------------------------------

        if name not in loaded:

            print(
                "  ❌ Mihomo 未加载"
            )

            continue


        # ----------------------------------------------------
        # 测速
        # ----------------------------------------------------

        delay = test_node(
            name
        )


        if delay is not None:

            print(
                f"  ✅ {delay} ms"
            )

            alive.append(
                name
            )

        else:

            print(
                "  ❌ FAIL"
            )


    print()
    print("======================================")
    print("测速完成")
    print("======================================")

    print(
        "候选节点:",
        len(proxies)
    )

    print(
        "可用节点:",
        len(alive)
    )


    return alive


# ============================================================
# 清理内部字段
# ============================================================

def clean_output(proxies):

    for proxy in proxies:

        proxy.pop(
            "_region",
            None
        )

        proxy.pop(
            "_source_name",
            None
        )


# ============================================================
# 保存 cleanvip.yaml
# ============================================================

def save_yaml(proxies):

    output = {
        "proxies": proxies
    }


    temp_file = (
        OUTPUT_FILE + ".tmp"
    )


    with open(
        temp_file,
        "w",
        encoding="utf-8"
    ) as f:

        yaml.safe_dump(

            output,

            f,

            allow_unicode=True,

            sort_keys=False

        )


    os.replace(
        temp_file,
        OUTPUT_FILE
    )


# ============================================================
# Mihomo 日志
# ============================================================

def show_mihomo_log():

    print()
    print("======================================")
    print("Mihomo 最近日志")
    print("======================================")


    if not os.path.exists(
        MIHOMO_LOG
    ):

        print(
            "没有 Mihomo 日志"
        )

        return


    try:

        with open(
            MIHOMO_LOG,
            "r",
            encoding="utf-8",
            errors="ignore"
        ) as f:

            lines = f.readlines()


        for line in lines[-100:]:

            print(
                line.rstrip()
            )


    except Exception as e:

        print(
            "读取日志失败:",
            e
        )


# ============================================================
# 停止 Mihomo
# ============================================================

def stop_mihomo(
    process,
    log
):

    print()
    print(
        "停止 Mihomo"
    )


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


    try:

        log.close()

    except Exception:

        pass


# ============================================================
# 主程序
# ============================================================

def main():

    print()
    print("======================================")
    print("VIP 节点自动清洗")
    print("======================================")


    # --------------------------------------------------------
    # Mihomo
    # --------------------------------------------------------

    if not os.path.exists(
        MIHOMO_BIN
    ):

        print(
            "❌ 找不到 Mihomo:",
            MIHOMO_BIN
        )

        sys.exit(1)


    # --------------------------------------------------------
    # 下载 VIP
    # --------------------------------------------------------

    vip_text = download_vip()


    # --------------------------------------------------------
    # YAML
    # --------------------------------------------------------

    try:

        data = yaml.safe_load(
            vip_text
        )

    except Exception as e:

        print(
            "❌ YAML 解析失败:",
            e
        )

        sys.exit(1)


    if not isinstance(
        data,
        dict
    ):

        print(
            "❌ VIP YAML 格式错误"
        )

        sys.exit(1)


    # --------------------------------------------------------
    # 筛选
    # --------------------------------------------------------

    candidates = collect_candidates(
        data
    )


    if not candidates:

        print(
            "❌ 没有候选节点"
        )

        sys.exit(1)


    # --------------------------------------------------------
    # 启动 Mihomo
    # --------------------------------------------------------

    process, log = start_mihomo(
        candidates
    )


    try:

        alive_names = test_all_nodes(
            candidates
        )

    finally:

        stop_mihomo(
            process,
            log
        )


    # --------------------------------------------------------
    # 找出通过节点
    # --------------------------------------------------------

    alive_set = set(
        alive_names
    )


    working = []


    for proxy in candidates:

        if proxy["name"] in alive_set:

            working.append(
                proxy
            )


    # --------------------------------------------------------
    # 结果
    # --------------------------------------------------------

    print()
    print("======================================")
    print("最终结果")
    print("======================================")


    print(
        "候选:",
        len(candidates)
    )

    print(
        "可用:",
        len(working)
    )

    print(
        "失效:",
        len(candidates) - len(working)
    )


    # --------------------------------------------------------
    # 全部失败
    #
    # 不覆盖旧文件。
    # --------------------------------------------------------

    if not working:

        print()
        print(
            "⚠️ 本轮没有可用节点"
        )

        print(
            f"⚠️ 不覆盖 {OUTPUT_FILE}"
        )

        print(
            "⚠️ 保留上一版本订阅"
        )

        return


    # --------------------------------------------------------
    # 清理内部字段
    # --------------------------------------------------------

    clean_output(
        working
    )


    # --------------------------------------------------------
    # 保存
    # --------------------------------------------------------

    save_yaml(
        working
    )


    # --------------------------------------------------------
    # 最终输出
    # --------------------------------------------------------

    print()
    print("======================================")
    print(
        f"✅ {OUTPUT_FILE} 生成成功"
    )
    print("======================================")


    for proxy in working:

        print(
            f"- {proxy['name']} "
            f"[{proxy.get('type', '')}]"
        )


    print()
    print(
        "最终保留:",
        len(working),
        "个节点"
    )


if __name__ == "__main__":

    main()
