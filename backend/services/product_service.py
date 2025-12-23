from typing import Tuple, List, Dict, Any
from backend.services.odoo_service import odoo_service
from backend.utils.formatter import format_currency, format_discount_message

class ProductService:
    """Service quản lý logic sản phẩm"""
    
    def __init__(self):
        self.Product = odoo_service.get_model('product.product')
    
    def handle_ambiguous_product(self, product_name: str) -> Tuple[bool, any]:
        """
        Xử lý khi tên sản phẩm mơ hồ
        
        Returns:
            Tuple[bool, any]: (is_single, result)
            - is_single=True: result = product_id (duy nhất 1 sản phẩm)
            - is_single=False: result = message (nhiều sản phẩm hoặc không tìm thấy)
        """
        try:
            products = self.Product.search_read(
                [('name', 'ilike', product_name), ('sale_ok', '=', True)],
                ['name', 'list_price', 'qty_available'],
                limit=15
            )
            
            if len(products) == 0:
                return (False, f"❌ Không tìm thấy sản phẩm '{product_name}' trong hệ thống.")
            
            elif len(products) == 1:
                return (True, products[0]['id'])
            
            else:
                # Nhiều sản phẩm -> Hiển thị danh sách
                product_list = []
                for i, p in enumerate(products, 1):
                    product_obj = self.Product.browse(p['id'])
                    tax_rate = 0
                    if product_obj.taxes_id:
                        tax = product_obj.taxes_id[0]
                        tax_rate = tax.amount if hasattr(tax, 'amount') else 0
                    
                    price_with_tax = p['list_price'] * (1 + tax_rate / 100)
                    stock_status = f"Kho: {p['qty_available']}" if p['qty_available'] > 0 else "⚠️ Hết hàng"
                    product_list.append(
                        f"{i}. {p['name']} - {format_currency(price_with_tax)} VNĐ ({stock_status})"
                    )
                
                message = f"""⚠️ Tìm thấy {len(products)} sản phẩm với từ khóa '{product_name}':

{chr(10).join(product_list)}

💡 Vui lòng chọn chính xác tên sản phẩm cần xử lý."""
                
                return (False, message)
        
        except Exception as e:
            return (False, f"❌ Lỗi hệ thống: {str(e)}")
    
    def suggest_pricing(self, product_name: str, customer_name: str = None, 
                       quantity: int = 1, customer_phone: str = None, 
                       customer_email: str = None) -> Dict[str, Any]:
        """
        Gợi ý giá chuẩn Odoo + Xử lý sản phẩm mơ hồ
        
        Returns:
            dict với các field: is_ambiguous, product_id, product_name, 
            base_price, suggested_price, price_with_tax, tax_rate, 
            quantity, pricelist, message
        """
        try:
            # Import customer_service ở đây để tránh circular import
            from backend.services.customer_service import customer_service
            
            # 1. VALIDATE SẢN PHẨM
            if not product_name or not str(product_name).strip():
                return {
                    "is_ambiguous": False,
                    "product_id": None,
                    "suggested_price": 0,
                    "message": "❌ Vui lòng cung cấp tên sản phẩm",
                    "base_price": 0
                }
            
            # 2. XỬ LÝ SẢN PHẨM MƠ HỒ
            is_single, result = self.handle_ambiguous_product(product_name)
            if not is_single:
                # Nhiều sản phẩm hoặc không tìm thấy
                return {
                    "is_ambiguous": True,
                    "product_id": None,
                    "suggested_price": 0,
                    "message": result,
                    "base_price": 0
                }
            
            product_id = result
            
            # 3. LẤY SẢN PHẨM
            product = self.Product.browse(product_id)
            base_price = product.list_price
            
            # 4. KIỂM TRA TỒN KHO (nếu có quantity)
            if quantity and product.qty_available < quantity:
                return {
                    "is_ambiguous": False,
                    "product_id": None,
                    "suggested_price": 0,
                    "message": f"❌ Sản phẩm '{product.name}' không đủ tồn kho.\n" +
                              f"Yêu cầu: {quantity} | Có sẵn: {product.qty_available}",
                    "base_price": base_price
                }
            
            # 5. Lấy thông tin thuế của sản phẩm
            tax_rate = 0
            if product.taxes_id:
                tax = product.taxes_id[0]
                tax_rate = tax.amount if hasattr(tax, 'amount') else 0
            
            # 6. XÁC ĐỊNH BẢNG GIÁ & KHÁCH HÀNG
            pricelist_id = None
            partner_id = None
            pricelist_name = "Giá niêm yết (Mặc định)"

            if customer_name:
                success, result = customer_service.find_customer(
                    customer_name, customer_phone, customer_email
                )
                
                if success:
                    partner_id = result
                    Partner = odoo_service.get_model('res.partner')
                    partner = Partner.browse(partner_id)
                    
                    if partner.property_product_pricelist:
                        pricelist_id = partner.property_product_pricelist.id
                        pricelist_name = partner.property_product_pricelist.name
            
            # Nếu không có pricelist, dùng pricelist mặc định
            if not pricelist_id:
                Pricelist = odoo_service.get_model('product.pricelist')
                default_pricelists = Pricelist.search([('active', '=', True)], limit=1)
                if default_pricelists:
                    pricelist_id = default_pricelists[0]
            
            # 7. TÍNH GIÁ THEO PRICELIST ITEMS (LOGIC TỪ MAIN_OLD.PY)
            final_price = base_price
            
            if pricelist_id:
                try:
                    PricelistItem = odoo_service.get_model('product.pricelist.item')
                    
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

            # 8. TÍNH TOÁN GIÁ CÓ THUẾ
            price_with_tax = final_price * (1 + tax_rate / 100)
            
            # 9. TÍNH TOÁN HIỂN THỊ RÕ RÀNG
            message_parts = [
                f"Giá niêm yết: {format_currency(base_price)} VNĐ",
                format_discount_message(base_price, final_price, pricelist_name)
            ]
            
            # Hiển thị giá sau thuế
            if tax_rate > 0:
                message_parts.append(f"Giá sau thuế ({tax_rate}%): {format_currency(price_with_tax)} VNĐ")
            
            message = "\n".join(message_parts)
            
            return {
                "is_ambiguous": False,
                "product_id": product_id,
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
            return {
                "is_ambiguous": False,
                "product_id": None,
                "suggested_price": 0, 
                "message": f"❌ Lỗi hệ thống: {str(e)}",
                "base_price": 0
            }
    
    def search_products(self, keyword: str, limit: int = 20) -> List[dict]:
        """Tìm kiếm sản phẩm theo từ khóa"""
        try:
            products = self.Product.search_read(
                [('sale_ok', '=', True), ('name', 'ilike', keyword)],
                ['name', 'list_price', 'qty_available'],
                limit=limit
            )
            return products
        except Exception as e:
            print(f"Lỗi tìm kiếm sản phẩm: {e}")
            return []
    
    def get_all_products(self, limit: int = 10) -> List[dict]:
        """Lấy danh sách top sản phẩm đang bán"""
        products = self.Product.search_read(
            [('sale_ok', '=', True)],
            ['name', 'list_price', 'qty_available'],
            limit=limit
        )
        return products

# Singleton instance
product_service = ProductService()