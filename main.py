# 1. NHẬP CÁC THƯ VIỆN CẦN THIẾT
from fastapi import FastAPI
from pydantic import BaseModel
from openai import OpenAI
import xmlrpc.client
import os
import json
from dotenv import load_dotenv
from fastapi.middleware.cors import CORSMiddleware

# 2. LOAD CẤU HÌNH TỪ FILE .ENV
load_dotenv()

ODOO_URL = os.getenv("ODOO_URL")
ODOO_DB = os.getenv("ODOO_DB")
ODOO_USERNAME = os.getenv("ODOO_USERNAME")
ODOO_PASSWORD = os.getenv("ODOO_PASSWORD")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# 3. KẾT NỐI VỚI ODOO
try:
    common = xmlrpc.client.ServerProxy(f'{ODOO_URL}/xmlrpc/2/common')
    uid = common.authenticate(ODOO_DB, ODOO_USERNAME, ODOO_PASSWORD, {})
    models = xmlrpc.client.ServerProxy(f'{ODOO_URL}/xmlrpc/2/object')
    print(f" Đã kết nối Odoo thành công! UID: {uid}")
except Exception as e:
    print(f" Lỗi kết nối Odoo: {e}")

# 4. KHỞI TẠO APP & OPENAI
app = FastAPI()
client = OpenAI(
    base_url="https://api.groq.com/openai/v1",
    api_key=OPENAI_API_KEY
)

# Cho phép React gọi API (Cấu hình CORS)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Định nghĩa dữ liệu đầu vào từ React
class ChatRequest(BaseModel):
    message: str
    history: list = []
    sales_rep_name: str = "Admin" 

# --- PHẦN 5:  HELPER FUNCTIONS ---

def extract_core_digits(phone):
    """
    TRÍCH XUẤT CHUỖI SỐ ĐỂ TÌM KIẾM:
    - Loại bỏ dấu +, space, -, (, )
    - Nếu bắt đầu bằng '0' (VN local) -> cắt bỏ số 0 đầu
    - Trả về chuỗi số để tìm kiếm
    
    VD: "0799368057" -> "799368057" (để khớp +84799368057)
        "+84799368057" -> "84799368057"
    """
    if not phone:
        return None
    
    phone_str = str(phone).strip()
    
    # Chỉ giữ lại số
    digits = ''.join(c for c in phone_str if c.isdigit())
    
    if not digits:
        return None
    
    # Nếu bắt đầu bằng 0 và đủ 10 số (VN) -> cắt số 0
    if digits.startswith('0') and len(digits) == 10:
        return digits[1:]  # "799368057"
    
    return digits

def find_customer(customer_name, phone=None, email=None):

    try:
        # --- BƯỚC 1: XÂY DỰNG DOMAIN ---
        # Tìm theo tên (OR name hoặc display_name)
        domain = ['|', ('name', 'ilike', customer_name), ('display_name', 'ilike', customer_name)]

        # Nếu có Phone -> Thêm điều kiện phone với NHIỀU PATTERN
        if phone:
            core_digits = extract_core_digits(phone)
            if core_digits:
                # Tạo nhiều pattern để khớp với Odoo có thể lưu dấu cách
                # VD: "799368057" -> ["799368057", "799 368 057", "0799368057"]
                patterns = [core_digits]
                
                # Thêm pattern có dấu cách (VN format: xxx xxx xxx)
                if len(core_digits) >= 9:
                    # "799368057" -> "799 368 057"
                    spaced = ' '.join([core_digits[i:i+3] for i in range(0, len(core_digits), 3)])
                    patterns.append(spaced)
                
                # Thêm số điện thoại gốc (nếu khác với core_digits)
                if phone != core_digits:
                    patterns.append(phone)
                
                # Xây dựng OR conditions cho tất cả patterns
                phone_conditions = [('phone', 'ilike', p) for p in patterns]
                
                if len(phone_conditions) == 1:
                    domain = ['&'] + domain + phone_conditions
                else:
                    # Tạo chuỗi OR: ['|', '|', cond1, cond2, cond3]
                    or_chain = ['|'] * (len(phone_conditions) - 1) + phone_conditions
                    domain = ['&'] + domain + or_chain

        # Nếu có Email -> Thêm điều kiện email
        if email:
            domain = ['&'] + domain + [('email', 'ilike', email)]

        # --- BƯỚC 2: GỌI ODOO 1 LẦN ---
        partners = models.execute_kw(
            ODOO_DB, uid, ODOO_PASSWORD, 
            'res.partner', 'search_read',
            [domain], 
            {'fields': ['name', 'phone', 'email'], 'limit': 5} 
        )
        
        # --- BƯỚC 3: XỬ LÝ KẾT QUẢ ---
        if not partners:
            return (False, f"❌ Không tìm thấy khách hàng '{customer_name}'" +
                          (f" với SĐT {phone}" if phone else "") +
                          (f" với email {email}" if email else ""))

        if len(partners) == 1:
            return (True, partners[0]['id'])
        
        # Nếu trùng nhiều người -> Trả về danh sách
        error_msg = f"⚠️ Tìm thấy {len(partners)} khách hàng phù hợp:\n"
        for p in partners:
            contact = p.get('phone') or "Không SĐT"
            error_msg += f"- {p['name']} (SĐT: {contact})\n"
        
        return (False, error_msg + "👉 Vui lòng cung cấp thêm Email hoặc SĐT chính xác hơn.")

    except Exception as e:
        return (False, f"❌ Lỗi hệ thống: {str(e)}")

def suggest_pricing(product_name, customer_name=None, quantity=1, customer_phone=None, customer_email=None):
    """
    GỢI Ý GIÁ CHUẨN ODOO (SỬ DỤNG HÀM NATIVE CỦA ODOO)
    """
    try:
        # 1. TÌM SẢN PHẨM
        product_ids = models.execute_kw(ODOO_DB, uid, ODOO_PASSWORD, 'product.product', 'search',
                                      [[['name', 'ilike', product_name]]], {'limit': 1})
        
        if not product_ids:
            return {"suggested_price": 0, "message": "❌ Không tìm thấy sản phẩm"}
        
        product_id = product_ids[0]
        
        # Lấy thông tin cơ bản sản phẩm
        product = models.execute_kw(ODOO_DB, uid, ODOO_PASSWORD, 'product.product', 'read',
                                  [product_id], {'fields': ['name', 'list_price', 'uom_id']})[0]
        base_price = product['list_price']
        
        # 2. XÁC ĐỊNH BẢNG GIÁ & KHÁCH HÀNG
        pricelist_id = None
        partner_id = None
        pricelist_name = "Giá niêm yết (Mặc định)"

        if customer_name:
            success, result = find_customer(customer_name, customer_phone, customer_email)
            if success:
                partner_id = result
                # Lấy bảng giá của khách
                partner_data = models.execute_kw(ODOO_DB, uid, ODOO_PASSWORD, 'res.partner', 'read',
                                               [partner_id], {'fields': ['property_product_pricelist']})[0]
                
                if partner_data.get('property_product_pricelist'):
                    pricelist_id = partner_data['property_product_pricelist'][0]
                    pricelist_name = partner_data['property_product_pricelist'][1]
        
        # Nếu không có khách hàng cụ thể, Odoo sẽ dùng bảng giá Public (thường là ID 1)
        # Tuy nhiên, để an toàn, nếu không có pricelist_id, ta dùng base_price
        
        final_price = base_price
        
        if pricelist_id:
            # =================================================================================
            # ⭐ TÍNH GIÁ THEO PRICELIST (ODOO 19.0 COMPATIBLE)
            # Đọc trực tiếp pricelist items
            # =================================================================================
            try:
                # Tìm pricelist item cho sản phẩm này
                items = models.execute_kw(
                    ODOO_DB, uid, ODOO_PASSWORD,
                    'product.pricelist.item', 'search_read',
                    [[['pricelist_id', '=', pricelist_id], 
                      '|', ['product_id', '=', product_id],
                           ['product_tmpl_id', '=', product.get('product_tmpl_id', False)]]],
                    {'fields': ['fixed_price', 'percent_price', 'price_discount', 'compute_price', 'min_quantity'], 
                     'order': 'min_quantity desc'}
                )
                
                # Filter theo min_quantity (nếu mua số lượng lớn có thể được giá tốt hơn)
                applicable_items = [item for item in items if item.get('min_quantity', 0) <= quantity]
                
                if applicable_items:
                    item = applicable_items[0]  # Lấy item đầu tiên (ưu tiên min_quantity cao nhất)
                    
                    if item['compute_price'] == 'fixed':
                        # Giá cố định
                        final_price = item['fixed_price']
                        print(f"DEBUG - Fixed price: {final_price} (min_qty: {item.get('min_quantity', 0)})")
                    elif item['compute_price'] == 'percentage':
                        # Giá theo % (VD: percent_price = 0.9 nghĩa là 90% giá gốc)
                        final_price = base_price * item['percent_price']
                        print(f"DEBUG - Percentage: {item['percent_price']} -> {final_price}")
                    elif item['compute_price'] == 'formula':
                        # Giá theo công thức (price_discount)
                        discount = item.get('price_discount', 0)
                        final_price = base_price * (1 - discount / 100)
                        print(f"DEBUG - Discount: {discount}% -> {final_price}")
                else:
                    print(f"DEBUG - No pricelist item found for product {product_id}, using base price")
                    
            except Exception as e:
                print(f"DEBUG - Pricelist error: {e}, using base price")
                final_price = base_price

        # 3. TÍNH TOÁN HIỂN THỊ
        discount_info = []
        if final_price < base_price:
            discount_percent = ((base_price - final_price) / base_price) * 100
            discount_info.append(f"Giảm {discount_percent:.1f}%")
        elif final_price > base_price:
            # Trường hợp bảng giá Cost-Plus (Giá vốn + Lãi) có thể cao hơn giá niêm yết ảo
            discount_info.append(f"Giá điều chỉnh theo thị trường")

        message = f"💰 Giá đề xuất: {final_price:,.0f} VNĐ"
        if discount_info:
            message += f" ({', '.join(discount_info)} theo {pricelist_name})"
        
        return {
            "product_name": product['name'],
            "base_price": base_price,
            "suggested_price": final_price,
            "quantity": quantity,
            "pricelist": pricelist_name,
            "message": message
        }

    except Exception as e:
        return {"suggested_price": 0, "message": f"❌ Lỗi hệ thống: {str(e)}"}

def get_customer_pricelist(customer_name, customer_phone=None, customer_email=None):
    """
    LẤY CHÍNH SÁCH GIÁ (PRICELIST) 
    """
    try:
        # 1. Tìm khách hàng
        success, result = find_customer(customer_name, customer_phone, customer_email)
        if not success:
            return result
        
        partner_id = result
        
        # 2. Lấy ID bảng giá
        partner = models.execute_kw(ODOO_DB, uid, ODOO_PASSWORD, 'res.partner', 'read',
                                   [partner_id], {'fields': ['name', 'property_product_pricelist']})[0]
        
        if not partner.get('property_product_pricelist'):
            return f"Khách hàng {partner['name']} đang dùng bảng giá mặc định."
            
        pricelist_id = partner['property_product_pricelist'][0]
        
        # 3. Lấy thông tin Header bảng giá
        pricelist = models.execute_kw(ODOO_DB, uid, ODOO_PASSWORD, 'product.pricelist', 'read',
                                    [pricelist_id], {'fields': ['name', 'currency_id', 'active']})[0]
        
        currency_name = pricelist['currency_id'][1] if pricelist['currency_id'] else 'VNĐ'

        # 4. Lấy chi tiết các dòng quy tắc (Items)
        # Sắp xếp theo độ ưu tiên: Sản phẩm cụ thể -> Nhóm -> Toàn bộ
        pricelist_items = models.execute_kw(ODOO_DB, uid, ODOO_PASSWORD, 'product.pricelist.item', 'search_read',
                                           [[['pricelist_id', '=', pricelist_id]]], 
                                           {'fields': [
                                               'applied_on',       # Phạm vi (3_global, 2_category, 1_product)
                                               'categ_id',         # ID nhóm hàng
                                               'product_tmpl_id',  # ID sản phẩm
                                               'compute_price',    # Cách tính (fixed, percentage, formula)
                                               'fixed_price',      # Giá cố định
                                               'percent_price',    # Phần trăm giảm
                                               'price_discount',   # Phần trăm giảm (trong formula)
                                               'price_surcharge',  # Phụ phí
                                               'min_quantity'      # Số lượng tối thiểu
                                           ], 
                                           'limit': 5}) # Lấy 5 dòng tiêu biểu
        
        rules_text = ""
        if pricelist_items:
            rules_text = "\n\n🎯 CHI TIẾT ƯU ĐÃI:"
            for item in pricelist_items:
                # A. Xác định đối tượng áp dụng
                target = ""
                if item['applied_on'] == '3_global':
                    target = "🔥 Tất cả sản phẩm"
                elif item['applied_on'] == '2_product_category' and item['categ_id']:
                    target = f"📂 Nhóm {item['categ_id'][1]}"
                elif item['applied_on'] == '1_product' and item['product_tmpl_id']:
                    target = f"📱 {item['product_tmpl_id'][1]}"
                else:
                    target = "Sản phẩm khác"

                # B. Xác định mức giá/chiết khấu
                detail = ""
                min_qty = f" (khi mua > {item['min_quantity']})" if item['min_quantity'] > 0 else ""

                if item['compute_price'] == 'fixed':
                    detail = f"Giá cố định: {item['fixed_price']:,.0f} {currency_name}"
                
                elif item['compute_price'] == 'percentage':
                    # LƯU Ý: Odoo lưu 10.0 nghĩa là 10%
                    detail = f"Giảm giá: {item['percent_price']}%"
                
                elif item['compute_price'] == 'formula':
                    # Xử lý hiển thị cho công thức (thường dùng cho đại lý)
                    # Nếu dùng công thức Cost + Margin thì khó hiển thị số cụ thể, nên báo chung
                    detail = "Áp dụng giá sỉ theo công thức (Giá vốn + Lợi nhuận)"
                    if item.get('price_discount'):
                         detail += f" - Chiết khấu thêm {item['price_discount']}%"

                rules_text += f"\n • {target}{min_qty}: {detail}"

        return f"""📋 CHÍNH SÁCH GIÁ - {partner['name']}

🏷️ Hạng thành viên: {pricelist['name']}
💱 Đơn vị tiền tệ: {currency_name}
✅ Trạng thái: {'Hoạt động' if pricelist['active'] else 'Đã khóa'}
{rules_text}"""

    except Exception as e:
        return f"❌ Lỗi hệ thống: {str(e)}"
    
def find_product(name):
    """Tìm sản phẩm trong Odoo theo tên"""
    # Tìm ID sản phẩm (tìm gần đúng với ilike)
    ids = models.execute_kw(ODOO_DB, uid, ODOO_PASSWORD, 'product.product', 'search', 
                           [[['name', 'ilike', name]]])
    
    if ids:
        # Lấy chi tiết: Tên, Giá, Tồn kho
        products = models.execute_kw(ODOO_DB, uid, ODOO_PASSWORD, 'product.product', 'read', 
                                    [ids], {'fields': ['name', 'list_price', 'qty_available']})
        return products
    return []

def create_sale_order(customer_name, product_name, quantity, sales_rep_name="Admin", customer_phone=None, customer_email=None):
    """
    Tạo đơn hàng bán theo quy trình chuẩn Odoo:
    1. Validate khách hàng & sản phẩm (xử lý trùng tên)
    2. Kiểm tra tồn kho
    3. Gợi ý giá tự động (suggest pricing)
    4. Tạo Sale Order (Draft)
    5. Thêm Order Lines với giá
    6. Confirm đơn hàng (chuyển sang Sale Order)
    7. Ghi log nhân viên tạo đơn
    """
    try:
        # 1. TÌM KHÁCH HÀNG với logic thông minh
        success, result = find_customer(customer_name, customer_phone, customer_email)
        
        if not success:
            return result  # Trả về error message
        
        partner_id = result
        
        # Lấy thông tin khách để hiển thị
        partner = models.execute_kw(ODOO_DB, uid, ODOO_PASSWORD, 'res.partner', 'read', 
                                   [partner_id], {'fields': ['name', 'phone', 'email']})[0]
        
        # 2. TÌM SẢN PHẨM & KIỂM TRA TỒN KHO
        product_ids = models.execute_kw(ODOO_DB, uid, ODOO_PASSWORD, 'product.product', 'search', 
                                       [[['name', 'ilike', product_name]]], {'limit': 1})
        if not product_ids:
            return f" Không tìm thấy sản phẩm '{product_name}' trong kho."
        
        # Lấy thông tin chi tiết sản phẩm
        product = models.execute_kw(ODOO_DB, uid, ODOO_PASSWORD, 'product.product', 'read', 
                                   [product_ids[0]], {'fields': ['name', 'list_price', 'qty_available']})[0]
        
        # KIỂM TRA TỒN KHO
        if product['qty_available'] < quantity:
            return f"⚠️ Không đủ hàng! Sản phẩm '{product['name']}' chỉ còn {product['qty_available']} máy trong kho."
        
        # 3. GỢI Ý GIÁ (Suggest Pricing theo Odoo Pricelist)
        pricing = suggest_pricing(product_name, customer_name, quantity)
        suggested_price = pricing['suggested_price'] if pricing['suggested_price'] > 0 else product['list_price']
        print(f"DEBUG - Product: {product['name']}, List Price: {product['list_price']}, Suggested: {suggested_price}, Pricelist: {pricing.get('pricelist', 'N/A')}")
        
        # 4. TẠO ĐƠN HÀNG (DRAFT STATE)
        order_id = models.execute_kw(ODOO_DB, uid, ODOO_PASSWORD, 'sale.order', 'create', [{
            'partner_id': partner_id,
            'note': f'Đơn hàng tạo bởi Chatbot AI - Sales Rep: {sales_rep_name}\n{pricing["message"]}',
        }])
        
        # 5. THÊM DÒNG SẢN PHẨM (với giá đề xuất)
        models.execute_kw(ODOO_DB, uid, ODOO_PASSWORD, 'sale.order.line', 'create', [{
            'order_id': order_id,
            'product_id': product_ids[0],
            'product_uom_qty': quantity,
            'price_unit': suggested_price,  # Dùng giá đã suggest
        }])
        
        # 6. XÁC NHẬN ĐƠN HÀNG (Chuyển từ Draft -> Sale Order)
        models.execute_kw(ODOO_DB, uid, ODOO_PASSWORD, 'sale.order', 'action_confirm', [[order_id]])
        
        # 7. LẤY THÔNG TIN ĐƠN HÀNG ĐÃ TẠO
        order_info = models.execute_kw(ODOO_DB, uid, ODOO_PASSWORD, 'sale.order', 'read', 
                                      [order_id], {'fields': ['name', 'amount_total', 'amount_untaxed', 'state']})[0]
        print(f"DEBUG - Order: {order_info['name']}, Untaxed: {order_info['amount_untaxed']}, Total: {order_info['amount_total']}")
        
        # Format số tiền
        total_amount = "{:,.0f}".format(order_info['amount_total'])
        discount_msg = f"\n💡 {pricing['message']}" if pricing['discount_info'] else ""
        
        # TRẢ VỀ THÔNG BÁO THÀNH CÔNG
        return f"""✅ Tạo đơn hàng thành công!
        
📋 Mã đơn: {order_info['name']}
👤 Khách hàng: {partner['name']}
📱 Sản phẩm: {product['name']} x {quantity}
💰 Tổng tiền: {total_amount} VNĐ{discount_msg}
📊 Trạng thái: Đã xác nhận
👨‍💼 Nhân viên: {sales_rep_name}
        
Đơn hàng đã được ghi nhận vào hệ thống!"""
        
    except Exception as e:
        return f" Lỗi khi tạo đơn hàng: {str(e)}. Vui lòng liên hệ quản trị viên."

def get_all_products(limit=10):
    """Lấy danh sách top sản phẩm đang bán"""
    # Tìm tất cả sản phẩm có thể bán được (sale_ok = True)
    # limit để tránh liệt kê quá dài làm lag bot
    ids = models.execute_kw(ODOO_DB, uid, ODOO_PASSWORD, 'product.product', 'search', 
                           [[['sale_ok', '=', True]]])
    
    if ids:
        products = models.execute_kw(ODOO_DB, uid, ODOO_PASSWORD, 'product.product', 'read', 
                                    [ids], {'fields': ['name', 'list_price', 'qty_available']})
        return products
    return []

def get_sale_orders(customer_name=None, limit=5, customer_phone=None, customer_email=None):
    """
    Tra cứu đơn hàng theo khách hàng
    """
    try:
        domain = []
        
        # Nếu có tên khách hàng, tìm theo partner với logic thông minh
        if customer_name:
            success, result = find_customer(customer_name, customer_phone, customer_email)
            
            if not success:
                return result  # Trả về error message
            
            domain.append(['partner_id', '=', result])
        
        # Tìm đơn hàng
        order_ids = models.execute_kw(ODOO_DB, uid, ODOO_PASSWORD, 'sale.order', 'search', 
                                     [domain], {'limit': limit, 'order': 'id desc'})
        
        if not order_ids:
            return "📭 Không tìm thấy đơn hàng nào."
        
        # Lấy thông tin chi tiết
        orders = models.execute_kw(ODOO_DB, uid, ODOO_PASSWORD, 'sale.order', 'read', 
                                  [order_ids], {'fields': ['name', 'partner_id', 'amount_total', 'state', 'date_order']})
        
        result = []
        for order in orders:
            state_map = {
                'draft': '📝 Nháp',
                'sent': '📧 Đã gửi',
                'sale': '✅ Đã xác nhận',
                'done': '✔️ Hoàn tất',
                'cancel': '❌ Đã hủy'
            }
            state_text = state_map.get(order['state'], order['state'])
            total = "{:,.0f}".format(order['amount_total'])
            
            result.append(f"• {order['name']} - {order['partner_id'][1]} - {total} VNĐ - {state_text}")
        
        return "📋 Danh sách đơn hàng:\n" + "\n".join(result)
        
    except Exception as e:
        return f"❌ Lỗi tra cứu: {str(e)}"

def cancel_sale_order(order_name):
    """
    Hủy đơn hàng
    """
    try:
        # Tìm đơn hàng theo tên (VD: SO001)
        order_ids = models.execute_kw(ODOO_DB, uid, ODOO_PASSWORD, 'sale.order', 'search', 
                                     [[['name', '=', order_name]]])
        
        if not order_ids:
            return f"❌ Không tìm thấy đơn hàng '{order_name}'"
        
        # Lấy thông tin đơn
        order = models.execute_kw(ODOO_DB, uid, ODOO_PASSWORD, 'sale.order', 'read', 
                                [order_ids[0]], {'fields': ['name', 'state']})[0]
        
        # Kiểm tra trạng thái
        if order['state'] == 'cancel':
            return f"⚠️ Đơn hàng {order_name} đã được hủy trước đó."
        
        if order['state'] == 'done':
            return f"⚠️ Không thể hủy đơn hàng {order_name} vì đã hoàn tất giao hàng."
        
        # Hủy đơn hàng
        models.execute_kw(ODOO_DB, uid, ODOO_PASSWORD, 'sale.order', 'action_cancel', [[order_ids[0]]])
        
        return f"✅ Đã hủy đơn hàng {order_name} thành công!"
        
    except Exception as e:
        return f"❌ Lỗi khi hủy đơn: {str(e)}"
# --- PHẦN 6: API CHAT (BỘ NÃO) ---

@app.post("/chat")
async def chat_endpoint(request: ChatRequest):
    user_msg = request.message
    print(f"User: {user_msg}") # Log ra terminal để xem

    # 1. Định nghĩa System Prompt
    system_instruction = """
    Bạn là trợ lý bán hàng AI thông minh cho hệ thống ERP. Nhiệm vụ:
    1. Phân tích yêu cầu của nhân viên bán hàng
    2. Đề xuất giá phù hợp với từng khách hàng
    3. Hỗ trợ tạo quotation và sales order nhanh chóng
    
    QUAN TRỌNG: Trả về kết quả dưới định dạng JSON với các action sau:
    
    CÁC ACTION HỖ TRỢ (JSON format):
    - Liệt kê sản phẩm (VD: "Có điện thoại nào?", "Show products"):
      -> {"action": "list_products"}
      
    - Kiểm tra giá/suggest pricing (VD: "Giá iPhone cho khách A?", "Giá 15 chiếc iPhone?"):
      -> {"action": "suggest_price", "product": "tên sản phẩm", "customer": "tên khách (optional)", "qty": số_lượng (mặc định 1), "phone": "SĐT (optional)", "email": "email (optional)"}
    
    - Xem chính sách giá của khách (VD: "Bảng giá của khách A", "Pricelist for B"):
      -> {"action": "get_customer_pricelist", "customer": "tên khách"}
      
    - Tạo đơn hàng (VD: "Tạo đơn iPhone cho khách A", "Create order Samsung for B"):
      -> {"action": "create_order", "customer": "tên khách", "product": "tên sản phẩm", "qty": số_lượng, "phone": "SĐT (optional)", "email": "email (optional)"}
      
    - Tra cứu đơn hàng (VD: "Xem đơn khách A", "Check orders"):
      -> {"action": "check_orders", "customer": "tên khách hoặc null", "phone": "SĐT (optional)", "email": "email (optional)"}
      
    - Hủy đơn (VD: "Hủy đơn SO001"):
      -> {"action": "cancel_order", "order_name": "SO001"}
      
    - Chat thông thường:
      -> {"action": "chat", "response": "câu trả lời"}
    
    LƯU Ý: 
    - qty phải là số nguyên
    - Ưu tiên phân tích khách hàng trước khi suggest giá
    - Luôn thân thiện và chuyên nghiệp
    - Luôn trả về đúng định dạng JSON object
    """
    # 2. Xây dựng danh sách tin nhắn gửi cho AI 
    # Bắt đầu bằng System Prompt
    messages_for_ai = [
        {"role": "system", "content": system_instruction}
    ]

    # Chèn Lịch sử chat (History) vào giữa
    for msg in request.history:
        role = "assistant" if msg['role'] == "bot" else "user"
        messages_for_ai.append({"role": role, "content": msg['content']})

    messages_for_ai.append({"role": "user", "content": user_msg})

    # 3. Gửi cho AI 
    try:
        gpt_response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=messages_for_ai,
            response_format={"type": "json_object"}
        )
        
        ai_content = gpt_response.choices[0].message.content
        data = json.loads(ai_content)
        print(f"AI Intent: {data}") # Log để debug

    except Exception as e:
        print(f"Lỗi AI: {e}")
        return {"reply": "Hệ thống đang bận, vui lòng thử lại sau."}

    bot_reply = ""

    # 4. Điều hướng hành động
    if data['action'] == 'list_products':
        # Gọi hàm lấy danh sách (đã viết ở bước trước)
        products = get_all_products(limit=5)
        if products:
            info_list = []
            for p in products:
                price = "{:,.0f}".format(p['list_price'])
                info_list.append(f"📱 {p['name']} - Giá: {price} đ (Kho: {p['qty_available']})")
            bot_reply = "Dạ, bên em đang sẵn hàng các mẫu này ạ:\n" + "\n".join(info_list)
        else:
            bot_reply = "Hiện tại cửa hàng đang tạm hết hàng ạ."

    elif data['action'] == 'check_price':
        products = find_product(data['product'])
        if products:
            info_list = []
            for p in products:
                price = "{:,.0f}".format(p['list_price'])
                info_list.append(f"- {p['name']}: {price} VNĐ (Còn {p['qty_available']} máy)")
            bot_reply = "Dạ, em tìm thấy:\n" + "\n".join(info_list)
        else:
            bot_reply = f"Hic, em tìm không thấy mẫu '{data['product']}' trong kho ạ."
    
    elif data['action'] == 'suggest_price':
        # Gợi ý giá cho sản phẩm
        product = data.get('product')
        customer = data.get('customer')
        phone = data.get('phone')
        email = data.get('email')
        qty = int(data.get('qty', 1))  # Lấy số lượng từ AI, mặc định 1
        pricing = suggest_pricing(product, customer, qty, phone, email)
        
        # Thêm thông tin tổng giá nếu mua nhiều
        if qty > 1:
            total = pricing['suggested_price'] * qty
            bot_reply = f"{pricing['message']}\n📦 Số lượng: {qty} chiếc\n💵 Tổng tiền: {total:,.0f} VNĐ"
        else:
            bot_reply = pricing['message']
    
    elif data['action'] == 'get_customer_pricelist':
        # Xem chính sách giá của khách hàng
        customer = data.get('customer')
        phone = data.get('phone')
        email = data.get('email')
        bot_reply = get_customer_pricelist(customer, phone, email)
    
    elif data['action'] == 'create_order':
        # Đảm bảo qty là số nguyên
        qty = int(data.get('qty', 1))
        sales_rep = request.sales_rep_name
        phone = data.get('phone')
        email = data.get('email')
        bot_reply = create_sale_order(data['customer'], data['product'], qty, sales_rep, phone, email)
    
    elif data['action'] == 'check_orders':
        # Tra cứu đơn hàng
        customer = data.get('customer')
        phone = data.get('phone')
        email = data.get('email')
        bot_reply = get_sale_orders(customer_name=customer, limit=10, customer_phone=phone, customer_email=email)
    
    elif data['action'] == 'cancel_order':
        # Hủy đơn hàng
        order_name = data.get('order_name')
        if order_name:
            bot_reply = cancel_sale_order(order_name)
        else:
            bot_reply = "⚠️ Vui lòng cung cấp mã đơn hàng cần hủy (VD: SO001)"

    else: # action == chat
        bot_reply = data.get('response', "Em chưa hiểu ý anh chị lắm.")

    return {"reply": bot_reply}

# --- PHẦN 7: TEST SERVER (Mẹo nhỏ) ---
@app.get("/")
def home():
    return {"message": "Server Chatbot đang chạy ngon lành!"}