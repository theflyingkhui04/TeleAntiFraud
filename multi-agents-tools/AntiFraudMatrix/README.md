# 诈骗对话生成系统

## 项目介绍

诈骗对话生成系统是一个基于大语言模型的多智能体对话生成框架，旨在创建逼真的诈骗对话数据集，用于反电信诈骗研究、训练和教育目的。本系统采用三个智能体协同工作：诈骗者智能体、用户智能体和管理者智能体，以模拟各种类型的诈骗场景和不同用户的反应。

通过本系统生成的对话数据可用于：
- 训练反诈骗检测模型
- 开发教育和预防工具
- 研究诈骗话术模式和演变
- 分析不同用户群体对诈骗的响应差异

## 系统架构

系统由以下核心组件组成：

1. **智能体模块**：
   - `LeftAgent`（诈骗者）：负责模拟各类诈骗话术和策略
   - `RightAgent`（用户）：模拟不同年龄、职业和防诈意识水平的用户反应
   - `ManagerAgent`（管理者）：监控对话，决定何时结束及由谁结束对话

2. **对话协调器**：
   - 协调诈骗者和用户之间的对话流程
   - 根据管理者决策控制对话结束
   - 生成自然的对话结束语

3. **工具类**：
   - OpenAI API 客户端封装
   - 对话记录器
   - 数据导出工具

## 功能特点

- **多样化诈骗类型**：支持投资诈骗、情感诈骗、钓鱼诈骗、身份盗窃、彩票诈骗、虚假工作和银行诈骗等7种诈骗类型
- **用户画像定制**：可根据年龄、职业和防诈意识水平定制用户反应
- **自然对话结束**：由管理者智能体决定对话自然结束点和结束方式
- **高效并行生成**：支持多线程并行生成大量对话数据
- **双格式数据导出**：同时支持精简的JSONL格式和详细的JSON格式
- **详细日志记录**：记录完整对话历史和系统运行状态
- **均匀分布采样**：确保年龄段、防诈意识和诈骗类型的均匀分布

## 安装要求

### 环境要求
- Python 3.8+
- 有效的API密钥（如OpenAI API或其他兼容API）

### 依赖包
```bash
pip install openai tqdm concurrent.futures
```

## 使用方法

### 基本用法

1. 配置API密钥和基础URL:
```bash
export OPENAI_API_KEY="your-api-key"
```

2. 运行单个对话生成:
```bash
python main.py --fraud_type investment --base_url "https://api.siliconflow.cn/v1" --api_key "your-api-key" --model "deepseek-ai/DeepSeek-V2.5"
```

3. 批量生成对话数据集:
```bash
python generate_dialogues.py --count 1000 --base_url "https://api.siliconflow.cn/v1" --api_key "your-api-key" --model "deepseek-ai/DeepSeek-V2.5" --workers 10 --output "fraud_dialogues.jsonl" --full_output_dir "full_dialogues"
```

### 参数说明

#### 单次对话生成 (main.py)
- `--fraud_type`: 诈骗类型 [investment, romance, phishing, identity_theft, lottery, job_offer, banking]
- `--user_age`: 用户年龄
- `--user_awareness`: 用户防诈意识 [low, medium, high]
- `--max_turns`: 最大对话轮次
- `--output`: 输出文件路径
- `--base_url`: 自定义API端点URL
- `--api_key`: 自定义API密钥
- `--model`: 模型名称

#### 批量对话生成 (generate_dialogues.py)
- `--count`: 要生成的对话总数
- `--output`: JSONL格式输出文件路径
- `--full_output_dir`: 完整对话JSON文件输出目录
- `--base_url`: 自定义API端点URL
- `--api_key`: 自定义API密钥
- `--model`: 模型名称
- `--max_turns`: 每个对话的最大轮次
- `--workers`: 并发生成的线程数

## 数据格式

### JSONL格式（简化版）
```json
{"tts_id": "tts_fraud_00001", "left": ["喂，您好，这边是建设银行的，您名下有一笔三十万的备用金可以申请，月息低至两厘三，您现在有资金需求吗？", "那您考虑一下，如果有需要随时联系我，这是我的联系方式。"], "right": ["喂，不用了，谢谢。", "好的，谢谢，再见。"], "user_age": 22, "user_awareness": "medium", "fraud_type": "banking", "occupation": "student", "termination_reason": "用户表示不需要...", "terminator": "right"}
```

### JSON格式（详细版）
```json
{
  "dialogue_history": [
    {
      "role": "left",
      "content": "喂，您好，这边是建设银行的，您名下有一笔三十万的备用金可以申请，月息低至两厘三，您现在有资金需求吗？",
      "timestamp": 1740545473.5704024
    },
    {
      "role": "right",
      "content": "喂，不用了，谢谢。",
      "timestamp": 1740545476.625075
    },
    ...
  ],
  "turns": 2,
  "terminated_by_manager": true,
  "termination_reason": "是。用户结束。理由：用户已经明确拒绝了诈骗者的提议...",
  "terminator": "right",
  "conclusion_messages": [...],
  "reached_max_turns": false
}
```

## 项目结构

```
├── agents/                     # 智能体模块
│   ├── base_agent.py           # 基础智能体抽象类
│   ├── left_agent.py           # 诈骗者智能体
│   ├── right_agent.py          # 用户智能体
│   ├── manager_agent.py        # 管理者智能体
│   └── prompts/                # 提示词模板
│       ├── left_prompts.py
│       ├── right_prompts.py
│       └── manager_prompts.py
├── logic/                      # 业务逻辑
│   └── dialogue_orchestrator.py # 对话协调器
├── utils/                      # 工具类
│   ├── openai_client.py        # OpenAI API客户端
│   └── conversation_logger.py  # 对话记录器
├── config.py                   # 配置文件
├── main.py                     # 单个对话生成入口
├── generate_dialogues.py       # 批量对话生成入口
├── requirements.txt            # 依赖包列表
└── README.md                   # 项目说明
```

## 诈骗类型说明

1. **投资诈骗 (investment)**：诱导用户投资虚假或高风险项目，承诺高回报
2. **情感诈骗 (romance)**：建立虚假情感关系，最终索要钱财或个人信息
3. **钓鱼诈骗 (phishing)**：伪装成合法机构，获取用户个人信息或账号密码
4. **身份盗窃 (identity_theft)**：盗取用户身份信息以实施其他犯罪活动
5. **彩票诈骗 (lottery)**：告知用户中奖，但要求支付手续费等费用
6. **虚假工作 (job_offer)**：提供看似优厚的工作机会，但要求预付费用或个人信息
7. **银行诈骗 (banking)**：伪装成银行工作人员，声称账户异常需要操作

## 用户画像参数

1. **年龄 (user_age)**:
   - 18-25: 青年
   - 26-40: 成年
   - 41-55: 中年
   - 56-70: 老年

2. **防诈意识 (user_awareness)**:
   - low: 低防诈意识，容易相信诈骗者
   - medium: 中等防诈意识，会有疑虑但可能被说服
   - high: 高防诈意识，高度警惕，难以被骗

3. **职业 (occupation)**:
   多种职业类型，包括学生、教师、工程师、医生、退休人员等

## 贡献者

本项目由[您的团队或机构名称]开发。

## 免责声明

本项目仅用于研究、教育和防范电信诈骗目的。严禁将本系统生成的内容用于任何非法或不道德用途。用户应当对使用本系统及其生成的内容负完全责任。

## 许可证

[适当的许可证，如MIT、Apache等]

---

## 常见问题

### Q: 如何添加新的诈骗类型？
A: 在 `config.py` 中的 `FRAUD_TYPES` 列表中添加新类型，然后在 `agents/prompts/left_prompts.py` 中添加相应的提示词模板。

### Q: 如何调整对话结束条件？
A: 在 `agents/prompts/manager_prompts.py` 中修改 `MANAGER_SYSTEM_PROMPT` 的终止条件部分。

### Q: 如何提高生成效率？
A: 增加 `--workers` 参数值可以提高并行处理能力，但需要注意API调用限制和系统资源消耗。

### Q: 如何自定义用户画像？
A: 通过 `--user_age`、`--user_awareness` 参数或在 `config.py` 中的 `USER_PROFILES` 字典中添加预设的用户画像。