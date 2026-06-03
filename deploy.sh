#!/bin/bash
# ============================================================
# AI教育网关 — 一键部署脚本
# 适用于树莓派5 / x86软路由 / RK3588开发板
# Ubuntu Server 24.04 LTS 环境
# ============================================================

set -e

echo "=========================================="
echo "  AI教育网关 一键部署脚本 v1.0"
echo "=========================================="

# ---------- 检查环境 ----------
OS="$(lsb_release -ds 2>/dev/null || cat /etc/os-release | grep PRETTY_NAME | cut -d= -f2)"
ARCH="$(uname -m)"
echo "系统: $OS"
echo "架构: $ARCH"

# ---------- 安装基础依赖 ----------
echo ""
echo "[1/6] 安装系统依赖..."
apt-get update -qq
apt-get install -y -qq docker.io docker-compose git curl wget python3 python3-pip \
    bridge-utils iptables net-tools 2>&1 | tail -1

# ---------- 下载模型 ----------
echo ""
echo "[2/6] 下载本地大模型 (Qwen2.5-3B-Q4)..."
mkdir -p /opt/models
if [ ! -f /opt/models/qwen2.5-3b-q4.gguf ]; then
    wget -q --show-progress \
        https://huggingface.co/bartowski/Qwen2.5-3B-Instruct-GGUF/resolve/main/Qwen2.5-3B-Instruct-Q4_K_M.gguf \
        -O /opt/models/qwen2.5-3b-q4.gguf
fi
echo "  模型就绪: $(ls -lh /opt/models/qwen2.5-3b-q4.gguf | awk '{print $5}')"

# ---------- 安装llama.cpp ----------
echo ""
echo "[3/6] 安装llama.cpp..."
pip install llama-cpp-python -q 2>&1 | tail -1
pip install mcp gradio pandas -q 2>&1 | tail -1

# ---------- 创建AI网关代码 ----------
echo ""
echo "[4/6] 部署AI教育网关代码..."
mkdir -p /opt/ai-gateway

# 部署Gradio Web
cat > /opt/ai-gateway/requirements.txt << 'EOF'
gradio>=5.0
pandas
llama-cpp-python>=0.2.0
mcp
EOF

# ---------- 创建MCP服务器 ----------
cat > /opt/ai-gateway/traffic_mcp_server.py << 'MCPEOF'
"""
AI教育网关 MCP Server
通过named pipe读取OpenWrt的nDPI流量数据
暴露给Hermes Agent调用
"""
import json, os, subprocess
from mcp.server import Server
from mcp.server.models import InitializationOptions
import mcp.server.stdio

TRAFFIC_LOG = "/var/log/ai-gateway/traffic.log"
os.makedirs(os.path.dirname(TRAFFIC_LOG), exist_ok=True)

app = Server("ai-edu-gateway")

@app.list_tools()
async def list_tools():
    return [
        {
            "name": "get_live_traffic",
            "description": "获取家庭网络实时流量分布（最后20条记录）",
            "inputSchema": {"type": "object", "properties": {}},
        },
        {
            "name": "get_device_list",
            "description": "获取当前在线设备列表",
            "inputSchema": {"type": "object", "properties": {}},
        },
        {
            "name": "block_app",
            "description": "封禁某个应用",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "app_name": {"type": "string"},
                    "duration_minutes": {"type": "integer", "default": 60}
                },
                "required": ["app_name"]
            },
        },
        {
            "name": "generate_report",
            "description": "生成AI上网分析报告",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "device_ip": {"type": "string"}
                },
                "required": ["device_ip"]
            },
        },
    ]

@app.call_tool()
async def call_tool(name, arguments):
    if name == "get_live_traffic":
        if os.path.exists(TRAFFIC_LOG):
            data = subprocess.run(
                ["tail", "-20", TRAFFIC_LOG],
                capture_output=True, text=True
            ).stdout
            return {"result": data or "暂无数据"}
        return {"result": "日志文件不存在，请确认nDPI已运行"}
    
    elif name == "get_device_list":
        arp = subprocess.run(
            ["arp", "-a"], capture_output=True, text=True
        ).stdout
        return {"result": arp}
    
    elif name == "block_app":
        app_name = arguments["app_name"]
        # 调用OpenWrt iptables添加规则
        result = subprocess.run(
            ["iptables", "-A", "FORWARD", "-m", "ndpi", "--proto", app_name, "-j", "DROP"],
            capture_output=True, text=True
        )
        if result.returncode == 0:
            return {"result": f"已封禁 {app_name}"}
        return {"error": f"封禁失败: {result.stderr}"}
    
    elif name == "generate_report":
        return {"result": "报告将异步生成，请稍后查看"}

async def main():
    async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
        await app.run(
            read_stream, write_stream,
            InitializationOptions(
                server_name="ai-edu-gateway",
                server_version="0.1.0",
            ),
        )

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
MCPEOF

# ---------- 创建启动脚本 ----------
cat > /opt/ai-gateway/start.sh << 'STARTEOF'
#!/bin/bash
# 启动AI教育网关所有组件
echo "启动AI教育网关..."

# 1. 启动nDPI流量监控（OpenWrt环境）
if command -v ndpi &> /dev/null; then
    ndpistat --interface br-lan --output /var/log/ai-gateway/traffic.log &
    echo "  [OK] nDPI 已启动"
fi

# 2. 启动MCP服务器（后台）
cd /opt/ai-gateway
python3 traffic_mcp_server.py &
echo "  [OK] MCP Server 已启动"

# 3. 启动Gradio Web界面
cd /root/ai-edu-gateway
python3 app.py &
echo "  [OK] Gradio Web 已启动 (http://$(hostname -I | awk '{print $1}'):7871)"

echo ""
echo "所有组件已启动！"
echo "  Web界面: http://$(hostname -I | awk '{print $1}'):7871"
echo "  Hermes MCP: 标准输入输出"
STARTEOF
chmod +x /opt/ai-gateway/start.sh

# ---------- 配置OpenWrt ----------
echo ""
echo "[5/6] 配置网络层..."
# 配置透明网桥模式
cat > /etc/config/network << 'NETEOF'
config interface 'loopback'
    option ifname 'lo'
    option proto 'static'
    option ipaddr '127.0.0.1'
    option netmask '255.0.0.0'

config globals 'globals'
    option ula_prefix 'fd00::/48'

# WAN口接光猫
config interface 'wan'
    option ifname 'eth0'
    option proto 'dhcp'

# LAN口接家庭路由器
config interface 'lan'
    option ifname 'eth1'
    option proto 'static'
    option ipaddr '192.168.100.1'
    option netmask '255.255.255.0'
    option dns '114.114.114.114 8.8.8.8'
NETEOF

# ---------- 完成 ----------
echo ""
echo "[6/6] 部署完成!"
echo "=========================================="
echo ""
echo "  设备部署位置: 光猫 → AI教育网关 → 家庭路由器"
echo ""
echo "  命令:"
echo "    启动全部:  sudo /opt/ai-gateway/start.sh"
echo "    查看日志:  tail -f /var/log/ai-gateway/traffic.log"
echo "    管理界面:  http://$(hostname -I | awk '{print $1}'):7871"
echo ""
echo "=========================================="
