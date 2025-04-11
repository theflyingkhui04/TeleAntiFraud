from typing import List, Dict, Any, Tuple
from .base_agent import BaseAgent
from .prompts.manager_prompts import MANAGER_SYSTEM_PROMPT
import config
import json
import time
import logging

class ManagerAgent(BaseAgent):
    """管理者智能体，评估对话并决定是否终止"""
    
    def __init__(self, model: str = None, strictness: str = "low", base_url: str = None, retry_delay: float = 5):
        super().__init__(role="manager", model=model or config.DEFAULT_MODEL, base_url=base_url)
        self.strictness = strictness  # low, medium, high
        self.retry_delay = retry_delay
        
    def get_system_prompt(self) -> str:
        """获取定制的系统提示词"""
        return MANAGER_SYSTEM_PROMPT.format(strictness=self.strictness)
    
    def generate_response(self, dialogue_history: List[Dict[str, str]]) -> Dict[str, Any]:
        """评估对话并返回终止决定、由谁终止以及理由"""
        messages = [{"role": "system", "content": self.get_system_prompt()}]
        
        # 构建完整对话记录
        dialogue_text = "\n".join([
            f"{'服务方' if msg['role'] == 'left' else '用户'}: {msg['content']}"
            for msg in dialogue_history
        ])
        
        # 使用构建好的对话文本
        messages.append({
            "role": "user", 
            "content": f"请评估以下对话，并判断是否应该终止以及由谁来结束对话：\n\n{dialogue_text}\n\n请以JSON格式回复，包含以下字段：\n- should_terminate：布尔值，表示是否应终止对话\n- terminator：字符串，可能的值为'left'（主叫结束）、'right'（用户结束）、'natural'（自然结束）或'endcall'(挂断）\n- reason：字符串，详细说明终止的理由或继续的理由"
        })
        
        # 添加重试逻辑
        retry_count = 0
        while True:
            try:
                # 调用API生成回复
                reply = self.client.chat_completion(
                    messages=messages,
                    model=self.model,
                    temperature=0.3,
                    max_tokens=500
                )
                # 成功获取回复，跳出循环
                if "API" in reply:
                    raise Exception("API调用失败，无法生成回复。")
                break
            except Exception as e:
                retry_count += 1
                error_msg = f"API请求失败 (尝试 {retry_count}): {str(e)}"
                self._log_error(error_msg)
                logging.warning(error_msg)
                
                # 延迟一段时间后重试
                time.sleep(self.retry_delay)
                logging.info(f"正在重试 API 请求...")
        
        # 解析JSON响应
        try:
            # 尝试提取JSON部分（如果回复中包含其他文本）
            json_match = self._extract_json(reply)
            if json_match:
                result = json.loads(json_match)
            else:
                # 如果没有找到格式良好的JSON，尝试直接解析整个回复
                result = json.loads(reply)
            
            # 确保所有必需的字段都存在
            if 'should_terminate' not in result:
                result['should_terminate'] = False
            if 'terminator' not in result:
                result['terminator'] = 'natural'
            if 'reason' not in result:
                result['reason'] = "无法确定终止原因，默认继续对话。"
                
            return result
            
        except json.JSONDecodeError:
            # 如果JSON解析失败，回退到原始文本分析方法
            self._log_error(f"JSON解析失败，回退到文本分析。原始回复: {reply}")
            return self._fallback_text_analysis(reply)
    
    def _extract_json(self, text: str) -> str:
        """从文本中提取JSON部分"""
        # 尝试查找花括号包围的JSON
        import re
        json_pattern = r'\{(?:[^{}]|(?:\{[^{}]*\}))*\}'
        matches = re.findall(json_pattern, text)
        
        # 尝试每个匹配项，返回第一个有效的JSON
        for match in matches:
            try:
                json.loads(match)
                return match
            except json.JSONDecodeError:
                continue
        
        return None
    
    def _fallback_text_analysis(self, reply: str) -> Dict[str, Any]:
        """当JSON解析失败时，回退到文本分析"""
        should_terminate = "是" in reply[:100] or "应该终止" in reply[:100] or "需要终止" in reply[:100]
        
        # 判断谁来结束对话
        terminator = "natural"  # 默认为自然结束
        if "服务方结束" in reply or "left" in reply.lower():
            terminator = "left"
        elif "用户结束" in reply or "right" in reply.lower():
            terminator = "right"
        elif "自然结束" in reply or "natural" in reply.lower():
            terminator = "natural"
        
        # 返回分析结果
        return {
            "should_terminate": should_terminate,
            "terminator": terminator,
            "reason": reply,
            "fallback_used": True  # 标记使用了后备解析方法
        }
    
    def _log_error(self, message: str):
        """记录错误信息"""
        # 这里可以根据你的日志系统进行适当修改
        print(f"[ERROR] ManagerAgent: {message}")