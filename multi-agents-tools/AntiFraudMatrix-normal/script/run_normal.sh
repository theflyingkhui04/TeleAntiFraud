#!/bin/bash

# Dialogue generation script
# Usage example: ./generate_dialogues.sh 10
# "sk-yjapnkiskowaksedsvcybiqccfwanqemwjalwwakibqxnvia"
# Set default values
DEFAULT_COUNT=2500
DEFAULT_MODEL="deepseek-ai/DeepSeek-V2.5"
DEFAULT_WORKERS=2
API_KEY="sk-snqprjadkwbxggowrmzmzkdhsdajpdlqirgeopejlalyvbxb"
BASE_URL="https://api.siliconflow.cn/v1"

# Get current timestamp
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")

# Parse command line arguments
COUNT=${1:-$DEFAULT_COUNT}
MODEL=${2:-$DEFAULT_MODEL}
WORKERS=${3:-$DEFAULT_WORKERS}

# Set output file name
OUTPUT_FILE="results/normal_dialogues-${TIMESTAMP}.jsonl"
FULL_OUTPUT_DIR="results/normal-full_dialogues_${TIMESTAMP}"

echo "====================================="
echo "Công việc tạo đối thoại đã bắt đầu"
echo "====================================="
echo "Số lượng cần tạo: $COUNT"
echo "Mô hình sử dụng: $MODEL"
echo "Luồng xử lý song song: $WORKERS"
echo "Tệp đầu ra: $OUTPUT_FILE"
echo "Thư mục đầu ra đầy đủ: $FULL_OUTPUT_DIR"
echo "Thời gian bắt đầu: $(date)"
echo "====================================="

# Create log directory
mkdir -p logs

# Run command and record log
python generate_dialogues.py \
  --count $COUNT \
  --base_url "$BASE_URL" \
  --api_key "$API_KEY" \
  --model "$MODEL" \
  --workers $WORKERS \
  --output "$OUTPUT_FILE" \
  --full_output_dir "$FULL_OUTPUT_DIR" 2>&1 | tee "logs/generate_${TIMESTAMP}.log"

# Check command execution status
EXIT_CODE=$?
if [ $EXIT_CODE -eq 0 ]; then
  echo "====================================="
  echo "Quá trình tạo đối thoại đã hoàn thành thành công!"
  echo "Thời gian kết thúc: $(date)"
  echo "Tệp đầu ra: $OUTPUT_FILE"
  echo "Thư mục đối thoại đầy đủ: $FULL_OUTPUT_DIR"
  echo "====================================="
else
  echo "====================================="
  echo "Quá trình tạo đối thoại thất bại! Mã lỗi: $EXIT_CODE"
  echo "Thời gian kết thúc: $(date)"
  echo "Kiểm tra tệp nhật ký để biết chi tiết: logs/generate_${TIMESTAMP}.log"
  echo "====================================="
fi

# Count the number of generated dialogues
if [ -f "$OUTPUT_FILE" ]; then
  COUNT_ACTUAL=$(wc -l < "$OUTPUT_FILE")
  echo "Số lượng cuộc trò chuyện tạo ra: $COUNT_ACTUAL"
fi

exit $EXIT_CODE