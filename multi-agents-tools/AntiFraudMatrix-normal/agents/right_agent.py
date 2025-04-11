from typing import List, Dict, Any
from .base_agent import BaseAgent
from .prompts.right_prompts import RIGHT_SYSTEM_PROMPT
import config
import time
import logging

class RightAgent(BaseAgent):
    """用户智能体，回应诈骗对话"""
    
    def __init__(self, model: str = None, user_profile: Dict[str, Any] = None, base_url: str = None, retry_delay: float = 5):
        super().__init__(role="right", model=model or config.DEFAULT_MODEL, base_url=base_url)
        self.user_profile = user_profile or {
            "age": 45,
            "communication_style": "medium",  # low, medium, high
            "occupation": "teacher"
        }
        self.retry_delay = retry_delay
        
    def get_system_prompt(self) -> str:
        """获取定制的系统提示词"""
        return RIGHT_SYSTEM_PROMPT.format(
            age=self.user_profile["age"],
            communication_style=self.user_profile["awareness"],
            occupation=self.user_profile["occupation"]
        )
    
    def generate_response(self, message: str) -> str:
        """生成用户回应，添加错误重试机制"""
        messages = [{"role": "system", "content": self.get_system_prompt()}]
        
        # 添加对话历史
        for msg in self.conversation_history:
            messages.append(msg)
            
        # 添加服务方的消息
        messages.append({"role": "user", "content": message})
        
        # 添加重试逻辑
        retry_count = 0
        while True:
            try:
                # 调用OpenAI API生成回复
                reply = self.client.chat_completion(
                    messages=messages,
                    model=self.model,
                    temperature=0.7,
                    max_tokens=300
                )
                # 成功获取回复，跳出循环
                if "API" in reply:
                    raise Exception("API调用失败，无法生成回复。")
                break
            except Exception as e:
                retry_count += 1
                logging.warning(f"API请求失败 (尝试 {retry_count}): {str(e)}")
                
                # 延迟一段时间后重试
                time.sleep(self.retry_delay)
                logging.info(f"正在重试 API 请求...")
        
        # 更新自己的对话历史，这里注意right的对话中，left的内容是user
        self.update_history("user", message)      # 左方(服务方)的消息
        self.update_history("assistant", reply)   # 自己(用户)的回复
        
        return reply