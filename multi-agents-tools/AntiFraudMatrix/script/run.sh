#!/bin/bash

# 对话生成脚本
# 用法示例: ./generate_dialogues.sh 10
# "sk-yjapnkiskowaksedsvcybiqccfwanqemwjalwwakibqxnvia"
# 设置默认值
DEFAULT_COUNT=1000
DEFAULT_MODEL="Qwen/Qwen2.5-72B-Instruct"
DEFAULT_WORKERS=2
API_KEY="sk-fpwiniyhjwughnzrzdckrrkiyxkebpgcoslhnenybgbxyvva"
BASE_URL="https://api.siliconflow.cn/v1"

# 获取当前时间戳
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")

# 解析命令行参数
COUNT=${1:-$DEFAULT_COUNT}
MODEL=${2:-$DEFAULT_MODEL}
WORKERS=${3:-$DEFAULT_WORKERS}

# 设置输出文件名
OUTPUT_FILE="results/fraud_dialogues-${TIMESTAMP}.jsonl"
FULL_OUTPUT_DIR="results/full_dialogues_${TIMESTAMP}"

echo "====================================="
echo "对话生成任务开始运行"
echo "====================================="
echo "生成数量: $COUNT"
echo "使用模型: $MODEL"
echo "并行工作进程: $WORKERS"
echo "输出文件: $OUTPUT_FILE"
echo "完整对话目录: $FULL_OUTPUT_DIR"
echo "开始时间: $(date)"
echo "====================================="

# 创建日志目录
mkdir -p logs

# 运行命令并记录日志
python generate_dialogues.py \
  --count $COUNT \
  --base_url "$BASE_URL" \
  --api_key "$API_KEY" \
  --model "$MODEL" \
  --workers $WORKERS \
  --output "$OUTPUT_FILE" \
  --full_output_dir "$FULL_OUTPUT_DIR" 2>&1 | tee "logs/generate_${TIMESTAMP}.log"

# 检查命令执行状态
EXIT_CODE=$?
if [ $EXIT_CODE -eq 0 ]; then
  echo "====================================="
  echo "对话生成任务成功完成!"
  echo "结束时间: $(date)"
  echo "输出文件: $OUTPUT_FILE"
  echo "完整对话目录: $FULL_OUTPUT_DIR"
  echo "====================================="
else
  echo "====================================="
  echo "对话生成任务失败! 错误代码: $EXIT_CODE"
  echo "结束时间: $(date)"
  echo "查看日志文件获取详细信息: logs/generate_${TIMESTAMP}.log"
  echo "====================================="
fi

# 统计生成的对话数量
if [ -f "$OUTPUT_FILE" ]; then
  COUNT_ACTUAL=$(wc -l < "$OUTPUT_FILE")
  echo "实际生成对话数量: $COUNT_ACTUAL"
fi

exit $EXIT_CODE