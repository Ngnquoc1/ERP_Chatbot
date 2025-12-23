import os
from dotenv import load_dotenv

# Load biến môi trường
load_dotenv()

class Settings:
    """Cấu hình ứng dụng"""
    
    # Odoo Configuration
    ODOO_URL: str = os.getenv("ODOO_URL")
    ODOO_DB: str = os.getenv("ODOO_DB")
    ODOO_USERNAME: str = os.getenv("ODOO_USERNAME")
    ODOO_PASSWORD: str = os.getenv("ODOO_PASSWORD")
    
    # OpenAI Configuration
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY")
    OPENAI_BASE_URL: str = "https://api.groq.com/openai/v1"
    OPENAI_MODEL: str = "llama-3.3-70b-versatile"
    
    # CORS Configuration
    CORS_ORIGINS: list = ["*"]

    
    @classmethod
    def validate(cls):
        """Kiểm tra cấu hình bắt buộc"""
        required = [cls.ODOO_URL, cls.ODOO_DB, cls.ODOO_USERNAME, 
                   cls.ODOO_PASSWORD, cls.OPENAI_API_KEY]
        missing = [name for name, val in vars(cls).items() 
                  if not name.startswith('_') and val is None]
        if missing:
            raise ValueError(f"Missing required config: {', '.join(missing)}")

settings = Settings()
settings.validate()