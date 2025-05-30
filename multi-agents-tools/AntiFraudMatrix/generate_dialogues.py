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

# Cấu hình ghi log toàn cục
logging.basicConfig(
    filename='run.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# Cấu hình các giá trị
AGE_RANGES = [
    (18, 25),  # Thanh niên
    (26, 40),  # Trung niên
    (41, 55),  # Trung cao tuổi
    (56, 70),  # Cao tuổi
]

AWARENESS_LEVELS = ["low", "medium", "high"]

FRAUD_TYPES = [
    "Đầu tư", "Phishing", "Chiếm đoạt danh tính", "Trúng thưởng", "Ngân hàng", "Bắt cóc", "Chăm sóc khách hàng", "Lừa đảo qua thư"
]

OCCUPATIONS = ["Học sinh/Sinh viên", "Giáo viên", "Kỹ sư", "Bác sĩ", "Người đã nghỉ hưu", "Thất nghiệp", "Chủ doanh nghiệp", "Nhân viên văn phòng", "Nông dân", "Nhân viên dịch vụ"]

def generate_dialogue(args, tts_id: str, user_age: int, user_awareness: str, fraud_type: str) -> Dict[str, Any]:
    """Sinh một hội thoại và trả về kết quả"""
    try:
        # Ghi log tham số hội thoại
        logger.info(f"Bắt đầu sinh hội thoại {tts_id}: age={user_age}, awareness={user_awareness}, fraud_type={fraud_type}")
        
        # Tạo agent bên trái (Kẻ lừa đảo)
        left_agent = LeftAgent(
            model=args.model,
            fraud_type=fraud_type,
            base_url=args.base_url
        )
        
        # Tạo agent bên phải (Người dùng)
        # Ngẫu nhiên chọn một độ tuổi trong khoảng
        user_age = random.randint(user_age[0], user_age[1])
        
        # Ngẫu nhiên chọn một nghề nghiệp
        occupation = random.choice(OCCUPATIONS)
        
        right_agent = RightAgent(
            model=args.model,
            user_profile={
                "age": user_age,
                "awareness": user_awareness,
                "occupation": occupation
            },
            base_url=args.base_url
        )
        
        # Tạo agent quản lý
        manager_agent = ManagerAgent(
            model=args.model,
            strictness="medium",
            base_url=args.base_url
        )
        
        # Tạo bộ điều phối hội thoại
        conv_logger = ConversationLogger(console_output=False)
        orchestrator = DialogueOrchestrator(
            left_agent=left_agent,
            right_agent=right_agent,
            manager_agent=manager_agent,
            max_turns=args.max_turns,
            logger=conv_logger
        )
        
        # Sinh hội thoại
        dialogue_result = orchestrator.run_dialogue()
        
        # Ghi log lịch sử hội thoại
        logger.info(f"Hội thoại {tts_id} hoàn thành, tổng {len(dialogue_result['dialogue_history'])} lượt")
        logger.info(f"Lịch sử hội thoại {tts_id}:")
        for msg in dialogue_result['dialogue_history']:
            role = "Kẻ lừa đảo" if msg['role'] == "left" else "Người dùng"
            logger.info(f"{role}: {msg['content']}")
        
        # Trích xuất lý do kết thúc
        termination_reason = "Đạt tối đa lượt" if dialogue_result.get("reached_max_turns", False) else dialogue_result.get("termination_reason", "Không xác định")
        # Nếu do quản lý kết thúc, rút ngắn lý do
        if dialogue_result.get("terminated_by_manager", False) and isinstance(termination_reason, str) and len(termination_reason) > 100:
            # Lấy 100 ký tự đầu hoặc đến dấu chấm đầu tiên
            short_reason = termination_reason.split("。")[0] if "。" in termination_reason[:100] else termination_reason[:100]
            termination_reason = short_reason + "..."
        
        # Tách biệt nội dung hội thoại của hai bên
        left_messages = []
        right_messages = []
        
        for message in dialogue_result["dialogue_history"]:
            if message["role"] == "left":
                left_messages.append(message["content"])
            elif message["role"] == "right":
                right_messages.append(message["content"])
        
        # Tạo entry dữ liệu JSONL
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
        
        # Lưu trữ hội thoại đầy đủ
        full_dialogue_path = os.path.join(args.full_output_dir, f"{tts_id}.json")
        with open(full_dialogue_path, 'w', encoding='utf-8') as f:
            json.dump(dialogue_result, f, ensure_ascii=False, indent=2)
        
        logger.info(f"Hội thoại {tts_id} xử lý xong, lý do kết thúc: {termination_reason}")
        logger.info(f"Đã lưu hội thoại đầy đủ vào {full_dialogue_path}")
        
        return entry
    
    except Exception as e:
        logger.error(f"Lỗi khi sinh hội thoại {tts_id}: {e}", exc_info=True)
        return {"error": str(e), "tts_id": tts_id}

def main():
    # Phân tích tham số dòng lệnh
    parser = argparse.ArgumentParser(description="Sinh dữ liệu hội thoại lừa đảo đa agent")
    parser.add_argument("--count", type=int, default=20, help="Số lượng hội thoại cần sinh")
    parser.add_argument("--output", default="fraud_dialogues.jsonl", help="Đường dẫn file kết quả")
    parser.add_argument("--full_output_dir", default="full_dialogues", help="Thư mục lưu hội thoại đầy đủ")
    parser.add_argument("--base_url", required=True, help="API endpoint tuỳ chỉnh")
    parser.add_argument("--api_key", required=True, help="API key tuỳ chỉnh")
    parser.add_argument("--model", required=True, help="Tên model sử dụng")
    parser.add_argument("--max_turns", type=int, default=15, help="Số lượt hội thoại tối đa")
    parser.add_argument("--workers", type=int, default=10, help="Số luồng xử lý song song")
    args = parser.parse_args()
    
    # Ghi log thông tin khởi động
    logger.info(f"Bắt đầu sinh {args.count} hội thoại, model: {args.model}, API: {args.base_url}")
    
    # Cấu hình API key và URL cơ sở
    config.OPENAI_API_KEY = args.api_key
    config.OPENAI_BASE_URL = args.base_url
    
    # Tạo thư mục lưu trữ kết quả nếu chưa tồn tại
    output_dir = os.path.dirname(args.output)
    if output_dir and not os.path.exists(output_dir):
        os.makedirs(output_dir)
    
    # Tạo thư mục lưu trữ hội thoại đầy đủ
    if not os.path.exists(args.full_output_dir):
        os.makedirs(args.full_output_dir)
    
    # Tạo danh sách nhiệm vụ
    tasks = []
    
    # Đảm bảo phân phối đều các tham số
    combinations = []
    for age_range in AGE_RANGES:
        for awareness in AWARENESS_LEVELS:
            for fraud in FRAUD_TYPES:
                combinations.append((age_range, awareness, fraud))
    
    # Phân bổ số lượng nhiệm vụ cho mỗi tổ hợp tham số
    per_combination = args.count // len(combinations)
    remainder = args.count % len(combinations)
    
    # Thêm nhiệm vụ vào danh sách
    tts_counter = 1
    for combo in combinations:
        age_range, awareness, fraud = combo
        # Số lượng nhiệm vụ cho tổ hợp này
        combo_count = per_combination + (1 if remainder > 0 else 0)
        if remainder > 0:
            remainder -= 1
            
        for _ in range(combo_count):
            user_age = random.randint(age_range[0], age_range[1])
            tts_id = f"tts_fraud_{tts_counter:05d}"
            tasks.append((tts_id, user_age, awareness, fraud))
            tts_counter += 1
    
    # Xáo trộn thứ tự nhiệm vụ
    random.shuffle(tasks)
    
    # Sinh hội thoại song song
    logger.info(f"Bắt đầu sinh hội thoại song song, số luồng: {args.workers}")
    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        # Gửi tất cả nhiệm vụ vào xử lý
        future_to_task = {
            executor.submit(generate_dialogue, args, tts_id, user_age, awareness, fraud): 
            (tts_id, user_age, awareness, fraud) 
            for tts_id, user_age, awareness, fraud in tasks
        }
        
        # Xử lý kết quả trả về
        for future in tqdm(as_completed(future_to_task), total=len(tasks), desc="Sinh hội thoại"):
            task = future_to_task[future]
            try:
                result = future.result()
                if "error" not in result:
                    results.append(result)
                    success_count += 1
                else:
                    logger.error(f"Nhiệm vụ {task[0]} thất bại: {result['error']}")
                    error_count += 1
            except Exception as e:
                logger.error(f"Lỗi khi xử lý nhiệm vụ {task[0]}: {e}", exc_info=True)
                error_count += 1
    
    # Ghi kết quả vào file JSONL
    with open(args.output, 'w', encoding='utf-8') as f:
        for entry in results:
            f.write(json.dumps(entry, ensure_ascii=False) + '\n')
    
    # Xuất thống kê phân phối
    stats_msg = "\nThống kê phân phối:"
    stats_msg += f"\nPhân bố độ tuổi: {age_stats}"
    stats_msg += f"\nPhân bố nhận thức: {awareness_stats}"
    stats_msg += f"\nPhân bố loại lừa đảo: {fraud_stats}"
    stats_msg += f"\nPhân bố bên kết thúc: {terminator_stats}"
    stats_msg += f"\nPhân bố nghề nghiệp: {occupations_stats}"
    
    print(stats_msg)
    logger.info(stats_msg)
    
if __name__ == "__main__":
    start_time = time.time()
    try:
        main()
    except Exception as e:
        logger.critical("Lỗi nghiêm trọng trong quá trình chạy chương trình", exc_info=True)
    elapsed = time.time() - start_time
    logger.info(f"Tổng thời gian: {elapsed:.2f} giây")
    print(f"Tổng thời gian: {elapsed:.2f} giây")