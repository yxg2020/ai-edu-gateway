#!/bin/bash
# ============================================================
# AI教育网关 - Ubuntu VM内一键部署脚本
# 在PVE的Ubuntu虚拟机里运行
#
# 用法: (在Ubuntu里) 
#   curl -sL https://raw.githubusercontent.com/yxg2020/ai-edu-gateway/main/pve-deploy/pve-setup-ubuntu.sh | bash
#   或: scp 这个脚本到Ubuntu，然后 bash pve-setup-ubuntu.sh
# ============================================================

set -e

echo "=========================================="
echo "  AI教育网关 - Ubuntu AI服务部署"
echo "=========================================="

# ---------- 检查环境 ----------
if [ "$EUID" -ne 0 ]; then
    echo "请用root或sudo运行"
    exit 1
fi

UBUNTU_IP=$(hostname -I | awk '{print $1}')
OPENWRT_IP="${1:-192.168.100.1}"   # 默认OpenWrt的LAN IP

echo "📡 Ubuntu IP: $UBUNTU_IP"
echo "🔗 OpenWrt IP: $OPENWRT_IP"
echo ""

# ---------- 1. 系统更新 ----------
echo "[1/8] 更新系统包..."
apt-get update -qq && apt-get upgrade -y -qq
echo "  ✅ 系统更新完成"

# ---------- 2. 安装Python依赖 ----------
echo "[2/8] 安装Python和基础工具..."
apt-get install -y -qq python3 python3-pip python3-venv git curl wget nginx 2>&1 | tail -2
pip3 install --quiet --upgrade pip 2>&1 | tail -1
echo "  ✅ Python安装完成"

# ---------- 3. 创建项目目录 ----------
echo "[3/8] 创建AI网关目录..."
mkdir -p /opt/ai-gateway/{models,logs,config,data}
chmod -R 755 /opt/ai-gateway
echo "  ✅ 目录创建完成"

# ---------- 4. 安装Python库 ----------
echo "[4/8] 安装Python依赖库..."
pip3 install --quiet gradio pandas requests llama-cpp-python mcp 2>&1 | tail -1

# 确认gradio可用
python3 -c "import gradio; print(f'  Gradio版本: {gradio.__version__}')"
python3 -c "import pandas; print(f'  Pandas版本: {pd.__version__}')" 2>/dev/null || python3 -c "import pandas; print('  Pandas已安装')"
echo "  ✅ Python库安装完成"

# ---------- 5. 下载本地大模型 ----------
echo "[5/8] 下载Qwen2.5-3B本地大模型..."
MODEL_FILE="/opt/ai-gateway/models/qwen2.5-3b-q4.gguf"

if [ -f "$MODEL_FILE" ] && [ $(stat -c%s "$MODEL_FILE") -gt 1000000000 ]; then
    echo "  模型已存在，跳过下载（大小: $(du -h $MODEL_FILE | cut -f1)）"
else
    echo "  正在下载模型（约1.9GB，可能需要5-10分钟）..."
    wget -q --show-progress \
        "https://huggingface.co/bartowski/Qwen2.5-3B-Instruct-GGUF/resolve/main/Qwen2.5-3B-Instruct-Q4_K_M.gguf" \
        -O "$MODEL_FILE" 2>&1
    
    if [ -f "$MODEL_FILE" ]; then
        echo "  ✅ 模型下载完成: $(du -h $MODEL_FILE | cut -f1)"
    else
        echo "  ⚠️ 模型下载失败，AI报告将使用规则引擎（不影响其他功能）"
    fi
fi

# ---------- 6. 部署AI网关代码 ----------
echo "[6/8] 部署AI网关代码..."

# 从本地的代码目录复制（如果是手动scp）
if [ -d "/root/ai-edu-gateway" ]; then
    cp -r /root/ai-edu-gateway/*.py /opt/ai-gateway/ 2>/dev/null || true
fi

# 从GitHub下载（如果有仓库）
# wget -q https://raw.githubusercontent.com/yxg2020/ai-edu-gateway/main/app.py -O /opt/ai-gateway/app.py 2>/dev/null || true

# 生成OpenWrt数据拉取配置
cat > /opt/ai-gateway/config/settings.json << CONFIGEOF
{
    "openwrt_ip": "$OPENWRT_IP",
    "traffic_api_url": "http://$OPENWRT_IP/cgi-bin/traffic.json",
    "dns_api_url": "http://$OPENWRT_IP/cgi-bin/dns_stats.json",
    "model_path": "/opt/ai-gateway/models/qwen2.5-3b-q4.gguf",
    "data_dir": "/opt/ai-gateway/data/",
    "log_dir": "/opt/ai-gateway/logs/",
    "refresh_interval_seconds": 30
}
CONFIGEOF
echo "  配置文件已生成"

# ---------- 7. 配置systemd服务 ----------
echo "[7/8] 配置开机自启服务..."

cat > /etc/systemd/system/ai-gateway.service << 'SERVICEOF'
[Unit]
Description=AI教育网关 - 家庭网络流量AI分析服务
After=network.target
Wants=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/opt/ai-gateway
ExecStart=/usr/bin/python3 /opt/ai-gateway/app.py
Restart=always
RestartSec=10
StandardOutput=append:/opt/ai-gateway/logs/app.log
StandardError=append:/opt/ai-gateway/logs/app.log

[Install]
WantedBy=multi-user.target
SERVICEOF

systemctl daemon-reload
systemctl enable ai-gateway.service
echo "  ✅ 服务已配置为开机自启"

# ---------- 8. 启动 ----------
echo "[8/8] 启动AI网关服务..."
systemctl start ai-gateway.service

sleep 5
if systemctl is-active --quiet ai-gateway.service; then
    echo "  ✅ AI网关已启动"
else
    echo "  ⚠️ 启动失败，查看日志: journalctl -u ai-gateway.service -n 30"
fi

# ---------- 完成 ----------
echo ""
echo "=========================================="
echo "  🎉 AI教育网关部署完成！"
echo "=========================================="
echo ""
echo "  📡 Ubuntu IP:       $UBUNTU_IP"
echo "  🌐 AI网关界面:     http://$UBUNTU_IP:7871"
echo "  🔗 OpenWrt地址:    http://$OPENWRT_IP"
echo ""
echo "  常用命令:"
echo "    查看状态:  systemctl status ai-gateway.service"
echo "    重启服务:  systemctl restart ai-gateway.service"
echo "    查看日志:  tail -f /opt/ai-gateway/logs/app.log"
echo ""
echo "  在OpenWrt上还需要安装nDPI，详见配套脚本 openwrt-setup.sh"
echo "=========================================="
