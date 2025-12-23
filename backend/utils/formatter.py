def format_currency(amount: float) -> str:
    """Format số tiền thành chuỗi có dấu phẩy"""
    return "{:,.0f}".format(amount)

def format_discount_message(base_price: float, final_price: float, pricelist_name: str) -> str:
    """Format thông điệp giảm giá"""
    if final_price < base_price:
        discount_percent = ((base_price - final_price) / base_price) * 100
        return f"Giá ưu đãi: {format_currency(final_price)} VNĐ (Giảm {discount_percent:.1f}% theo {pricelist_name})"
    elif final_price > base_price:
        return f"Giá điều chỉnh: {format_currency(final_price)} VNĐ (theo {pricelist_name})"
    else:
        return f"Giá bán: {format_currency(final_price)} VNĐ"

def extract_core_digits(phone: str) -> str:
    """Trích xuất chuỗi số từ số điện thoại"""
    if not phone:
        return None
    
    phone_str = str(phone).strip()
    digits = ''.join(c for c in phone_str if c.isdigit())
    
    if not digits:
        return None
    
    # Nếu bắt đầu bằng 0 và đủ 10 số (VN) -> cắt số 0
    if digits.startswith('0') and len(digits) == 10:
        return digits[1:]
    
    return digits

def format_order_response(order, status_text: str, sales_rep: str = None, is_quotation: bool = False) -> str:
    """Format phản hồi đơn hàng/báo giá thống nhất"""
    products_info = []
    for line in order.order_line:
        products_info.append(f"{line.product_id.name} x {int(line.product_uom_qty)}")
    
    info = {
        'name': order.name,
        'customer': order.partner_id.name,
        'products': ', '.join(products_info),
        'total': format_currency(order.amount_total),
        'state': order.state
    }
    
    if is_quotation:
        result = f"""✅ Tạo báo giá thành công!
        
Mã báo giá: {info['name']}
Khách hàng: {info['customer']}
Sản phẩm: {info['products']}
Tổng tiền: {info['total']} VNĐ
Trạng thái: {status_text}"""
        if sales_rep:
            result += f"\nNhân viên: {sales_rep}"
        result += f"\n\n➡ Khi khách đồng ý, dùng lệnh: \"Xác nhận báo giá {info['name']}\""
    else:
        result = f"""✅ {status_text}!
        
Mã đơn: {info['name']}
Khách hàng: {info['customer']}
Sản phẩm: {info['products']}
Tổng tiền: {info['total']} VNĐ
Trạng thái: {status_text}"""
        if sales_rep:
            result += f"\nNhân viên: {sales_rep}"
        if not is_quotation:
            result += "\n\nĐơn hàng đã được ghi nhận vào hệ thống!"
    
    return result