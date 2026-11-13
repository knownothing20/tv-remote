# tv-remote · 无界面服务镜像（Web 面板 + ADB 采集）
# 构建： docker build -t tv-remote .
# 运行： docker run -d -p 8777:8777 -e TVREMOTE_DEVICE=192.168.1.10:5555 tv-remote
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    ADB_MDNS=0 \
    TVREMOTE_HOST=0.0.0.0 \
    TVREMOTE_PORT=8777

# 优先用发行版 adb（amd64 / arm64 都有）；没有则回退官方 platform-tools（仅 amd64）
RUN set -eux; \
    apt-get update; \
    if apt-get install -y --no-install-recommends adb ca-certificates; then \
        echo "using distro adb"; \
    else \
        apt-get install -y --no-install-recommends curl unzip ca-certificates; \
        arch="$(dpkg --print-architecture)"; \
        if [ "$arch" != "amd64" ]; then echo "no adb available for $arch"; exit 1; fi; \
        curl -fsSL https://dl.google.com/android/repository/platform-tools-latest-linux.zip -o /tmp/pt.zip; \
        unzip -q /tmp/pt.zip -d /opt; \
        rm -f /tmp/pt.zip; \
        apt-get purge -y curl unzip; \
        apt-get autoremove -y; \
    fi; \
    rm -rf /var/lib/apt/lists/*

ENV PATH="/opt/platform-tools:${PATH}"

WORKDIR /app
COPY main.py ./
COPY src/ ./src/

VOLUME ["/app/local"]

EXPOSE 8777

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request;urllib.request.urlopen('http://127.0.0.1:8777/api/ping',timeout=4)"

CMD ["python", "main.py", "--headless"]
