# 🤖 AI Chatbot for Sales Process in ERP

> **Develop an AI Chatbot to assist sales representatives in creating Quotations and Sales Orders in the ERP system. The chatbot analyzes customer requests, suggests pricing, and generates sales orders.**

---

## 🎯 Tổng quan

Hệ thống AI Chatbot tích hợp với **Odoo ERP** để hỗ trợ nhân viên bán hàng:

✅ **Analyze Customer Requests** - Phân tích khách hàng thông minh  
✅ **Suggest Pricing** - Gợi ý giá dựa trên lịch sử mua  
✅ **Generate Sales Orders** - Tạo đơn hàng tự động  
✅ **Sales Rep Tracking** - Theo dõi nhân viên tạo đơn  

---

## ✨ Tính năng Chính

### 1️⃣ **Customer Analysis** (Phân tích khách hàng)
- Lịch sử mua hàng
- Tổng chi tiêu & số đơn
- Phân loại hạng (VIP/Trung thành/Mới)
- Đề xuất chính sách chăm sóc

### 2️⃣ **Smart Pricing** (Gợi ý giá thông minh)
- Giá tự động theo hạng khách
- VIP: -5% | Trung thành: -3%
- Dựa trên lịch sử giao dịch

### 3️⃣ **Quick Order Creation** (Tạo đơn nhanh)
- Validate khách hàng & sản phẩm
- Kiểm tra tồn kho tự động
- Áp dụng giá đề xuất
- Confirm đơn hàng 1 bước

### 4️⃣ **Sales Rep Context**
- Track nhân viên tạo đơn
- Audit trail đầy đủ
- Ghi log vào Odoo

---

## 🛠️ Công nghệ

**Backend:** FastAPI + Odoo XML-RPC + Groq AI (Llama 3.3 70B)  
**Frontend:** React + Vite  
**Database:** Odoo PostgreSQL  

---

## 📦 Cài đặt

### 1. Requirements
- Python 3.8+
- Node.js 16+
- Odoo 14+

### 2. Clone & Setup Backend
### 2. Clone & Setup Backend
```bash
cd DoAn_Chatbot_ERP

# Tạo virtual environment
python -m venv venv
venv\Scripts\activate  # Windows

# Cài dependencies
pip install fastapi uvicorn openai python-dotenv
```

### 3. Cấu hình (.env file)
```env
ODOO_URL=http://localhost:8069
ODOO_DB=your_database
ODOO_USERNAME=admin
ODOO_PASSWORD=your_password
OPENAI_API_KEY=your_groq_api_key
```

### 4. Setup Frontend
```bash
cd frontend-chat
npm install
```

---

## 🚀 Chạy ứng dụng

**Backend:**
```bash
python -m uvicorn main:app --reload
# → http://localhost:8000
```

**Frontend:**

**Frontend:**
```bash
cd frontend-chat
npm run dev
# → http://localhost:5173
```

---

## 🎯 Cách sử dụng

### Quick Actions (UI)
- **📱 Sản phẩm** - Liệt kê sản phẩm
- **📊 Phân tích KH** - Phân tích khách hàng
- **💰 Gợi ý giá** - Suggest pricing
- **📋 Đơn hàng** - Tra cứu đơn hàng

### Sample Commands

| Lệnh | Kết quả |
|------|---------|
| `"Phân tích khách Nguyễn Văn A"` | Hiển thị lịch sử, hạng, tổng chi tiêu |
| `"Gợi ý giá iPhone cho khách A"` | Giá đề xuất với discount (nếu có) |
| `"Tạo đơn Samsung 2 máy cho B"` | Tạo đơn hàng tự động |
| `"Xem đơn hàng gần đây"` | 10 đơn mới nhất |

---

## 📁 Cấu trúc Dự án

```
DoAn_Chatbot_ERP/
├── main.py                    # Backend API (FastAPI + Odoo + Groq AI)
├── .env                       # Config (không commit)
├── README.md                  # File này
├── FEATURES.md                # Chi tiết tính năng
├── AUTHENTICATION_ANALYSIS.md # Phân tích security model (B2B vs B2C)
└── frontend-chat/             # Frontend React + Vite
    ├── src/
    │   ├── App.jsx            # Main component
    │   └── main.jsx           # Entry point
    └── package.json
```

---

## 📚 Tài liệu Bổ sung

- **[FEATURES.md](FEATURES.md)** - Chi tiết đầy đủ về các tính năng (analyze_customer, suggest_pricing, create_sale_order)
- **[AUTHENTICATION_ANALYSIS.md](AUTHENTICATION_ANALYSIS.md)** - Phân tích về security model (B2B tool for sales reps, không cần auth riêng)

---

## 🎓 Compliance với Đề bài

| Yêu cầu Đề bài | ✅ Status | Implementation |
|----------------|----------|----------------|
| **Assist sales representatives** | ✅ | Sales rep context tracking trong mọi action |
| **Analyze customer requests** | ✅ | `analyze_customer()` - history, tier, recommendations |
| **Suggest pricing** | ✅ | Smart pricing với VIP discount logic |
| **Generate sales orders** | ✅ | Full Odoo workflow với validation & auto-confirm |
| **Connect to CRM/Sales** | ✅ | Odoo XML-RPC integration (real-time) |
| **GPT-based AI** | ✅ | Groq Llama 3.3 70B Versatile |

---

## 📝 TODO

- [ ] Export báo cáo doanh số theo sales rep
- [ ] Multi-language support (EN/VN)
- [ ] Integration vào Odoo UI (embeddable widget)
- [ ] Mobile responsive
- [ ] Unit tests & E2E tests

---

## 👥 Team

**Đồ án:** AI Chatbot for Sales Process in ERP  
**Trường:** Đại học Công nghệ Thông tin - UIT  
**Năm:** 2025

---

⭐ **Happy Coding!** ⭐
