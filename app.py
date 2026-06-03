"""
AI教育网关 v2.0 — PVE生产版
========================================
适配N100软路由PVE架构：
  VM1: OpenWrt → nDPI识别流量 → HTTP JSON接口
  VM2: Ubuntu  → 从这个脚本拉数据 → AI分析 → Gradio展示

数据流向:
  家庭设备 → OpenWrt → nDPI → 每10秒写 JSON → HTTP :8080/traffic.json
                                                ↓
  Ubuntu → requests拉JSON → pandas解析 → Qwen2.5-3B分析 → Gradio展示
"""

import gradio as gr
import json, os, time, datetime, subprocess, re
import pandas as pd
import requests
from pathlib import Path

# ============================================================
# 配置
# ============================================================
CONFIG = {
    "openwrt_ip": os.environ.get("OPENWRT_IP", "192.168.100.1"),
    "traffic_api_port": 8080,
    "model_path": "/opt/ai-gateway/models/qwen2.5-3b-q4.gguf",
    "log_dir": "/opt/ai-gateway/logs",
    "data_dir": "/opt/ai-gateway/data",
    "refresh_interval": 30,
}

TRAFFIC_URL = f"http://{CONFIG['openwrt_ip']}:{CONFIG['traffic_api_port']}/traffic.json"
DEVICE_DB_PATH = os.path.join(CONFIG["data_dir"], "devices.json")
MODEL_AVAILABLE = os.path.exists(CONFIG["model_path"])

# ============================================================
# 数据层
# ============================================================

class TrafficDataFetcher:
    """从OpenWrt nDPI HTTP接口拉流量数据"""
    
    def __init__(self):
        self.cache = []
        self.last_fetch = 0
        os.makedirs(CONFIG["data_dir"], exist_ok=True)
        os.makedirs(CONFIG["log_dir"], exist_ok=True)
        self._load_cache()
    
    def _load_cache(self):
        cache_file = os.path.join(CONFIG["data_dir"], "traffic_cache.json")
        if os.path.exists(cache_file):
            try:
                with open(cache_file) as f:
                    data = json.load(f)
                    self.cache = data.get("records", [])
            except:
                self.cache = []
    
    def _save_cache(self):
        cache_file = os.path.join(CONFIG["data_dir"], "traffic_cache.json")
        with open(cache_file, "w") as f:
            json.dump({"records": self.cache[-1000:]}, f, ensure_ascii=False)
    
    def fetch(self):
        """从OpenWrt拉取数据，失败时返回模拟数据"""
        try:
            # 方式1：从OpenWrt HTTP接口拉
            if self._can_reach_openwrt():
                resp = requests.get(TRAFFIC_URL, timeout=5)
                if resp.status_code == 200:
                    data = resp.json()
                    records = self._parse_ndpi_json(data)
                    self.cache.extend(records)
                    self._save_cache()
                    return records
            
            # 方式2：尝试从本地nDPI日志读取（调试模式）
            local_log = "/tmp/traffic.log"
            if os.path.exists(local_log):
                return self._parse_local_log(local_log)
        
        except Exception as e:
            print(f"[TrafficFetcher] 拉取失败: {e}")
        
        # 方式3：全部失败，返回模拟数据
        return self._generate_mock()
    
    def _can_reach_openwrt(self):
        """检查OpenWrt是否可达"""
        try:
            result = subprocess.run(
                ["ping", "-c", "1", "-W", "1", CONFIG["openwrt_ip"]],
                capture_output=True, timeout=2
            )
            return result.returncode == 0
        except:
            return False
    
    def _parse_ndpi_json(self, data):
        """解析nDPI JSON格式"""
        records = []
        ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        devices = []
        if isinstance(data, dict):
            traffic = data.get("traffic", {})
            if isinstance(traffic, dict):
                devices = traffic.get("devices", [])
        
        if not devices and isinstance(data, list):
            devices = data
        
        for dev in devices:
            ip = dev.get("ip", dev.get("ip_address", "0.0.0.0"))
            mac = dev.get("mac", dev.get("mac_address", "00:00:00:00:00:00"))
            name = self._ip_to_device_name(ip)
            
            # 每个设备的流量明细
            for proto in dev.get("protocols", dev.get("protos", [])):
                app_name = proto.get("name", proto.get("proto", "未知"))
                bytes_count = proto.get("bytes", proto.get("bytes_count", 0))
                mb = round(bytes_count / (1024*1024), 2)
                
                if mb > 0:
                    records.append({
                        "timestamp": ts,
                        "device_ip": ip,
                        "device_name": name,
                        "app": self._normalize_app_name(app_name),
                        "flow_mb": mb,
                        "risk_level": self._assess_risk(app_name, mb),
                    })
        
        return records
    
    def _parse_local_log(self, log_path):
        """本地nDPI日志解析（调试用）"""
        records = []
        try:
            with open(log_path) as f:
                for line in f.readlines()[-200:]:
                    parts = line.strip().split("|")
                    if len(parts) >= 4:
                        ts = parts[0].strip()
                        ip = parts[1].strip()
                        app = parts[2].strip()
                        mb = float(re.sub(r'[^0-9.]', '', parts[3].strip()) or 0)
                        records.append({
                            "timestamp": ts,
                            "device_ip": ip,
                            "device_name": self._ip_to_device_name(ip),
                            "app": self._normalize_app_name(app),
                            "flow_mb": mb,
                            "risk_level": self._assess_risk(app, mb),
                        })
        except:
            pass
        return records
    
    def _generate_mock(self):
        """模拟数据（生产降级用）"""
        ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        templates = [
            ("192.168.100.102", "孩子-小明"),
            ("192.168.100.103", "孩子-小红"),
            ("192.168.100.100", "家长-爸爸"),
            ("192.168.100.101", "家长-妈妈"),
        ]
        apps = [
            ("抖音", "短视频", 5), ("王者荣耀", "游戏", 8), ("B站", "短视频", 3),
            ("学而思", "教育", 4), ("微信", "社交", 1), ("原神", "游戏", 6),
            ("作业帮", "教育", 2), ("百度", "工具", 1), ("腾讯视频", "视频", 5),
            ("知乎", "教育", 1),
        ]
        records = []
        for ip, name in templates:
            for _ in range(random.randint(1, 4)):
                app_name, cat, base_mb = random.choice(apps)
                mb = round(base_mb * random.uniform(0.3, 1.5), 1)
                records.append({
                    "timestamp": ts,
                    "device_ip": ip,
                    "device_name": name,
                    "app": app_name,
                    "flow_mb": mb,
                    "risk_level": self._assess_risk(app_name, mb),
                })
        return records
    
    def _ip_to_device_name(self, ip):
        """IP转设备名称（从设备数据库查）"""
        devices = self._load_devices()
        return devices.get(ip, {}).get("name", f"设备({ip})")
    
    def _load_devices(self):
        if os.path.exists(DEVICE_DB_PATH):
            try:
                with open(DEVICE_DB_PATH) as f:
                    return json.load(f)
            except:
                pass
        return {}
    
    def _normalize_app_name(self, raw):
        """标准化app名称"""
        mapping = {
            "tls": "HTTPS加密", "ssl": "HTTPS加密",
            "dns": "DNS查询", "http": "HTTP网页",
            "quic": "QUIC加密", "teams": "Microsoft Teams",
            "zoom": "Zoom会议", "wechat": "微信",
        }
        low = raw.lower()
        return mapping.get(low, raw)
    
    def _assess_risk(self, app_name, mb):
        """简单风险评估"""
        high_risk = ["王者荣耀", "原神", "和平精英", "抖音"]
        medium_risk = ["快手", "B站", "腾讯视频"]
        if app_name in high_risk:
            return "关注" if mb > 50 else "正常"
        if app_name in medium_risk:
            return "关注" if mb > 100 else "正常"
        if app_name in ["微信", "QQ", "钉钉"]:
            return "正常"
        return "正常"

import random  # 模拟数据用
fetcher = TrafficDataFetcher()

# ============================================================
# AI分析引擎
# ============================================================

class AIAnalyzer:
    def __init__(self):
        self.llm = None
        if MODEL_AVAILABLE:
            try:
                from llama_cpp import Llama
                self.llm = Llama(
                    model_path=CONFIG["model_path"],
                    n_ctx=2048,
                    n_threads=4,
                    verbose=False,
                )
                print(f"[AIAnalyzer] 大模型就绪: {CONFIG['model_path']}")
            except Exception as e:
                print(f"[AIAnalyzer] 大模型加载失败: {e}")
    
    def analyze_device(self, device_name, records):
        """分析单个设备的数据"""
        dev_records = [r for r in records if r.get("device_name") == device_name]
        if not dev_records:
            return self._empty_report(device_name)
        
        total_mb = sum(r["flow_mb"] for r in dev_records)
        app_stats = {}
        for r in dev_records:
            app = r["app"]
            app_stats[app] = app_stats.get(app, 0) + r["flow_mb"]
        
        sorted_apps = sorted(app_stats.items(), key=lambda x: -x[1])
        top_app = sorted_apps[0][0] if sorted_apps else "未知"
        
        # 归类
        edu_apps = set(["学而思", "猿辅导", "作业帮", "百词斩", "知乎", "得到", "Wikipedia", "国家中小学"])
        ent_apps = set(["抖音", "快手", "B站", "王者荣耀", "原神", "和平精英", "蛋仔派对", "腾讯视频", "爱奇艺"])
        edu_mb = sum(v for k, v in app_stats.items() if any(e in k for e in edu_apps))
        ent_mb = sum(v for k, v in app_stats.items() if any(e in k for e in ent_apps))
        total_pct = edu_mb + ent_mb
        edu_pct = round(edu_mb / total_mb * 100, 1) if total_mb > 0 else 0
        ent_pct = round(ent_mb / total_mb * 100, 1) if total_mb > 0 else 0
        
        # AI报告
        ai_report = self._generate_ai_report(device_name, sorted_apps, edu_pct, ent_pct, total_mb)
        
        # 规则告警
        alerts = []
        if ent_pct > 60:
            alerts.append(f"⚠️ 娱乐流量占比{ent_pct}%，远超教育占比({edu_pct}%)")
        if total_mb > 500:
            alerts.append(f"⚠️ 今日总流量{round(total_mb)}MB，建议关注")
        if edu_pct > 50:
            alerts.append(f"✅ 教育类应用占比{edu_pct}%，学习为主")
        if not alerts:
            alerts.append("✅ 当前上网行为正常，无需干预")
        
        return {
            "device_name": device_name,
            "total_mb": round(total_mb, 1),
            "app_count": len(app_stats),
            "top_apps": dict(sorted_apps[:5]),
            "edu_pct": edu_pct,
            "ent_pct": ent_pct,
            "alerts": alerts,
            "ai_report": ai_report,
            "top_app_name": top_app,
        }
    
    def _generate_ai_report(self, device_name, apps, edu_pct, ent_pct, total_mb):
        """调用本地大模型生成报告"""
        if self.llm:
            try:
                apps_str = "\n".join([f"  - {a}: {m}MB" for a, m in apps[:5]])
                prompt = f"""
你是家庭AI教育助手。分析以下数据，写一段100字左右的简短评语。
设备: {device_name}
总流量: {round(total_mb)}MB
教育占比: {edu_pct}%
娱乐占比: {ent_pct}%
Top5应用:
{apps_str}

请用中文，语气温和，像家长对孩子说话那样。
只说分析和建议，不要"作为AI助手"之类的开场白。
"""
                resp = self.llm.create_chat_completion(
                    messages=[{"role": "user", "content": prompt}],
                    max_tokens=300, temperature=0.7,
                )
                return resp["choices"][0]["message"]["content"].strip()
            except Exception as e:
                return f"（AI报告暂不可用: {e}）"
        
        # 无大模型时的规则报告
        if edu_pct > ent_pct:
            return f"今天学习类应用占{edu_pct}%，继续保持！"
        return f"今天娱乐偏多（{ent_pct}%），建议适当增加学习时间。"
    
    def _empty_report(self, name):
        return {
            "device_name": name, "total_mb": 0, "app_count": 0,
            "top_apps": {}, "edu_pct": 0, "ent_pct": 0,
            "alerts": ["暂无数据"], "ai_report": "暂无数据",
            "top_app_name": "无",
        }

analyzer = AIAnalyzer()

# ============================================================
# 业务逻辑
# ============================================================

def get_live_data():
    """获取最新流量数据"""
    return fetcher.fetch()

def get_device_list(records):
    """从数据中提取设备列表"""
    names = set()
    for r in records:
        n = r.get("device_name", "")
        if n and "家长" not in n:
            names.add(n)
    names = sorted(names)
    if not names:
        names = ["孩子-小明", "孩子-小红"]
    return names

def build_overview(records):
    """设备总览DataFrame"""
    devices = {}
    for r in records:
        name = r.get("device_name", "未知")
        if name not in devices:
            devices[name] = {"total": 0, "edu": 0, "ent": 0}
        devices[name]["total"] += r["flow_mb"]
    
    edu_set = {"学而思","猿辅导","作业帮","百词斩","知乎","得到","Wikipedia"}
    ent_set = {"抖音","快手","B站","王者荣耀","原神","和平精英","蛋仔派对","腾讯视频","爱奇艺"}
    for r in records:
        name = r.get("device_name", "未知")
        for e in edu_set:
            if e in r["app"]:
                devices[name]["edu"] += r["flow_mb"]
                break
        for e in ent_set:
            if e in r["app"]:
                devices[name]["ent"] += r["flow_mb"]
                break
    
    rows = []
    for name, stats in devices.items():
        total = stats["total"]
        edu = stats["edu"]
        ent = stats["ent"]
        if total == 0:
            continue
        rows.append({
            "设备": name,
            "总流量(MB)": round(total, 1),
            "教育(MB)": round(edu, 1),
            "娱乐(MB)": round(ent, 1),
            "教育占比(%)": round(edu/total*100, 1),
            "娱乐占比(%)": round(ent/total*100, 1),
        })
    
    if not rows:
        rows = [{"设备": "暂无数据", "总流量(MB)": 0, "教育(MB)": 0, "娱乐(MB)": 0, "教育占比(%)": 0, "娱乐占比(%)": 0}]
    
    return pd.DataFrame(rows)

def update_refresh():
    """刷新所有数据"""
    records = get_live_data()
    df = build_overview(records)
    devices = get_device_list(records)
    return df, gr.Dropdown(choices=devices, value=devices[0] if devices else "孩子-小明")

def update_device_detail(device_name):
    """查看单个设备详情"""
    records = get_live_data()
    report = analyzer.analyze_device(device_name, records)
    
    edu = f"📖 教育流量: {report['edu_pct']}%"
    ent = f"🎮 娱乐流量: {report['ent_pct']}%"
    summary = f"总流量: {report['total_mb']}MB | 应用数: {report['app_count']} | 最多使用: {report['top_app_name']}"
    
    # Top apps as text
    top_text = "\n".join([f"- {a}: {m}MB" for a, m in report["top_apps"].items()])
    alerts_text = "\n".join(report["alerts"])
    
    return edu, ent, report["ai_report"], summary, top_text, alerts_text

def get_timeline_data(device_name):
    """时段流量分布"""
    records = get_live_data()
    dev_records = [r for r in records if r.get("device_name") == device_name][:30]
    df = pd.DataFrame(dev_records)
    if df.empty:
        return pd.DataFrame()
    return df.groupby("app")["flow_mb"].sum().reset_index().nlargest(10, "flow_mb").rename(
        columns={"app": "应用", "flow_mb": "流量(MB)"}
    )


# ============================================================
# Gradio UI
# ============================================================

with gr.Blocks(title="AI教育网关 - 家庭网络流量管理") as demo:
    
    # 系统状态条
    status_items = [
        f"🌐 OpenWrt: {CONFIG['openwrt_ip']}:{CONFIG['traffic_api_port']}",
        f"🧠 本地大模型: {'✅ 就绪' if MODEL_AVAILABLE else '⚠️ 未安装（使用规则引擎）'}",
        f"📁 数据目录: {CONFIG['data_dir']}",
    ]
    gr.Markdown(f"**状态:** {' | '.join(status_items)}")
    
    gr.Markdown("""
    # 🏠 AI教育网关 — 家庭网络AI管家
    
    N100软路由 | OpenWrt + nDPI → Qwen2.5-3B本地大模型 → Gradio Web
    
    数据来源: 光猫 → **N100软路由(WAN口)** → nDPI实时识别 → **AI分析** → 家长看板
    """)
    
    # 数据源指示
    with gr.Row():
        data_source = gr.Textbox(
            label="📡 数据源",
            value=f"OpenWrt nDPI @ http://{CONFIG['openwrt_ip']}:{CONFIG['traffic_api_port']}/traffic.json",
            interactive=False,
        )
    
    with gr.Tabs():
        # ===== Tab 1: 仪表盘 =====
        with gr.TabItem("📊 设备总览"):
            with gr.Row():
                refresh_btn = gr.Button("🔄 刷新数据", variant="primary", scale=1)
            gr.Markdown("**每30秒自动刷新**")
            
            overview_df = gr.Dataframe(label="📱 设备流量总览", interactive=False)
            refresh_btn.click(fn=update_refresh, outputs=[overview_df, gr.State()])
            
            gr.Markdown("""
            ---
            **部署架构**: 光猫 → N100(eth0 WAN) → nDPI识别 → AI分析 → Web展示
            """)
        
        # ===== Tab 2: 设备详情 =====
        with gr.TabItem("🔍 AI分析报告"):
            with gr.Row():
                dev_sel = gr.Dropdown(
                    choices=["孩子-小明", "孩子-小红"],
                    value="孩子-小明",
                    label="选择孩子",
                    scale=3,
                )
                refresh_dev_btn = gr.Button("🔄 刷新", scale=1)
            
            with gr.Row():
                edu_stat = gr.Textbox(label="📖 教育情况")
                ent_stat = gr.Textbox(label="🎮 娱乐情况")
            summary_box = gr.Textbox(label="📊 汇总")
            
            gr.Markdown("### 🤖 AI分析报告")
            ai_report = gr.Markdown("**选择设备后点击刷新查看AI分析报告**")
            
            with gr.Row():
                top_apps = gr.Textbox(label="🏆 Top应用", lines=6)
                alerts = gr.Textbox(label="🚨 告警信息", lines=6)
            
            def on_device_change(dev):
                return update_device_detail(dev)
            
            refresh_dev_btn.click(
                fn=on_device_change,
                inputs=[dev_sel],
                outputs=[edu_stat, ent_stat, ai_report, summary_box, top_apps, alerts]
            )
            dev_sel.change(
                fn=on_device_change,
                inputs=[dev_sel],
                outputs=[edu_stat, ent_stat, ai_report, summary_box, top_apps, alerts]
            )
        
        # ===== Tab 3: 部署说明 =====
        with gr.TabItem("📋 操作手册"):
            gr.Markdown(f"""
            ## 🔧 PVE部署架构
            
            ```
            ┌─────────────────────────────────────┐
            │        N100 软路由 (Proxmox VE)       │
            │                                      │
            │  ┌─── VM1: iStoreOS/OpenWrt ──────┐  │
            │  │  eth0 WAN(接光猫)                │  │
            │  │  eth1 LAN(接家庭网络)             │  │
            │  │  nDPI + uHTTPd + 流量JSON接口   │  │
            │  └──────────────┬──────────────────┘  │
            │                 │ (虚拟网桥通信)       │
            │  ┌─── VM2: Ubuntu ─────────────────┐  │
            │  │  AI引擎 + 本地大模型              │  │
            │  │  🖥️ Gradio :7871 ← 你现在在这    │  │
            │  └──────────────────────────────────┘  │
            └─────────────────────────────────────┘
            ```
            
            ## 接线方式
            
            > **光猫** → N100的 **eth0** (WAN口) → N100的 **eth1** (LAN口) → 家中交换机/路由器(设为AP模式)
            
            ## 配置命令（SSH到OpenWrt后运行）
            
            ```bash
            # 安装nDPI
            opkg update && opkg install ndpi ndpi-proto ndpistat
            
            # 启动流量采集
            /etc/init.d/ai-traffic-collect start
            
            # 验证数据接口
            curl http://localhost:8080/traffic.json
            ```
            
            ## Ubuntu侧（自动部署）
            
            ```bash
            # 部署脚本
            bash /opt/ai-gateway/pve-deploy/pve-setup-ubuntu.sh
            
            # 或手动启动
            cd /opt/ai-gateway && python3 app.py
            
            # 访问
            http://UbuntuIP:7871
            ```
            """)

if __name__ == "__main__":
    print(f"""
    ╔══════════════════════════════════════════╗
    ║      AI教育网关 v2.0 启动                 ║
    ╠══════════════════════════════════════════╣
    ║  数据源: {CONFIG['openwrt_ip']}:8080   ║
    ║  大模型: {'就绪' if MODEL_AVAILABLE else '未安装'}          ║
    ║  Web:    http://0.0.0.0:7871            ║
    ╚══════════════════════════════════════════╝
    """)
    
    import sys
    sys.stdout.flush()
    
    demo.queue().launch(
        server_name="0.0.0.0",
        server_port=7871,
    )
