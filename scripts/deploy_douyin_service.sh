#!/bin/bash
# 抖音 Cookie 服务部署脚本

echo "=== 抖音 Cookie 服务部署 ==="

# 1. 安装系统依赖
echo "[1/5] 安装系统依赖..."
apt-get update && apt-get install -y \
    wget \
    gnupg \
    curl \
    ca-certificates \
    fonts-liberation \
    libasound2 \
    libatk-bridge2.0-0 \
    libatk1.0-0 \
    libatspi2.0-0 \
    libcups2 \
    libdbus-1-3 \
    libdrm2 \
    libgbm1 \
    libgtk-3-0 \
    libnspr4 \
    libnss3 \
   -xcb libx111 \
    libxcb1 \
    libxcomposite1 \
    libxcursor1 \
    libxdamage1 \
    libxext6 \
    libxfixes3 \
    libxi6 \
    libxrandr2 \
    libxrender1 \
    libxss1 \
    libxtst6 \
    xdg-utils

# 2. 安装 Python 和 pip
echo "[2/5] 安装 Python..."
if ! command -v python3 &> /dev/null; then
    apt-get install -y python3 python3-pip
fi

# 3. 安装 Playwright
echo "[3/5] 安装 Playwright..."
pip3 install playwright
playwright install chromium

# 4. 安装 Python 依赖
echo "[4/5] 安装 Python 依赖..."
pip3 install \
    fastapi \
    uvicorn \
    pydantic \
    python-multipart

# 5. 启动服务
echo "[5/5] 启动服务..."

# 创建启动脚本
cat > /root/start_douyin_service.sh << 'EOF'
#!/bin/bash
cd /root
nohup python3 scripts/douyin_cookie_service.py > /root/douyin_service.log 2>&1 &
echo "服务已启动"
EOF

chmod +x /root/start_douyin_service.sh

# 启动服务
nohup python3 /root/scripts/douyin_cookie_service.py > /root/douyin_service.log 2>&1 &

echo "=== 部署完成 ==="
echo "服务地址: http://117.72.207.52:8000"
echo "API 端点: http://117.72.207.52:8000/api/douyin/cookies"
echo ""
echo "查看日志: tail -f /root/douyin_service.log"
