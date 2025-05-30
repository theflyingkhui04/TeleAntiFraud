from typing import List, Dict, Any, Tuple
from .base_agent import BaseAgent
from .prompts.manager_prompts import MANAGER_SYSTEM_PROMPT
import config
import json
import time
import logging

class ManagerAgent(BaseAgent):
    """Manager agent, evaluates dialogue and decides whether to terminate"""
    
    def __init__(self, model: str = None, strictness: str = "low", base_url: str = None, retry_delay: float = 5):
        super().__init__(role="manager", model=model or config.DEFAULT_MODEL, base_url=base_url)
        self.strictness = strictness  # low, medium, high
        self.retry_delay = retry_delay
        
    def get_system_prompt(self) -> str:
        """Get customized system prompt"""
        return MANAGER_SYSTEM_PROMPT.format(strictness=self.strictness)
    
    def generate_response(self, dialogue_history: List[Dict[str, str]]) -> Dict[str, Any]:
        """Evaluate dialogue and return termination decision, who terminates, and reason"""
        messages = [{"role": "system", "content": self.get_system_prompt()}]
        
        # Build complete dialogue history
        dialogue_text = "\n".join([
            f"{'Service' if msg['role'] == 'left' else 'User'}: {msg['content']}"
            for msg in dialogue_history
        ])
        
        # Use the constructed dialogue text
        messages.append({
            "role": "user", 
            "content": f"Please evaluate the following dialogue, and determine whether it should be terminated and by whom: \n\n{dialogue_text}\n\nPlease reply in JSON format, including the following fields:\n- should_terminate: Boolean, indicating whether the dialogue should be terminated\n- terminator: String, possible values are 'left' (caller ends), 'right' (user ends), 'natural' (natural end) or 'endcall' (hang up)\n- reason: String, detailing the reason for termination or continuation"
        })
        
        # Add retry logic
        retry_count = 0
        while True:
            try:
                # Call API to generate reply
                reply = self.client.chat_completion(
                    messages=messages,
                    model=self.model,
                    temperature=0.3,
                    max_tokens=500
                )
                # Successfully received reply, break the loop
                if "API" in reply:
                    raise Exception("API call failed, unable to generate reply.")
                break
            except Exception as e:
                retry_count += 1
                error_msg = f"API request failed (Attempt {retry_count}): {str(e)}"
                self._log_error(error_msg)
                logging.warning(error_msg)
                
                # Retry after a delay
                time.sleep(self.retry_delay)
                logging.info(f"Retrying API request...")
        
        # Parse JSON response
        try:
            # Attempt to extract JSON part (if the reply contains other text)
            json_match = self._extract_json(reply)
            if json_match:
                result = json.loads(json_match)
            else:
                # If no well-formatted JSON is found, try to parse the entire reply directly
                result = json.loads(reply)
            
            # Ensure all required fields are present
            if 'should_terminate' not in result:
                result['should_terminate'] = False
            if 'terminator' not in result:
                result['terminator'] = 'natural'
            if 'reason' not in result:
                result['reason'] = "Unable to determine termination reason, defaulting to continue dialogue."
                
            return result
            
        except json.JSONDecodeError:
            # If JSON parsing fails, fallback to original text analysis method
            self._log_error(f"JSON parsing failed, falling back to text analysis. Original reply: {reply}")
            return self._fallback_text_analysis(reply)
    
    def _extract_json(self, text: str) -> str:
        """Extract JSON part from text"""
        # Attempt to find JSON surrounded by curly braces
        import re
        json_pattern = r'\{(?:[^{}]|(?:\{[^{}]*\}))*\}'
        matches = re.findall(json_pattern, text)
        
        # Attempt each match, return the first valid JSON
        for match in matches:
            try:
                json.loads(match)
                return match
            except json.JSONDecodeError:
                continue
        
        return None
    
    def _fallback_text_analysis(self, reply: str) -> Dict[str, Any]:
        """Fallback to text analysis when JSON parsing fails"""
        should_terminate = "yes" in reply[:100].lower() or "should terminate" in reply[:100].lower() or "need to terminate" in reply[:100].lower()
        
        # Determine who should terminate the conversation
        terminator = "natural"  # Default is natural termination
        if "service terminates" in reply or "left" in reply.lower():
            terminator = "left"
        elif "user terminates" in reply or "right" in reply.lower():
            terminator = "right"
        elif "natural termination" in reply or "natural" in reply.lower():
            terminator = "natural"
        
        # Return analysis result
        return {
            "should_terminate": should_terminate,
            "terminator": terminator,
            "reason": reply,
            "fallback_used": True  # Mark that fallback analysis was used
        }
    
    def _log_error(self, message: str):
        """Log error information"""
        # You can modify this according to your logging system
        print(f"[ERROR] ManagerAgent: {message}")