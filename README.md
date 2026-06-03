# AI教育网关

N100双网口软路由 + OpenWrt(nDPI) + Qwen2.5-3B本地大模型 + Gradio Web

**家庭网络AI流量管理与智慧教育管家**

## 整体架构

```
光猫 ──→ N100 eth0(WAN) ── PVE虚拟机 ──→ eth1(LAN) ──→ 家中WiFi(AP模式)
             │                                 │
         ┌───┴───┐                       [各设备上网]
         │ VM1:  │
         │OpenWrt│ ── nDPI识别抖音/王者/学而思 → HTTP JSON接口(:8080)
         └───┬───┘
             │ 虚拟网桥通信
         ┌───┴───┐
         │ VM2:  │
         │Ubuntu │ ── 拉数据 → Qwen2.5-3B分析 → Gradio Web(:7871)
         └───────┘
```

## 项目文件

| 文件 | 用途 |
|---|---|
| `app.py` | Gradio Web主程序（AI分析引擎+家长看板） |
| `pve-deploy/pve-create-vms.sh` | PVE宿主机上运行，一键创建两个VM |
| `pve-deploy/pve-setup-ubuntu.sh` | Ubuntu VM里运行，装AI环境 |
| `pve-deploy/openwrt-setup.sh` | OpenWrt VM里运行，装nDPI |
| `deploy.sh` | 单机部署（备用） |

## 硬件需求

- N100双网口软路由（8GB RAM+128GB SSD），淘宝800-1000元
- U盘一个（8GB+）装PVE安装盘

## 快速开始

详见 [pve-deploy/README.md](pve-deploy/README.md)
