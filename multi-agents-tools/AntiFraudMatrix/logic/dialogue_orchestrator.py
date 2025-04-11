from typing import List, Dict, Any, Optional
from agents.left_agent import LeftAgent
from agents.right_agent import RightAgent 
from agents.manager_agent import ManagerAgent
from agents.prompts.manager_prompts import LEFT_TERMINATION_PROMPT, RIGHT_TERMINATION_PROMPT
from utils.conversation_logger import ConversationLogger
import time

class DialogueOrchestrator:
    """对话协调器，管理整个对话流程"""
    
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
        """运行完整的对话流程"""
        turn_count = 0
        terminated_by_manager = False
        end_call_signal_detected = False
        termination_reason = ""
        terminator = ""
        conclusion_messages = []
        
        # 如果没有提供初始消息，让诈骗者生成一个
        if not initial_message:
            left_message = self.left_agent.generate_response()
        else:
            left_message = initial_message
            
        self.full_dialogue_history.append({
            "role": "left",
            "content": left_message,
            "timestamp": time.time()
        })
        
        self.logger.log("对话开始")
        self.logger.log(f"诈骗者: {left_message}")
        
        # 主对话循环
        while turn_count < self.max_turns:
            # 用户回应
            right_message = self.right_agent.generate_response(left_message)
            self.full_dialogue_history.append({
                "role": "right",
                "content": right_message,
                "timestamp": time.time()
            })
            self.logger.log(f"用户: {right_message}")
            
            # 检查用户是否挂断
            if "##ENDCALL_SIGNAL##" in right_message:
                #删除挂断信号
                # self.full_dialogue_history[-1]["content"] = right_message.replace("##ENDCALL_SIGNAL##", "")
                end_call_signal_detected = True
                terminator = "right"
                termination_reason = "用户主动挂断电话"
                self.logger.log("检测到挂断信号，用户主动结束对话")
                
                # 获取管理者对挂断行为的评估
                manager_evaluation = self.evaluate_end_call(terminator="right")
                termination_reason = manager_evaluation["reason"]
                
                # 不进入最后回应环节
                break
            
            # 管理者评估
            manager_decision = self.evaluate_dialogue()
            
            if manager_decision["should_terminate"]:
                terminated_by_manager = True
                termination_reason = manager_decision["reason"]
                terminator = manager_decision["terminator"]
                
                self.logger.log(f"管理者终止对话: {termination_reason}")
                self.logger.log(f"终止方式: {'诈骗者结束' if terminator == 'left' else '用户结束' if terminator == 'right' else '自然结束'}")
                
                # 处理对话结束
                conclusion_messages = self.handle_termination(terminator)
                break
                
            # 诈骗者回应
            left_message = self.left_agent.generate_response(right_message)
            self.full_dialogue_history.append({
                "role": "left",
                "content": left_message,
                "timestamp": time.time()
            })
            self.logger.log(f"诈骗者: {left_message}")
            
            # 检查诈骗者是否挂断
            if "##ENDCALL_SIGNAL##" in left_message:
                # 删除挂断信号
                # self.full_dialogue_history[-1]["content"] = left_message.replace("##ENDCALL_SIGNAL##", "")
                end_call_signal_detected = True
                terminator = "left"
                termination_reason = "诈骗者主动挂断电话"
                self.logger.log("检测到挂断信号，诈骗者主动结束对话")
                
                # 获取管理者对挂断行为的评估
                manager_evaluation = self.evaluate_end_call(terminator="left")
                termination_reason = manager_evaluation["reason"]
                
                # 不进入最后回应环节
                break
            
            turn_count += 1
        
        #删除挂断信号
        for message in self.full_dialogue_history:
            message["content"] = message["content"].replace("##ENDCALL_SIGNAL##", "")

        # 对话结束，返回结果
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
        
        self.logger.log("对话结束")
        return result
    
    def evaluate_dialogue(self) -> Dict[str, Any]:
        """管理者评估对话并决定是否终止"""
        return self.manager_agent.generate_response(self.full_dialogue_history)
    
    def evaluate_end_call(self, terminator: str) -> Dict[str, Any]:
        """管理者评估挂断行为"""
        messages = [{"role": "system", "content": self.manager_agent.get_system_prompt()}]
        
        # 构建对话记录
        dialogue_text = "\n".join([
            f"{'诈骗者' if msg['role'] == 'left' else '用户'}: {msg['content']}"
            for msg in self.full_dialogue_history
        ])
        
        terminator_name = "诈骗者" if terminator == "left" else "用户"
        messages.append({
            "role": "user", 
            "content": f"{terminator_name}主动挂断了电话。请评估以下对话，分析{terminator_name}挂断的原因和意图：\n\n{dialogue_text}\n\n请以JSON格式回复，包含以下字段：\n- reason：字符串，详细说明挂断的可能原因和{terminator_name}的意图"
        })
        
        # 调用API生成回复
        reply = self.manager_agent.client.chat_completion(
            messages=messages,
            model=self.manager_agent.model,
            temperature=0.3,
            max_tokens=500
        )
        
        # 尝试解析JSON
        try:
            import json
            json_match = self._extract_json(reply)
            if json_match:
                result = json.loads(json_match)
            else:
                result = json.loads(reply)
                
            if 'reason' not in result:
                result['reason'] = f"{terminator_name}主动挂断了通话，原因未明。"
            return result
        except:
            # 解析失败时返回原始回复作为reason
            return {
                "reason": f"{terminator_name}主动挂断了通话。{reply}"
            }
    
    def _extract_json(self, text: str) -> str:
        """从文本中提取JSON部分"""
        import re
        json_pattern = r'\{(?:[^{}]|(?:\{[^{}]*\}))*\}'
        matches = re.findall(json_pattern, text)
        
        # 尝试每个匹配项，返回第一个有效的JSON
        for match in matches:
            try:
                import json
                json.loads(match)
                return match
            except json.JSONDecodeError:
                continue
        
        return None
    
    def handle_termination(self, terminator: str) -> List[Dict[str, str]]:
        """处理对话终止情况"""
        conclusion_messages = []
        
        if terminator == "left":
            # 同步right最后一句
            right_history = self.right_agent.get_history()
            last_right_message = right_history[-1]["content"]
            self.left_agent.update_history("user", last_right_message)
                
            # 让诈骗者结束对话
            left_conclusion = self.get_conclusion_from_left()
            self.full_dialogue_history.append({
                "role": "left",
                "content": left_conclusion,
                "timestamp": time.time()
            })
            conclusion_messages.append({"role": "left", "content": left_conclusion})
            self.logger.log(f"诈骗者结束: {left_conclusion}")
            
            # 用户的最后回应
            right_conclusion = self.right_agent.generate_response(left_conclusion)
            self.full_dialogue_history.append({
                "role": "right",
                "content": right_conclusion,
                "timestamp": time.time()
            })
            conclusion_messages.append({"role": "right", "content": right_conclusion})
            self.logger.log(f"用户回应: {right_conclusion}")
            
        elif terminator == "right":
            # 让用户结束对话
            right_conclusion = self.get_conclusion_from_right()
            self.full_dialogue_history.append({
                "role": "right",
                "content": right_conclusion,
                "timestamp": time.time()
            })
            conclusion_messages.append({"role": "right", "content": right_conclusion})
            self.logger.log(f"用户结束: {right_conclusion}")
            
            # 诈骗者的最后回应
            left_conclusion = self.left_agent.generate_response(right_conclusion)
            self.full_dialogue_history.append({
                "role": "left",
                "content": left_conclusion,
                "timestamp": time.time()
            })
            conclusion_messages.append({"role": "left", "content": left_conclusion})
            self.logger.log(f"诈骗者回应: {left_conclusion}")
        
        else:  # 自然结束
            # 双方都给出结束语
            left_conclusion = self.get_conclusion_from_left()
            self.full_dialogue_history.append({
                "role": "left",
                "content": left_conclusion,
                "timestamp": time.time()
            })
            conclusion_messages.append({"role": "left", "content": left_conclusion})
            self.logger.log(f"诈骗者结束: {left_conclusion}")
            
            right_conclusion = self.right_agent.generate_response(left_conclusion)
            self.full_dialogue_history.append({
                "role": "right",
                "content": right_conclusion,
                "timestamp": time.time()
            })
            conclusion_messages.append({"role": "right", "content": right_conclusion})
            self.logger.log(f"用户结束: {right_conclusion}")
            
        return conclusion_messages
    
    def get_conclusion_from_left(self) -> str:
        """让诈骗者生成结束语"""
        left_history = self.left_agent.get_history()
        messages = [
            {"role": "system", "content": self.left_agent.get_system_prompt()},
        ]+left_history+[{"role": "user", "content": LEFT_TERMINATION_PROMPT}]

        # 调用API生成回复
        reply = self.left_agent.client.chat_completion(
            messages=messages,
            model=self.left_agent.model,
            temperature=0.7,
            max_tokens=200
        )
        
        return reply
    
    def get_conclusion_from_right(self) -> str:
        """让用户生成结束语"""
        right_history = self.right_agent.get_history()
        messages = [
            {"role": "system", "content": self.right_agent.get_system_prompt()},
        ]+right_history+[
            {"role": "user", "content": RIGHT_TERMINATION_PROMPT}
        ]
        
        # 调用API生成回复
        reply = self.right_agent.client.chat_completion(
            messages=messages,
            model=self.right_agent.model,
            temperature=0.7,
            max_tokens=200
        )
        
        return reply