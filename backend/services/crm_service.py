from backend.services.odoo_service import odoo_service
from backend.services.customer_service import customer_service
from backend.utils.formatter import format_currency

class CRMService:
    """Service quản lý logic CRM"""
    
    def __init__(self):
        self.Lead = odoo_service.get_model('crm.lead')
    
    def create_opportunity(self, customer_name: str, phone: str = None, 
                          email: str = None, product_interest: str = None,
                          quantity: int = 1,expected_revenue: float = None,
                          note: str = None,sales_rep_user_id: int = None) -> str:
        """
        Tạo cơ hội bán hàng (CRM Opportunity) với đầy đủ thông tin
        
        Parameters:
        - customer_name: Tên khách hàng tiềm năng
        - phone: SĐT liên hệ (optional)
        - email: Email liên hệ (optional)
        - product_interest: Sản phẩm quan tâm (optional)
        - expected_revenue: Doanh thu dự kiến (optional)
        - note: Ghi chú nhu cầu (optional)
        - sales_rep_user_id: ID nhân viên phụ trách (optional)
        
        Returns: Success message hoặc error message
        """
        try:
            Partner = odoo_service.get_model('res.partner')
            
            # 1. TÌM HOẶC TẠO KHÁCH HÀNG
            partner_id = None
            is_new_customer = False
            
            # Thử tìm khách hàng hiện có
            if customer_name:
                success, result = customer_service.find_customer(customer_name, phone, email)
                
                if success:
                    partner_id = result
                else:
                    # Không tìm thấy -> Tạo mới
                    partner_vals = {'name': customer_name, 'customer_rank': 1,'is_company': False,}
                    if phone:
                        partner_vals['phone'] = phone
                    if email:
                        partner_vals['email'] = email
                    
                    partner_id = Partner.create(partner_vals)
                    is_new_customer = True
            
            # 2. XÂY DỰNG THÔNG TIN OPPORTUNITY
            opportunity_title = f"Cơ hội: {customer_name}"
            if product_interest:
                opportunity_title = f"Cơ hội: {customer_name} - {product_interest}"
            
            lead_vals = {
                'name': opportunity_title,
                'partner_id': partner_id,
                'type': 'opportunity',  # Opportunity, không phải Lead
                'priority': '1',  # Ưu tiên thấp, có thể thay đổi
            }
            
            # Thêm phone/email nếu có
            if phone:
                lead_vals['phone'] = phone
            if email:
                lead_vals['email_from'] = email
            
            # Thêm mô tả chi tiết
            description_parts = []
            if product_interest:
                    description_parts.append(f"Sản phẩm quan tâm: {product_interest} x {quantity}")   
            if note:
                description_parts.append(f"Ghi chú: {note}")
            if is_new_customer:
                description_parts.append("⭐ Khách hàng mới (tạo tự động)")
            
            if description_parts:
                lead_vals['description'] = "\n".join(description_parts)
            
            # Thêm doanh thu dự kiến
            if expected_revenue and expected_revenue > 0:
                lead_vals['expected_revenue'] = expected_revenue
                lead_vals['probability'] = 50  # Xác suất mặc định 50%
            
            # Gán nhân viên phụ trách (để tính KPI)
            if sales_rep_user_id:
                lead_vals['user_id'] = sales_rep_user_id
            
            # 3. TẠO OPPORTUNITY
            lead_id = self.Lead.create(lead_vals)
            lead = self.Lead.browse(lead_id)
            
            # 4. FORMAT RESPONSE
            result = f"""✅ ĐÃ TẠO CƠ HỘI CRM THÀNH CÔNG!

Mã Opportunity: {lead.name}
Khách hàng: {customer_name}"""
            
            if is_new_customer:
                result += "\n⭐ Khách hàng mới đã được tạo tự động"
            
            if phone:
                result += f"\nSĐT: {phone}"
            if email:
                result += f"\nEmail: {email}"
            if product_interest:
                result += f"\nSản phẩm: {product_interest}"
            if expected_revenue:
                result += f"\nDoanh thu dự kiến: {format_currency(expected_revenue)} VNĐ"
            if sales_rep_user_id:
                result += f"\nNhân viên phụ trách: User ID {sales_rep_user_id}"
            
            result += "\n\n💡 Bước tiếp theo:\n"
            result += "1. Gọi điện xác nhận nhu cầu\n"
            result += "2. Tạo báo giá khi khách đồng ý\n"
            result += f"3. Dùng lệnh: \"Tạo báo giá {product_interest or 'sản phẩm'} cho {customer_name}\""
            
            return result
            
        except Exception as e:
            return f"❌ Lỗi khi tạo CRM Opportunity: {str(e)}"

# Singleton instance
crm_service = CRMService()