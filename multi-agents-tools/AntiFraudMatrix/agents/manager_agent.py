from typing import List, Dict, Any, Tuple
from .base_agent import BaseAgent
from .prompts.manager_prompts import MANAGER_SYSTEM_PROMPT
import config
import json
import time
import logging

class ManagerAgent(BaseAgent):
    """Agent quản lý, đánh giá hội thoại và quyết định có nên kết thúc hay không"""
    
    def __init__(self, model: str = None, strictness: str = "medium", base_url: str = None, retry_delay: float = 5):
        super().__init__(role="manager", model=model or config.DEFAULT_MODEL, base_url=base_url)
        self.strictness = strictness  # low, medium, high
        self.retry_delay = retry_delay
        
    def get_system_prompt(self) -> str:
        """Lấy prompt hệ thống đã được tuỳ biến"""
        return MANAGER_SYSTEM_PROMPT.format(strictness=self.strictness)
    
    def generate_response(self, dialogue_history: List[Dict[str, str]]) -> Dict[str, Any]:
        """Đánh giá hội thoại và trả về quyết định kết thúc, ai là người kết thúc và lý do"""
        messages = [{"role": "system", "content": self.get_system_prompt()}]
        
        # Xây dựng lịch sử hội thoại đầy đủ
        dialogue_text = "\n".join([
            f"{'Kẻ lừa đảo' if msg['role'] == 'left' else 'Người dùng'}: {msg['content']}"
            for msg in dialogue_history
        ])
        
        # Sử dụng đoạn hội thoại đã xây dựng
        messages.append({
            "role": "user", 
            "content": f"Hãy đánh giá đoạn hội thoại sau và quyết định có nên kết thúc không, ai là người nên kết thúc:\n\n{dialogue_text}\n\nVui lòng trả lời bằng định dạng JSON, gồm các trường sau:\n- should_terminate: giá trị True/False, cho biết có nên kết thúc không\n- terminator: chuỗi, giá trị có thể là 'left' (kẻ lừa đảo kết thúc), 'right' (người dùng kết thúc), 'natural' (kết thúc tự nhiên) hoặc 'endcall' (gác máy)\n- reason: chuỗi, giải thích chi tiết lý do kết thúc hoặc tiếp tục"
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
            # Cố gắng trích xuất phần JSON (nếu phản hồi có kèm văn bản khác)
            json_match = self._extract_json(reply)
            if json_match:
                result = json.loads(json_match)
            else:
                # Nếu không tìm thấy JSON hợp lệ, thử parse toàn bộ phản hồi
                result = json.loads(reply)
            
            # Đảm bảo các trường bắt buộc đều có
            if 'should_terminate' not in result:
                result['should_terminate'] = False
            if 'terminator' not in result:
                result['terminator'] = 'natural'
            if 'reason' not in result:
                result['reason'] = "Không xác định được lý do kết thúc, mặc định tiếp tục hội thoại."
            
            return result
            
        except json.JSONDecodeError:
            # Nếu parse JSON thất bại, fallback sang phân tích văn bản
            self._log_error(f"Lỗi parse JSON, fallback sang phân tích text. Phản hồi gốc: {reply}")
            return self._fallback_text_analysis(reply)
    
    def _extract_json(self, text: str) -> str:
        """Trích xuất phần JSON từ văn bản"""
        # Tìm kiếm JSON nằm trong dấu ngoặc nhọn
        import re
        json_pattern = r'\{(?:[^{}]|(?:\{[^{}]*\}))*\}'
        matches = re.findall(json_pattern, text)
        
        # Thử từng đoạn, trả về đoạn JSON hợp lệ đầu tiên
        for match in matches:
            try:
                json.loads(match)
                return match
            except json.JSONDecodeError:
                continue
        
        return None
    
    def _fallback_text_analysis(self, reply: str) -> Dict[str, Any]:
        """Khi không parse được JSON thì fallback sang phân tích text"""
        should_terminate = "có" in reply[:100] or "nên kết thúc" in reply[:100] or "cần kết thúc" in reply[:100]
        
        # Xác định ai là người kết thúc
        terminator = "natural"  # Mặc định là kết thúc tự nhiên
        if "kẻ lừa đảo kết thúc" in reply or "left" in reply.lower():
            terminator = "left"
        elif "người dùng kết thúc" in reply or "right" in reply.lower():
            terminator = "right"
        elif "kết thúc tự nhiên" in reply or "natural" in reply.lower():
            terminator = "natural"
        
        # Trả về kết quả phân tích
        return {
            "should_terminate": should_terminate,
            "terminator": terminator,
            "reason": reply,
            "fallback_used": True  # Đánh dấu đã dùng phương pháp fallback
        }
    
    def _log_error(self, message: str):
        """Ghi log lỗi"""
        print(f"[ERROR] ManagerAgent: {message}")