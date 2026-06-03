# AI教育网关 — OpenWrt + Hermes + 本地大模型融合方案

## 核心思路
将"基于大模型智慧教育管家"项目落地为：
**家庭网络流量管理硬件设备 + AI教育管家**

## 三层架构
| 层 | 技术 | 职责 |
|---|---|---|
| 🌐 网络层 | OpenWrt + nDPI | 流量识别、应用分类、iptables管控 |
| 🧠 AI服务层 | Qwen2.5-3B + llama.cpp | 行为分析、AI报告生成、策略推荐 |
| 🔌 能力层 | Hermes MCP Server | 暴露流量管控API给AI Agent |
| 🖥️ 展示层 | Gradio Web | 家长管理界面、数据可视化 |

## 硬件选型
- 快速原型: 树莓派5 8GB + USB千兆网卡 (~800元)
- 实用部署: x86软路由 N100/8GB/双2.5G网口 (~1000元)
- 量产方案: RK3588定制板 4GB/32GB/3网口/WiFi6 (~500元BOM)

## 部署步骤
1. 硬件装Ubuntu Server / OpenWrt
2. 运行 `bash /root/projects/ai-edu-gateway/deploy.sh`
3. 浏览器访问 `http://设备IP:7871`

## 部署拓扑
光猫 → [AI教育网关 WAN口] → [LAN口] → 家庭路由器 → 各设备

## 代码位置
- `/root/projects/ai-edu-gateway/app.py` - Gradio Web界面
- `/root/projects/ai-edu-gateway/deploy.sh` - 一键部署脚本
- `/root/projects/ai-edu-gateway/traffic_mcp_server.py` - MCP服务器
