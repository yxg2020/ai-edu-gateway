# AI教育网关 — N100软路由PVE部署完全手册

## 买什么硬件

淘宝搜索 **"N100 软路由 双网口"**，推荐配置：
- CPU: Intel N100
- 内存: 8GB DDR4/DDR5
- 存储: 128GB NVMe SSD
- 网口: 双 Intel i226-V 2.5G
- 价格约 800-1000 元

品牌参考：倍控、畅网、零刻EQ系列

到手就一个巴掌大的金属盒子 + 电源，开箱即用。

## 接线方式

```
光猫 ──网线──→ N100软路由(左网口 eth0)
                     │
                     ├── N100软路由(右网口 eth1) ──→ 家中WiFi路由器(AP模式)
                     │
                     └── 其他有线设备
```

**关键**：
- eth0（靠近电源口那个一般是WAN）→ 接光猫
- eth1（另一个网口）→ 接家里原来的路由器，**把原路由器设成AP模式**（关闭DHCP，只发WiFi）
- 家里原来的路由器如果搞不懂AP模式，可以先把它的LAN口接到N100的LAN口，关掉原路由器的DHCP

## 软件部署步骤

### 第1步：给N100装Proxmox VE（约1小时）

1. 下载 [Proxmox VE ISO](https://www.proxmox.com/en/downloads)
2. 用 Rufus/Ventoy 写进U盘
3. N100插上键盘显示器U盘，开机按F2/F7进BIOS
4. 设U盘为第一启动项
5. 按PVE安装向导：
   - 目标磁盘：选你的NVMe SSD
   - 密码：设好记住
   - 管理网络：选 eth0 那个网口
   - IP地址：可以设 192.168.1.10（临时）
6. 装好后拔U盘重启
7. 浏览器访问 `https://你设的IP:8006`（用户 root，密码就是你设的）

### 第2步：配置PVE网络（约15分钟）

PVE装好后，需要创建两个网桥：

**在PVE shell里运行（或Web界面 → 节点 → 网络）：**

```bash
# 查看网口名称
ip link show
# 通常看到 enp1s0(eth0) 和 enp2s0(eth1)

# 创建WAN网桥（接光猫）
cat > /etc/network/interfaces.d/vmbr0 << 'EOF'
auto vmbr0
iface vmbr0 inet manual
    bridge-ports enp1s0
    bridge-stp off
    bridge-fd 0
EOF

# 创建LAN网桥（接家中网络）
cat > /etc/network/interfaces.d/vmbr1 << 'EOF'
auto vmbr1
iface vmbr1 inet static
    address 192.168.100.1/24
    bridge-ports enp2s0
    bridge-stp off
    bridge-fd 0
EOF

# 重启网络生效
systemctl restart networking
```

### 第3步：运行一键创建VM脚本

把 `pve-create-vms.sh` 传到PVE上运行，或直接在PVE shell里跑：

```bash
# 如果脚本在本地，scp到PVE
scp pve-create-vms.sh root@PVE_IP:/root/

# 然后在PVE shell里
cd /root
chmod +x pve-create-vms.sh
./pve-create-vms.sh
```

这个脚本自动完成：
- 下载 iStoreOS 镜像
- 下载 Ubuntu 24.04 镜像
- 创建 VM1（iStoreOS：1GB内存/2核/4GB磁盘）
- 创建 VM2（Ubuntu：6GB内存/4核/32GB磁盘）

### 第4步：配置 iStoreOS 虚拟机（VM1）

1. 在PVE Web界面 → VM1 → 启动
2. 打开VM1的VNC控制台
3. iStoreOS启动后，按回车进入命令行
4. 运行：

```bash
# 设置LAN口IP
uci set network.lan.ipaddr='192.168.100.1'
uci set network.lan.gateway='192.168.100.1'
uci commit network
/etc/init.d/network restart

# 用浏览器访问 http://192.168.100.1
# 进iStoreOS Web界面
# 确认：WAN口能获取到IP（接光猫）LAN口是 192.168.100.1
```

5. **在iStoreOS里安装nDPI**：
   进入iStoreOS Web → 系统 → 软件包 → 搜索 ndpi → 安装 ndpi、ndpi-proto、ndpistat

6. **运行OpenWrt配置脚本**：
```bash
# SSH进iStoreOS（ssh root@192.168.100.1）
# 然后运行openwrt-setup.sh
# 或者手动执行下面的命令：

# 安装必要软件
opkg update
opkg install ndpi nginx curl jq

# 启动流量采集器
cat > /usr/bin/traffic-collect.sh << 'EOF'
#!/bin/sh
while true; do
    ndpistat -j > /tmp/traffic.json 2>/dev/null
    sleep 10
done
EOF
chmod +x /usr/bin/traffic-collect.sh
/usr/bin/traffic-collect.sh &

# 验证数据接口
curl http://127.0.0.1:8080/traffic.json
```

### 第5步：配置 Ubuntu 虚拟机（VM2）

1. 在PVE Web界面 → VM2 → 启动
2. 打开VNC控制台，安装Ubuntu：
   - 语言：English
   - 键盘：Chinese
   - 用户名：ubuntu
   - 密码：自己设一个
   - 安装OpenSSH Server ✅
3. 安装完成后重启，记下IP（ifconfig 看 eth0 的IP）

4. **SSH进Ubuntu，一键部署AI网关**：

```bash
ssh ubuntu@Ubuntu_IP

# 把部署脚本传过去或在Ubuntu里直接下载
# 如果用scp：从你的电脑
scp pve-setup-ubuntu.sh ubuntu@Ubuntu_IP:/home/ubuntu/

# 在Ubuntu里运行
sudo bash pve-setup-ubuntu.sh
```

这个脚本自动完成：
- 安装Python3/pip
- 安装gradio/pandas/llama-cpp-python/mcp
- 下载Qwen2.5-3B大模型（约1.9GB）
- 配置AI网关为系统服务（开机自启）
- 启动Web界面

### 第6步：验收

1. 浏览器打开 `http://Ubuntu_IP:7871`
2. 应该看到AI教育网关仪表盘
3. 数据源显示为 OpenWrt nDPI
4. 如果OpenWrt那边nDPI还没流量数据，系统会自动使用模拟数据

## 查看运行状态

```bash
# 查看AI网关服务
systemctl status ai-gateway.service
journalctl -u ai-gateway.service -n 50

# 查看OpenWrt流量数据（SSH进OpenWrt）
curl http://127.0.0.1:8080/traffic.json | jq .

# 重启AI网关
sudo systemctl restart ai-gateway.service

# 查看日志
tail -f /opt/ai-gateway/logs/app.log
```

## 常见问题

### Q: 家里原来的路由器怎么设AP模式？
进入原路由器Web管理界面 → 关闭DHCP服务器 → 网线插LAN口（不是WAN口）→ 重启。这样原路由器就变成了纯WiFi信号扩展器。

### Q: 我不想用PVE，直接装OpenWrt做底层行不行？
行。但建议PVE，因为PVE可以Web管理虚拟机。如果直接OpenWrt做底层，AI服务用LXC容器跑。

### Q: Qwen2.5-3B模型下载慢怎么办？
下载约1.9GB，取决于网络。如果太慢可以先用规则引擎模式（不加载模型照样跑），等模型下好了再重启服务。

### Q: 为什么仪表盘显示"暂无数据"？
因为OpenWrt还没安装完nDPI。这是正常的——AI网关会自动降级到模拟数据模式，不影响你体验界面。

## 文件清单

| 文件 | 位置 | 用途 |
|---|---|---|
| `app.py` | 最终在 `/opt/ai-gateway/app.py` | Gradio Web主程序 |
| `pve-create-vms.sh` | PVE宿主机上运行 | 一键创建两个虚拟机 |
| `pve-setup-ubuntu.sh` | Ubuntu VM里运行 | 安装AI网关环境 |
| `openwrt-setup.sh` | OpenWrt VM里运行 | 安装nDPI+HTTP接口 |
