import { useState, useRef, useEffect } from 'react'
import axios from 'axios'
import './App.css'

function App() {
  // Danh sách tin nhắn ban đầu
  const [messages, setMessages] = useState([
    { role: 'bot', content: '👋 Xin chào! Em là AI Sales Assistant cho hệ thống ERP.\n\n📋 Em có thể giúp anh/chị:\n✅ Tra cứu sản phẩm\n✅ Gợi ý giá bán theo pricelist\n✅ Tạo đơn hàng nhanh\n✅ Tra cứu đơn hàng\n\nAnh/chị cần hỗ trợ gì ạ?' }
  ]);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [salesRepName, setSalesRepName] = useState('Admin'); // Tên nhân viên
  const [showSettings, setShowSettings] = useState(false);
  
  // Tự động cuộn xuống tin nhắn mới nhất
  const messagesEndRef = useRef(null);
  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };
  useEffect(() => { scrollToBottom() }, [messages]);

  const sendMessage = async () => {
    if (!input.trim()) return;

    // 1. Hiển thị tin nhắn người dùng ngay lập tức
    const newMessages = [...messages, { role: 'user', content: input }];
    setMessages(newMessages);
    setInput('');
    setIsLoading(true);

    try {
      // 2. Gửi sang Python Backend (Cổng 8000) với thông tin sales rep
      const response = await axios.post('http://127.0.0.1:8000/chat', {
        message: input,
        history: messages,
        sales_rep_name: salesRepName  
      });

      // 3. Nhận phản hồi từ Bot
      setMessages([...newMessages, { role: 'bot', content: response.data.reply }]);
    } catch (error) {
      console.error("Lỗi:", error);
      setMessages([...newMessages, { role: 'bot', content: "⚠️ Lỗi kết nối Server! Bạn đã chạy backend chưa?" }]);
    } finally {
      setIsLoading(false);
    }
  };

  // Quick actions - Gửi command nhanh
  const quickAction = (text) => {
    setInput(text);
  };

  return (
    <div className="container">
      <div className="header">
        <h2>🤖 AI Sales Assistant - ERP</h2>
        <div className="salesRepBadge" onClick={() => setShowSettings(!showSettings)}>
          👤 {salesRepName} ⚙️
        </div>
      </div>

      {/* Settings Panel */}
      {showSettings && (
        <div className="settingsPanel">
          <label style={{marginRight: '10px'}}>Tên nhân viên:</label>
          <input 
            type="text"
            value={salesRepName}
            onChange={(e) => setSalesRepName(e.target.value)}
            className="input"
            style={{flex: 1}}
            placeholder="Nhập tên của bạn"
          />
        </div>
      )}

      {/* Quick Actions */}
      <div className="quickActions">
        <button className="quickBtn" onClick={() => quickAction("Liệt kê sản phẩm")}>
          📱 Sản phẩm
        </button>
        <button className="quickBtn" onClick={() => quickAction("Gợi ý giá iPhone 15 cho khách Nguyễn Văn A")}>
          💰 Gợi ý giá
        </button>
        <button className="quickBtn" onClick={() => quickAction("Xem đơn hàng gần đây")}>
          📋 Đơn hàng
        </button>
      </div>

      {/* KHUNG CHAT */}
      <div className="chatBox">
        {messages.map((msg, index) => (
          <div key={index} style={{ 
              display: 'flex', 
              justifyContent: msg.role === 'user' ? 'flex-end' : 'flex-start',
              marginBottom: '15px' 
            }}>
            <div className={msg.role === 'user' ? 'userBubble' : 'botBubble'}>
              {msg.content.split('\n').map((line, i) => (
                <div key={i}>{line}</div>
              ))}
            </div>
          </div>
        ))}
        {isLoading && <div style={{fontStyle: 'italic', color: '#666'}}>Bot đang nhập...</div>}
        <div ref={messagesEndRef} />
      </div>

      {/* KHUNG NHẬP LIỆU */}
      <div className="inputArea">
        <input 
          className="input"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && sendMessage()}
          placeholder="Nhập yêu cầu (VD: Giá iPhone 15 bao nhiêu?)..."
          disabled={isLoading}
        />
        <button 
          className="button" 
          onClick={sendMessage}
          disabled={isLoading}
        >
          Gửi
        </button>
      </div>
    </div>
  )
}

export default App