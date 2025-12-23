from typing import Tuple, Optional
from backend.services.odoo_service import odoo_service
from backend.utils.formatter import extract_core_digits

class CustomerService:
    """Service quản lý logic khách hàng"""
    
    def __init__(self):
        self.Partner = odoo_service.get_model('res.partner')
    
    def find_customer(self, customer_name: str, phone: str = None, email: str = None) -> Tuple[bool, any]:
        """
        Tìm khách hàng theo tên/SĐT/email
        
        Returns:
            Tuple[bool, any]: (success, result_or_error)
            - success=True: result = partner_id
            - success=False: result = error_message
        """
        try:
            # XÂY DỰNG DOMAIN
            domain = ['|', ('name', 'ilike', customer_name), ('display_name', 'ilike', customer_name)]

            # Thêm điều kiện phone
            if phone:
                core_digits = extract_core_digits(phone)
                if core_digits:
                    patterns = [core_digits]
                    
                    if len(core_digits) >= 9:
                        spaced = ' '.join([core_digits[i:i+3] for i in range(0, len(core_digits), 3)])
                        patterns.append(spaced)
                    
                    if phone != core_digits:
                        patterns.append(phone)
                    
                    phone_conditions = [('phone', 'ilike', p) for p in patterns]
                    
                    if len(phone_conditions) == 1:
                        domain = ['&'] + domain + phone_conditions
                    else:
                        or_chain = ['|'] * (len(phone_conditions) - 1) + phone_conditions
                        domain = ['&'] + domain + or_chain

            # Thêm điều kiện email
            if email:
                domain = ['&'] + domain + [('email', 'ilike', email)]

            # TÌM KIẾM
            partners = self.Partner.search_read(domain, ['name', 'phone', 'email'], limit=5)
            
            # XỬ LÝ KẾT QUẢ
            if not partners:
                return (False, f"Không tìm thấy khách hàng '{customer_name}'" +
                              (f" với SĐT {phone}" if phone else "") +
                              (f" với email {email}" if email else ""))

            if len(partners) == 1:
                return (True, partners[0]['id'])
            
            # Trùng nhiều người
            error_msg = f"Tìm thấy {len(partners)} khách hàng phù hợp:\n"
            for p in partners:
                contact = p.get('phone') or "Không SĐT"
                error_msg += f"- {p['name']} (SĐT: {contact})\n"
            
            return (False, error_msg + "\nVui lòng cung cấp thêm Email hoặc SĐT chính xác hơn.")

        except Exception as e:
            return (False, f"❌ Lỗi hệ thống: {str(e)}")
    
    def get_customer_pricelist(self, customer_name: str, phone: str = None, email: str = None) -> str:
        """Lấy chính sách giá của khách hàng"""
        try:
            # Tìm khách hàng
            success, result = self.find_customer(customer_name, phone, email)
            if not success:
                return result
            
            partner_id = result
            partner = self.Partner.browse(partner_id)
            
            # Kiểm tra bảng giá
            if not partner.property_product_pricelist:
                return f"Khách hàng {partner.name} đang dùng bảng giá mặc định."
                
            pricelist = partner.property_product_pricelist
            currency_name = pricelist.currency_id.name if pricelist.currency_id else 'VNĐ'

            # Lấy chi tiết các dòng quy tắc (Items)
            PricelistItem = odoo_service.get_model('product.pricelist.item')
            pricelist_items = PricelistItem.search_read(
                [('pricelist_id', '=', pricelist.id)],
                ['applied_on', 'categ_id', 'product_tmpl_id', 'product_id',
                 'compute_price', 'fixed_price', 'percent_price', 'price_discount',
                 'price_surcharge', 'min_quantity'],
                limit=10
            )
            
            # Format rules (giữ nguyên logic cũ)
            # ... (code format rules)
            
            return f"""CHÍNH SÁCH GIÁ - {partner.name}
...
"""
        
        except Exception as e:
            return f"❌ Lỗi hệ thống: {str(e)}"

# Singleton instance
customer_service = CustomerService()