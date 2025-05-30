# agents/base_agent.py
from abc import ABC, abstractmethod

class BaseAgent(ABC):
    """Lớp cơ sở cho tất cả các tác nhân, xác định giao diện chung"""
    
    def __init__(self, name, role_prompt, memory_window=10):
        """
        Khởi tạo tác nhân

        Args:
        name (str): tên tác nhân
        role_prompt (str): lời nhắc vai trò
        memory_window (int): kích thước cửa sổ bộ nhớ
        """
        self.name = name
        self.role_prompt = role_prompt
        self.memory_window = memory_window
        self.dialogue_history = []
    
    def add_to_history(self, speaker, message):
        """
        Thêm tin nhắn vào lịch sử

        Args:
        speaker (str): speaker
        message (str): nội dung tin nhắn
        """
        self.dialogue_history.append({"speaker": speaker, "message": message})
        # Duy trì kích thước cửa sổ bộ nhớ
        if len(self.dialogue_history) > self.memory_window:
            self.dialogue_history = self.dialogue_history[-self.memory_window:]
    
    def get_context(self):
        """Nhận bối cảnh hiện tại"""
        return self.dialogue_history.copy()
    
    @abstractmethod
    def generate_response(self, context):
        """
        Tạo phản hồi

        Args:
        context (danh sách): Bối cảnh hội thoại

        Trả về:
        str: Phản hồi đã tạo
        """
        pass