# agents/base_agent.py
from abc import ABC, abstractmethod

class BaseAgent(ABC):
    """所有智能体的基类，定义通用接口"""
    
    def __init__(self, name, role_prompt, memory_window=10):
        """
        初始化智能体
        
        Args:
            name (str): 智能体名称
            role_prompt (str): 角色提示词
            memory_window (int): 记忆窗口大小
        """
        self.name = name
        self.role_prompt = role_prompt
        self.memory_window = memory_window
        self.dialogue_history = []
    
    def add_to_history(self, speaker, message):
        """
        添加消息到历史记录
        
        Args:
            speaker (str): 发言者
            message (str): 消息内容
        """
        self.dialogue_history.append({"speaker": speaker, "message": message})
        # 维持记忆窗口大小
        if len(self.dialogue_history) > self.memory_window:
            self.dialogue_history = self.dialogue_history[-self.memory_window:]
    
    def get_context(self):
        """获取当前上下文"""
        return self.dialogue_history.copy()
    
    @abstractmethod
    def generate_response(self, context):
        """
        生成回复
        
        Args:
            context (list): 对话上下文
            
        Returns:
            str: 生成的回复
        """
        pass