from typing import List, Dict, Any, Optional
from agents.left_agent import LeftAgent
from agents.right_agent import RightAgent 
from agents.manager_agent import ManagerAgent
from agents.prompts.manager_prompts import LEFT_TERMINATION_PROMPT, RIGHT_TERMINATION_PROMPT
from utils.conversation_logger import ConversationLogger
import time

class DialogueOrchestrator:
    """Bộ phối hợp hội thoại, quản lý toàn bộ luồng hội thoại"""
    
    def __init__(self, 
                 left_agent: LeftAgent, 
                 right_agent: RightAgent,
                 manager_agent: ManagerAgent,
                 max_turns: int = 20,
                 logger: Optional[ConversationLogger] = None):
        self.left_agent = left_agent
        self.right_agent = right_agent
        self.manager_agent = manager_agent
        self.max_turns = max_turns
        self.logger = logger or ConversationLogger()
        self.full_dialogue_history = []
        
    def run_dialogue(self, initial_message: str = None) -> Dict[str, Any]:
        """Chạy toàn bộ quy trình hội thoại"""
        turn_count = 0
        terminated_by_manager = False
        end_call_signal_detected = False
        termination_reason = ""
        terminator = ""
        conclusion_messages = []
        
        # Nếu không cung cấp tin nhắn ban đầu, để kẻ lừa đảo tạo một tin nhắn
        if not initial_message:
            left_message = self.left_agent.generate_response()
        else:
            left_message = initial_message
        self.full_dialogue_history.append({
            "role": "left",
            "content": left_message,
            "timestamp": time.time()
        })
        self.logger.log("Bắt đầu hội thoại")
        self.logger.log(f"Kẻ lừa đảo: {left_message}")
        
        # Vòng lặp hội thoại chính
        while turn_count < self.max_turns:
            # Người dùng phản hồi
            right_message = self.right_agent.generate_response(left_message)
            self.full_dialogue_history.append({
                "role": "right",
                "content": right_message,
                "timestamp": time.time()
            })
            self.logger.log(f"Người dùng: {right_message}")
            
            # Kiểm tra người dùng có ngắt máy không
            if "##ENDCALL_SIGNAL##" in right_message:
                end_call_signal_detected = True
                terminator = "right"
                termination_reason = "Người dùng chủ động ngắt máy"
                self.logger.log("Phát hiện tín hiệu ngắt máy, người dùng chủ động kết thúc hội thoại")
                
                # Nhận đánh giá từ quản lý về hành động ngắt máy
                manager_evaluation = self.evaluate_end_call(terminator="right")
                termination_reason = manager_evaluation["reason"]
                
                # Không vào giai đoạn phản hồi cuối
                break
            
            # Quản lý đánh giá
            manager_decision = self.evaluate_dialogue()
            
            if manager_decision["should_terminate"]:
                terminated_by_manager = True
                termination_reason = manager_decision["reason"]
                terminator = manager_decision["terminator"]
                
                self.logger.log(f"Quản lý kết thúc hội thoại: {termination_reason}")
                self.logger.log(f"Cách kết thúc: {'Kẻ lừa đảo kết thúc' if terminator == 'left' else 'Người dùng kết thúc' if terminator == 'right' else 'Kết thúc tự nhiên'}")
                
                # Xử lý khi hội thoại kết thúc
                conclusion_messages = self.handle_termination(terminator)
                break
                
            # Kẻ lừa đảo phản hồi
            left_message = self.left_agent.generate_response(right_message)
            self.full_dialogue_history.append({
                "role": "left",
                "content": left_message,
                "timestamp": time.time()
            })
            self.logger.log(f"Kẻ lừa đảo: {left_message}")
            
            # Kiểm tra kẻ lừa đảo có ngắt máy không
            if "##ENDCALL_SIGNAL##" in left_message:
                end_call_signal_detected = True
                terminator = "left"
                termination_reason = "Kẻ lừa đảo chủ động ngắt máy"
                self.logger.log("Phát hiện tín hiệu ngắt máy, kẻ lừa đảo chủ động kết thúc hội thoại")
                
                # Nhận đánh giá từ quản lý về hành động ngắt máy
                manager_evaluation = self.evaluate_end_call(terminator="left")
                termination_reason = manager_evaluation["reason"]
                
                # Không vào giai đoạn phản hồi cuối
                break
            
            turn_count += 1
        
        # Xoá tín hiệu ngắt máy khỏi nội dung
        for message in self.full_dialogue_history:
            message["content"] = message["content"].replace("##ENDCALL_SIGNAL##", "")

        # Kết thúc hội thoại, trả về kết quả
        result = {
            "dialogue_history": self.full_dialogue_history,
            "turns": turn_count,
            "terminated_by_manager": terminated_by_manager,
            "end_call_signal_detected": end_call_signal_detected,
            "termination_reason": termination_reason,
            "terminator": terminator,
            "conclusion_messages": conclusion_messages,
            "reached_max_turns": turn_count >= self.max_turns
        }
        
        self.logger.log("Kết thúc hội thoại")
        return result
    
    def evaluate_dialogue(self) -> Dict[str, Any]:
        """Quản lý đánh giá hội thoại và quyết định có nên kết thúc không"""
        return self.manager_agent.generate_response(self.full_dialogue_history)
    
    def evaluate_end_call(self, terminator: str) -> Dict[str, Any]:
        """Quản lý đánh giá hành vi ngắt máy"""
        messages = [{"role": "system", "content": self.manager_agent.get_system_prompt()}]
        
        # Xây dựng lại lịch sử hội thoại
        dialogue_text = "\n".join([
            f"{'Kẻ lừa đảo' if msg['role'] == 'left' else 'Người dùng'}: {msg['content']}"
            for msg in self.full_dialogue_history
        ])
        
        terminator_name = "Kẻ lừa đảo" if terminator == "left" else "Người dùng"
        messages.append({
            "role": "user", 
            "content": f"{terminator_name} chủ động ngắt máy. Hãy đánh giá hội thoại sau, phân tích lý do và ý định của {terminator_name} khi ngắt máy:\n\n{dialogue_text}\n\nVui lòng trả lời bằng JSON, gồm trường:\n- reason: chuỗi, giải thích chi tiết lý do và ý định của {terminator_name}"
        })
        
        # Gọi API để tạo phản hồi
        reply = self.manager_agent.client.chat_completion(
            messages=messages,
            model=self.manager_agent.model,
            temperature=0.3,
            max_tokens=500
        )
        
        # Thử phân tích cú pháp JSON
        try:
            import json
            json_match = self._extract_json(reply)
            if json_match:
                result = json.loads(json_match)
            else:
                result = json.loads(reply)
                
            if 'reason' not in result:
                result['reason'] = f"{terminator_name} chủ động ngắt máy, lý do không rõ."
            return result
        except:
            # Khi phân tích thất bại, trả về phản hồi gốc dưới dạng lý do
            return {
                "reason": f"{terminator_name} chủ động ngắt máy. {reply}"
            }
    
    def _extract_json(self, text: str) -> str:
        """Trích xuất phần JSON từ văn bản"""
        import re
        json_pattern = r'\{(?:[^{}]|(?:\{[^{}]*\}))*\}'
        matches = re.findall(json_pattern, text)
        
        # Thử từng mục khớp, trả về JSON hợp lệ đầu tiên
        for match in matches:
            try:
                import json
                json.loads(match)
                return match
            except json.JSONDecodeError:
                continue
        
        return None
    
    def handle_termination(self, terminator: str) -> List[Dict[str, str]]:
        """Xử lý khi hội thoại kết thúc"""
        conclusion_messages = []
        
        if terminator == "left":
            # Đồng bộ tin nhắn cuối cùng của người dùng
            right_history = self.right_agent.get_history()
            last_right_message = right_history[-1]["content"]
            self.left_agent.update_history("user", last_right_message)
                
            # Để kẻ lừa đảo kết thúc hội thoại
            left_conclusion = self.get_conclusion_from_left()
            self.full_dialogue_history.append({
                "role": "left",
                "content": left_conclusion,
                "timestamp": time.time()
            })
            conclusion_messages.append({"role": "left", "content": left_conclusion})
            self.logger.log(f"Kẻ lừa đảo kết thúc: {left_conclusion}")
            
            # Phản hồi cuối cùng của người dùng
            right_conclusion = self.right_agent.generate_response(left_conclusion)
            self.full_dialogue_history.append({
                "role": "right",
                "content": right_conclusion,
                "timestamp": time.time()
            })
            conclusion_messages.append({"role": "right", "content": right_conclusion})
            self.logger.log(f"Người dùng phản hồi: {right_conclusion}")
            
        elif terminator == "right":
            # Để người dùng kết thúc hội thoại
            right_conclusion = self.get_conclusion_from_right()
            self.full_dialogue_history.append({
                "role": "right",
                "content": right_conclusion,
                "timestamp": time.time()
            })
            conclusion_messages.append({"role": "right", "content": right_conclusion})
            self.logger.log(f"Người dùng kết thúc: {right_conclusion}")
            
            # Phản hồi cuối cùng của kẻ lừa đảo
            left_conclusion = self.left_agent.generate_response(right_conclusion)
            self.full_dialogue_history.append({
                "role": "left",
                "content": left_conclusion,
                "timestamp": time.time()
            })
            conclusion_messages.append({"role": "left", "content": left_conclusion})
            self.logger.log(f"Kẻ lừa đảo phản hồi: {left_conclusion}")
        
        else:  # Kết thúc tự nhiên
            # Cả hai bên đều đưa ra lời kết thúc
            left_conclusion = self.get_conclusion_from_left()
            self.full_dialogue_history.append({
                "role": "left",
                "content": left_conclusion,
                "timestamp": time.time()
            })
            conclusion_messages.append({"role": "left", "content": left_conclusion})
            self.logger.log(f"Kẻ lừa đảo kết thúc: {left_conclusion}")
            
            right_conclusion = self.right_agent.generate_response(left_conclusion)
            self.full_dialogue_history.append({
                "role": "right",
                "content": right_conclusion,
                "timestamp": time.time()
            })
            conclusion_messages.append({"role": "right", "content": right_conclusion})
            self.logger.log(f"Người dùng kết thúc: {right_conclusion}")
            
        return conclusion_messages
    
    def get_conclusion_from_left(self) -> str:
        """Yêu cầu kẻ lừa đảo sinh câu kết thúc"""
        left_history = self.left_agent.get_history()
        messages = [
            {"role": "system", "content": self.left_agent.get_system_prompt()},
        ]+left_history+[{"role": "user", "content": LEFT_TERMINATION_PROMPT}]

        # Gọi API để tạo phản hồi
        reply = self.left_agent.client.chat_completion(
            messages=messages,
            model=self.left_agent.model,
            temperature=0.7,
            max_tokens=200
        )
        
        return reply
    
    def get_conclusion_from_right(self) -> str:
        """Yêu cầu người dùng sinh câu kết thúc"""
        right_history = self.right_agent.get_history()
        messages = [
            {"role": "system", "content": self.right_agent.get_system_prompt()},
        ]+right_history+[
            {"role": "user", "content": RIGHT_TERMINATION_PROMPT}
        ]
        
        # Gọi API để tạo phản hồi
        reply = self.right_agent.client.chat_completion(
            messages=messages,
            model=self.right_agent.model,
            temperature=0.7,
            max_tokens=200
        )
        
        return reply