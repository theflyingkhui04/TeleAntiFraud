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

# 配置全局日志
logging.basicConfig(
    filename='run.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# 配置参数
AGE_RANGES = [
    (18, 25),  # 青年
    (26, 40),  # 成年
    (41, 55),  # 中年
    (56, 70),  # 老年
]

# AWARENESS_LEVELS = [ "high","medium", "low",]
AWARENESS_LEVELS = [ "低","中", "高",]

# 对话场景类型（保持fraud_types变量名）
FRAUD_TYPES = [
    "订餐服务", "咨询客服", "预约服务", 
     "交通咨询", "日常购物", 
    "打车服务", "外卖服务"
]

OCCUPATIONS = [ "学生", "教师", "工程师", "医生", "退休人员", "企业主", "上班族", "农民", "服务员" ]

def generate_dialogue(args, tts_id: str, user_age: int, user_awareness: str, fraud_type: str) -> Dict[str, Any]:
    """生成单个对话并返回结果"""
    try:
        # 记录对话参数
        logger.info(f"开始生成对话 {tts_id}: age={user_age}, awareness={user_awareness}, fraud_type={fraud_type}")
        
        # 创建智能体
        left_agent = LeftAgent(
            model=args.model,
            fraud_type=fraud_type,  # 保持原变量名
            base_url=args.base_url
        )
        
        # 随机选择一个职业
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
        
        # 创建对话协调器，禁用控制台输出
        conv_logger = ConversationLogger(console_output=False)
        orchestrator = DialogueOrchestrator(
            left_agent=left_agent,
            right_agent=right_agent,
            manager_agent=manager_agent,
            max_turns=args.max_turns,
            logger=conv_logger
        )
        
        # 运行对话
        dialogue_result = orchestrator.run_dialogue()
        
        # 记录完整对话历史到日志
        logger.info(f"对话 {tts_id} 完成，共 {len(dialogue_result['dialogue_history'])} 轮")
        logger.info(f"对话历史 {tts_id}:")
        for msg in dialogue_result['dialogue_history']:
            role = "服务方" if msg['role'] == "left" else "用户"
            logger.info(f"{role}: {msg['content']}")
        
        # 提取终止原因
        termination_reason = "达到最大轮次" if dialogue_result.get("reached_max_turns", False) else dialogue_result.get("termination_reason", "未知")
        # 如果是管理者终止的，提取简短的终止原因描述
        if dialogue_result.get("terminated_by_manager", False) and isinstance(termination_reason, str) and len(termination_reason) > 100:
            # 提取前100个字符或到第一个句号的内容
            short_reason = termination_reason.split("。")[0] if "。" in termination_reason[:100] else termination_reason[:100]
            termination_reason = short_reason + "..."
        
        # 提取左右对话内容
        left_messages = []
        right_messages = []
        
        for message in dialogue_result["dialogue_history"]:
            if message["role"] == "left":
                left_messages.append(message["content"])
            elif message["role"] == "right":
                right_messages.append(message["content"])
        
        # 创建JSONL格式的数据条目
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
        
        # 保存完整对话记录
        full_dialogue_path = os.path.join(args.full_output_dir, f"{tts_id}.json")
        with open(full_dialogue_path, 'w', encoding='utf-8') as f:
            json.dump(dialogue_result, f, ensure_ascii=False, indent=2)
        
        logger.info(f"对话 {tts_id} 处理完成，终止原因: {termination_reason}")
        logger.info(f"完整对话已保存到 {full_dialogue_path}")
        
        return entry
    
    except Exception as e:
        logger.error(f"生成对话 {tts_id} 时出错: {e}", exc_info=True)
        # 返回一个错误标记，稍后会过滤掉
        return {"error": str(e), "tts_id": tts_id}

def main():
    # 解析命令行参数
    parser = argparse.ArgumentParser(description="多智能体对话数据生成")
    parser.add_argument("--count", type=int, default=20, help="要生成的对话数量")
    parser.add_argument("--output", default="fraud_dialogues.jsonl", help="输出文件路径")
    parser.add_argument("--full_output_dir", default="full_dialogues", help="完整对话输出目录")
    parser.add_argument("--base_url", required=True, help="自定义API端点URL")
    parser.add_argument("--api_key", required=True, help="自定义API密钥")
    parser.add_argument("--model", required=True, help="模型名称")
    parser.add_argument("--max_turns", type=int, default=15, help="最大对话轮次")
    parser.add_argument("--workers", type=int, default=10, help="并发工作线程数")
    args = parser.parse_args()
    
    # 记录启动信息
    logger.info(f"开始生成 {args.count} 个对话，模型: {args.model}, API基础URL: {args.base_url}")
    
    # 设置API密钥和基础URL
    config.OPENAI_API_KEY = args.api_key
    config.OPENAI_BASE_URL = args.base_url
    
    # 创建输出目录
    output_dir = os.path.dirname(args.output)
    if output_dir and not os.path.exists(output_dir):
        os.makedirs(output_dir)
    
    # 创建完整对话输出目录
    if not os.path.exists(args.full_output_dir):
        os.makedirs(args.full_output_dir)
    
    # 准备任务参数列表
    tasks = []
    
    # 确保参数均匀分布
    combinations = []
    for age_range in AGE_RANGES:
        for awareness in AWARENESS_LEVELS:
            for fraud in FRAUD_TYPES:
                combinations.append((age_range, awareness, fraud))
    
    # 为每个组合分配数量
    per_combination = args.count // len(combinations)
    remainder = args.count % len(combinations)
    
    # 添加任务
    tts_counter = 1
    for combo in combinations:
        age_range, awareness, fraud = combo
        # 该组合的任务数
        combo_count = per_combination + (1 if remainder > 0 else 0)
        if remainder > 0:
            remainder -= 1
            
        for _ in range(combo_count):
            user_age = random.randint(age_range[0], age_range[1])
            tts_id = f"tts_fraud_{tts_counter:05d}"
            tasks.append((tts_id, user_age, awareness, fraud))
            tts_counter += 1
    
    # 随机打乱任务顺序
    random.shuffle(tasks)
    
    # 使用线程池并行生成对话
    results = []
    success_count = 0
    error_count = 0
    
    logger.info(f"开始并行生成对话，线程数: {args.workers}")
    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        # 提交所有任务
        future_to_task = {
            executor.submit(generate_dialogue, args, tts_id, user_age, awareness, fraud): 
            (tts_id, user_age, awareness, fraud) 
            for tts_id, user_age, awareness, fraud in tasks
        }
        
        # 处理完成的任务
        for future in tqdm(as_completed(future_to_task), total=len(tasks), desc="生成对话"):
            task = future_to_task[future]
            try:
                result = future.result()
                if "error" not in result:
                    results.append(result)
                    success_count += 1
                else:
                    logger.error(f"任务 {task[0]} 失败: {result['error']}")
                    error_count += 1
            except Exception as e:
                logger.error(f"处理任务 {task[0]} 时出错: {e}", exc_info=True)
                error_count += 1
    
    # 写入结果到JSONL文件
    with open(args.output, 'w', encoding='utf-8') as f:
        for entry in results:
            f.write(json.dumps(entry, ensure_ascii=False) + '\n')
    
    # 输出统计信息
    completion_msg = f"完成！共生成 {len(results)} 个对话，成功: {success_count}，失败: {error_count}，已保存到 {args.output}"
    print(completion_msg)
    logger.info(completion_msg)
    
    # 统计分布情况
    age_stats = {"18-25": 0, "26-40": 0, "41-55": 0, "56-70": 0}
    awareness_stats = {"低": 0, "中": 0, "高": 0}
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
        
        # 统计终止方
        terminator = entry.get("terminator", "natural")
        if terminator in terminator_stats:
            terminator_stats[terminator] += 1
    
    # 打印统计信息
    stats_msg = "\n分布统计:"
    stats_msg += f"\n年龄分布: {age_stats}"
    stats_msg += f"\n沟通风格分布: {awareness_stats}"  # 仅修改描述，不修改变量名
    stats_msg += f"\n对话类型分布: {fraud_stats}"  # 仅修改描述，不修改变量名
    stats_msg += f"\n终止方分布: {terminator_stats}"
    stats_msg += f"\n职业分布: {occupations_stats}"
    
    print(stats_msg)
    logger.info(stats_msg)
    
if __name__ == "__main__":
    start_time = time.time()
    try:
        main()
    except Exception as e:
        logger.critical("程序执行过程中发生严重错误", exc_info=True)
    
    elapsed = time.time() - start_time
    logger.info(f"总耗时: {elapsed:.2f}秒")
    print(f"总耗时: {elapsed:.2f}秒")