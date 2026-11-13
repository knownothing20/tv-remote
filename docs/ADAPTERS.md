# 机型适配器

面板抓到的都是**原始包名**（`com.tcl.cyberui`、`com.tcl.guard`…），看不懂也没法判断能不能停。
适配器就是一张 **包名 → 中文名 / 角色 / 是否可禁用** 的映射表，一个机型一个 JSON 文件。

```
adapters/
├─ tcl_mt5879_cn.json     # TCL MT5879（Android 11 国内版）— 参考实现，57 条
├─ _template.json         # 新机型从这里复制
└─ <vendor>_<soc>_<region>.json
```

## 文件格式

```json
{
  "id": "tcl_mt5879_cn",
  "name": "TCL MT5879 系列（Android 11 · 国内版）",
  "vendor": "TCL",
  "match": {
    "ro.product.model": ["tcl_mt5879_cn"],
    "ro.product.brand": ["TCL"]
  },
  "reference_device": "TCL 65Q10K（4GB RAM / Android 11）",
  "updated": "2026-11-13",
  "packages": {
    "com.tcl.cyberui": {
      "name": "TCL 桌面（启动器）",
      "role": "system",
      "policy": "avoid",
      "note": "禁用会黑屏"
    }
  }
}
```

### 匹配规则

`match` 里每个键对应一个 `getprop` 属性，值是候选列表；**全部提供的键都要命中**，且至少命中一个。
命中后面板顶部显示 `适配器 <id>`，未命中则显示原始包名（不影响功能）。

### policy 取值

| 值 | 含义 | 面板显示 |
|---|---|---|
| `avoid` | 绝对不能动（桌面、system_server、安装器…） | 红色「禁止」 |
| `keep` | 保留（缺了会影响核心功能） | 无标签 |
| `optional` | 可停用，但会失去对应功能 | 「可停」 |
| `bloat` | 厂商预装/推广，建议停用 | 黄色「建议停」 |

### role 取值

`system` / `tcl`（厂商）/ `media` / `thirdparty` / `google` —— 仅用于分类展示。

## 新增一个机型（约 20 分钟）

1. **拿到设备属性**

```bash
adb shell getprop ro.product.model    # 例如 tcl_mt5879_cn
adb shell getprop ro.product.brand    # TCL
adb shell getprop ro.build.version.release
```

2. **拿到自启动包名**

```bash
adb shell dumpsys package | grep -B2 BOOT_COMPLETED | grep -oE 'com\.[a-zA-Z0-9_.]+' | sort -u
```

3. **拿到运行中的服务**

```bash
adb shell dumpsys activity services | grep -oE '[a-zA-Z0-9_.]+/[a-zA-Z0-9_.$]+' | sort -u
```

4. **补齐中文名**：把 `_template.json` 复制成 `<vendor>_<soc>_<region>.json`，逐条填 `name`。
   名字不知道怎么写？用 `adb shell pm dump <包名> | grep -i label` 或直接判断（游戏/影院/音乐多是预装推广）。

5. **判定 policy**：先在电视上 `pm disable-user --user 0 <包名>` 试，确认不影响使用再写 `bloat`/`optional`；
   桌面、`system_server`、`tcl_system_server`、安装器、权限管理、`systemui` 一律 `avoid`。

6. 提交 PR，文件放 `adapters/` 即可，无需改代码、**也不需要重新打包 exe**。

## 调试

```bash
curl "http://127.0.0.1:8777/api/adapter?token=你的口令"
```

返回 `matched`（命中的适配器 id）、`packages`（映射表）、`available`（仓库里所有适配器）。

> 适配器的改动**不影响任何功能**，只影响"显示成什么名字"和"标签颜色"。
> 真正禁用仍然要显式执行 `pm disable-user`。
