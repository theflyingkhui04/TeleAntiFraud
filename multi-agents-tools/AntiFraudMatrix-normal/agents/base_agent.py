from abc import ABC, abstractmethod
from typing import List, Dict, Any
from utils.openai_client import OpenAIClient

class BaseAgent(ABC):
    """基础智能体抽象类，定义所有智能体的通用接口"""
    
    def __init__(self, role: str, model: str = None, base_url: str = None):
        self.role = role
        self.model = model
        self.conversation_history = []
        self.client = OpenAIClient(base_url=base_url)
        
    @abstractmethod
    def get_system_prompt(self) -> str:
        """返回系统提示词"""
        pass
        
    @abstractmethod
    def generate_response(self, message: str) -> str:
        """生成对当前消息的回应"""
        pass
    
    def update_history(self, role: str, content: str) -> None:
        """更新对话历史"""
        self.conversation_history.append({"role": role, "content": content})
    
    def get_history(self) -> List[Dict[str, str]]:
        """获取当前对话历史"""
        return self.conversation_history
    
    def clear_history(self) -> None:
        """清空对话历史"""
        self.conversation_history = []

    def set_history(self, history: List[Dict[str, str]]) -> None:
        """设置对话历史"""
        self.conversation_history = history