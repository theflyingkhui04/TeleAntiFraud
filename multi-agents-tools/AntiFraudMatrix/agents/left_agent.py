from typing import List, Dict, Any
from .base_agent import BaseAgent
from .prompts.left_prompts import LEFT_SYSTEM_PROMPT
import config
import time
import logging

class LeftAgent(BaseAgent):
    """诈骗者智能体，负责发起诈骗对话"""
    
    def __init__(self, model: str = None, fraud_type: str = "general", base_url: str = None, max_retries: int = 10, retry_delay: float = 5):
        super().__init__(role="left", model=model or config.DEFAULT_MODEL, base_url=base_url)
        self.fraud_type = fraud_type
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        
    def get_system_prompt(self) -> str:
        """获取定制的系统提示词"""
        return LEFT_SYSTEM_PROMPT.format(fraud_type=self.fraud_type)
    
    def generate_response(self, message: str = None) -> str:
        """生成诈骗回应，添加错误重试机制"""
        # 初始消息或回复
        messages = [{"role": "system", "content": self.get_system_prompt()}]
        
        # 添加对话历史
        for msg in self.conversation_history:
            messages.append(msg)
            
        # 如果有新消息，添加到消息列表
        if message:
            messages.append({"role": "user", "content": message})
        
        # 添加重试逻辑
        retry_count = 0
        while True:
            try:
                # 调用OpenAI API生成回复
                reply = self.client.chat_completion(
                    messages=messages,
                    model=self.model,
                    temperature=0.8,
                    max_tokens=500
                )
                # 成功获取回复，跳出循环
                if "API" in reply:
                    raise Exception("API调用失败，无法生成回复。")
                break
            except Exception as e:
                retry_count += 1
                logging.warning(f"API请求失败 (尝试 {retry_count}): {str(e)}")
                
                # 可选：如果设置了最大重试次数且达到上限，可以抛出异常
                # if self.max_retries and retry_count >= self.max_retries:
                #     raise Exception(f"达到最大重试次数 ({self.max_retries})，无法获取回复")
                
                # 延迟一段时间后重试
                time.sleep(self.retry_delay)
        
        # 更新自己的对话历史，这里注意left的对话中，right的内容是user
        if message:
            self.update_history("user", message)  # 右方(用户)的消息
        self.update_history("assistant", reply)   # 自己(诈骗者)的回复
        
        return reply