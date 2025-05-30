from typing import List, Dict, Any
from .base_agent import BaseAgent
from .prompts.left_prompts import LEFT_SYSTEM_PROMPT
import config
import time
import logging

class LeftAgent(BaseAgent):
    """Thông minh giả mạo, chịu trách nhiệm khởi xướng cuộc trò chuyện giả mạo"""
    
    def __init__(self, model: str = None, fraud_type: str = "general", base_url: str = None, max_retries: int = 10, retry_delay: float = 5):
        super().__init__(role="left", model=model or config.DEFAULT_MODEL, base_url=base_url)
        self.fraud_type = fraud_type
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        
    def get_system_prompt(self) -> str:
        """Lấy lời nhắc hệ thống tùy chỉnh"""
        return LEFT_SYSTEM_PROMPT.format(fraud_type=self.fraud_type)
    
    def generate_response(self, message: str = None) -> str:
        """Tạo phản hồi giả mạo, thêm cơ chế thử lại lỗi"""
        # Tin nhắn hoặc phản hồi ban đầu
        messages = [{"role": "system", "content": self.get_system_prompt()}]
        
        # Thêm lịch sử trò chuyện
        for msg in self.conversation_history:
            messages.append(msg)
            
        # Nếu có tin nhắn mới, thêm vào danh sách tin nhắn
        if message:
            messages.append({"role": "user", "content": message})
        
        # Thêm logic retry khi gọi API
        retry_count = 0
        while True:
            try:
                # Gọi OpenAI API để sinh phản hồi
                reply = self.client.chat_completion(
                    messages=messages,
                    model=self.model,
                    temperature=0.8,
                    max_tokens=500
                )
                # Nếu phản hồi chứa "API" thì coi như lỗi
                if "API" in reply:
                    raise Exception("Gọi API thất bại, không thể sinh phản hồi.")
                break
            except Exception as e:
                retry_count += 1
                logging.warning(f"API request thất bại (lần thử {retry_count}): {str(e)}")
                # Tuỳ chọn: Nếu đã đạt số lần retry tối đa thì raise lỗi
                # if self.max_retries and retry_count >= self.max_retries:
                #     raise Exception(f"Đã đạt số lần thử tối đa ({self.max_retries}), không thể lấy phản hồi")
                # Đợi một khoảng rồi thử lại
                time.sleep(self.retry_delay)
        
        # Cập nhật lịch sử trò chuyện của chính mình, ở đây lưu ý trong cuộc trò chuyện của bên trái, nội dung của bên phải là người dùng
        if message:
            self.update_history("user", message)  # Tin nhắn của bên phải (người dùng)
        self.update_history("assistant", reply)   # Phản hồi của chính mình (kẻ lừa đảo)
        
        return reply