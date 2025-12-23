import odoorpc
from urllib.parse import urlparse
from backend.config import settings

class OdooService:
    """Service quản lý kết nối Odoo"""
    
    _instance = None
    _odoo = None
    
    def __new__(cls):
        """Singleton pattern - Chỉ tạo 1 instance duy nhất"""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        """Khởi tạo kết nối Odoo"""
        if self._odoo is None:
            self._connect()
    
    def _connect(self):
        """Kết nối đến Odoo"""
        try:
            parsed_url = urlparse(settings.ODOO_URL)
            odoo_host = parsed_url.hostname or 'localhost'
            
            if parsed_url.scheme == 'https':
                odoo_protocol = 'jsonrpc+ssl'
                odoo_port = parsed_url.port or 443
            else:
                odoo_protocol = 'jsonrpc'
                odoo_port = parsed_url.port or 8069
            
            self._odoo = odoorpc.ODOO(odoo_host, protocol=odoo_protocol, port=odoo_port)
            self._odoo.login(settings.ODOO_DB, settings.ODOO_USERNAME, settings.ODOO_PASSWORD)
            
            print(f"✅ Đã kết nối Odoo thành công! UID: {self._odoo.env.uid}")
        except Exception as e:
            print(f"❌ Lỗi kết nối Odoo: {e}")
            raise
    
    @property
    def odoo(self):
        """Trả về Odoo connection"""
        if self._odoo is None:
            self._connect()
        return self._odoo
    
    def get_model(self, model_name: str):
        """Lấy Odoo model"""
        return self.odoo.env[model_name]

# Singleton instance
odoo_service = OdooService()