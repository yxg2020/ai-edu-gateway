#!/bin/bash
# ============================================================
# AI教育网关 - PVE一键部署脚本
# 在N100 Proxmox VE上自动创建
#   VM1: iStoreOS/OpenWrt (路由器 + nDPI)
#   VM2: Ubuntu Server (AI分析引擎 + Gradio Web)
#
# 用法: 在PVE的shell里运行:
#   wget -qO- http://你的IP/pve-create-vms.sh | bash
#   或: chmod +x pve-create-vms.sh && ./pve-create-vms.sh
# ============================================================

set -e

# ---------- 配置参数 ----------
STORAGE="local-lvm"          # PVE存储池名，一般local-lvm或local
BRIDGE_WAN="vmbr0"           # WAN口网桥（接光猫）
BRIDGE_LAN="vmbr1"           # LAN口网桥（接家庭内网）
UBUNTU_ISO="ubuntu-24.04-live-server-amd64.iso"
ISTORE_IMG="istoreos-22.03.6-*.img.gz"
DISK_SIZE_VM1="4"            # OpenWrt磁盘大小(GB)
DISK_SIZE_VM2="32"           # Ubuntu磁盘大小(GB)
MEM_VM1="1024"               # OpenWrt内存(MB)
MEM_VM2="6144"               # Ubuntu内存(MB) - 6GB够跑大模型
CORE_VM1="2"                 # OpenWrt CPU核心
CORE_VM2="4"                 # Ubuntu CPU核心
VM1_ID="200"                 # OpenWrt VM ID
VM2_ID="201"                 # Ubuntu VM ID
AI_GATEWAY_REPO="https://raw.githubusercontent.com/yxg2020/ai-edu-gateway/main"
# 注意：上面的repo需要你先创建，或者临时用本地路径

echo "=========================================="
echo "  AI教育网关 - PVE一键部署"
echo "=========================================="
echo ""

# ---------- 检查PVE环境 ----------
if [ ! -f /usr/bin/pvesh ]; then
    echo "❌ 这不是Proxmox VE环境！请在PVE宿主机的shell里运行。"
    exit 1
fi

echo "✅ PVE环境检测通过"
echo ""

# ---------- 第1步：下载iStoreOS镜像 ----------
echo "[1/5] 下载iStoreOS镜像..."
ISTORE_ISO="/var/lib/vz/template/iso/istoreos.img.gz"
if [ ! -f "$ISTORE_ISO" ]; then
    wget -q --show-progress \
        https://archive.istoreos.com/istoreos/22.03.6/x86_64/istoreos-22.03.6-20250315-x86-64-generic-squashfs-combined.img.gz \
        -O "$ISTORE_ISO"
    echo "  iStoreOS镜像下载完成"
else
    echo "  iStoreOS镜像已存在，跳过"
fi

# ---------- 第2步：下载Ubuntu Server镜像 ----------
echo "[2/5] 下载Ubuntu Server 24.04镜像..."
UBUNTU_ISO_PATH="/var/lib/vz/template/iso/$UBUNTU_ISO"
if [ ! -f "$UBUNTU_ISO_PATH" ]; then
    wget -q --show-progress \
        https://releases.ubuntu.com/24.04/ubuntu-24.04.2-live-server-amd64.iso \
        -O "$UBUNTU_ISO_PATH"
    echo "  Ubuntu镜像下载完成"
else
    echo "  Ubuntu镜像已存在，跳过"
fi

# ---------- 第3步：创建VM1 (iStoreOS/OpenWrt) ----------
echo "[3/5] 创建iStoreOS虚拟机 (VM ID: $VM1_ID)..."

# 如果已存在则删除
qm stop $VM1_ID 2>/dev/null || true
qm destroy $VM1_ID 2>/dev/null || true

# 创建VM
qm create $VM1_ID \
    --name "iStoreOS-Router" \
    --memory $MEM_VM1 \
    --cores $CORE_VM1 \
    --net0 virtio,bridge=$BRIDGE_WAN \
    --net1 virtio,bridge=$BRIDGE_LAN \
    --ostype l26 \
    --agent 1

# 导入磁盘
# iStoreOS镜像需要解压后转为PVE磁盘格式
gunzip -c "$ISTORE_ISO" > /tmp/istoreos.img
qm importdisk $VM1_ID /tmp/istoreos.img $STORAGE
rm -f /tmp/istoreos.img
qm set $VM1_ID --scsihw virtio-scsi-pci --scsi0 ${STORAGE}:vm-${VM1_ID}-disk-0

# 设置启动顺序
qm set $VM1_ID --boot c --bootdisk scsi0

echo "  ✅ iStoreOS虚拟机创建完成"
echo "  ⚠️ 重要：请检查 /etc/pve/qemu-server/${VM1_ID}.conf"
echo "     确认 net0 对应的是接光猫的网口"
echo ""

# ---------- 第4步：创建VM2 (Ubuntu AI服务) ----------
echo "[4/5] 创建Ubuntu AI服务虚拟机 (VM ID: $VM2_ID)..."

qm stop $VM2_ID 2>/dev/null || true
qm destroy $VM2_ID 2>/dev/null || true

qm create $VM2_ID \
    --name "AI-Gateway-Service" \
    --memory $MEM_VM2 \
    --cores $CORE_VM2 \
    --net0 virtio,bridge=$BRIDGE_LAN \
    --ostype l26 \
    --agent 1 \
    --cdrom ${STORAGE}:iso/$UBUNTU_ISO \
    --scsihw virtio-scsi-pci \
    --scsi0 ${STORAGE}:$DISK_SIZE_VM2

echo "  ✅ Ubuntu虚拟机创建完成"
echo ""

# ---------- 第5步：输出后续操作指南 ----------
echo "[5/5] 部署完成！后续操作："
echo "=========================================="
echo ""
echo "  1. 启动iStoreOS路由器:"
echo "     qm start $VM1_ID"
echo "     # 然后通过VNC或用浏览器访问 http://PVE_IP:8006"
echo "     # 进入iStoreOS的Web界面设置WAN/LAN"
echo ""
echo "  2. 安装Ubuntu:"
echo "     qm start $VM2_ID"
echo "     # 通过VNC完成Ubuntu安装（选默认即可）"
echo "     # 重要：安装时创建用户名为 ubuntu"
echo ""
echo "  3. 在Ubuntu里部署AI网关:"
echo "     ssh ubuntu@192.168.x.xxx"
echo "     # 然后运行："
echo "     curl -s https://raw.githubusercontent.com/yxg2020/ai-edu-gateway/main/pve-deploy/pve-setup-ubuntu.sh | bash"
echo ""
echo "  4. 网络接线:"
echo "     光猫 → N100 eth0(VM1 WAN) → N100 eth1(VM1 LAN) → 家里交换机/路由器(AP模式)"
echo ""
echo "  5. 访问:"
echo "     iStoreOS管理界面: http://192.168.100.1"
echo "     AI网关界面:       http://ubuntu虚拟机IP:7871"
echo "=========================================="
echo ""
echo "⚠️ 重要提醒：创建完成后，需要手动做两件事："
echo "  1. 在PVE Web界面 → VM1的硬件 → 直通真实的物理网口给VM1"
echo "  2. 确保vmbr0（WAN）和vmbr1（LAN）分别绑定到不同的物理网口"
