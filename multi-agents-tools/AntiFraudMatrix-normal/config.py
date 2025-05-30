# Cấu hình API OpenAI
OPENAI_API_KEY = "sk-fpwiniyhjwughnzrzdckrrkiyxkebpgcoslhnenybgbxyvva"  # 请替换为实际密钥
OPENAI_BASE_URL = "https://api.siliconflow.cn/v1"  # Điểm cuối API tùy chỉnh

# Cấu hình mô hình
DEFAULT_MODEL = "deepseek-ai/DeepSeek-V2.5"  # Sử dụng mô hình trong ví dụ của bạn theo mặc định
FALLBACK_MODEL = "deepseek-ai/DeepSeek-V2.5"  # Mô hình dự phòng, có thể được đặt thành các mô hình khả dụng khác

# Cấu hình hội thoại
MAX_DIALOGUE_TURNS = 20
MAX_TOKENS_PER_MESSAGE = 500

# Danh sách các loại gian lận
FRAUD_TYPES = [
    "investment",     # 投资诈骗
    "romance",        # 情感诈骗
    "phishing",       # 钓鱼诈骗
    "identity_theft", # 身份盗窃
    "lottery",        # 彩票诈骗
    "job_offer",      # 虚假工作
    "banking"         # 银行诈骗
]

# Cấu hình hồ sơ người dùng
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