# agents/base_agent.py
from abc import ABC, abstractmethod

class BaseAgent(ABC):
    """Lớp cơ sở cho tất cả các agent, định nghĩa giao diện chung"""
    
    def __init__(self, name, role_prompt, memory_window=10):
        """
        Khởi tạo agent
        
        Args:
            name (str): Tên agent
            role_prompt (str): Prompt vai trò
            memory_window (int): Kích thước cửa sổ ghi nhớ hội thoại
        """
        self.name = name
        self.role_prompt = role_prompt
        self.memory_window = memory_window
        self.dialogue_history = []
    
    def add_to_history(self, speaker, message):
        """
        Thêm tin nhắn vào lịch sử hội thoại
        
        Args:
            speaker (str): Người nói
            message (str): Nội dung tin nhắn
        """
        self.dialogue_history.append({"speaker": speaker, "message": message})
        # Giữ lịch sử hội thoại không vượt quá cửa sổ ghi nhớ
        if len(self.dialogue_history) > self.memory_window:
            self.dialogue_history = self.dialogue_history[-self.memory_window:]
    
    def get_context(self):
        """Lấy ngữ cảnh hội thoại hiện tại"""
        return self.dialogue_history.copy()
    
    @abstractmethod
    def generate_response(self, context):
        """
        Sinh phản hồi
        
        Args:
            context (list): Ngữ cảnh hội thoại
            
        Returns:
            str: Câu trả lời được sinh ra
        """
        pass