import argparse
import json
from agents.left_agent import LeftAgent
from agents.right_agent import RightAgent
from agents.manager_agent import ManagerAgent
from logic.dialogue_orchestrator import DialogueOrchestrator
from utils.conversation_logger import ConversationLogger
import config

def main():
    # 解析命令行参数
    parser = argparse.ArgumentParser(description="多智能体诈骗对话生成系统")
    parser.add_argument("--fraud_type", default="investment", help="诈骗类型")
    parser.add_argument("--user_age", type=int, default=45, help="用户年龄")
    parser.add_argument("--user_awareness", default="high", help="用户防诈意识: low, medium, high")
    parser.add_argument("--max_turns", type=int, default=20, help="最大对话轮次")
    parser.add_argument("--output", default="dialogue_output.json", help="输出文件路径")
    parser.add_argument("--base_url", default='https://api.siliconflow.cn/v1', help="自定义API端点URL")
    parser.add_argument("--api_key", default='', help="自定义API密钥")
    parser.add_argument("--model", default='Qwen/Qwen2.5-72B-Instruct', help="模型名称")
    args = parser.parse_args()
    
    # 使用命令行参数覆盖默认API设置
    if args.api_key:
        config.OPENAI_API_KEY = args.api_key
    if args.base_url:
        config.OPENAI_BASE_URL = args.base_url
    if args.model:
        config.DEFAULT_MODEL = args.model
    
    # 初始化日志记录器
    logger = ConversationLogger()
    
    # 创建智能体
    left_agent = LeftAgent(
        model=args.model,
        fraud_type=args.fraud_type,
        base_url=args.base_url
    )
    
    right_agent = RightAgent(
        model=args.model,
        user_profile={
            "age": args.user_age,
            "awareness": args.user_awareness,
            "occupation": "teacher"  # 可以添加更多参数
        },
        base_url=args.base_url
    )
    
    manager_agent = ManagerAgent(
        model=args.model,
        strictness="medium",
        base_url=args.base_url
    )
    
    # 创建对话协调器
    orchestrator = DialogueOrchestrator(
        left_agent=left_agent,
        right_agent=right_agent,
        manager_agent=manager_agent,
        max_turns=args.max_turns,
        logger=logger
    )
    
    # 运行对话
    result = orchestrator.run_dialogue()
    
    # 保存结果
    with open(args.output, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    
    print(f"对话生成完成，共{len(result['dialogue_history'])}条消息，已保存到{args.output}")

if __name__ == "__main__":
    main()