import argparse
import json
from agents.left_agent import LeftAgent
from agents.right_agent import RightAgent
from agents.manager_agent import ManagerAgent
from logic.dialogue_orchestrator import DialogueOrchestrator
from utils.conversation_logger import ConversationLogger
import config

def main():
    # Phân tích các đối số dòng lệnh
    parser = argparse.ArgumentParser(description="Multi-agent daily conversation generation system")
    parser.add_argument("--fraud_type", default="Customer service inquiry", help="Dialogue scenario type")
    parser.add_argument("--user_age", type=int, default=45, help="User age")
    parser.add_argument("--awareness", default="medium", help="User awareness level: low, medium, high")
    parser.add_argument("--max_turns", type=int, default=20, help="Maximum dialogue turns")
    parser.add_argument("--output", default="dialogue_output.json", help="Output file path")
    parser.add_argument("--base_url", default='https://api.siliconflow.cn/v1', help="Custom API endpoint URL")
    parser.add_argument("--api_key", default='', help="Custom API key")
    parser.add_argument("--model", default='Qwen/Qwen2.5-72B-Instruct', help="Model name")
    args = parser.parse_args()
    
    # Ghi đè cài đặt API mặc định bằng cách sử dụng đối số dòng lệnh
    if args.api_key:
        config.OPENAI_API_KEY = args.api_key
    if args.base_url:
        config.OPENAI_BASE_URL = args.base_url
    if args.model:
        config.DEFAULT_MODEL = args.model
    
    # Khởi tạo trình ghi nhật ký
    logger = ConversationLogger()
    
    # Tạo một tác nhân
    left_agent = LeftAgent(
        model=args.model,
        fraud_type=args.fraud_type,  # Giữ nguyên tên biến ban đầu fraud_type
        base_url=args.base_url
    )
    
    right_agent = RightAgent(
        model=args.model,
        user_profile={
            "age": args.user_age,
            "awareness": args.awareness,  # Giữ nguyên nhận thức về tên biến ban đầu
            "occupation": "Teacher"  # You can add more parameters
        },
        base_url=args.base_url
    )
    
    manager_agent = ManagerAgent(
        model=args.model,
        strictness="medium",
        base_url=args.base_url
    )
    
    # Tạo một điều phối viên hội thoại
    orchestrator = DialogueOrchestrator(
        left_agent=left_agent,
        right_agent=right_agent,
        manager_agent=manager_agent,
        max_turns=args.max_turns,
        logger=logger
    )
    
    # Chạy cuộc trò chuyện
    result = orchestrator.run_dialogue()
    
    # Lưu kết quả
    with open(args.output, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    
    print(f"Hoàn tất việc tạo hộp thoại, tổng cộng {len(result['dialogue_history'])} tin nhắn, đã lưu vào {args.output}")

if __name__ == "__main__":
    main()