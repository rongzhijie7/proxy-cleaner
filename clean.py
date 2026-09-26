import yaml

with open("source.yaml", "r", encoding="utf-8") as f:
    data = yaml.safe_load(f)

proxies = data.get("proxies", [])

print("=" * 80)
print(f"当前 source.yaml 节点数量: {len(proxies)}")
print("=" * 80)

for i, proxy in enumerate(proxies, 1):
    print(f"{i:03d}. {proxy.get('name', '')}")

print("=" * 80)
print("节点名称输出完成")
print("=" * 80)
