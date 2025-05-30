from typing import List, Dict, Any
from .base_agent import BaseAgent
from .prompts.right_prompts import RIGHT_SYSTEM_PROMPT
import config
import time
import logging

class RightAgent(BaseAgent):
    """Agent người dùng, phản hồi hội thoại lừa đảo"""
    
    def __init__(self, model: str = None, user_profile: Dict[str, Any] = None, base_url: str = None, retry_delay: float = 5):
        super().__init__(role="right", model=model or config.DEFAULT_MODEL, base_url=base_url)
        self.user_profile = user_profile or {
            "age": 45,
            "awareness": "medium",  # thấp, trung bình, cao
            "occupation": "teacher"
        }
        self.retry_delay = retry_delay
        
    def get_system_prompt(self) -> str:
        """Lấy prompt hệ thống đã được tuỳ biến"""
        return RIGHT_SYSTEM_PROMPT.format(
            age=self.user_profile["age"],
            awareness=self.user_profile["awareness"],
            occupation=self.user_profile["occupation"]
        )
    
    def generate_response(self, message: str) -> str:
        """Sinh phản hồi của người dùng, có cơ chế retry khi lỗi API"""
        messages = [{"role": "system", "content": self.get_system_prompt()}]
        
        # Thêm lịch sử hội thoại
        for msg in self.conversation_history:
            messages.append(msg)
            
        # Thêm tin nhắn từ kẻ lừa đảo
        messages.append({"role": "user", "content": message})
        
        # Thêm logic retry khi gọi API
        retry_count = 0
        while True:
            try:
                # Gọi OpenAI API để sinh phản hồi
                reply = self.client.chat_completion(
                    messages=messages,
                    model=self.model,
                    temperature=0.7,
                    max_tokens=300
                )
                # Nếu phản hồi chứa "API" thì coi như lỗi
                if "API" in reply:
                    raise Exception("Gọi API thất bại, không thể sinh phản hồi.")
                break
            except Exception as e:
                retry_count += 1
                logging.warning(f"API request thất bại (lần thử {retry_count}): {str(e)}")
                
                # Đợi một khoảng rồi thử lại
                time.sleep(self.retry_delay)
                logging.info(f"Đang thử lại gọi API...")
        
        # Cập nhật lịch sử hội thoại, lưu ý right: left là user
        self.update_history("user", message)      # Tin nhắn từ kẻ lừa đảo
        self.update_history("assistant", reply)   # Phản hồi của người dùng
        
        return reply