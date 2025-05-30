import os
import json
import random
import argparse
import time
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from tqdm import tqdm
from typing import Dict, List, Any

from agents.left_agent import LeftAgent
from agents.right_agent import RightAgent
from agents.manager_agent import ManagerAgent
from logic.dialogue_orchestrator import DialogueOrchestrator
from utils.conversation_logger import ConversationLogger
import config

# Configure global logging
logging.basicConfig(
    filename='run.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# Các giá trị cấu hình tiếng Việt
AGE_RANGES = [
    (18, 25),  # Thanh niên
    (26, 40),  # Người lớn
    (41, 55),  # Trung niên
    (56, 70),  # Người cao tuổi
]

AWARENESS_LEVELS = ["thấp", "trung bình", "cao"]

# Các loại tình huống gian lận (tiếng Việt)
FRAUD_TYPES = {
    "investment": "Gian lận đầu tư",
    "romance": "Gian lận tình cảm",
    "phishing": "Gian lận lừa đảo",
    "identity_theft": "Trộm cắp danh tính",
    "lottery": "Gian lận xổ số",
    "job_offer": "Công việc giả mạo",
    "banking": "Gian lận ngân hàng"
}

OCCUPATIONS = {
    "student": "Sinh viên",
    "teacher": "Giáo viên",
    "engineer": "Kỹ sư",
    "doctor": "Bác sĩ",
    "retired": "Người đã nghỉ hưu",
    "business_owner": "Chủ doanh nghiệp",
    "office_worker": "Nhân viên văn phòng",
    "farmer": "Nông dân",
    "waiter": "Phục vụ"
}

def generate_dialogue(args, tts_id: str, user_age: int, user_awareness: str, fraud_type: str) -> Dict[str, Any]:
    """Generate a single dialogue and return the result"""
    try:
        # Log dialogue parameters
        logger.info(f"Start generating dialogue {tts_id}: age={user_age}, awareness={user_awareness}, fraud_type={fraud_type}")
        
        # Create agents
        left_agent = LeftAgent(
            model=args.model,
            fraud_type=fraud_type,  # 保持原变量名
            base_url=args.base_url
        )
        
        # Randomly select an occupation
        occupation = random.choice(OCCUPATIONS)
        
        right_agent = RightAgent(
            model=args.model,
            user_profile={
                "age": user_age,
                "awareness": user_awareness,  # 保持原变量名
                "occupation": occupation
            },
            base_url=args.base_url
        )
        
        manager_agent = ManagerAgent(
            model=args.model,
            strictness="medium",
            base_url=args.base_url
        )
        
        # Create dialogue orchestrator, disable console output
        conv_logger = ConversationLogger(console_output=False)
        orchestrator = DialogueOrchestrator(
            left_agent=left_agent,
            right_agent=right_agent,
            manager_agent=manager_agent,
            max_turns=args.max_turns,
            logger=conv_logger
        )
        
        # Run dialogue
        dialogue_result = orchestrator.run_dialogue()
        
        # Log full dialogue history
        logger.info(f"Dialogue {tts_id} completed, total {len(dialogue_result['dialogue_history'])} turns")
        logger.info(f"Dialogue history {tts_id}:")
        for msg in dialogue_result['dialogue_history']:
            role = "Left" if msg['role'] == "left" else "Right"
            logger.info(f"{role}: {msg['content']}")
        
        # Extract termination reason
        termination_reason = "Reached maximum turns" if dialogue_result.get("reached_max_turns", False) else dialogue_result.get("termination_reason", "Unknown")
        # If terminated by manager, extract short termination reason
        if dialogue_result.get("terminated_by_manager", False) and isinstance(termination_reason, str) and len(termination_reason) > 100:
            # Extract first 100 characters or up to the first period
            short_reason = termination_reason.split(".")[0] if "." in termination_reason[:100] else termination_reason[:100]
            termination_reason = short_reason + "..."
        
        # Extract left and right messages
        left_messages = []
        right_messages = []
        
        for message in dialogue_result["dialogue_history"]:
            if message["role"] == "left":
                left_messages.append(message["content"])
            elif message["role"] == "right":
                right_messages.append(message["content"])
        
        # Create JSONL format entry
        entry = {
            "tts_id": tts_id,
            "left": left_messages,
            "right": right_messages,
            "user_age": user_age,
            "user_awareness": user_awareness,
            "fraud_type": fraud_type,
            "occupation": occupation,
            "termination_reason": termination_reason,
            "terminator": dialogue_result.get("terminator", "natural")
        }
        
        # Save full dialogue record
        full_dialogue_path = os.path.join(args.full_output_dir, f"{tts_id}.json")
        with open(full_dialogue_path, 'w', encoding='utf-8') as f:
            json.dump(dialogue_result, f, ensure_ascii=False, indent=2)
        
        logger.info(f"Dialogue {tts_id} processed, termination reason: {termination_reason}")
        logger.info(f"Full dialogue saved to {full_dialogue_path}")
        
        return entry
    
    except Exception as e:
        logger.error(f"Error generating dialogue {tts_id}: {e}", exc_info=True)
        # Return an error marker, will be filtered out later
        return {"error": str(e), "tts_id": tts_id}

def main():
    # Parse command line arguments
    parser = argparse.ArgumentParser(description="Multi-agent dialogue data generation")
    parser.add_argument("--count", type=int, default=20, help="Number of dialogues to generate")
    parser.add_argument("--output", default="fraud_dialogues.jsonl", help="Output file path")
    parser.add_argument("--full_output_dir", default="full_dialogues", help="Full dialogue output directory")
    parser.add_argument("--base_url", required=True, help="Custom API endpoint URL")
    parser.add_argument("--api_key", required=True, help="Custom API key")
    parser.add_argument("--model", required=True, help="Model name")
    parser.add_argument("--max_turns", type=int, default=15, help="Maximum dialogue turns")
    parser.add_argument("--workers", type=int, default=10, help="Number of concurrent worker threads")
    args = parser.parse_args()
    
    # Log startup info
    logger.info(f"Start generating {args.count} dialogues, model: {args.model}, API base URL: {args.base_url}")
    
    # Set API key and base URL
    config.OPENAI_API_KEY = args.api_key
    config.OPENAI_BASE_URL = args.base_url
    
    # Create output directory
    output_dir = os.path.dirname(args.output)
    if output_dir and not os.path.exists(output_dir):
        os.makedirs(output_dir)
    
    # Create full dialogue output directory
    if not os.path.exists(args.full_output_dir):
        os.makedirs(args.full_output_dir)
    
    # Prepare task parameter list
    tasks = []
    
    # Ensure even parameter distribution
    combinations = []
    for age_range in AGE_RANGES:
        for awareness in AWARENESS_LEVELS:
            for fraud in FRAUD_TYPES:
                combinations.append((age_range, awareness, fraud))
    
    # For each combination, assign a number
    per_combination = args.count // len(combinations)
    remainder = args.count % len(combinations)
    
    # Add tasks
    tts_counter = 1
    for combo in combinations:
        age_range, awareness, fraud = combo
        # Number of tasks for this combination
        combo_count = per_combination + (1 if remainder > 0 else 0)
        if remainder > 0:
            remainder -= 1
            
        for _ in range(combo_count):
            user_age = random.randint(age_range[0], age_range[1])
            tts_id = f"tts_fraud_{tts_counter:05d}"
            tasks.append((tts_id, user_age, awareness, fraud))
            tts_counter += 1
    
    # Randomly shuffle task order
    random.shuffle(tasks)
    
    # Use thread pool to generate dialogues in parallel
    results = []
    success_count = 0
    error_count = 0
    
    logger.info(f"Start parallel dialogue generation, threads: {args.workers}")
    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        # Submit all tasks
        future_to_task = {
            executor.submit(generate_dialogue, args, tts_id, user_age, awareness, fraud): 
            (tts_id, user_age, awareness, fraud) 
            for tts_id, user_age, awareness, fraud in tasks
        }
        
        # Process completed tasks
        for future in tqdm(as_completed(future_to_task), total=len(tasks), desc="Generating dialogues"):
            task = future_to_task[future]
            try:
                result = future.result()
                if "error" not in result:
                    results.append(result)
                    success_count += 1
                else:
                    logger.error(f"Task {task[0]} failed: {result['error']}")
                    error_count += 1
            except Exception as e:
                logger.error(f"Error processing task {task[0]}: {e}", exc_info=True)
                error_count += 1
    
    # Write results to JSONL file
    with open(args.output, 'w', encoding='utf-8') as f:
        for entry in results:
            f.write(json.dumps(entry, ensure_ascii=False) + '\n')
    
    # Output statistics
    completion_msg = f"Done! Generated {len(results)} dialogues, success: {success_count}, failed: {error_count}, saved to {args.output}"
    print(completion_msg)
    logger.info(completion_msg)
    
    # Statistics
    age_stats = {"18-25": 0, "26-40": 0, "41-55": 0, "56-70": 0}
    awareness_stats = {"low": 0, "medium": 0, "high": 0}
    fraud_stats = {fraud_type: 0 for fraud_type in FRAUD_TYPES}
    terminator_stats = {"left": 0, "right": 0, "natural": 0}
    occupations_stats = {occupation: 0 for occupation in OCCUPATIONS}
    
    for entry in results:
        age = entry["user_age"]
        if 18 <= age <= 25:
            age_stats["18-25"] += 1
        elif 26 <= age <= 40:
            age_stats["26-40"] += 1
        elif 41 <= age <= 55:
            age_stats["41-55"] += 1
        elif 56 <= age <= 70:
            age_stats["56-70"] += 1
            
        awareness_stats[entry["user_awareness"]] += 1
        fraud_stats[entry["fraud_type"]] += 1
        occupations_stats[entry["occupation"]] += 1
        
        # Count terminator
        terminator = entry.get("terminator", "natural")
        if terminator in terminator_stats:
            terminator_stats[terminator] += 1
    
    # Print statistics
    stats_msg = "\nDistribution statistics:"
    stats_msg += f"\nAge distribution: {age_stats}"
    stats_msg += f"\nAwareness distribution: {awareness_stats}"  # Only change description, not variable name
    stats_msg += f"\nDialogue type distribution: {fraud_stats}"  # Only change description, not variable name
    stats_msg += f"\nTerminator distribution: {terminator_stats}"
    stats_msg += f"\nOccupation distribution: {occupations_stats}"
    
    print(stats_msg)
    logger.info(stats_msg)
    
if __name__ == "__main__":
    start_time = time.time()
    try:
        main()
    except Exception as e:
        logger.critical("A critical error occurred during program execution", exc_info=True)
    
    elapsed = time.time() - start_time
    logger.info(f"Total time: {elapsed:.2f} seconds")
    print(f"Total time: {elapsed:.2f} seconds")