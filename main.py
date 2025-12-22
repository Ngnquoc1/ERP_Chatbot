# 1. NHẬP CÁC THƯ VIỆN CẦN THIẾT
from fastapi import FastAPI
from pydantic import BaseModel
from openai import OpenAI
import odoorpc
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
    # Parse URL để lấy host và port
    from urllib.parse import urlparse
    parsed_url = urlparse(ODOO_URL)
    odoo_host = parsed_url.hostname or 'localhost'
    
    # OdooRPC chỉ hỗ trợ 'jsonrpc' và 'jsonrpc+ssl'
    if parsed_url.scheme == 'https':
        odoo_protocol = 'jsonrpc+ssl'
        odoo_port = parsed_url.port or 443
    else:
        odoo_protocol = 'jsonrpc'
        odoo_port = parsed_url.port or 8069
    
    odoo = odoorpc.ODOO(odoo_host, protocol=odoo_protocol, port=odoo_port)
    odoo.login(ODOO_DB, ODOO_USERNAME, ODOO_PASSWORD)
    print(f"✅ Đã kết nối Odoo thành công! UID: {odoo.env.uid}")
except Exception as e:
    print(f"❌ Lỗi kết nối Odoo: {e}")

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
    TRÍCH XUẤT CHUỖI SỐ ĐỂ TÌM KIẾM
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
        Partner = odoo.env['res.partner']
        
        # --- BƯỚC 1: XÂY DỰNG DOMAIN ---
        # Tìm theo tên (OR name hoặc display_name)
        domain = ['|', ('name', 'ilike', customer_name), ('display_name', 'ilike', customer_name)]

        # Nếu có Phone -> Thêm điều kiện phone với NHIỀU PATTERN
        if phone:
            core_digits = extract_core_digits(phone)
            if core_digits:
                patterns = [core_digits]
                
                # Thêm pattern có dấu cách (VN format: xxx xxx xxx)
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

        # Nếu có Email -> Thêm điều kiện email
        if email:
            domain = ['&'] + domain + [('email', 'ilike', email)]

        # --- BƯỚC 2: TÌM KIẾM ---
        partners = Partner.search_read(domain, ['name', 'phone', 'email'], limit=5)
        
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
        # 1. VALIDATE SẢN PHẨM
        if not product_name or not str(product_name).strip():
            return {
                "suggested_price": 0, 
                "message": "❌ Vui lòng cung cấp tên sản phẩm cần kiểm tra giá", 
                "base_price": 0
            }
        
        # 2. TÌM SẢN PHẨM
        Product = odoo.env['product.product']
        products = Product.search([('name', 'ilike', product_name)], limit=1)
        
        if not products:
            return {"suggested_price": 0, "message": f"❌ Không tìm thấy sản phẩm '{product_name}' trong hệ thống", "base_price": 0}
        
        product = Product.browse(products[0])
        base_price = product.list_price
        
        # Lấy thông tin thuế của sản phẩm
        tax_rate = 0
        if product.taxes_id:
            # Lấy thuế đầu tiên (thường là VAT)
            tax = product.taxes_id[0]
            tax_rate = tax.amount if hasattr(tax, 'amount') else 0
        
        # 3. XÁC ĐỊNH BẢNG GIÁ & KHÁCH HÀNG
        pricelist_id = None
        partner_id = None
        pricelist_name = "Giá niêm yết (Mặc định)"

        if customer_name:
            success, result = find_customer(customer_name, customer_phone, customer_email)
            if success:
                partner_id = result
                Partner = odoo.env['res.partner']
                partner = Partner.browse(partner_id)
                
                if partner.property_product_pricelist:
                    pricelist_id = partner.property_product_pricelist.id
                    pricelist_name = partner.property_product_pricelist.name
            else:
                return {
                    "suggested_price": 0,
                    "message": result,
                    "base_price": 0
                }
        
        # Nếu không có pricelist, dùng pricelist mặc định
        if not pricelist_id:
            Pricelist = odoo.env['product.pricelist']
            default_pricelists = Pricelist.search([('active', '=', True)], limit=1)
            if default_pricelists:
                pricelist_id = default_pricelists[0]
        
        # =================================================================================
        # ⭐ TÍNH GIÁ THEO PRICELIST ITEMS (Compatible with Odoo Standard Logic)
        # =================================================================================
        final_price = base_price
        
        if pricelist_id:
            try:
                PricelistItem = odoo.env['product.pricelist.item']
                
                # Tìm pricelist items áp dụng cho sản phẩm này
                domain = [
                    ('pricelist_id', '=', pricelist_id),
                    '|', ('product_id', '=', product.id),
                    '|', ('product_tmpl_id', '=', product.product_tmpl_id.id),
                         ('applied_on', '=', '3_global')
                ]
                
                items = PricelistItem.search_read(
                    domain,
                    ['applied_on', 'fixed_price', 'percent_price', 'price_discount', 
                     'compute_price', 'min_quantity', 'base'],
                    order='applied_on, min_quantity desc'
                )
                
                # Lọc items phù hợp với quantity
                applicable_item = None
                for item in items:
                    if item.get('min_quantity', 0) <= quantity:
                        applicable_item = item
                        break
                
                if applicable_item:
                    compute_price = applicable_item.get('compute_price', 'fixed')
                    
                    if compute_price == 'fixed':
                        # Giá cố định
                        final_price = applicable_item.get('fixed_price', base_price)
                        print(f"DEBUG - Fixed price: {final_price}")
                        
                    elif compute_price == 'percentage':
                        # Giá theo phần trăm
                        percent = applicable_item.get('percent_price', 0)
                        final_price = base_price * (1 - percent / 100)
                        print(f"DEBUG - Percentage: {percent}% off -> {final_price} (base: {base_price})")
                        
                    elif compute_price == 'formula':
                        # Giá theo công thức
                        base_type = applicable_item.get('base', 'list_price')
                        price_discount = applicable_item.get('price_discount', 0)
                        
                        if base_type == 'list_price':
                            base_for_formula = base_price
                        elif base_type == 'standard_price':
                            base_for_formula = product.standard_price
                        else:
                            base_for_formula = base_price
                        
                        final_price = base_for_formula * (1 - price_discount / 100)
                        print(f"DEBUG - Formula: base={base_for_formula}, discount={price_discount}% -> {final_price}")
                    
                    else:
                        print(f"DEBUG - Unknown compute_price: {compute_price}, using base price")
                else:
                    print(f"DEBUG - No applicable pricelist item found, using base price")
                    
            except Exception as e:
                print(f"DEBUG - Pricelist calculation error: {e}, using base price")
                final_price = base_price

        # 4. TÍNH TOÁN GIÁ CÓ THUẾ
        price_with_tax = final_price * (1 + tax_rate / 100)
        
        # 5. TÍNH TOÁN HIỂN THỊ RÕ RÀNG
        message_parts = []
        
        # Hiển thị giá gốc
        message_parts.append(f"📋 Giá niêm yết: {base_price:,.0f} VNĐ")
        
        # Hiển thị giá sau giảm (nếu có)
        if final_price < base_price:
            discount_percent = ((base_price - final_price) / base_price) * 100
            message_parts.append(f"💰 Giá ưu đãi: {final_price:,.0f} VNĐ (Giảm {discount_percent:.1f}% theo {pricelist_name})")
        elif final_price > base_price:
            message_parts.append(f"💰 Giá điều chỉnh: {final_price:,.0f} VNĐ (theo {pricelist_name})")
        else:
            message_parts.append(f"💰 Giá bán: {final_price:,.0f} VNĐ")
        
        # Hiển thị giá sau thuế
        if tax_rate > 0:
            message_parts.append(f"💵 Giá sau thuế: {price_with_tax:,.0f} VNĐ (+ {tax_rate:.0f}% VAT)")
        
        message = "\n".join(message_parts)
        
        return {
            "product_name": product.name,
            "base_price": base_price,
            "suggested_price": final_price,
            "price_with_tax": price_with_tax,
            "tax_rate": tax_rate,
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
        Partner = odoo.env['res.partner']
        partner = Partner.browse(partner_id)
        
        # 2. Kiểm tra bảng giá
        if not partner.property_product_pricelist:
            return f"Khách hàng {partner.name} đang dùng bảng giá mặc định."
            
        pricelist = partner.property_product_pricelist
        currency_name = pricelist.currency_id.name if pricelist.currency_id else 'VNĐ'

        # 3. Lấy chi tiết các dòng quy tắc (Items)
        PricelistItem = odoo.env['product.pricelist.item']
        pricelist_items = PricelistItem.search_read(
            [('pricelist_id', '=', pricelist.id)],
            ['applied_on', 'categ_id', 'product_tmpl_id', 'product_id',
             'compute_price', 'fixed_price', 'percent_price', 'price_discount',
             'price_surcharge', 'min_quantity'],
            limit=10
        )
        
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
                elif item['applied_on'] == '0_product_variant' and item['product_id']:
                    target = f"📱 {item['product_id'][1]} (Variant)"
                else:
                    target = "Sản phẩm khác"

                # B. Xác định mức giá/chiết khấu
                detail = ""
                min_qty_value = item['min_quantity']
                min_qty_display = int(min_qty_value) if min_qty_value == int(min_qty_value) else min_qty_value
                min_qty = f" (khi mua từ {min_qty_display} sp)" if item['min_quantity'] > 0 else ""

                if item['compute_price'] == 'fixed':
                    detail = f"Giá cố định: {item['fixed_price']:,.0f} {currency_name}"
                elif item['compute_price'] == 'percentage':
                    percent_value = item['percent_price']
                    detail = f"Giảm giá: {percent_value}%"
                elif item['compute_price'] == 'formula':
                    detail = "Áp dụng giá sỉ theo công thức (Giá vốn + Lợi nhuận)"
                    if item.get('price_discount'):
                         detail += f" - Chiết khấu thêm {item['price_discount']}%"

                rules_text += f"\n • {target}{min_qty}: {detail}"

        return f"""📋 CHÍNH SÁCH GIÁ - {partner.name}

🏷️ Hạng thành viên: {pricelist.name}
💱 Đơn vị tiền tệ: {currency_name}
✅ Trạng thái: {'Hoạt động' if pricelist.active else 'Đã khóa'}
{rules_text}"""

    except Exception as e:
        return f"❌ Lỗi hệ thống: {str(e)}"

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
        
        Partner = odoo.env['res.partner']
        partner = Partner.browse(partner_id)
        
        # 2. TÌM SẢN PHẨM & KIỂM TRA TỒN KHO
        Product = odoo.env['product.product']
        products = Product.search([('name', 'ilike', product_name)], limit=1)
        
        if not products:
            return f"❌ Không tìm thấy sản phẩm '{product_name}' trong kho."
        
        product = Product.browse(products[0])
        
        # KIỂM TRA TỒN KHO
        if product.qty_available < quantity:
            return f"⚠️ Không đủ hàng! Sản phẩm '{product.name}' chỉ còn {product.qty_available} máy trong kho."
        
        # 3. GỢI Ý GIÁ
        pricing = suggest_pricing(product_name, customer_name, quantity, customer_phone, customer_email)
        suggested_price = pricing['suggested_price'] if pricing['suggested_price'] > 0 else product.list_price
        print(f"DEBUG - Product: {product.name}, List Price: {product.list_price}, Suggested: {suggested_price}, Pricelist: {pricing.get('pricelist', 'N/A')}")
        
        # 4. TẠO ĐƠN HÀNG
        SaleOrder = odoo.env['sale.order']
        order_id = SaleOrder.create({
            'partner_id': partner_id,
            'note': f'Đơn hàng tạo bởi Chatbot AI - Sales Rep: {sales_rep_name}\n{pricing["message"]}',
            'order_line': [(0, 0, {
                'product_id': product.id,
                'product_uom_qty': quantity,
                'price_unit': suggested_price,
            })]
        })
        
        # Browse order để có thể gọi methods
        order = SaleOrder.browse(order_id)
        
        # 5. XÁC NHẬN ĐƠN HÀNG
        order.action_confirm()
        
        # 6. LẤY THÔNG TIN ĐƠN HÀNG
        print(f"DEBUG - Order: {order.name}, Untaxed: {order.amount_untaxed}, Total: {order.amount_total}")
        
        total_amount = "{:,.0f}".format(order.amount_total)
        discount_msg = ""
        if pricing.get('base_price', 0) > pricing.get('suggested_price', 0):
            discount_msg = f"\n💡 {pricing['message']}"
        
        return f"""✅ Tạo đơn hàng thành công!
        
📋 Mã đơn: {order.name}
👤 Khách hàng: {partner.name}
📱 Sản phẩm: {product.name} x {quantity}
💰 Tổng tiền: {total_amount} VNĐ{discount_msg}
📊 Trạng thái: Đã xác nhận
👨‍💼 Nhân viên: {sales_rep_name}
        
Đơn hàng đã được ghi nhận vào hệ thống!"""
        
    except Exception as e:
        return f" Lỗi khi tạo đơn hàng: {str(e)}. Vui lòng liên hệ quản trị viên."

def get_all_products(limit=10):
    """Lấy danh sách top sản phẩm đang bán"""
    Product = odoo.env['product.product']
    products = Product.search_read(
        [('sale_ok', '=', True)],
        ['name', 'list_price', 'qty_available'],
        limit=limit
    )
    return products

def get_sale_orders(customer_name=None, limit=5, customer_phone=None, customer_email=None):
    """
    Tra cứu đơn hàng theo khách hàng
    """
    try:
        domain = []
        
        if customer_name:
            success, result = find_customer(customer_name, customer_phone, customer_email)
            if not success:
                return result
            domain.append(('partner_id', '=', result))
        
        # Tìm đơn hàng
        SaleOrder = odoo.env['sale.order']
        orders = SaleOrder.search_read(
            domain,
            ['name', 'partner_id', 'amount_total', 'state', 'date_order'],
            limit=limit,
            order='id desc'
        )
        
        if not orders:
            return "📭 Không tìm thấy đơn hàng nào."
        
        result = []
        state_map = {
            'draft': '📝 Nháp',
            'sent': '📧 Đã gửi',
            'sale': '✅ Đã xác nhận',
            'done': '✔️ Hoàn tất',
            'cancel': '❌ Đã hủy'
        }
        
        for order in orders:
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
        SaleOrder = odoo.env['sale.order']
        orders = SaleOrder.search([('name', '=', order_name)])
        
        if not orders:
            return f"❌ Không tìm thấy đơn hàng '{order_name}'"
        
        order = SaleOrder.browse(orders[0])
        
        # Kiểm tra trạng thái
        if order.state == 'cancel':
            return f"⚠️ Đơn hàng {order_name} đã được hủy trước đó."
        
        if order.state == 'done':
            return f"⚠️ Không thể hủy đơn hàng {order_name} vì đã hoàn tất giao hàng."
        
        # Hủy đơn hàng
        order.action_cancel()
        
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
    
    - Xem chính sách giá của khách (VD: "Bảng giá của khách A", "Pricelist for B", "Chính sách giá của khách A"):
      -> {"action": "get_customer_pricelist", "customer": "tên khách","phone": "SĐT (optional)", "email": "email (optional)"}
      
    - Tạo đơn hàng (VD: "Tạo đơn iPhone cho khách A", "Create order Samsung for B"):
      -> {"action": "create_order", "customer": "tên khách", "product": "tên sản phẩm", "qty": số_lượng, "phone": "SĐT (optional)", "email": "email (optional)"}
      
    - Tra cứu đơn hàng (VD: "Xem đơn khách A", "Check orders", "Danh sách đơn hàng gần đây"):
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
        # Gọi hàm lấy danh sách
        products = get_all_products(limit=10)
        if products:
            info_list = []
            for p in products:
                # Tính giá có thuế (giả sử VAT 10% nếu có)
                Product = odoo.env['product.product']
                product_obj = Product.browse(p['id'])
                tax_rate = 0
                if product_obj.taxes_id:
                    tax = product_obj.taxes_id[0]
                    tax_rate = tax.amount if hasattr(tax, 'amount') else 0
                
                price_with_tax = p['list_price'] * (1 + tax_rate / 100)
                price_display = "{:,.0f}".format(price_with_tax)
                info_list.append(f"📱 {p['name']} - Giá: {price_display} đ (Kho: {p['qty_available']})")
            bot_reply = "Dạ, bên em đang sẵn hàng các mẫu này ạ:\n" + "\n".join(info_list)
        else:
            bot_reply = "Hiện tại cửa hàng đang tạm hết hàng ạ."

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
            total_with_tax = pricing.get('price_with_tax', pricing['suggested_price']) * qty
            bot_reply = f"{pricing['message']}\n📦 Số lượng: {qty} chiếc\n💵 Tổng thanh toán: {total_with_tax:,.0f} VNĐ"
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

# --- PHẦN 7: TEST SERVER ---
@app.get("/")
def home():
    return {"message": "Server Chatbot đang chạy ngon lành!"}