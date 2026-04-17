# 项目常量定义
import os


# 项目根目录
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))

# 保存剪映草稿的目录
DRAFT_DIR = os.path.join(PROJECT_ROOT, "output", "draft")

# 临时文件目录
TEMP_DIR = os.path.join(PROJECT_ROOT, "temp")

# 剪映草稿的下载路径
DRAFT_URL = os.getenv("DRAFT_URL", "http://127.0.0.1:30000/openapi/capcut-mate/v1/get_draft")

# 将本地文件路径转成下载路径
DOWNLOAD_URL = os.getenv("DOWNLOAD_URL", "http://127.0.0.1:30000/")

# 草稿提示URL
TIP_URL = os.getenv("TIP_URL", "https://docs.jcaigc.cn/")

# 贴纸配置文件路径
STICKER_CONFIG_PATH = os.path.join(os.path.dirname(__file__), "config", "sticker.json")

# 花字配置文件路径
HUAZI_CONFIG_PATH = os.path.join(os.path.dirname(__file__), "config", "huazi.json")

# 模板目录路径
TEMPLATE_DIR = os.path.join(os.path.dirname(__file__), "template")

# 剪映草稿保存路径（下载剪映草稿保存位置）-- 云渲染必需配置
# 使用项目内 temp/drafts 目录，避免权限问题
DRAFT_SAVE_PATH = os.path.join(PROJECT_ROOT, "temp", "drafts")

# 剪映应用草稿文件夹路径（用于自动导出视频）
# 请将此路径设置为剪映专业版中配置的草稿位置
# 可在剪映中查看：设置 -> 全局设置 -> 草稿位置
JIANYING_DRAFT_PATH = os.getenv("JIANYING_DRAFT_PATH", r"D:\JianyingPro Drafts")

# 腾讯云对象存储配置 -- 云渲染必需配置
COS_SECRET_ID = os.getenv("COS_SECRET_ID", "xxx")
COS_SECRET_KEY = os.getenv("COS_SECRET_KEY", "xxx")
COS_BUCKET_NAME = os.getenv("COS_BUCKET_NAME", "xxx")
COS_REGION = os.getenv("COS_REGION", "xxx")

# APIKEY启用配置-默认启用 -- 云渲染必需配置（环境变量 true / false，大小写不敏感）
ENABLE_APIKEY = os.getenv("ENABLE_APIKEY", "false").strip().lower() == "true"

# 文件下载大小限制（字节），默认200MB
DOWNLOAD_FILE_SIZE_LIMIT = int(os.getenv("DOWNLOAD_FILE_SIZE_LIMIT", str(200 * 1024 * 1024)))

# ==================== OpenAI 配置 ====================
# OpenAI API 密钥
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "sk-stNCnaSdsAm0cJ9nDFwfCXQqpawyKcEKxbdIstKTEzAmBex8")
# OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "sk-bf-addfef18-e0f2-4493-9876-c42a15eed4ea")

# OpenAI API 基础 URL（可选，用于兼容第三方 API 服务）
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "https://happyapi.org/v1")
# OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "http://154.219.101.233:8080/v1")

# OpenAI 模型名称
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-5-mini-2025-08-07")
# OPENAI_MODEL = os.getenv("OPENAI_MODEL", "free")

# 视频输出目录
VIDEO_OUTPUT_PATH = os.getenv("VIDEO_OUTPUT_PATH", r"C:\Users\64061\capcut-mate\temp")
