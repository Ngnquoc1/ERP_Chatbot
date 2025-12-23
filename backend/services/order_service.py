from backend.services.odoo_service import odoo_service
from backend.services.customer_service import customer_service
from backend.services.product_service import product_service
from backend.utils.formatter import format_order_response, format_currency

class OrderService:
    """Service quản lý logic đơn hàng"""
    
    def __init__(self):
        self.SaleOrder = odoo_service.get_model('sale.order')
    
    def create_quotation(self, customer_name: str, product_name: str, quantity,
                        sales_rep_name: str = "Admin", customer_phone: str = None, 
                        customer_email: str = None) -> str:
        """Tạo báo giá (Quotation). Hỗ trợ nhiều sản phẩm với format 'product1;product2' và 'qty1;qty2'"""
        try:
            # 1. TÌM KHÁCH HÀNG
            success, partner_id = customer_service.find_customer(customer_name, customer_phone, customer_email)
            if not success:
                return partner_id  # Error message
            
            # 2. PARSE MULTIPLE PRODUCTS VÀ QUANTITIES
            products = []
            quantities = []
            
            if product_name and ';' in str(product_name):
                products = [p.strip() for p in str(product_name).split(';')]
            elif product_name:
                products = [product_name]
            
            if quantity:
                if ';' in str(quantity):
                    try:
                        quantities = [int(q.strip()) for q in str(quantity).split(';')]
                    except ValueError:
                        return "❌ Số lượng không hợp lệ. Vui lòng nhập dạng '2;20' hoặc '5'"
                else:
                    try:
                        quantities = [int(quantity)]
                    except ValueError:
                        return "❌ Số lượng phải là số nguyên"
            else:
                quantities = [1] * len(products)
            
            # Validate
            if len(products) != len(quantities):
                return f"❌ Số sản phẩm ({len(products)}) và số lượng ({len(quantities)}) không khớp. VD: 'iPhone 15;Samsung' với '2;5'"
            
            # 3. GỢI Ý GIÁ VÀ TẠO ORDER LINES (GIỐNG MAIN_OLD.PY)
            order_lines = []
            product_details = []
            
            for idx, prod_name in enumerate(products):
                qty = quantities[idx]
                
                # GỌI SUGGEST_PRICING CHO TỪNG SẢN PHẨM
                pricing = product_service.suggest_pricing(prod_name, customer_name, qty, customer_phone, customer_email)
                
                if pricing.get('is_ambiguous'):
                    return f"❌ Sản phẩm '{prod_name}' mơ hồ.\n{pricing['message']}"
                
                if not pricing.get('product_id'):
                    return f"❌ Không tìm thấy sản phẩm '{prod_name}'.\n{pricing['message']}"
                
                # DÙNG SUGGESTED_PRICE TỪ SUGGEST_PRICING (QUAN TRỌNG!)
                order_lines.append((0, 0, {
                    'product_id': pricing['product_id'],
                    'product_uom_qty': qty,
                    'price_unit': pricing['suggested_price'],  # ✅ Lấy giá từ suggest_pricing
                }))
                
                product_details.append(f"{pricing['product_name']} x {qty}")
            
            # 4. TẠO QUOTATION (DRAFT)
            SaleOrder = self.SaleOrder
            order_id = SaleOrder.create({
                'partner_id': partner_id,
                'note': f'Báo giá tạo bởi Chatbot AI - Sales Rep: {sales_rep_name}\nGồm {len(products)} sản phẩm',
                'order_line': order_lines
            })
            
            order = SaleOrder.browse(order_id)
            
            # 5. TRẢ VỀ RESPONSE
            return format_order_response(order, "📝 Chờ xác nhận (Draft)", sales_rep_name, is_quotation=True)
        except Exception as e:
            return f"❌ Lỗi khi tạo báo giá: {str(e)}"  
    
    def confirm_quotation(self, order_name: str, sales_rep_name: str = "Admin") -> str:
        """Xác nhận báo giá"""
        try:
            SaleOrder = self.SaleOrder
            orders = SaleOrder.search([('name', '=', order_name)])
            
            if not orders:
                return f"❌ Không tìm thấy báo giá '{order_name}'"
            
            order = SaleOrder.browse(orders[0])
            
            # Kiểm tra trạng thái
            if order.state == 'sale':
                return f"⚠️ Báo giá {order_name} đã được xác nhận trước đó rồi!"
            
            if order.state == 'cancel':
                return f"❌ Báo giá {order_name} đã bị hủy, không thể xác nhận!"
            
            if order.state not in ['draft', 'sent']:
                return f"⚠️ Báo giá {order_name} có trạng thái '{order.state}', không thể xác nhận!"
            
            # XÁC NHẬN QUOTATION → SALE ORDER
            order.action_confirm()
            
            return format_order_response(order, "✅ Đã xác nhận", f"Nhân viên xác nhận: {sales_rep_name}", is_quotation=False)
            
        except Exception as e:
            return f"❌ Lỗi khi xác nhận báo giá: {str(e)}"
    
    def update_quotation(self, order_name: str, product_name: str = None, 
                        quantity = None, sales_rep_name: str = "Admin") -> str:
        """Cập nhật báo giá (chỉ khi ở trạng thái draft/sent). Hỗ trợ nhiều sản phẩm với format 'product1;product2' và 'qty1;qty2'"""
        try:
            SaleOrder = self.SaleOrder
            orders = SaleOrder.search([('name', '=', order_name)])
            
            if not orders:
                return f"❌ Không tìm thấy báo giá '{order_name}'"
            
            order = SaleOrder.browse(orders[0])
            
            # Chỉ cho phép sửa khi còn draft/sent
            if order.state not in ['draft', 'sent']:
                return f"⚠️ Chỉ có thể sửa báo giá ở trạng thái Nháp hoặc Đã gửi. Báo giá {order_name} đang ở trạng thái '{order.state}'"
            
            # Lấy thông tin khách hàng
            customer_name = order.partner_id.name
            
            # Parse multiple products và quantities
            products = []
            quantities = []
            
            if product_name and ';' in str(product_name):
                # Multiple products
                products = [p.strip() for p in str(product_name).split(';')]
            elif product_name:
                products = [product_name]
            
            if quantity:
                if ';' in str(quantity):
                    # Multiple quantities
                    try:
                        quantities = [int(q.strip()) for q in str(quantity).split(';')]
                    except ValueError:
                        return "❌ Số lượng không hợp lệ. Vui lòng nhập dạng '2;20' hoặc '5'"
                else:
                    try:
                        quantities = [int(quantity)]
                    except ValueError:
                        return "❌ Số lượng phải là số nguyên"
            
            # Validate số lượng products và quantities phải khớp
            if products and quantities and len(products) != len(quantities):
                return f"❌ Số sản phẩm ({len(products)}) và số lượng ({len(quantities)}) không khớp. VD đúng: 'iPhone 15;iPhone 14' với số lượng '2;20'"
            
            # Nếu không có product, chỉ đổi số lượng dòng đầu tiên
            if not products and quantities and len(quantities) == 1 and order.order_line:
                order.order_line[0].write({'product_uom_qty': quantities[0]})
                product_display = f"{order.order_line[0].product_id.name} x {quantities[0]}"
            
            # Nếu có products - Xóa tất cả và tạo lại
            elif products:
                # Xóa dòng cũ
                if order.order_line:
                    order.order_line.unlink()
                
                # Thêm từng dòng mới
                new_lines = []
                product_details = []
                
                for idx, prod_name in enumerate(products):
                    qty = quantities[idx] if idx < len(quantities) else 1
                    
                    pricing = product_service.suggest_pricing(
                        prod_name, 
                        customer_name, 
                        qty
                    )
                    
                    if pricing.get('is_ambiguous'):
                        return f"❌ Sản phẩm '{prod_name}' mơ hồ.\n{pricing['message']}"
                    
                    if not pricing.get('product_id'):
                        return f"❌ Không tìm thấy sản phẩm '{prod_name}'.\n{pricing['message']}"
                    
                    new_lines.append((0, 0, {
                        'product_id': pricing['product_id'],
                        'product_uom_qty': qty,
                        'price_unit': pricing['suggested_price'],
                    }))
                    
                    product_details.append(f"  • {pricing['product_name']} x {qty} - {format_currency(pricing['suggested_price'] * qty)} VNĐ")
                
                # Cập nhật order
                order.write({
                    'order_line': new_lines,
                    'note': f"Báo giá cập nhật bởi Chatbot AI - Sales Rep: {sales_rep_name}\nCập nhật {len(products)} sản phẩm"
                })
                
                product_display = "\n".join(product_details)
            else:
                return "⚠️ Vui lòng cung cấp sản phẩm hoặc số lượng cần thay đổi"
            
            # Refresh order để lấy giá mới
            order = SaleOrder.browse(order.id)
            
            return f"""✅ ĐÃ CẬP NHẬT BÁO GIÁ {order_name}

📋 Thông tin mới:
Khách hàng: {order.partner_id.name}
Danh sách sản phẩm:
{product_display}

💰 Tổng tiền: {format_currency(order.amount_total)} VNĐ
📝 Cập nhật bởi: {sales_rep_name}"""
            
        except Exception as e:
            return f"❌ Lỗi khi cập nhật báo giá: {str(e)}"
    
    def create_sale_order(self, customer_name: str, product_name: str, quantity,
                         sales_rep_name: str = "Admin", customer_phone: str = None,
                         customer_email: str = None) -> str:
        """Tạo đơn hàng nhanh - Tạo và xác nhận luôn. Hỗ trợ nhiều sản phẩm với format 'product1;product2' và 'qty1;qty2'"""
        try:
            # 1. TÌM KHÁCH HÀNG
            success, partner_id = customer_service.find_customer(customer_name, customer_phone, customer_email)
            if not success:
                return partner_id  # Error message
            
            # 2. PARSE MULTIPLE PRODUCTS VÀ QUANTITIES
            products = []
            quantities = []
            
            if product_name and ';' in str(product_name):
                products = [p.strip() for p in str(product_name).split(';')]
            elif product_name:
                products = [product_name]
            
            if quantity:
                if ';' in str(quantity):
                    try:
                        quantities = [int(q.strip()) for q in str(quantity).split(';')]
                    except ValueError:
                        return "❌ Số lượng không hợp lệ. Vui lòng nhập dạng '2;20' hoặc '5'"
                else:
                    try:
                        quantities = [int(quantity)]
                    except ValueError:
                        return "❌ Số lượng phải là số nguyên"
            else:
                quantities = [1] * len(products)
            
            # Validate
            if len(products) != len(quantities):
                return f"❌ Số sản phẩm ({len(products)}) và số lượng ({len(quantities)}) không khớp. VD: 'iPhone 15;Samsung' với '2;5'"
            
            # 3. GỢI Ý GIÁ VÀ TẠO ORDER LINES
            order_lines = []
            product_details = []
            
            for idx, prod_name in enumerate(products):
                qty = quantities[idx]
                
                pricing = product_service.suggest_pricing(prod_name, customer_name, qty, customer_phone, customer_email)
                
                if pricing.get('is_ambiguous'):
                    return f"❌ Sản phẩm '{prod_name}' mơ hồ.\n{pricing['message']}"
                
                if not pricing.get('product_id'):
                    return f"❌ Không tìm thấy sản phẩm '{prod_name}'.\n{pricing['message']}"
                
                order_lines.append((0, 0, {
                    'product_id': pricing['product_id'],
                    'product_uom_qty': qty,
                    'price_unit': pricing['suggested_price'],
                }))
                
                product_details.append(f"{pricing['product_name']} x {qty}")
                print(f"DEBUG - Product: {pricing['product_name']}, List Price: {pricing['base_price']}, Suggested: {pricing['suggested_price']}, Pricelist: {pricing.get('pricelist', 'N/A')}")
            
            # 4. TẠO VÀ XÁC NHẬN ĐƠN HÀNG
            SaleOrder = self.SaleOrder
            order_id = SaleOrder.create({
                'partner_id': partner_id,
                'note': f'Đơn hàng tạo bởi Chatbot AI - Sales Rep: {sales_rep_name}\nGồm {len(products)} sản phẩm',
                'order_line': order_lines
            })
            
            order = SaleOrder.browse(order_id)
            order.action_confirm()
            
            print(f"DEBUG - Order: {order.name}, Untaxed: {order.amount_untaxed}, Total: {order.amount_total}")
            
            return format_order_response(order, "Tạo đơn hàng thành công", sales_rep_name, is_quotation=False)
            
        except Exception as e:
            return f"❌ Lỗi khi tạo đơn hàng: {str(e)}. Vui lòng liên hệ quản trị viên."
    
    def get_sale_orders(self, customer_name: str = None, limit: int = 5,
                       customer_phone: str = None, customer_email: str = None) -> str:
        """Tra cứu đơn hàng"""
        try:
            domain = []
            
            if customer_name:
                success, partner_id = customer_service.find_customer(customer_name, customer_phone, customer_email)
                if not success:
                    return partner_id
                domain.append(('partner_id', '=', partner_id))
            
            # Tìm đơn hàng (không dùng search_read để có thể browse picking_ids)
            SaleOrder = self.SaleOrder
            order_ids = SaleOrder.search(domain, limit=limit, order='id desc')
            
            if not order_ids:
                return "Không tìm thấy đơn hàng nào."
            
            # Map trạng thái đơn hàng
            state_map = {
                'draft': 'Nháp',
                'sent': 'Đã gửi',
                'sale': 'Đã xác nhận',
                'done': 'Hoàn tất',
                'cancel': 'Đã hủy'
            }
            
            # Map trạng thái hóa đơn (Field chuẩn Odoo)
            invoice_map = {
                'upselling': 'Chờ hóa đơn',
                'invoiced': 'Đã xuất HĐ',
                'to invoice': 'Cần xuất HĐ',
                'no': 'Không HĐ'
            }
            
            # Map trạng thái giao hàng (Tính toán)
            delivery_map = {
                'pending': 'Chờ giao',
                'partial': 'Giao 1 phần',
                'full': 'Đã giao đủ',
                'no': 'Không giao'
            }
            
            result = []
            for order_id in order_ids:
                order = SaleOrder.browse(order_id)
                
                # Lấy thông tin sản phẩm
                products_info = []
                for line in order.order_line:
                    products_info.append(f"{line.product_id.name} x {int(line.product_uom_qty)}")
                
                # Xác định trạng thái giao hàng
                delivery_status = 'no'
                if order.picking_ids:
                    picking_states = [p.state for p in order.picking_ids]
                    if all(s == 'done' for s in picking_states):
                        delivery_status = 'full'
                    elif any(s == 'done' for s in picking_states):
                        delivery_status = 'partial'
                    else:
                        delivery_status = 'pending'
                
                order_info = f"• {order.name} - {order.partner_id.name} - {format_currency(order.amount_total)} VNĐ\n  [{state_map.get(order.state, order.state)}] [{invoice_map.get(order.invoice_status, order.invoice_status)}] [{delivery_map.get(delivery_status, delivery_status)}]"
                result.append(order_info)
            
            return "DANH SÁCH ĐƠN HÀNG:\n\n" + "\n\n".join(result)
            
        except Exception as e:
            return f"❌ Lỗi tra cứu: {str(e)}"
    
    def cancel_sale_order(self, order_name: str) -> str:
        """Hủy đơn hàng"""
        try:
            SaleOrder = self.SaleOrder
            orders = SaleOrder.search([('name', '=', order_name)])
            
            # 1. KIỂM TRA TỒN TẠI
            if not orders:
                return f"❌ Không tìm thấy đơn hàng '{order_name}'"
            
            order = SaleOrder.browse(orders[0])
            print(f"DEBUG - Cancel Order: {order.name}, State: {order.state}")
            
            # 2. KIỂM TRA TRẠNG THÁI CƠ BẢN
            if order.state == 'cancel':
                return f"⚠️ Đơn hàng {order_name} đã bị hủy trước đó rồi!"
            
            if order.state == 'done':
                return f"❌ Không thể hủy đơn hàng {order_name} vì đã hoàn tất (done). Vui lòng liên hệ quản trị viên."
            
            # 3. KIỂM TRA HÓA ĐƠN (INVOICE)
            if order.invoice_ids:
                invoice_states = [inv.state for inv in order.invoice_ids]
                
                # Kiểm tra có hóa đơn đã xác nhận (posted)
                if 'posted' in invoice_states:
                    invoices_info = []
                    for inv in order.invoice_ids:
                        if inv.state == 'posted':
                            invoices_info.append(f"{inv.name} ({inv.state})")
                    
                    return f"""❌ KHÔNG THỂ HỦY ĐƠN HÀNG {order_name}

Lý do: Đã có hóa đơn được xác nhận:
{chr(10).join(invoices_info)}

 Giải pháp:
1. Hủy/Đảo ngược (Reverse) các hóa đơn trong Odoo trước
2. Sau đó mới có thể hủy đơn hàng

⚠️ Lưu ý: Thao tác này cần quyền Kế toán/Quản trị viên"""
                
                # Nếu chỉ có draft invoice -> Có thể hủy được
                if all(s == 'draft' for s in invoice_states):
                    print(f"INFO - Order {order_name} has only draft invoices, can proceed to cancel")
            
            # 4. KIỂM TRA PHIẾU GIAO HÀNG (DELIVERY/PICKING)
            if order.picking_ids:
                picking_states = [pick.state for pick in order.picking_ids]
                
                # Kiểm tra có phiếu đã giao hàng (done)
                if 'done' in picking_states:
                    pickings_info = []
                    for pick in order.picking_ids:
                        if pick.state == 'done':
                            pickings_info.append(f"{pick.name} ({pick.state})")
                    
                    return f"""❌ KHÔNG THỂ HỦY ĐƠN HÀNG {order_name}

Lý do: Đã có phiếu giao hàng hoàn tất:
{chr(10).join(pickings_info)}

 Giải pháp:
1. Tạo phiếu trả hàng (Return) trong Odoo
2. Sau đó mới có thể hủy đơn hàng

⚠️ Lưu ý: Cần kiểm tra kho hàng và quy trình hoàn trả"""
            
            # 5. THỰC HIỆN HỦY ĐƠN HÀNG
            print(f"DEBUG - All checks passed, proceeding to cancel order {order_name}")
            order.action_cancel()
            
            # 6. XÁC NHẬN ĐÃ HỦY THÀNH CÔNG
            order_after = SaleOrder.browse(order.id)
            if order_after.state == 'cancel':
                return f"""✅ ĐÃ HỦY ĐƠN HÀNG THÀNH CÔNG

Mã đơn: {order_name}
Khách hàng: {order.partner_id.name}
Tổng tiền: {format_currency(order.amount_total)} VNĐ
Trạng thái: Đã hủy (Cancelled)

 Tồn kho đã được hoàn lại (nếu đã reserve)"""
            else:
                return f"⚠️ Lệnh hủy đã thực thi nhưng trạng thái vẫn là '{order_after.state}'. Vui lòng kiểm tra lại trong Odoo."
            
        except Exception as e:
            error_msg = str(e)
            print(f"ERROR - Cancel order failed: {error_msg}")
            
            # Phân tích lỗi cụ thể
            if "invoice" in error_msg.lower():
                return f"""❌ LỖI HỦY ĐƠN HÀNG: {order_name}

Nguyên nhân: Có vấn đề với hóa đơn
Chi tiết: {error_msg}

 Giải pháp:
1. Vào Odoo → Tìm đơn hàng {order_name}
2. Kiểm tra tab Invoices
3. Hủy hoặc xóa các hóa đơn draft/posted
4. Thử lại lệnh hủy đơn"""
            
            elif "picking" in error_msg.lower() or "delivery" in error_msg.lower():
                return f"""❌ LỖI HỦY ĐƠN HÀNG: {order_name}

Nguyên nhân: Có vấn đề với phiếu giao hàng
Chi tiết: {error_msg}

 Giải pháp:
1. Vào Odoo → Tìm đơn hàng {order_name}
2. Kiểm tra tab Delivery
3. Hủy hoặc trả hàng (Return) các phiếu giao hàng
4. Thử lại lệnh hủy đơn"""
            
            elif "done" in error_msg.lower():
                return f"❌ Đơn hàng {order_name} đã hoàn tất, không thể hủy. Liên hệ quản trị viên."
            
            else:
                return f"❌ Lỗi khi hủy đơn hàng: {error_msg}"

# Singleton instance
order_service = OrderService()