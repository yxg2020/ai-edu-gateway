#!/bin/sh
# ============================================================
# AI教育网关 - OpenWrt/iStoreOS侧部署脚本
# 在OpenWrt的shell里运行 (通过SSH或VNC进入软路由)
#
# 用法:
#   1. ssh root@192.168.100.1
#   2. 复制脚本内容粘贴运行 或 wget执行
# ============================================================

echo "=========================================="
echo "  AI教育网关 - OpenWrt侧配置"
echo "=========================================="
echo ""

# ---------- 1. 更新opkg ----------
echo "[1/6] 更新软件源..."
opkg update 2>&1 | tail -1

# ---------- 2. 安装nDPI ----------
echo "[2/6] 安装nDPI (网络流量识别引擎)..."
opkg install ndpi ndpi-proto ndpistat ndpi-dev 2>&1 | tail -3

# 验证
if ndpistat -h 2>&1 | grep -q "usage"; then
    echo "  ✅ nDPI安装成功"
else
    echo "  ⚠️ nDPI安装可能有问题，检查: opkg list-installed | grep ndpi"
fi

# ---------- 3. 安装Web服务 ----------
echo "[3/6] 安装Web服务和工具..."
opkg install nginx uhttpd curl jq 2>&1 | tail -2
echo "  ✅ Web服务安装完成"

# ---------- 4. 配置nDPI自动启动 ----------
echo "[4/6] 配置nDPI自动采集..."

# 创建nDPI配置
cat > /etc/config/ndpi << 'NDPICONF'
config ndpi 'settings'
    option enabled '1'
    option interface 'br-lan'
    option polling_interval '10'
    option log_enabled '1'
    option log_file '/tmp/traffic.log'
    option log_format 'json'
NDPICONF

# 创建流量日志收集脚本（每秒采集nDPI数据写入JSON文件）
cat > /usr/bin/traffic-collect.sh << 'COLLECT'
#!/bin/sh
# AI教育网关 流量数据采集器
# 每10秒采集一次nDPI数据，输出为HTTP可访问的JSON

LOG_FILE="/tmp/traffic.json"
TMP_FILE="/tmp/traffic.tmp"

while true; do
    # 用ndpistat获取当前流量统计
    ndpistat -j 2>/dev/null > "$TMP_FILE" || echo '{"error":"ndpi not ready","devices":[]}' > "$TMP_FILE"
    
    # 同时获取DHCP设备列表（知道谁是谁）
    {
        echo "{"
        echo "  \"timestamp\": \"$(date '+%Y-%m-%d %H:%M:%S')\","
        echo "  \"traffic\": "
        cat "$TMP_FILE"
        echo ","
        echo "  \"dhcp_leases\": "
        cat /tmp/dhcp.leases 2>/dev/null | awk '{
            split($0, a, " ");
            if(length(a)>=4) printf "{\"mac\":\"%s\",\"ip\":\"%s\",\"name\":\"%s\"},", a[2], a[3], a[4]
        }' | sed 's/,$//' 
        echo "  []"
        echo "}"
    } > "$LOG_FILE" 2>/dev/null
    
    sleep 10
done
COLLECT
chmod +x /usr/bin/traffic-collect.sh

# ---------- 5. 配置HTTP API接口 ----------
echo "[5/6] 配置HTTP接口供Ubuntu侧拉取数据..."

# 创建uhttpd附加配置
cat > /etc/uhttpd.crtraffic << 'UHTTPDCONF'
config uhttpd 'traffic'
    list listen_http '0.0.0.0:8080'
    option home '/www/traffic'
    option index_page 'traffic.json'
    option rfc1918_filter '0'
    option cgi_prefix '/cgi-bin'
UHTTPDCONF

# 创建数据目录和静态文件
mkdir -p /www/traffic
ln -sf /tmp/traffic.json /www/traffic/traffic.json 2>/dev/null

# 创建CGI接口（备用方式）
mkdir -p /www/cgi-bin
cat > /www/cgi-bin/traffic << 'CGIEOF'
#!/bin/sh
echo "Content-Type: application/json"
echo ""
cat /tmp/traffic.json 2>/dev/null || echo '{"status":"waiting"}'
CGIEOF
chmod +x /www/cgi-bin/traffic

echo "  ✅ HTTP接口配置完成"

# ---------- 6. 配置开机自启 ----------
echo "[6/6] 配置开机自启..."

cat > /etc/init.d/ai-traffic-collect << 'INITEOF'
#!/bin/sh /etc/rc.common
START=99
STOP=10

start() {
    echo "启动AI教育网关-流量采集器..."
    /usr/bin/traffic-collect.sh &
    echo $! > /var/run/ai-traffic-collect.pid
}

stop() {
    echo "停止AI教育网关-流量采集器..."
    if [ -f /var/run/ai-traffic-collect.pid ]; then
        kill $(cat /var/run/ai-traffic-collect.pid) 2>/dev/null
        rm -f /var/run/ai-traffic-collect.pid
    fi
}

restart() {
    stop
    sleep 1
    start
}
INITEOF
chmod +x /etc/init.d/ai-traffic-collect
/etc/init.d/ai-traffic-colect enable

# ---------- 立即启动 ----------
echo ""
echo "启动所有服务..."
/etc/init.d/ai-traffic-collect start 2>/dev/null || /usr/bin/traffic-collect.sh &

# 重启uhttpd让配置生效
/etc/init.d/uhttpd restart 2>/dev/null

echo ""
echo "=========================================="
echo "  🎉 OpenWrt侧配置完成！"
echo "=========================================="
echo ""
echo "  流量数据接口:"
echo "    http://$(uci get network.lan.ipaddr 2>/dev/null || echo '192.168.100.1'):8080/traffic.json"
echo ""
echo "  验证方法:"
echo "    curl http://127.0.0.1:8080/traffic.json"
echo ""
echo "  接下来:"
echo "    1. 在Ubuntu侧确认AI网关能拉取到数据"
echo "    2. 浏览器打开 http://Ubuntu-IP:7871"
echo ""
echo "=========================================="
