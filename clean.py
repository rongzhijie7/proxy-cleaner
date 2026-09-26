import os
import re
import sys
import requests
import yaml

GIST_ID = “76ce5d8efc7e0f92cda3b59a82536532”
GIST_RAW_URL = “https://gist.githubusercontent.com/rongzhijie7/76ce5d8efc7e0f92cda3b59a82536532/raw/VIP”
OUTPUT_FILE = “cleanvip.yaml”

=========================

允许保留的地区

=========================

REGIONS = [
(“香港”, “香港”),
(“澳门”, “澳门”),
(“台湾”, “台湾”),
(“新加坡”, “新加坡”),
(“狮城”, “新加坡”),
(“日本”, “日本”),
(“韩国”, “韩国”),
(“美国”, “美国”),
(“英国”, “英国”),
(“德国”, “德国”),
(“法国”, “法国”),
(“加拿大”, “加拿大”),
(“澳大利亚”, “澳大利亚”),
(“印度”, “印度”),
(“土耳其”, “土耳其”),
(“意大利”, “意大利”),
(“泰国”, “泰国”),
(“墨西哥”, “墨西哥”),
(“巴西”, “巴西”),
]

基础节点实际只保留这些地区

BASIC_REGIONS = {
“香港”,
“台湾”,
“新加坡”,
“日本”,
“美国”,
}

=========================

HTTP

=========================

session = requests.Session()

session.headers.update({
“User-Agent”: “cleanvip-github-actions”,
“Accept”: “application/vnd.github+json”,
})

=========================

从 Gist API 获取 VIP

=========================

def download_from_gist_api():
url = f”https://api.github.com/gists/{GIST_ID}”

print("================================")
print("尝试通过 GitHub Gist API 获取 VIP")
print(url)
print("================================")
r = session.get(
    url,
    timeout=30
)
print("Gist API HTTP 状态:", r.status_code)
r.raise_for_status()
data = r.json()
files = data.get("files", {})
print("Gist 文件数量:", len(files))
if not files:
    raise RuntimeError("Gist 中没有找到任何文件")
# 优先精确寻找 VIP
vip_file = None
for filename, info in files.items():
    print("发现文件:", filename)
    if filename == "VIP":
        vip_file = info
        break
# 如果文件名不是 VIP，则寻找大小写不敏感的 VIP
if vip_file is None:
    for filename, info in files.items():
        if filename.lower() == "vip":
            vip_file = info
            break
if vip_file is None:
    raise RuntimeError(
        "Gist API 成功，但是没有找到名为 VIP 的文件"
    )
print("找到 VIP 文件")
print("文件大小:", vip_file.get("size", "unknown"))
print("是否截断:", vip_file.get("truncated", False))
# API 可能直接提供 content
content = vip_file.get("content")
# 如果没有完整 content，则使用 raw_url
if not content or vip_file.get("truncated", False):
    raw_url = vip_file.get("raw_url")
    if not raw_url:
        raise RuntimeError(
            "VIP 文件没有 raw_url"
        )
    print("通过 raw_url 获取完整 VIP:")
    print(raw_url)
    r = session.get(
        raw_url,
        timeout=60
    )
    print("VIP raw HTTP 状态:", r.status_code)
    r.raise_for_status()
    content = r.text
if not content.strip():
    raise RuntimeError(
        "获取到的 VIP 内容为空"
    )
print("VIP 内容长度:", len(content))
return content

=========================

备用：直接读取原始 Raw

=========================

def download_from_raw():
print(”================================”)
print(“Gist API 失败，尝试备用 Raw 地址”)
print(GIST_RAW_URL)
print(”================================”)

r = session.get(
    GIST_RAW_URL,
    timeout=60
)
print("Raw HTTP 状态:", r.status_code)
r.raise_for_status()
content = r.text
if not content.strip():
    raise RuntimeError(
        "Raw 内容为空"
    )
print("Raw 内容长度:", len(content))
return content

=========================

获取 VIP

=========================

def get_source():
try:
return download_from_gist_api()

except Exception as e:
    print()
    print("Gist API 获取失败:")
    print(type(e).__name__, str(e))
    print()
    print("启动备用 Raw 获取方式")
    return download_from_raw()

=========================

YAML 解析

=========================

def parse_yaml(content):
print()
print(”================================”)
print(“开始解析 VIP YAML”)
print(”================================”)

try:
    data = yaml.safe_load(content)
except Exception as e:
    raise RuntimeError(
        f"YAML 解析失败: {e}"
    )
if not isinstance(data, dict):
    raise RuntimeError(
        "VIP YAML 顶层不是字典结构"
    )
proxies = data.get("proxies")
if not isinstance(proxies, list):
    raise RuntimeError(
        "VIP YAML 中没有找到 proxies 列表"
    )
print("原始节点数量:", len(proxies))
if len(proxies) == 0:
    raise RuntimeError(
        "proxies 列表为空"
    )
print()
print("========== 原始节点名称 ==========")
for i, proxy in enumerate(proxies, 1):
    if isinstance(proxy, dict):
        print(
            f"{i:03d}. {proxy.get('name', '<无名称>')}"
        )
    else:
        print(
            f"{i:03d}. <不是节点字典>"
        )
print("==================================")
print()
return proxies

=========================

判断地区

=========================

def detect_region(name):
for keyword, region in REGIONS:
if keyword in name:
return region

return None

=========================

主处理

=========================

def clean_vip(proxies):

experimental = []
basic = []
for proxy in proxies:
    if not isinstance(proxy, dict):
        continue
    name = str(
        proxy.get("name", "")
    ).strip()
    if not name:
        continue
    # 必须存在服务器地址
    if not proxy.get("server"):
        continue
    region = detect_region(name)
    if not region:
        continue
    # =========================
    # 实验性
    # =========================
    if "实验性" in name:
        if region in {
            "香港",
            "日本",
            "新加坡",
            "美国",
        }:
            new_proxy = proxy.copy()
            new_proxy["name"] = (
                f"{region}专线"
            )
            experimental.append(new_proxy)
    # =========================
    # 基础
    # =========================
    elif "基础" in name:
        if region in BASIC_REGIONS:
            new_proxy = proxy.copy()
            new_proxy["_region"] = region
            basic.append(new_proxy)
print("实验性节点:", len(experimental))
print("基础节点:", len(basic))
# =========================
# 实验性去重
# =========================
experimental_result = []
experimental_regions = set()
for proxy in experimental:
    region = proxy["name"].replace(
        "专线",
        ""
    )
    if region in experimental_regions:
        continue
    experimental_regions.add(region)
    proxy.pop("_region", None)
    experimental_result.append(proxy)
# =========================
# 基础节点重新编号
# =========================
basic_count = {}
basic_result = []
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
            f"{region}备用"
        )
    else:
        proxy["name"] = (
            f"{region}备用-{count}"
        )
    basic_result.append(proxy)
# =========================
# 最终输出
# =========================
result = (
    experimental_result
    + basic_result
)
return result

=========================

写入 cleanvip.yaml

=========================

def save_result(proxies):

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
) as f:
    yaml.safe_dump(
        output,
        f,
        allow_unicode=True,
        sort_keys=False
    )
print()
print("最终节点数量:", len(proxies))
print()
print("========== 最终节点 ==========")
for i, proxy in enumerate(
    proxies,
    1
):
    print(
        f"{i:03d}. {proxy.get('name', '')}"
    )
print()
print(
    "已生成:",
    OUTPUT_FILE
)

=========================

Main

=========================

def main():

print()
print("========================================")
print("        CleanVIP")
print("========================================")
print()
content = get_source()
proxies = parse_yaml(content)
result = clean_vip(proxies)
if not result:
    raise RuntimeError(
        "筛选后没有任何节点，请检查 VIP 节点名称或筛选规则"
    )
save_result(result)

if name == “main”:
main()
