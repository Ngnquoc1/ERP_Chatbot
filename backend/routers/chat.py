from fastapi import APIRouter
from openai import OpenAI
import json

from backend.models import ChatRequest, ChatResponse
from backend.config import settings
from backend.services.product_service import product_service
from backend.services.customer_service import customer_service
from backend.services.order_service import order_service
from backend.services.crm_service import crm_service

router = APIRouter()

# Khởi tạo OpenAI client
client = OpenAI(
    base_url=settings.OPENAI_BASE_URL,
    api_key=settings.OPENAI_API_KEY
)

@router.post("/chat", response_model=ChatResponse)
async def chat_endpoint(request: ChatRequest):
    """Endpoint xử lý chat"""
    user_msg = request.message
    print(f"User: {user_msg}")

    # System instruction
    system_instruction = """
    Bạn là trợ lý bán hàng AI thông minh cho hệ thống ERP. Nhiệm vụ:
    1. Phân tích yêu cầu của nhân viên bán hàng
    2. Đề xuất giá phù hợp với từng khách hàng
    3. Hỗ trợ tạo quotation và sales order nhanh chóng
    4. Quản lý cơ hội bán hàng (CRM Opportunity)
    
    QUAN TRỌNG: Trả về kết quả dưới định dạng JSON với các action sau:
    
    CÁC ACTION HỖ TRỢ (JSON format):
    - Tạo cơ hội CRM (VD: "Tạo opportunity cho khách A", "Khách B quan tâm 3 iPhone", "Lead mới: C muốn mua Samsung"):
      -> {"action": "create_opportunity", "customer": "tên khách", "phone": "SĐT (optional)", "email": "email (optional)","qty": 1 (default), "product": "sản phẩm quan tâm (optional)", "note": "ghi chú (optional)"}
    
    - Liệt kê sản phẩm (VD: "Có điện thoại nào?", "Show products", "Liệt kê iPhone", "Tìm Samsung"):
      -> {"action": "list_products", "keyword": "từ khóa tìm kiếm (optional)"}
      Nếu có keyword -> tìm các sản phẩm chứa từ khóa đó
      Nếu không có keyword -> liệt kê top sản phẩm đang bán
      
    - Kiểm tra giá/suggest pricing (VD: "Giá iPhone cho khách A?", "Giá 15 chiếc iPhone?"):
      -> {"action": "suggest_price", "product": "tên sản phẩm", "customer": "tên khách (optional)", "qty": số_lượng (mặc định 1), "phone": "SĐT (optional)", "email": "email (optional)"}
    
    - Xem chính sách giá của khách (VD: "Bảng giá của khách A", "Pricelist for B", "Chính sách giá của khách A"):
      -> {"action": "get_customer_pricelist", "customer": "tên khách","phone": "SĐT (optional)", "email": "email (optional)"}
          - Tạo báo giá/quotation (VD: "Tạo báo giá iPhone cho khách A", "Báo giá 2 iPhone và 3 Samsung cho B"):
      -> {"action": "create_quotation", "customer": "tên khách", "product": "tên sản phẩm", "qty": số_lượng, "phone": "SĐT (optional)", "email": "email (optional)"}
      Lưu ý: Hỗ trợ nhiều sản phẩm: product="iPhone 15;Samsung" và qty="2;3"
      
    - Xác nhận báo giá (VD: "Xác nhận báo giá SO001", "Confirm SO001", "Khách đồng ý báo giá SO001"):
      -> {"action": "confirm_quotation", "order_name": "SO001"}
      
    - Sửa báo giá (VD: "Sửa báo giá SO001 thành 5 máy", "Đổi sản phẩm báo giá SO002 thành Samsung", "Update SO003 quantity 10"):
      -> {"action": "update_quotation", "order_name": "SO001", "product": "tên sản phẩm (optional)", "qty": số_lượng (optional)}
      Lưu ý: Chỉ sửa được báo giá ở trạng thái Draft/Sent. Phải có order_name và ít nhất 1 trong 2: product hoặc qty. Hỗ trợ nhiều sản phẩm: product="iPhone;Samsung" và qty="2;3"
          - Tạo đơn hàng (VD: "Tạo đơn iPhone cho khách A", "Đơn hàng 2 iPhone và 3 Samsung cho B"):
      -> {"action": "create_order", "customer": "tên khách", "product": "tên sản phẩm", "qty": số_lượng, "phone": "SĐT (optional)", "email": "email (optional)"}
      Lưu ý: Hỗ trợ nhiều sản phẩm: product="iPhone 15;Samsung" và qty="2;3"
      
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
    
    # Xây dựng messages
    messages_for_ai = [{"role": "system", "content": system_instruction}]
    
    for msg in request.history:
        role = "assistant" if msg['role'] == "bot" else "user"
        messages_for_ai.append({"role": role, "content": msg['content']})
    
    messages_for_ai.append({"role": "user", "content": user_msg})

    # Gọi AI
    try:
        gpt_response = client.chat.completions.create(
            model=settings.OPENAI_MODEL,
            messages=messages_for_ai,
            response_format={"type": "json_object"}
        )
        
        ai_content = gpt_response.choices[0].message.content
        data = json.loads(ai_content)
        print(f"AI Intent: {data}")

    except Exception as e:
        print(f"Lỗi AI: {e}")
        return ChatResponse(reply="Hệ thống đang bận, vui lòng thử lại sau.")

    # Điều hướng action
    bot_reply = ""
    
    if data['action'] == 'create_opportunity':
        # Tạo cơ hội CRM
        customer = data.get('customer')
        phone = data.get('phone')
        email = data.get('email')
        product = data.get('product')
        qty = int(data.get('qty', 1))
        note = data.get('note')
        
        # Ước tính doanh thu dự kiến dựa trên sản phẩm (nếu có)
        expected_revenue = None
        if product:
            try:
                products = product_service.search_products(product, limit=1)
                if products:
                    price_per_unit = products[0]['list_price']
                    expected_revenue = price_per_unit * qty
            except:
                pass
        
        bot_reply = crm_service.create_opportunity(
            customer_name=customer,
            phone=phone,
            email=email,
            product_interest=product,
            expected_revenue=expected_revenue,
            note=note
        )
    
    elif data['action'] == 'list_products':
        # Liệt kê sản phẩm
        keyword = data.get('keyword')
        
        if keyword:
            products = product_service.search_products(keyword, limit=20)
            if products:
                from backend.utils.formatter import format_currency
                info_list = []
                for p in products:
                    Product = product_service.Product
                    product_obj = Product.browse(p['id'])
                    tax_rate = 0
                    if product_obj.taxes_id:
                        tax = product_obj.taxes_id[0]
                        tax_rate = tax.amount if hasattr(tax, 'amount') else 0
                    
                    price_with_tax = p['list_price'] * (1 + tax_rate / 100)
                    price_display = format_currency(price_with_tax)
                    info_list.append(f"- {p['name']} - Giá: {price_display} VNĐ (Kho: {p['qty_available']})")
                bot_reply = f"Tìm thấy {len(products)} sản phẩm với từ khóa '{keyword}':\n" + "\n".join(info_list)
            else:
                bot_reply = f"Không tìm thấy sản phẩm nào với từ khóa '{keyword}'."
        else:
            products = product_service.get_all_products(limit=10)
            if products:
                from backend.utils.formatter import format_currency
                info_list = []
                for p in products:
                    Product = product_service.Product
                    product_obj = Product.browse(p['id'])
                    tax_rate = 0
                    if product_obj.taxes_id:
                        tax = product_obj.taxes_id[0]
                        tax_rate = tax.amount if hasattr(tax, 'amount') else 0
                    
                    price_with_tax = p['list_price'] * (1 + tax_rate / 100)
                    price_display = format_currency(price_with_tax)
                    info_list.append(f"- {p['name']} - Giá: {price_display} VNĐ (Kho: {p['qty_available']})")
                bot_reply = "Danh sách sản phẩm đang có:\n" + "\n".join(info_list)
            else:
                bot_reply = "Hiện tại không có sản phẩm nào."

    elif data['action'] == 'suggest_price':
        # Gợi ý giá
        product = data.get('product')
        customer = data.get('customer')
        phone = data.get('phone')
        email = data.get('email')
        qty = int(data.get('qty', 1))
        
        pricing = product_service.suggest_pricing(product, customer, qty, phone, email)
        
        if qty > 1:
            from backend.utils.formatter import format_currency
            total_with_tax = pricing.get('price_with_tax', pricing['suggested_price']) * qty
            bot_reply = f"{pricing['message']}\nSố lượng: {qty} chiếc\nTổng thanh toán: {format_currency(total_with_tax)} VNĐ"
        else:
            bot_reply = pricing['message']
    
    elif data['action'] == 'get_customer_pricelist':
        # Xem chính sách giá khách hàng
        customer = data.get('customer')
        phone = data.get('phone')
        email = data.get('email')
        bot_reply = customer_service.get_customer_pricelist(customer, phone, email)
    
    elif data['action'] == 'create_quotation':
        # Tạo báo giá
        qty = data.get('qty', 1)
        sales_rep = request.sales_rep_name
        phone = data.get('phone')
        email = data.get('email')
        bot_reply = order_service.create_quotation(
            data['customer'], data['product'], qty, sales_rep, phone, email
        )
    
    elif data['action'] == 'confirm_quotation':
        # Xác nhận báo giá
        order_name = data.get('order_name')
        sales_rep = request.sales_rep_name
        if order_name:
            bot_reply = order_service.confirm_quotation(order_name, sales_rep)
        else:
            bot_reply = "⚠️ Vui lòng cung cấp mã báo giá cần xác nhận (VD: SO001)"
    
    elif data['action'] == 'update_quotation':
        # Cập nhật báo giá
        order_name = data.get('order_name')
        product = data.get('product')
        qty = data.get('qty')
        sales_rep = request.sales_rep_name
        
        if order_name:
            # Không parse qty ở đây, để update_quotation xử lý multiple products
            bot_reply = order_service.update_quotation(order_name, product, qty, sales_rep)
        else:
            bot_reply = "⚠️ Vui lòng cung cấp mã báo giá cần cập nhật (VD: SO001)"
    
    elif data['action'] == 'create_order':
        # Tạo đơn hàng trực tiếp
        qty = data.get('qty', 1)
        sales_rep = request.sales_rep_name
        phone = data.get('phone')
        email = data.get('email')
        bot_reply = order_service.create_sale_order(
            data['customer'], data['product'], qty, sales_rep, phone, email
        )
    
    elif data['action'] == 'check_orders':
        # Tra cứu đơn hàng
        customer = data.get('customer')
        phone = data.get('phone')
        email = data.get('email')
        bot_reply = order_service.get_sale_orders(
            customer_name=customer, limit=10, customer_phone=phone, customer_email=email
        )
    
    elif data['action'] == 'cancel_order':
        # Hủy đơn hàng
        order_name = data.get('order_name')
        if order_name:
            bot_reply = order_service.cancel_sale_order(order_name)
        else:
            bot_reply = "⚠️ Vui lòng cung cấp mã đơn hàng cần hủy (VD: SO001)"

    else:  # action == 'chat'
        bot_reply = data.get('response', "Em chưa hiểu ý anh chị lắm.")
    
    return ChatResponse(reply=bot_reply)