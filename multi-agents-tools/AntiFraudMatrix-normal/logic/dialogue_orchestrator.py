from typing import List, Dict, Any, Optional
from agents.left_agent import LeftAgent
from agents.right_agent import RightAgent 
from agents.manager_agent import ManagerAgent
from agents.prompts.manager_prompts import LEFT_TERMINATION_PROMPT, RIGHT_TERMINATION_PROMPT
from utils.conversation_logger import ConversationLogger
import time

class DialogueOrchestrator:
    """Dialogue orchestrator, manages the entire conversation flow"""
    
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
        """Run the complete dialogue process"""
        turn_count = 0
        terminated_by_manager = False
        end_call_signal_detected = False
        termination_reason = ""
        terminator = ""
        conclusion_messages = []
        
        # If no initial message is provided, let the left agent generate one
        if not initial_message:
            left_message = self.left_agent.generate_response()
        else:
            left_message = initial_message
            
        self.full_dialogue_history.append({
            "role": "left",
            "content": left_message,
            "timestamp": time.time()
        })
        
        self.logger.log("Dialogue started")
        self.logger.log(f"Left: {left_message}")
        
        # Main dialogue loop
        while turn_count < self.max_turns:
            # User responds
            right_message = self.right_agent.generate_response(left_message)
            self.full_dialogue_history.append({
                "role": "right",
                "content": right_message,
                "timestamp": time.time()
            })
            self.logger.log(f"Right: {right_message}")
            
            # Check if user ends the conversation
            if "##ENDCALL_SIGNAL##" in right_message:
                end_call_signal_detected = True
                terminator = "right"
                termination_reason = "User actively ended the conversation"
                self.logger.log("End signal detected, user actively ended the conversation")
                
                # Get manager's evaluation of the end action
                manager_evaluation = self.evaluate_end_call(terminator="right")
                termination_reason = manager_evaluation["reason"]
                
                # Do not enter the final response phase
                break
            
            # Manager evaluation
            manager_decision = self.evaluate_dialogue()
            
            if manager_decision["should_terminate"]:
                terminated_by_manager = True
                termination_reason = manager_decision["reason"]
                terminator = manager_decision["terminator"]
                
                self.logger.log(f"Manager terminated the conversation: {termination_reason}")
                self.logger.log(f"Termination type: {'Left ended' if terminator == 'left' else 'Right ended' if terminator == 'right' else 'Natural end'}")
                
                # Handle conversation termination
                conclusion_messages = self.handle_termination(terminator)
                break
                
            # Left agent responds
            left_message = self.left_agent.generate_response(right_message)
            self.full_dialogue_history.append({
                "role": "left",
                "content": left_message,
                "timestamp": time.time()
            })
            self.logger.log(f"Left: {left_message}")
            
            # Check if left agent ends the conversation
            if "##ENDCALL_SIGNAL##" in left_message:
                end_call_signal_detected = True
                terminator = "left"
                termination_reason = "Left agent actively ended the conversation"
                self.logger.log("End signal detected, left agent actively ended the conversation")
                
                # Get manager's evaluation of the end action
                manager_evaluation = self.evaluate_end_call(terminator="left")
                termination_reason = manager_evaluation["reason"]
                
                # Do not enter the final response phase
                break
            
            turn_count += 1
        
        # Remove end call signals
        for message in self.full_dialogue_history:
            message["content"] = message["content"].replace("##ENDCALL_SIGNAL##", "")

        # Dialogue ended, return result
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
        
        self.logger.log("Dialogue ended")
        return result
    
    def evaluate_dialogue(self) -> Dict[str, Any]:
        """Manager evaluates the dialogue and decides whether to terminate"""
        return self.manager_agent.generate_response(self.full_dialogue_history)
    
    def evaluate_end_call(self, terminator: str) -> Dict[str, Any]:
        """Manager evaluates the end call action"""
        messages = [{"role": "system", "content": self.manager_agent.get_system_prompt()}]
        
        # Build dialogue record
        dialogue_text = "\n".join([
            f"{'Left' if msg['role'] == 'left' else 'Right'}: {msg['content']}"
            for msg in self.full_dialogue_history
        ])
        
        terminator_name = "Left" if terminator == "left" else "Right"
        messages.append({
            "role": "user", 
            "content": f"{terminator_name} actively ended the conversation. Please evaluate the following dialogue, analyze the reason and intention for {terminator_name} ending the conversation:\n\n{dialogue_text}\n\nPlease reply in JSON format, including the following field:\n- reason: string, detailed explanation of the possible reason and intention for ending the conversation by {terminator_name}"
        })
        
        # Call API to generate reply
        reply = self.manager_agent.client.chat_completion(
            messages=messages,
            model=self.manager_agent.model,
            temperature=0.3,
            max_tokens=500
        )
        
        # Try to parse JSON
        try:
            import json
            json_match = self._extract_json(reply)
            if json_match:
                result = json.loads(json_match)
            else:
                result = json.loads(reply)
                
            if 'reason' not in result:
                result['reason'] = f"{terminator_name} actively ended the conversation, reason unknown."
            return result
        except:
            # If parsing fails, return the original reply as reason
            return {
                "reason": f"{terminator_name} actively ended the conversation. {reply}"
            }
    
    def _extract_json(self, text: str) -> str:
        """Extract JSON part from text"""
        import re
        json_pattern = r'\{(?:[^{}]|(?:\{[^{}]*\}))*\}'
        matches = re.findall(json_pattern, text)
        
        # Try each match, return the first valid JSON
        for match in matches:
            try:
                import json
                json.loads(match)
                return match
            except json.JSONDecodeError:
                continue
        
        return None
    
    def handle_termination(self, terminator: str) -> List[Dict[str, str]]:
        """Handle dialogue termination"""
        conclusion_messages = []
        
        if terminator == "left":
            # Sync the last right message
            right_history = self.right_agent.get_history()
            last_right_message = right_history[-1]["content"]
            self.left_agent.update_history("user", last_right_message)
                
            # Let left agent end the conversation
            left_conclusion = self.get_conclusion_from_left()
            self.full_dialogue_history.append({
                "role": "left",
                "content": left_conclusion,
                "timestamp": time.time()
            })
            conclusion_messages.append({"role": "left", "content": left_conclusion})
            self.logger.log(f"Left ended: {left_conclusion}")
            
            # User's final response
            right_conclusion = self.right_agent.generate_response(left_conclusion)
            self.full_dialogue_history.append({
                "role": "right",
                "content": right_conclusion,
                "timestamp": time.time()
            })
            conclusion_messages.append({"role": "right", "content": right_conclusion})
            self.logger.log(f"Right response: {right_conclusion}")
            
        elif terminator == "right":
            # Let user end the conversation
            right_conclusion = self.get_conclusion_from_right()
            self.full_dialogue_history.append({
                "role": "right",
                "content": right_conclusion,
                "timestamp": time.time()
            })
            conclusion_messages.append({"role": "right", "content": right_conclusion})
            self.logger.log(f"Right ended: {right_conclusion}")
            
            # Left agent's final response
            left_conclusion = self.left_agent.generate_response(right_conclusion)
            self.full_dialogue_history.append({
                "role": "left",
                "content": left_conclusion,
                "timestamp": time.time()
            })
            conclusion_messages.append({"role": "left", "content": left_conclusion})
            self.logger.log(f"Left response: {left_conclusion}")
        
        else:  # Natural end
            # Both sides give closing statements
            left_conclusion = self.get_conclusion_from_left()
            self.full_dialogue_history.append({
                "role": "left",
                "content": left_conclusion,
                "timestamp": time.time()
            })
            conclusion_messages.append({"role": "left", "content": left_conclusion})
            self.logger.log(f"Left ended: {left_conclusion}")
            
            right_conclusion = self.right_agent.generate_response(left_conclusion)
            self.full_dialogue_history.append({
                "role": "right",
                "content": right_conclusion,
                "timestamp": time.time()
            })
            conclusion_messages.append({"role": "right", "content": right_conclusion})
            self.logger.log(f"Right ended: {right_conclusion}")
            
        return conclusion_messages
    
    def get_conclusion_from_left(self) -> str:
        """Let the left agent generate a closing statement"""
        left_history = self.left_agent.get_history()
        messages = [
            {"role": "system", "content": self.left_agent.get_system_prompt()},
        ]+left_history+[{"role": "user", "content": LEFT_TERMINATION_PROMPT}]

        # Call API to generate reply
        reply = self.left_agent.client.chat_completion(
            messages=messages,
            model=self.left_agent.model,
            temperature=0.7,
            max_tokens=200
        )
        
        return reply
    
    def get_conclusion_from_right(self) -> str:
        """Let the right agent generate a closing statement"""
        right_history = self.right_agent.get_history()
        messages = [
            {"role": "system", "content": self.right_agent.get_system_prompt()},
        ]+right_history+[
            {"role": "user", "content": RIGHT_TERMINATION_PROMPT}
        ]
        
        # Call API to generate reply
        reply = self.right_agent.client.chat_completion(
            messages=messages,
            model=self.right_agent.model,
            temperature=0.7,
            max_tokens=200
        )
        
        return reply