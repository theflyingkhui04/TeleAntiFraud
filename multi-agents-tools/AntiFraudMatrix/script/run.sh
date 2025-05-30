#!/bin/bash

# Script sinh hội thoại
# Cách dùng ví dụ: ./generate_dialogues.sh 10
# "sk-yjapnkiskowaksedsvcybiqccfwanqemwjalwwakibqxnvia"
# Thiết lập giá trị mặc định
DEFAULT_COUNT=1000
DEFAULT_MODEL="Qwen/Qwen2.5-72B-Instruct"
DEFAULT_WORKERS=2
API_KEY="sk-fpwiniyhjwughnzrzdckrrkiyxkebpgcoslhnenybgbxyvva"
BASE_URL="https://api.siliconflow.cn/v1"

# Lấy timestamp hiện tại
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")

# Xử lý tham số dòng lệnh
COUNT=${1:-$DEFAULT_COUNT}
MODEL=${2:-$DEFAULT_MODEL}
WORKERS=${3:-$DEFAULT_WORKERS}

# Thiết lập tên file xuất kết quả
OUTPUT_FILE="results/fraud_dialogues-${TIMESTAMP}.jsonl"
FULL_OUTPUT_DIR="results/full_dialogues_${TIMESTAMP}"

echo "====================================="
echo "Bắt đầu sinh hội thoại"
echo "====================================="
echo "Số lượng: $COUNT"
echo "Model sử dụng: $MODEL"
echo "Số tiến trình song song: $WORKERS"
echo "File kết quả: $OUTPUT_FILE"
echo "Thư mục lưu hội thoại đầy đủ: $FULL_OUTPUT_DIR"
echo "Thời gian bắt đầu: $(date)"
echo "====================================="

# Tạo thư mục log
mkdir -p logs

# Chạy lệnh và ghi log
python generate_dialogues.py \
  --count $COUNT \
  --base_url "$BASE_URL" \
  --api_key "$API_KEY" \
  --model "$MODEL" \
  --workers $WORKERS \
  --output "$OUTPUT_FILE" \
  --full_output_dir "$FULL_OUTPUT_DIR" 2>&1 | tee "logs/generate_${TIMESTAMP}.log"

# Kiểm tra trạng thái thực thi
EXIT_CODE=$?
if [ $EXIT_CODE -eq 0 ]; then
  echo "====================================="
  echo "Sinh hội thoại thành công!"
  echo "Thời gian kết thúc: $(date)"
  echo "File kết quả: $OUTPUT_FILE"
  echo "Thư mục lưu hội thoại đầy đủ: $FULL_OUTPUT_DIR"
  echo "====================================="
else
  echo "====================================="
  echo "Sinh hội thoại thất bại! Mã lỗi: $EXIT_CODE"
  echo "Thời gian kết thúc: $(date)"
  echo "Xem chi tiết trong log: logs/generate_${TIMESTAMP}.log"
  echo "====================================="
fi

# Thống kê số hội thoại đã sinh
if [ -f "$OUTPUT_FILE" ]; then
  COUNT_ACTUAL=$(wc -l < "$OUTPUT_FILE")
  echo "Số hội thoại thực tế đã sinh: $COUNT_ACTUAL"
fi

exit $EXIT_CODE