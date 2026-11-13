# Docker 部署

镜像里跑的是**无界面版**：只有 Web 面板 + ADB 采集，没有托盘图标。
适合丢在 NAS / 小主机上常开，家里任何设备用浏览器打开面板。

- 镜像：`ghcr.io/knownothing20/tv-remote:latest`（也提供 `:v1.1.0` 这类版本标签）
- 端口：`8777`
- 架构：`linux/amd64`、`linux/arm64`（依赖发行版 `adb`）

> v1.7.2 起，GitHub Actions 只发布 Windows exe。已有 GHCR 镜像保留，但不会随新版本自动更新；需要最新代码时可自行 `docker build -t tv-remote .`。

## 一句话启动

```bash
docker run -d --name tv-remote \
  -p 8777:8777 \
  -e TVREMOTE_DEVICE=192.168.1.10:5555 \
  -e TVREMOTE_HOST=0.0.0.0 \
  -v $(pwd)/local:/app/local \
  --restart unless-stopped \
  ghcr.io/knownothing20/tv-remote:latest
```

打开 `http://<宿主机IP>:8777`。

## docker compose

```bash
mkdir -p tv-remote && cd tv-remote
curl -fsSLO https://raw.githubusercontent.com/knownothing20/tv-remote/main/docker-compose.yml
# 改里面的 TVREMOTE_DEVICE 为你的电视地址
docker compose up -d
```

## 环境变量

| 变量 | 默认 | 说明 |
|---|---|---|
| `TVREMOTE_DEVICE` | — | 电视 ADB 地址，如 `192.168.1.10:5555` |
| `TVREMOTE_HOST` | `127.0.0.1` | 容器内必须是 `0.0.0.0` |
| `TVREMOTE_PORT` | `8777` | 面板端口 |
| `TVREMOTE_TOKEN` | 空 | 设置后所有请求需带 `?token=xxx` 或 `X-Auth-Token` 头 |
| `TVREMOTE_POLL` | `5` | 状态轮询秒数 |
| `TVREMOTE_ADB` | 自动 | 指定 adb 可执行文件路径 |

## adb 授权（关键）

容器里的 adb 对电视来说是**一台新电脑**，第一次连接时电视会弹「允许 USB 调试吗？」，
勾选「一律允许」即可。若电视上不方便操作，可以复用宿主机的密钥：

```yaml
volumes:
  - ${HOME}/.android:/root/.android:ro
```

## 手机 / iPad 访问

面板默认开启隐私脱敏，IP 与序列号是打码的；如暴露到整个局域网，建议同时设置
`TVREMOTE_TOKEN`，访问时带上参数：

```
http://192.168.1.20:8777/?token=你的口令
```

> 不要把面板直接暴露到公网。它没有账号体系，仅有可选的口令校验。

## 常见问题

**面板显示「离线」**：容器内 `adb connect <IP>:5555` 失败。进容器排查：

```bash
docker exec -it tv-remote adb connect 192.168.1.10:5555
docker exec -it tv-remote adb devices
```

**电视重启后离线**：电视关闭了网络调试或换了 IP。面板每次请求失败会自动重连一次，
IP 变化时改 `TVREMOTE_DEVICE` 并重启容器。

**ARM NAS 构建失败**：确保用的是 `:latest` 多架构镜像；自行构建时 base 镜像与 `adb`
都需要对应架构（Dockerfile 已优先使用发行版 `adb`）。

**截图存哪**：容器内 `/app/local/shots`，通过 `-v ./local:/app/local` 映射到宿主机。
