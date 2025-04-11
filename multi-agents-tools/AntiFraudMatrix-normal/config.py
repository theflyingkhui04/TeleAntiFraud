# OpenAI API配置
OPENAI_API_KEY = "sk-fpwiniyhjwughnzrzdckrrkiyxkebpgcoslhnenybgbxyvva"  # 请替换为实际密钥
OPENAI_BASE_URL = "https://api.siliconflow.cn/v1"  # 自定义 API 端点

# 模型配置
DEFAULT_MODEL = "deepseek-ai/DeepSeek-V2.5"  # 默认使用您示例中的模型
FALLBACK_MODEL = "deepseek-ai/DeepSeek-V2.5"  # 备用模型，可以设置为其他可用模型

# 对话配置
MAX_DIALOGUE_TURNS = 20
MAX_TOKENS_PER_MESSAGE = 500

# 诈骗类型列表
FRAUD_TYPES = [
    "investment",     # 投资诈骗
    "romance",        # 情感诈骗
    "phishing",       # 钓鱼诈骗
    "identity_theft", # 身份盗窃
    "lottery",        # 彩票诈骗
    "job_offer",      # 虚假工作
    "banking"         # 银行诈骗
]

# 用户画像配置
USER_PROFILES = {
    "elderly": {
        "age": 70,
        "awareness": "low",
        "occupation": "retired"
    },
    "youth": {
        "age": 22,
        "awareness": "medium",
        "occupation": "student"
    },
    "professional": {
        "age": 40,
        "awareness": "high",
        "occupation": "engineer"
    }
}