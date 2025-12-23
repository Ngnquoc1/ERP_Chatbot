# 🤖 AI Chatbot for Sales Process in ERP

> **AI Chatbot hỗ trợ nhân viên bán hàng tạo Báo giá và Đơn hàng trong hệ thống ERP. Chatbot phân tích yêu cầu khách hàng, gợi ý giá thông minh, và tự động tạo đơn hàng.**

---

## 📋 Tổng quan

Hệ thống AI Chatbot tích hợp với **Odoo ERP** để hỗ trợ nhân viên bán hàng:

✅ **Phân tích khách hàng thông minh** - Tìm kiếm theo tên, SĐT, email  
✅ **Gợi ý giá theo chính sách** - Áp dụng pricelist, discount tự động  
✅ **Tạo báo giá & đơn hàng** - Hỗ trợ nhiều sản phẩm trong 1 đơn  
✅ **Sửa đổi báo giá** - Cập nhật sản phẩm, số lượng trước khi xác nhận  
✅ **Quản lý CRM Opportunity** - Theo dõi cơ hội bán hàng  
✅ **Audit trail** - Ghi nhận nhân viên tạo/xử lý đơn  

---

## ⭐ Tính năng Chính

### 1️⃣ **Quản lý Báo giá (Quotation)**
- ✅ Tạo báo giá với nhiều sản phẩm
- ✅ Xác nhận báo giá → chuyển thành đơn hàng
- ✅ **Sửa báo giá** (thêm/bớt/đổi sản phẩm)
- ✅ Tự động áp dụng giá theo chính sách khách hàng

### 2️⃣ **Quản lý Đơn hàng (Sales Order)**
- ✅ Tạo đơn hàng nhanh (tạo + xác nhận 1 bước)
- ✅ Hỗ trợ nhiều sản phẩm với số lượng khác nhau
- ✅ Tra cứu đơn hàng theo khách hàng
- ✅ Hủy đơn hàng với validation đầy đủ

### 3️⃣ **Gợi ý Giá Thông minh (Smart Pricing)**
- ✅ Tự động lấy giá từ Pricelist của khách hàng
- ✅ Áp dụng discount theo rule (Fixed, Percentage, Formula)
- ✅ Tính thuế VAT tự động
- ✅ Kiểm tra tồn kho trước khi báo giá

### 4️⃣ **Tìm kiếm & Tra cứu**
- ✅ Tìm khách hàng theo tên/SĐT/email
- ✅ Tìm sản phẩm với fuzzy search
- ✅ Xử lý sản phẩm mơ hồ (hiển thị danh sách)
- ✅ Xem chính sách giá của khách hàng

### 5️⃣ **CRM Integration**
- ✅ Tạo CRM Opportunity cho lead mới
- ✅ Ước tính doanh thu dự kiến
- ✅ Gán nhân viên phụ trách

---

## 🛠️ Công nghệ

**Backend:**  
- FastAPI (REST API)
- OdooRPC (Odoo XML-RPC integration)
- Groq AI (Llama 3.3 70B Versatile)
- Pydantic (Data validation)

**Frontend:**  
- React 18
- Vite
- Axios

**Database:**  
- Odoo PostgreSQL (via Odoo ERP)

---

## 📦 Cài đặt

### 1️⃣ Requirements
- Python 3.8+
- Node.js 16+
- Odoo 14+ (running)

### 2️⃣ Clone & Setup Backend
```bash
cd DoAn_Chatbot_ERP

# Tạo virtual environment
python -m venv venv
venv\Scripts\activate  # Windows: venv\Scripts\activate
                       # Linux/Mac: source venv/bin/activate

# Cài dependencies
pip install fastapi uvicorn odoorpc openai python-dotenv
```

### 3️⃣ Cấu hình (.env file)
Tạo file `.env` trong thư mục gốc:
```env
# Odoo Connection
ODOO_URL=http://localhost:8069
ODOO_DB=your_database_name
ODOO_USERNAME=admin
ODOO_PASSWORD=your_password

# Groq AI API
OPENAI_API_KEY=your_groq_api_key
OPENAI_BASE_URL=https://api.groq.com/openai/v1
OPENAI_MODEL=llama-3.3-70b-versatile

# CORS (Frontend URLs)
CORS_ORIGINS=["http://localhost:5173"]
```

### 4️⃣ Setup Frontend
```bash
cd frontend-chat
npm install
```

---

## 🚀 Chạy ứng dụng

### Backend (FastAPI):
```bash
# Từ thư mục gốc
python -m uvicorn backend.main:app --reload
# → http://localhost:8000
```

### Frontend (React):
```bash
cd frontend-chat
npm run dev
# → http://localhost:5173
```

---

## 💬 Cách sử dụng

### Quick Actions (UI)
- **📱 Sản phẩm** - Liệt kê sản phẩm có sẵn
- **💰 Gợi ý giá** - Suggest pricing nhanh
- **📋 Đơn hàng** - Tra cứu đơn hàng gần đây

### Sample Commands

| Lệnh | Kết quả |
|------|---------|
| **Sản phẩm** |
| `"Liệt kê sản phẩm"` | Hiển thị top sản phẩm đang bán |
| `"Tìm iPhone"` | Tìm sản phẩm chứa từ "iPhone" |
| **Giá & Chính sách** |
| `"Giá iPhone 15 cho khách A"` | Gợi ý giá theo pricelist khách hàng |
| `"Bảng giá của khách Nguyễn Văn A"` | Xem chính sách giá (pricelist) |
| **Báo giá** |
| `"Tạo báo giá 2 iPhone 15 cho khách A"` | Tạo quotation với 1 sản phẩm |
| `"Báo giá: 3 iPhone và 5 Samsung cho B"` | Tạo quotation nhiều sản phẩm |
| `"Sửa báo giá SO001 thành 10 máy"` | Đổi số lượng báo giá |
| `"Sửa SO002: 2 iPhone 15 và 20 iPhone 14"` | Đổi nhiều sản phẩm trong báo giá |
| `"Xác nhận báo giá SO001"` | Xác nhận → chuyển thành Sales Order |
| **Đơn hàng** |
| `"Tạo đơn Samsung cho khách C"` | Tạo đơn hàng nhanh (tạo + confirm) |
| `"Đơn hàng: 1 iPhone và 3 AirPods cho D"` | Tạo đơn nhiều sản phẩm |
| `"Xem đơn hàng gần đây"` | Liệt kê 10 đơn mới nhất |
| `"Xem đơn của khách A"` | Tra cứu đơn theo khách hàng |
| `"Hủy đơn SO005"` | Hủy đơn hàng (có validation) |
| **CRM** |
| `"Tạo opportunity cho khách E"` | Tạo cơ hội bán hàng mới |
| `"Lead mới: F quan tâm 10 iPhone"` | Tạo lead với thông tin chi tiết |

---

## 📁 Cấu trúc Dự án

```
DoAn_Chatbot_ERP/
├── backend/
│   ├── main.py                 # FastAPI entry point
│   ├── config.py               # Cấu hình (load .env)
│   ├── models.py               # Pydantic models
│   ├── routers/
│   │   └── chat.py             # Chat endpoint + AI logic
│   ├── services/
│   │   ├── odoo_service.py     # Odoo connection
│   │   ├── customer_service.py # Tìm khách hàng
│   │   ├── product_service.py  # Xử lý sản phẩm + pricing
│   │   ├── order_service.py    # Báo giá & đơn hàng
│   │   └── crm_service.py      # CRM Opportunity
│   └── utils/
│       └── formatter.py        # Format currency, messages
├── frontend-chat/              # React + Vite
│   ├── src/
│   │   ├── App.jsx             # Main component
│   │   ├── App.css             # Styling
│   │   └── main.jsx            # Entry point
│   └── package.json
├── .env                        # Config (KHÔNG commit)
├── README.md                   # File này
└── requirements.txt            # Python dependencies (optional)
```

---

## 🔑 Điểm nổi bật

### ✨ Multi-Product Support
Hỗ trợ tạo/sửa đơn hàng với **nhiều sản phẩm khác nhau**:
```
Format: "product1;product2" với số lượng "qty1;qty2"
VD: "2 iPhone 15;5 Samsung Galaxy" → 2 iPhone + 5 Samsung trong 1 đơn
```

### 🎯 Smart Pricing Logic
- Tự động lấy giá từ **Pricelist** của khách hàng
- Hỗ trợ 3 loại compute price:
  - **Fixed**: Giá cố định
  - **Percentage**: Giảm % từ giá gốc
  - **Formula**: Công thức phức tạp (base + discount)
- Ưu tiên rule **cụ thể nhất** (product → template → global)

### 🔍 Fuzzy Search
- Tìm khách hàng linh hoạt (tên/SĐT/email)
- Xử lý nhiều pattern SĐT (0xxx, +84, xxx xxx)
- Gợi ý khi sản phẩm mơ hồ

### ✅ Validation & Error Handling
- Kiểm tra tồn kho trước khi tạo đơn
- Validate hóa đơn/phiếu giao hàng trước khi hủy
- Try-catch đầy đủ với error messages rõ ràng

---

## 👥 Team

**Đồ án:** AI Chatbot for Sales Process in ERP  
**Trường:** Đại học Công nghệ Thông tin - ĐHQG TP.HCM (UIT)  
**Năm:** 2025

---

## 📝 Notes

- **Tất cả giá đều tính theo VNĐ**
- **Số lượng phải là số nguyên**
- **Chỉ sửa được báo giá ở trạng thái Draft/Sent**
- **Không thể hủy đơn đã có hóa đơn/giao hàng**

---

⭐ **Happy Coding!** ⭐
