from abc import ABC, abstractmethod
from typing import List, Dict, Any
from utils.openai_client import OpenAIClient

class BaseAgent(ABC):
    """Lớp trừu tượng của tác nhân cơ sở, xác định giao diện chung cho tất cả các tác nhân"""
    
    def __init__(self, role: str, model: str = None, base_url: str = None):
        self.role = role
        self.model = model
        self.conversation_history = []
        self.client = OpenAIClient(base_url=base_url)
        
    @abstractmethod
    def get_system_prompt(self) -> str:
        """Quay lại lời nhắc hệ thống"""
        pass
        
    @abstractmethod
    def generate_response(self, message: str) -> str:
        """Tạo phản hồi cho tin nhắn hiện tại"""
        pass
    
    def update_history(self, role: str, content: str) -> None:
        """Cập nhật lịch sử trò chuyện"""
        self.conversation_history.append({"role": role, "content": content})
    
    def get_history(self) -> List[Dict[str, str]]:
        """Nhận lịch sử cuộc trò chuyện hiện tại"""
        return self.conversation_history
    
    def clear_history(self) -> None:
        """Xóa lịch sử trò chuyện"""
        self.conversation_history = []

    def set_history(self, history: List[Dict[str, str]]) -> None:
        """Thiết lập lịch sử trò chuyện"""
        self.conversation_history = history