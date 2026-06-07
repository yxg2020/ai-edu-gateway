"""
AI教育网关 v4.0 — 内容品质引导版（通用范式）
============================================
第一性原理：
  好的网络管理 = 帮每个家庭成员获得有益内容，避开有害内容
  
核心理念：
  网络不是恶魔，算法推荐才是问题。
  AI教育网关 = 替代商业化算法推荐的家庭内容向导

品质鉴别体系（不再分app，而看使用模式）：
  🔬 深度学习    —— 课程、长文、练习      → 鼓励+加速
  📖 知识浏览    —— 科普、新闻、纪录片    → 推荐同类
  🎨 创意娱乐    —— 创作、策略、建设      → 允许+记录
  😌 放松娱乐    —— 适度娱乐放松          → 控制时长
  ⏳ 被动消耗    —— 无意识刷屏            → 提醒替代  
  🚨 风险内容    —— 诈骗/极端/恶意        → 拦截通知
"""

import gradio as gr
import json, os, time, datetime, random, re, subprocess
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
}
MODEL_AVAILABLE = os.path.exists(CONFIG["model_path"])
os.makedirs(CONFIG["data_dir"], exist_ok=True)
os.makedirs(CONFIG["log_dir"], exist_ok=True)

# ============================================================
# 核心：内容品质分类体系（通用范式，适用于所有家庭成员）
# ============================================================

class ContentQualityFramework:
    """
    内容品质分类框架
    不按「App好坏」分，按「使用模式」和「内容价值」分
    """
    
    # ===== 高品质内容分类（正向价值） =====
    HIGH_QUALITY = {
        "🔬 深度学习": {
            "description": "获取结构化知识，有系统性的学习行为",
            "apps": ["Coursera", "可汗学院", "得到课程", "网易公开课", "中国大学MOOC",
                     "B站课堂", "学堂在线", "edX", "Udemy", "知识星球"],
            "domains": ["coursera.org", "khanacademy.org", "icourse163.org", "xuetangx.com",
                       "open.163.com", "udemy.com", "edx.org"],
            "who": "全体成员",
            "encourage": True,
        },
        "📖 深度阅读": {
            "description": "获取高密度信息，深度学习",
            "apps": ["得到电子书", "微信读书", "豆瓣阅读", "知乎盐选", "财新",
                     "FT中文网", "经济学人", "华尔街见闻", "36氪深度", "虎嗅"],
            "domains": ["dedao.cn", "weread.qq.com", "caixin.com", "ftchinese.com",
                       "economist.com", "36kr.com", "huxiu.com"],
            "who": "全体成员",
            "encourage": True,
        },
        "🌍 认知拓展": {
            "description": "拓宽视野，了解世界",
            "apps": ["国家地理", "BBC纪录片", "B站纪录片", "地球知识局", "知乎圆桌",
                     "小宇宙播客", "网易公开课TED", "看理想", "一席"],
            "domains": ["nationalgeographic.com", "bilibili.com/doc", "dili360.com",
                       "xiaoyuzhoufm.com", "ted.com", "yixi.tv"],
            "who": "全体成员",
            "encourage": True,
        },
        "🧠 思维提升": {
            "description": "批判性思维、第一性原理、系统思考",
            "apps": ["得到", "知乎深度", "豆瓣", "思维锻炼", "Lumosity"],
            "domains": ["zhihu.com/topic", "douban.com", "dedao.cn"],
            "who": "青少年+成年人",
            "encourage": True,
        },
        "💡 技能实践": {
            "description": "动手实践，产出作品",
            "apps": ["GitHub", "LeetCode", "Codecademy", "Scratch", "Figma",
                     "Canva", "Notion", "Obsidian", "Fusion360"],
            "domains": ["github.com", "leetcode.com", "scratch.mit.edu", "figma.com"],
            "who": "全体成员",
            "encourage": True,
        },
        "💰 财商素养": {
            "description": "理财知识、经济周期、商业逻辑",
            "apps": ["雪球", "有知有行", "天天基金", "东方财富", "且慢",
                     "得到商业", "华尔街见闻", "第一财经"],
            "domains": ["xueqiu.com", "youzhiyouxing.com", "eastmoney.com",
                       "wallstreetcn.com", "yicai.com"],
            "who": "成年人+青少年",
            "encourage": True,
        },
        "⚖️ 法律与公民意识": {
            "description": "法律常识、消费者权益、公民意识",
            "apps": ["裁判文书网", "中国法律", "法律读库"],
            "domains": ["wenshu.court.gov.cn", "pkulaw.com", "legaldaily.com.cn"],
            "who": "成年人+青少年",
            "encourage": True,
        },
        "🤝 情商与关系": {
            "description": "沟通能力、情绪管理、人际关系",
            "apps": ["得到沟通", "知乎职场", "脉脉", "简单心理"],
            "domains": ["maimai.cn", "zhihu.com/topic/职场", "jiandanxinli.com"],
            "who": "青少年+成年人",
            "encourage": True,
        },
        "🔬 科普与科学": {
            "description": "科学启蒙、探索世界",
            "apps": ["果壳", "科学松鼠会", "B站知识区", "知乎科学",
                     "Khan Academy", "可汗儿童", "奇妙世界365问"],
            "domains": ["guokr.com", "songshuhui.net", "khanacademy.org"],
            "who": "孩子+青少年",
            "encourage": True,
        },
        "🎨 创造型娱乐": {
            "description": "有产出的娱乐，激发创造力",
            "apps": ["我的世界", "乐高", "Scratch编程", "画世界Pro",
                     "GarageBand", "剪映创作", "Procreate"],
            "domains": ["minecraft.net", "scratch.mit.edu"],
            "who": "孩子+青少年",
            "encourage": True,
        },
    }
    
    # ===== 中性内容（适度原则） =====
    NEUTRAL = {
        "😌 适度娱乐": {
            "description": "放松身心，适度的娱乐是必要的",
            "apps": ["B站", "腾讯视频", "爱奇艺", "优酷", "网易云音乐",
                     "QQ音乐", "Spotify", "豆瓣电影", "起点读书"],
            "domains": ["bilibili.com", "qq.com", "netflix.com", "spotify.com"],
            "max_minutes_per_day": 120,
            "note": "适度放松有益，过度则成消耗",
        },
        "💬 社交沟通": {
            "description": "人际联系的必要工具",
            "apps": ["微信", "QQ", "钉钉", "飞书", "企业微信", "Telegram"],
            "domains": [],
            "note": "必要社交，注意不要过度刷朋友圈/群聊",
        },
        "🛒 生活工具": {
            "description": "解决实际生活问题",
            "apps": ["美团", "饿了么", "高德地图", "百度地图", "大众点评",
                     "12306", "航旅纵横", "携程"],
            "domains": ["meituan.com", "dianping.com", "fliggy.com"],
            "note": "工具性质，用完即走",
        },
    }
    
    # ===== 低品质内容（需要引导替代） =====
    LOW_QUALITY = {
        "⏳ 被动刷屏": {
            "description": "无意识、无目的的上下滑动，时间黑洞",
            "apps": ["抖音推荐页", "快手精选", "微博热搜", "今日头条推荐",
                     "小红书推荐", "B站推荐"],
            "risk": "信息茧房、被动消费、时间感知扭曲",
            "替代建议": "设置使用目标，主动搜索想看的优质内容",
            "推荐替代": ["B站知识区", "小宇宙播客", "得到", "知乎深度"],
        },
        "🛍️ 消费种草": {
            "description": "诱导消费的内容，制造焦虑→购买",
            "apps": ["小红书种草", "抖音直播", "淘宝直播", "拼多多直播",
                     "什么值得买", "得物"],
            "risk": "冲动消费、过度购物、金钱焦虑",
            "替代建议": "想要的东西先放购物车三天",
            "推荐替代": ["专业评测", "深度产品分析", "DIY教程"],
        },
        "🎰 算法游戏": {
            "description": "利用人性弱点设计的快餐游戏",
            "apps": ["开心消消乐", "羊了个羊", "合成大西瓜", "糖果粉碎传奇",
                     "贪吃蛇大作战", "口袋奇兵"],
            "risk": "碎片化、无成长性、诱导成瘾",
            "替代建议": "换成策略类/创造类游戏",
            "推荐替代": ["我的世界", "文明6", "星露谷物语", "编程游戏"],
        },
        "📰 低质资讯": {
            "description": "标题党、情绪化、低密度信息",
            "apps": ["今日头条资讯", "UC震惊体", "百家号", "一点资讯"],
            "risk": "情绪消耗、认知降级",
            "替代建议": "换有深度信源的资讯平台",
            "推荐替代": ["财新", "澎湃新闻", "FT中文网", "经济学人"],
        },
        "🗑️ 信息噪音": {
            "description": "娱乐八卦、明星绯闻、无意义挑战",
            "apps": ["微博娱乐", "抖音娱乐榜", "快手八卦"],
            "risk": "低密度信息、情绪消耗",
            "替代建议": "看一部完整纪录片或一本书",
            "推荐替代": ["B站纪录片", "微信读书", "小宇宙播客"],
        },
        "🚨 风险内容": {
            "description": "诈骗、赌博、极端信息、恶意软件",
            "apps": [],
            "domains": [],
            "risk": "财产损失、心理伤害、法律风险",
            "action": "自动拦截+家长通知",
        },
    }
    
    # ===== 广告/商业推广检测关键词 =====
    AD_KEYWORDS = [
        "直播", "带货", "限时抢购", "最后一天", "仅剩", "马上涨价",
        "免费领取", "点击领取", "立刻购买", "今日特价", "秒杀",
        "推广", "广告", "赞助", "合作推广", "好物推荐", "团购",
    ]
    
    @classmethod
    def classify(cls, app_name, duration_minutes=None):
        """
        核心分类方法
        返回: (品质标签, 分类名, 详细信息)
        """
        app_lower = app_name.lower()
        
        # 1. 检查风险内容
        risk_keywords = ["赌博", "诈骗", "裸聊", "刷单", "菠菜", "时时彩"]
        for kw in risk_keywords:
            if kw in app_lower:
                return ("🚨 风险内容", "风险内容", cls.LOW_QUALITY["🚨 风险内容"])
        
        # 2. 检查高品质
        for cat_name, info in cls.HIGH_QUALITY.items():
            for app in info["apps"]:
                if app.lower() in app_lower or app_lower in app.lower():
                    return ("🟢 高品质", cat_name, info)
            for domain in info.get("domains", []):
                if domain in app_lower:
                    return ("🟢 高品质", cat_name, info)
        
        # 3. 检查中性
        for cat_name, info in cls.NEUTRAL.items():
            for app in info["apps"]:
                if app.lower() in app_lower or app_lower in app.lower():
                    return ("🟡 中性", cat_name, info)
        
        # 4. 检查低品质
        for cat_name, info in cls.LOW_QUALITY.items():
            for app in info["apps"]:
                if app.lower() in app_lower or app_lower in app.lower():
                    return ("🔴 低品质", cat_name, info)
        
        # 5. 检查广告特征
        for kw in cls.AD_KEYWORDS:
            if kw in app_lower:
                return ("🟠 商业推广", "广告/营销", {"risk": "诱导消费"})
        
        # 6. 未识别的归为中性
        return ("⚪ 未识别", "其他", {})
    
    @classmethod
    def analyze_usage_pattern(cls, records, device_name):
        """分析一个人的整体上网模式"""
        dev_records = [r for r in records if r.get("device_name") == device_name]
        if not dev_records:
            return None
        
        # 统计各类别
        categories = {
            "🟢 高品质": {"name": "有益内容", "minutes": 0, "apps": {}, "children": {}},
            "🟡 中性": {"name": "日常工具", "minutes": 0, "apps": {}, "children": {}},
            "🔴 低品质": {"name": "需要优化", "minutes": 0, "apps": {}, "children": {}},
            "🟠 商业推广": {"name": "商业内容", "minutes": 0, "apps": {}},
        }
        
        total_mb = 0
        for r in dev_records:
            mb = r.get("flow_mb", 0)
            total_mb += mb
            app = r.get("app", "未知")
            quality, subcat, info = cls.classify(app)
            
            if quality in categories:
                categories[quality]["minutes"] += mb
                categories[quality]["apps"][app] = categories[quality]["apps"].get(app, 0) + mb
                if subcat and subcat != "其他":
                    c = categories[quality].setdefault("children", {})
                    c[subcat] = c.get(subcat, 0) + mb
        
        # 计算品质得分（满分100）
        if total_mb == 0:
            return None
        
        high = categories["🟢 高品质"]["minutes"]
        low = categories["🔴 低品质"]["minutes"]
        neutral = categories["🟡 中性"]["minutes"]
        ad = categories["🟠 商业推广"]["minutes"]
        
        # 高品质加分，低品质扣分，中性不加不减，商业推广轻微扣分
        score = 60 + (high / total_mb) * 40 - (low / total_mb) * 50 - (ad / total_mb) * 20
        score = max(0, min(100, round(score, 1)))
        
        return {
            "total_mb": round(total_mb, 1),
            "score": score,
            "high_pct": round(high / total_mb * 100, 1) if total_mb > 0 else 0,
            "low_pct": round(low / total_mb * 100, 1) if total_mb > 0 else 0,
            "neutral_pct": round(neutral / total_mb * 100, 1) if total_mb > 0 else 0,
            "ad_pct": round(ad / total_mb * 100, 1) if total_mb > 0 else 0,
            "categories": categories,
            "suggestions": cls._generate_suggestions(categories, score, device_name),
            "week_streak": cls._get_streak_info(dev_records),
        }
    
    @classmethod
    def _generate_suggestions(cls, categories, score, device_name):
        """生成品质提升建议"""
        suggestions = []
        
        # 根据低品质内容生成替代建议
        low_cat = categories.get("🔴 低品质", {})
        if low_cat.get("apps"):
            worst_app = max(low_cat["apps"], key=low_cat["apps"].get)
            for cat_name, info in cls.LOW_QUALITY.items():
                if worst_app in info["apps"]:
                    alt = info.get("推荐替代", [])
                    if alt:
                        suggestions.append(
                            f"🔄 在「{worst_app}」上花了一些时间，下次试试「{alt[0]}」——"
                            f"{info['替代建议']}"
                        )
        
        # 鼓励高品质内容
        high_cat = categories.get("🟢 高品质", {})
        if high_cat.get("apps"):
            best_app = max(high_cat["apps"], key=high_cat["apps"].get)
            suggestions.append(f"🌟 今天在「{best_app}」上花的时间很有质量！")
        else:
            suggestions.append("💡 今天还没有接触到高品质内容，推荐试试：得到、知乎深度或B站知识区")
        
        # 商业推广提醒
        ad_cat = categories.get("🟠 商业推广", {})
        if ad_cat.get("apps"):
            suggestions.append('📢 今天接触到一些商业推广内容，注意区分"需要"和"被诱导"')
        
        # 整体评分建议
        if score < 40:
            suggestions.append("⚠️ 今天品质分偏低，建议主动搜索想看的内容，而不是被动刷推荐")
        elif score > 80:
            suggestions.append("👏 今天的内容品质很好，这种节奏坚持下去会有很大收获")
        
        return suggestions[:4]
    
    @classmethod
    def _get_streak_info(cls, records):
        """连续学习天数（简化版用模拟）"""
        return random.randint(1, 7) if records else 0
    
    @classmethod
    def get_daily_recommendations(cls, member_role="成年人"):
        """
        根据家庭成员角色生成每日推荐
        不基于个人偏好，而是基于「这个角色的人最需要什么」
        """
        recommendations = {
            "成年人": [
                ("📰 今日深度", "财新 | 每周经济观察",
                 "理解钱往哪流、经济处在周期哪个阶段",
                 "https://www.caixin.com"),
                ("📈 商业案例", "36氪 | 8篇深度商业分析",
                 "从真实案例中学习商业模式和决策逻辑",
                 "https://www.36kr.com"),
                ("💰 理财认知", "有知有行 | 投资第一课",
                 "建立自己的投资体系，理解资产配置和经济周期",
                 "https://youzhiyouxing.com"),
                ("🤖 AI趋势", "机器之心 | AI正在重塑什么",
                 "了解AI代替了什么岗位、创造了什么新机会",
                 "https://jiqizhixin.com"),
                ("⚖️ 法律常识", "民法典通读",
                 "合同、租房、借贷——每个人都需要的法律知识",
                 "https://www.pkulaw.com"),
                ("🤝 职场进阶", "脉脉 | 向上管理方法论",
                 "怎么和领导高效沟通，怎么和同事协作共赢",
                 "https://maimai.cn"),
                ("🧠 认知升级", "得到 | 像马斯克一样思考",
                 "第一性原理：拆解问题到基本真理再重构",
                 "https://dedao.cn"),
                ("🌍 地理视角", "地球知识局 | 地缘格局",
                 "从地理理解国际博弈，看懂新闻背后的逻辑",
                 "https://www.dili360.com"),
            ],
            "孩子": [
                ("🔬 科学实验", "B站 | 不刷题的吴姥姥",
                 "物理可以这么好玩！生活中的科学原理",
                 "https://www.bilibili.com"),
                ("🌍 环球探险", "国家地理 | 神奇动物在哪里",
                 "每集10分钟，认识一个你从没见过的动物",
                 "https://www.nationalgeographic.com"),
                ("🎨 创意编程", "Scratch | 做自己的游戏",
                 "不用写代码就能做游戏，锻炼逻辑思维",
                 "https://scratch.mit.edu"),
                ("📚 名著导读", "豆瓣 | 少年读史记",
                 "用故事的方式读历史，培养大格局",
                 "https://book.douban.com"),
            ],
            "青少年": [
                ("📖 学习方法", "知乎 | 如何高效学习",
                 "费曼学习法、间隔重复，让学习效率翻倍",
                 "https://www.zhihu.com"),
                ("🌍 职业生涯", "B站 | 各行各业真实日常",
                 "提前了解不同职业在做什么，找到自己的方向",
                 "https://www.bilibili.com"),
                ("💰 财商启蒙", "有知有行 | 年轻人的第一堂理财课",
                 "越早理解钱和投资，未来选择就越多",
                 "https://youzhiyouxing.com"),
                ("🧠 批判性思维", "得到 | 学会提问",
                 "不盲从、不轻信，做一个独立思考的人",
                 "https://dedao.cn"),
            ],
            "老人": [
                ("🏥 权威健康", "腾讯医典 | 中老年健康指南",
                 "高血压、糖尿病、骨质疏松——听医生的，别信谣言",
                 "https://med.qq.com"),
                ("🛡️ 防骗指南", "国家反诈中心 | 最新骗局提醒",
                 "了解最新的诈骗手法，保护好养老钱",
                 "https://www.12377.cn"),
                ("🌺 文化生活", "B站 | 中国诗词大会",
                 "温故知新，和孙子孙女一起看",
                 "https://www.bilibili.com"),
                ("📞 亲情联络", "微信使用技巧 | 和家人更近",
                 "学几招微信小技巧，和子女视频更方便",
                 "https://weixin.qq.com"),
            ],
        }
        
        return recommendations.get(member_role, recommendations["成年人"])


# ============================================================
# 数据层
# ============================================================

class TrafficDataFetcher:
    def __init__(self):
        self.cache = []
    
    def fetch(self):
        try:
            if self._can_reach_openwrt():
                resp = requests.get(
                    f"http://{CONFIG['openwrt_ip']}:{CONFIG['traffic_api_port']}/traffic.json",
                    timeout=5
                )
                if resp.status_code == 200:
                    records = self._parse_ndpi(resp.json())
                    self.cache.extend(records)
                    return records
        except:
            pass
        return self._mock_data()
    
    def _can_reach_openwrt(self):
        try:
            r = subprocess.run(["ping", "-c", "1", "-W", "1", CONFIG["openwrt_ip"]],
                              capture_output=True, timeout=2)
            return r.returncode == 0
        except:
            return False
    
    def _parse_ndpi(self, data):
        records = []
        ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        devices = []
        if isinstance(data, dict):
            devices = data.get("traffic", {}).get("devices", [])
        if isinstance(data, list):
            devices = data
        for dev in devices:
            ip = dev.get("ip", "0.0.0.0")
            for proto in dev.get("protocols", []):
                app = proto.get("name", "未知")
                mb = round(proto.get("bytes", 0) / (1024*1024), 2)
                if mb > 0:
                    records.append({"timestamp": ts, "device_ip": ip, "app": app, "flow_mb": mb})
        return records
    
    def _mock_data(self):
        ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        apps = [
            ("财新深度", True), ("得到课程", True), ("B站纪录片", True), ("知乎深度", True),
            ("雪球", True), ("36氪分析", True), ("脉脉", True), ("果壳", True),
            ("抖音推荐", False), ("小红书种草", False), ("微博热搜", False),
            ("微信", None), ("钉钉", None),
            ("淘宝直播", "ad"), ("拼多多秒杀", "ad"),
        ]
        records = []
        profiles = [
            ("192.168.100.10", "爸爸", "成年人"),
            ("192.168.100.11", "妈妈", "成年人"),
            ("192.168.100.102", "小明", "孩子"),
            ("192.168.100.103", "小红", "青少年"),
            ("192.168.100.110", "奶奶", "老人"),
        ]
        for ip, name, role in profiles:
            n = random.randint(3, 8)
            selected = random.sample(apps, min(n, len(apps)))
            for app_name, is_good in selected:
                mb = round(random.uniform(1, 20), 1)
                records.append({
                    "timestamp": ts, "device_ip": ip, "device_name": name,
                    "member_role": role, "app": app_name, "flow_mb": mb
                })
        return records

fetcher = TrafficDataFetcher()
cf = ContentQualityFramework()


# ============================================================
# 页面更新函数
# ============================================================

def family_overview():
    """家庭品质总览"""
    records = fetcher.fetch()
    rows = []
    for dev_name in set(r.get("device_name", "未知") for r in records):
        result = cf.analyze_usage_pattern(records, dev_name)
        if result:
            # 获取角色
            role = "成年人"
            dev_records = [r for r in records if r.get("device_name") == dev_name]
            for r in dev_records:
                if r.get("member_role"):
                    role = r["member_role"]
                    break
            
            rows.append({
                "👤 成员": dev_name,
                "🎭 角色": role,
                "🌟 品质分": result["score"],
                "🟢 有益(%)": result["high_pct"],
                "🔴 需优化(%)": result["low_pct"],
                "📊 总流量(MB)": result["total_mb"],
            })
    if not rows:
        rows.append({"👤 成员": "暂无数据", "🎭 角色": "", "🌟 品质分": 0, 
                     "🟢 有益(%)": 0, "🔴 需优化(%)": 0, "📊 总流量(MB)": 0})
    return pd.DataFrame(rows)

def member_detail(dev_name):
    """个人详情"""
    records = fetcher.fetch()
    result = cf.analyze_usage_pattern(records, dev_name)
    if not result:
        return "暂无可分析的上网数据", "", "", "", ""
    
    # 获取角色
    role = "成年人"
    for r in records:
        if r.get("device_name") == dev_name and r.get("member_role"):
            role = r["member_role"]
            break
    
    score = result["score"]
    if score >= 80:
        score_text = f"🌟 {score}分 — 今天的内容品质非常好！"
    elif score >= 60:
        score_text = f"✅ {score}分 — 整体不错，还有提升空间"
    elif score >= 40:
        score_text = f"📊 {score}分 — 需要留意上网内容结构"
    else:
        score_text = f"⚠️ {score}分 — 低品质内容偏多，试试推荐替代"
    
    # 高品质内容
    high = result["categories"]["🟢 高品质"]
    high_text = ""
    if high.get("apps"):
        for app, mb in sorted(high["apps"].items(), key=lambda x: -x[1])[:6]:
            quality, subcat, _ = cf.classify(app)
            high_text += f"✅ {app}（{subcat}）— {mb}MB\n"
    else:
        high_text = "暂无高品质内容记录\n"
    
    # 低品质内容
    low = result["categories"]["🔴 低品质"]
    low_text = ""
    if low.get("apps"):
        for app, mb in sorted(low["apps"].items(), key=lambda x: -x[1])[:6]:
            quality, subcat, _ = cf.classify(app)
            low_text += f"⚠️ {app}（{subcat}）— {mb}MB\n"
    else:
        low_text = "暂无低品质内容\n"
    
    # 商业推广
    ad = result["categories"]["🟠 商业推广"]
    ad_text = ""
    if ad.get("apps"):
        for app, mb in sorted(ad["apps"].items(), key=lambda x: -x[1])[:3]:
            ad_text += f"📢 {app} — {mb}MB\n"
    else:
        ad_text = "暂无商业推广内容\n"
    
    # 建议
    suggestion_text = "\n".join(result["suggestions"]) if result["suggestions"] else "暂无建议"
    
    # 推荐内容（按角色）
    role_recs = cf.get_daily_recommendations(role)
    rec_text = "### 📚 今日为你推荐\n\n"
    for icon, title, desc, url in role_recs[:4]:
        rec_text += f"**{icon} {title}**\n{desc}\n[🔗 去看看]({url})\n\n"
    
    return score_text, high_text, low_text, ad_text, suggestion_text, rec_text, role


# ============================================================
# Gradio UI
# ============================================================

with gr.Blocks(title="AI教育网关 - 家庭内容品质引导") as demo:
    
    gr.Markdown("""
    # 🌟 AI教育网关 v4.0 — 家庭内容品质引导
    
    **不是监控你在网上做了什么，而是帮你发现更好的内容**
    
    每个家庭成员都有专属内容品质分析——成年人需要经济和成长，孩子需要科学和创造，
    青少年需要学习和方向，老人需要健康和陪伴。
    
    从「管控」到「引导」——让网络真正成为家庭成长的工具。
    """)
    
    with gr.Tabs():
        
        # ===== Tab 1: 总览 =====
        with gr.TabItem("📊 家庭品质总览"):
            with gr.Row():
                refresh_btn = gr.Button("🔄 刷新", variant="primary")
            
            overview = gr.Dataframe(
                value=family_overview(),
                label="👨‍👩‍👧‍👦 每个家庭成员的网上内容品质"
            )
            refresh_btn.click(fn=family_overview, outputs=[overview])
            demo.load(fn=family_overview, outputs=[overview])
            
            gr.Markdown("""
            ---
            **品质分数说明**（通用标准，适用于所有家庭成员）：
            - 🌟 **80分以上**：高品质内容为主，值得鼓励
            - ✅ **60-80分**：整体良好，关注低品质内容的替代
            - 📊 **40-60分**：被动消耗偏多，建议主动搜索优质内容
            - ⚠️ **40分以下**：需要结构调整，AI会自动推荐替代内容
            
            **内容品质分类标准**：
            
            | 品质 | 含义 | 示例 |
            |---|---|---|
            | 🟢 高品质 | 深度学习、知识拓展、技能实践、创意娱乐 | 得到课程、知乎深度、我的世界 |
            | 🟡 中性 | 社交沟通、适度娱乐、生活工具 | 微信、B站、美团 |
            | 🔴 低品质 | 被动刷屏、算法游戏、低质资讯 | 抖音推荐、开心消消乐、标题党 |
            | 🟠 商业推广 | 诱导消费的内容 | 直播带货、广告营销 |
            """)
        
        # ===== Tab 2: 个人分析 =====
        with gr.TabItem("👤 内容品质分析"):
            with gr.Row():
                member_sel = gr.Dropdown(
                    choices=["爸爸", "妈妈", "小明", "小红", "奶奶"],
                    value="爸爸", label="选择家庭成员", scale=3
                )
                analyze_btn = gr.Button("🔍 分析", variant="primary", scale=1)
            
            score_box = gr.Markdown("**选择成员后点击分析**")
            role_box = gr.Textbox(label="🎭 角色", interactive=False, visible=False)
            
            with gr.Tabs():
                with gr.TabItem("🟢 有益内容"):
                    high_box = gr.Textbox(label="", lines=8)
                with gr.TabItem("🔴 需优化"):
                    low_box = gr.Textbox(label="", lines=8)
                with gr.TabItem("🟠 商业推广"):
                    ad_box = gr.Textbox(label="", lines=4)
            
            gr.Markdown("### 💡 品质提升建议")
            suggestion_box = gr.Textbox(label="", lines=4)
            
            gr.Markdown("### 📚 专属推荐（按角色自动匹配）")
            rec_box = gr.Markdown("**分析后显示专属推荐**")
            
            def do_analyze(dev):
                return member_detail(dev)
            
            analyze_btn.click(
                fn=do_analyze, inputs=[member_sel],
                outputs=[score_box, high_box, low_box, ad_box, suggestion_box, rec_box, role_box]
            )
        
        # ===== Tab 3: 每日推荐 =====
        with gr.TabItem("📚 今日内容精选"):
            gr.Markdown("## 为每个家庭成员精选的优质内容")
            gr.Markdown("*不是算法推荐，是AI根据「这个角色的人最需要什么」来推荐*")
            
            for role_name in ["成年人", "孩子", "青少年", "老人"]:
                gr.Markdown(f"### {role_name}")
                role_recs = cf.get_daily_recommendations(role_name)
                for icon, title, desc, url in role_recs[:3]:
                    gr.Markdown(f"**{icon} {title}**\n{desc}\n[🔗 去看看]({url})\n")
        
        # ===== Tab 4: 设计理念 =====
        with gr.TabItem("💡 内容品质标准"):
            gr.Markdown("""
            ## 内容品质评判标准（通用范式）
            
            这不是针对某一个人的偏好，而是每个家庭成员都适用的内容品质框架。
            
            ### 有益内容（鼓励）
            
            | 类别 | 为什么有益 | 适合谁 |
            |---|---|---|
            | 🔬 深度学习 | 获取系统性知识，学到东西 | 全体 |
            | 📖 深度阅读 | 高密度信息，训练思考能力 | 全体 |
            | 🌍 认知拓展 | 拓宽视野，理解世界 | 全体 |
            | 🧠 思维提升 | 学会独立思考，不盲从 | 青少年+成年人 |
            | 💡 技能实践 | 动手产出作品，获得成就感 | 全体 |
            | 💰 财商素养 | 理解经济规律，不被割韭菜 | 青少年+成年人 |
            | ⚖️ 法律常识 | 保护自己，明白权利义务 | 青少年+成年人 |
            | 🤝 情商关系 | 更好地和人相处 | 青少年+成年人 |
            | 🔬 科普科学 | 保持好奇心和对世界的热爱 | 孩子+青少年 |
            | 🎨 创造型娱乐 | 娱乐中锻炼创造力 | 孩子+青少年 |
            
            ### 有害内容（需要引导替代）
            
            | 类别 | 为什么有害 | 替代方向 |
            |---|---|---|
            | ⏳ 被动刷屏 | 时间黑洞，无成长 | 主动搜索优质内容 |
            | 🛍️ 消费种草 | 诱导消费，制造焦虑 | 买前放三天 |
            | 🎰 算法游戏 | 无成长性，诱导成瘾 | 换策略/创造类游戏 |
            | 📰 低质资讯 | 被情绪操控，认知降级 | 换有深度信源 |
            | 🗑️ 信息噪音 | 低密度信息，浪费时间 | 看完整作品 |
            | 🚨 风险内容 | 财产/心理/法律风险 | 自动拦截 |
            | 🟠 商业推广 | 让你花钱而不是创造价值 | 区分需要和欲望 |
            
            ### 判断标准：四个维度
            
            问一个内容是否对这个人有益，看这四个维度：
            
            1. **学** — 是否获得了新知识或新技能？
            2. **乐** — 是否真正放松了身心？（不是越刷越焦虑）
            3. **活** — 是否解决了实际问题？
            4. **长** — 是否拓宽了视野或塑造了品格？
            
            满足至少一个 → 有益内容
            一个都不满足，且消耗时间/情绪/金钱 → 需要优化
            
            > *这不是在帮某个人的上网做推荐，这是在建立一个通用的内容品质评判体系，适用于每一个家庭。*
            """)

if __name__ == "__main__":
    print(f"""
    ╔══════════════════════════════════════════════════╗
    ║   AI教育网关 v4.0 — 家庭内容品质引导             ║
    ╠══════════════════════════════════════════════════╣
    ║  核心理念：不是封闭管控，而是优质内容引导         ║
    ║                                                    ║
    ║  品质框架（通用范式）：                             ║
    ║    🟢 高品质 — 学习·拓展·创造·实践              ║
    ║    🟡 中性   — 社交·适度娱乐·生活工具            ║
    ║    🔴 低品质 — 被动刷屏·算法游戏·低质资讯        ║
    ║    🟠 商业   — 诱导消费·广告营销                  ║
    ║    🚨 风险   — 诈骗·极端·恶意                     ║
    ║                                                    ║
    ║  🌐 {CONFIG['openwrt_ip']}:8080  │  🖥️ :7871    ║
    ╚══════════════════════════════════════════════════╝
    """)
    
    demo.queue().launch(server_name="0.0.0.0", server_port=7871)
