from typing import List, Dict, Any
from .base_agent import BaseAgent
from .prompts.left_prompts import LEFT_SYSTEM_PROMPT
import config
import time
import logging

class LeftAgent(BaseAgent):
    """Nhân viên dịch vụ, chịu trách nhiệm khởi xướng các cuộc trò chuyện gian lận"""
    
    def __init__(self, model: str = None, fraud_type: str = "general", base_url: str = None, max_retries: int = 10, retry_delay: float = 5):
        super().__init__(role="left", model=model or config.DEFAULT_MODEL, base_url=base_url)
        self.fraud_type = fraud_type
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        
    def get_system_prompt(self) -> str:
        """Nhận các từ nhắc nhở hệ thống tùy chỉnh"""
        return LEFT_SYSTEM_PROMPT.format(conversation_type=self.fraud_type)
    
    def generate_response(self, message: str = None) -> str:
        """Tạo phản hồi gian lận và thêm cơ chế thử lại lỗi"""
        # Tin nhắn hoặc trả lời ban đầu
        messages = [{"role": "system", "content": self.get_system_prompt()}]
        
        # Thêm lịch sử trò chuyện
        for msg in self.conversation_history:
            messages.append(msg)
            
        # Nếu có tin nhắn mới, hãy thêm vào danh sách tin nhắn
        if message:
            messages.append({"role": "user", "content": message})
        
        # Thêm logic thử lại
        retry_count = 0
        while True:
            try:
                # Gọi OpenAI API để tạo phản hồi
                reply = self.client.chat_completion(
                    messages=messages,
                    model=self.model,
                    temperature=0.8,
                    max_tokens=500
                )
                # Nhận được phản hồi thành công và thoát khỏi vòng lặp
                if "API" in reply:
                    raise Exception("API调用失败，无法生成回复。")
                break
            except Exception as e:
                retry_count += 1
                logging.warning(f"API请求失败 (尝试 {retry_count}): {str(e)}")
                
                # Optional: If the maximum number of retries is set and the limit is reached, an exception can be thrown
                # if self.max_retries and retry_count >= self.max_retries:
                # raise Exception(f"Maximum number of retries ({self.max_retries}) reached, unable to get a response")

                # Retry after a delay
                time.sleep(self.retry_delay)
        
        # Cập nhật lịch sử trò chuyện của riêng bạn. Lưu ý rằng trong cuộc trò chuyện bên trái, nội dung bên phải là người dùng
        if message:
            self.update_history("user", message)
        self.update_history("assistant", reply) 
        
        return reply