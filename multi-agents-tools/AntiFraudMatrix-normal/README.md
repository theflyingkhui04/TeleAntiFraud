# Hệ thống tạo đối thoại gian lận

## Giới thiệu dự án

Hệ thống tạo đối thoại gian lận là một khuôn khổ tạo đối thoại đa tác nhân dựa trên mô hình ngôn ngữ lớn, nhằm mục đích tạo ra các tập dữ liệu đối thoại gian lận thực tế cho mục đích nghiên cứu, đào tạo và giáo dục chống gian lận viễn thông. Hệ thống này sử dụng ba tác nhân để làm việc cùng nhau: tác nhân gian lận, tác nhân người dùng và tác nhân quản lý để mô phỏng các loại tình huống gian lận khác nhau và các phản ứng khác nhau của người dùng.

Dữ liệu hội thoại do hệ thống này tạo ra có thể được sử dụng cho:
- Đào tạo các mô hình phát hiện gian lận
- Phát triển các công cụ giáo dục và phòng ngừa
- Nghiên cứu các mô hình và sự tiến hóa của lời nói gian lận
- Phân tích sự khác biệt trong phản ứng với gian lận của các nhóm người dùng khác nhau

## Kiến trúc hệ thống

Hệ thống bao gồm các thành phần cốt lõi sau:

1. **Mô-đun tác nhân**:
- `LeftAgent` (kẻ lừa đảo): chịu trách nhiệm mô phỏng nhiều lời nói và chiến lược gian lận khác nhau
- `RightAgent` (người dùng): mô phỏng phản ứng của người dùng ở nhiều độ tuổi, nghề nghiệp và mức độ nhận thức chống gian lận khác nhau
- `ManagerAgent` (người quản lý): theo dõi cuộc trò chuyện và quyết định khi nào và ai sẽ kết thúc cuộc trò chuyện

2. **Điều phối viên cuộc trò chuyện**:
- Điều phối luồng hội thoại giữa kẻ lừa đảo và người dùng
- Kiểm soát kết thúc cuộc trò chuyện theo quyết định của người quản lý
- Tạo kết thúc cuộc trò chuyện tự nhiên

3. **Công cụ**:
- Đóng gói ứng dụng khách API OpenAI
- Ghi lại cuộc trò chuyện
- Công cụ xuất dữ liệu

## Tính năng

- **Gian lận đa dạng types**: Hỗ trợ 7 loại gian lận, bao gồm gian lận đầu tư, gian lận tình cảm, gian lận lừa đảo, trộm cắp danh tính, gian lận xổ số, việc làm giả và gian lận ngân hàng
- **Tùy chỉnh chân dung người dùng**: Phản ứng của người dùng có thể được tùy chỉnh dựa trên độ tuổi, nghề nghiệp và mức độ nhận thức chống gian lận
- **Kết thúc cuộc trò chuyện tự nhiên**: Tác nhân quản lý xác định điểm kết thúc tự nhiên và phương thức kết thúc cuộc trò chuyện
- **Tạo song song hiệu quả**: Hỗ trợ tạo song song đa luồng với lượng lớn dữ liệu cuộc trò chuyện
- **Xuất dữ liệu định dạng kép**: Hỗ trợ cả định dạng JSONL hợp lý hóa và định dạng JSON chi tiết
- **Ghi nhật ký chi tiết**: Ghi lại toàn bộ lịch sử cuộc trò chuyện và trạng thái hoạt động của hệ thống
- **Lấy mẫu phân phối đồng đều**: Đảm bảo phân phối đồng đều nhóm tuổi, nhận thức chống gian lận và các loại gian lận

## Yêu cầu cài đặt

### Yêu cầu về môi trường
- Python 3.8 trở lên
- Khóa API hợp lệ (như API OpenAI hoặc API tương thích khác)

### Dependency
```bash
pip install openai tqdm concurrent.futures
```

## Sử dụng

### Sử dụng cơ bản

1. Cấu hình khóa API và URL cơ sở:
```bash
export OPENAI_API_KEY="your-api-key"
```

2. Chạy tạo hộp thoại đơn:
```bash
python main.py --fraud_type investment --base_url "https://api.siliconflow.cn/v1" --api_key "your-api-key" --model "deepseek-ai/DeepSeek-V2.5"
```

3. Tạo hàng loạt tập dữ liệu hộp thoại:
```bash
python generate_dialogues.py --count 1000 --base_url "https://api.siliconflow.cn/v1" --api_key "your-api-key" --model "deepseek-ai/DeepSeek-V2.5" --workers 10 --output "fraud_dialogues.jsonl" --full_output_dir "full_dialogues"
```

### Mô tả tham số

#### Tạo hộp thoại đơn (main.py)
- `--fraud_type`: Loại gian lận [đầu tư, lãng mạn, lừa đảo, trộm cắp danh tính, xổ số, việc làm, ngân hàng]
- `--user_age`: độ tuổi của người dùng
- `--user_awareness`: nhận thức chống gian lận của người dùng [thấp, trung bình, cao]
- `--max_turns`: số lượt trò chuyện tối đa
- `--output`: đường dẫn tệp đầu ra
- `--base_url`: URL điểm cuối API tùy chỉnh
- `--api_key`: khóa API tùy chỉnh
- `--model`: tên mô hình

#### Tạo hộp thoại hàng loạt (generate_dialogues.py)
- `--count`: tổng số hộp thoại cần tạo
- `--output`: đường dẫn tệp đầu ra định dạng JSONL
- `--full_output_dir`: thư mục đầu ra tệp JSON của hộp thoại đầy đủ
- `--base_url`: URL điểm cuối API tùy chỉnh
- `--api_key`: khóa API tùy chỉnh
- `--model`: tên mô hình
- `--max_turns`: số lượt tối đa cho mỗi hộp thoại
- `--workers`: số luồng được tạo đồng thời

## Định dạng dữ liệu

### Định dạng JSONL (phiên bản đơn giản hóa)
```json
{
    "tts_id": "tts_fraud_00001",
    "left": [
        "Xin chào, đây là Ngân hàng Xây dựng Trung Quốc. Bạn có quỹ dự trữ 300.000 nhân dân tệ đứng tên mình. Lãi suất hàng tháng chỉ thấp tới 2,3%. Bạn có cần tiền ngay không?",
        "Vậy thì hãy cân nhắc nhé. Nếu bạn cần, vui lòng liên hệ với tôi. Đây là thông tin liên hệ của tôi."
    ],
    "right": [
        "Xin chào, không, cảm ơn.",
        "Được rồi, cảm ơn, tạm biệt."
    ],
    "user_age": 22,
    "user_awareness": "medium",
    "fraud_type": "banking",
    "occupation": "student",
    "termination_reason": "Người dùng nói rằng không cần...",
    "terminator": "right"
}
```

### Định dạng JSON (phiên bản chi tiết)
```json
{
    "tts_id": "tts_fraud_00001",
    "dialogue_history": [
        {
            "role": "left",
            "content": "Xin chào, đây là Ngân hàng Xây dựng Trung Quốc. Bạn có quỹ dự trữ 300.000 nhân dân tệ đứng tên mình. Lãi suất hàng tháng chỉ thấp tới 2,3%. Bạn có cần tiền ngay không?",
            "timestamp": 1740545473.5704024
        },
        {
            "role": "right",
            "content": "Xin chào, không, cảm ơn bạn.",
            "timestamp": 1740545476.625075
        }
    ],
    "user_age": 22,
    "user_awareness": "medium",
    "fraud_type": "banking",
    "occupation": "student",
    "turns": 2,
    "terminated_by_manager": true,
    "termination_reason": "Có. Người dùng đã chấm dứt. Lý do: Người dùng đã từ chối đề xuất của kẻ lừa đảo một cách rõ ràng...",
    "terminator": "right",
    "conclusion_messages": [],
    "reached_max_turns": false
}
```
```

## Cấu trúc dự án

```
├── agents/ # Mô-đun tác nhân
│ ├── base_agent.py # Lớp trừu tượng tác nhân cơ sở
│ ├── left_agent.py # Tác nhân lừa đảo
│ ├── right_agent.py # Tác nhân người dùng
│ ├── manager_agent.py # Tác nhân quản lý
│ └── prompts/ # Mẫu lời nhắc
│ ├── left_prompts.py
│ ├── right_prompts.py
│ └── manager_prompts.py
├── logic/ # Logic nghiệp vụ
│ └── dialogue_orchestrator.py # Điều phối viên đối thoại
├── utils/ # Lớp tiện ích
│ ├── openai_client.py # Máy khách API OpenAI
│ └── conversation_logger.py # Trình ghi nhật ký đối thoại
├── config.py # Tệp cấu hình
├── main.py # Mục tạo đối thoại đơn lẻ
├── generate_dialogues.py # Tạo đối thoại hàng loạt entry
├── requirements.txt # Danh sách gói phụ thuộc
└── README.md # Mô tả dự án
```

## Mô tả loại gian lận

1. **Gian lận đầu tư (đầu tư)**: Dụ dỗ người dùng đầu tư vào các dự án giả mạo hoặc rủi ro cao và hứa hẹn lợi nhuận cao
2. **Gian lận tình cảm (lãng mạn)**: Thiết lập mối quan hệ tình cảm giả tạo và cuối cùng yêu cầu tiền hoặc thông tin cá nhân
3. **Gian lận lừa đảo (phishing)**: Ngụy trang thành một tổ chức hợp pháp để lấy thông tin cá nhân hoặc mật khẩu tài khoản của người dùng
4. **Trộm cắp danh tính (identity_theft)**: Đánh cắp thông tin danh tính của người dùng để thực hiện các hoạt động tội phạm khác
5. **Gian lận xổ số (lottery)**: Thông báo cho người dùng rằng họ đã trúng xổ số, nhưng yêu cầu thanh toán phí và các khoản phí khác
6. **Công việc giả mạo (job_offer)**: Cung cấp các cơ hội việc làm có vẻ hào phóng, nhưng yêu cầu trả trước phí hoặc thông tin cá nhân
7. **Gian lận ngân hàng (ngân hàng)**: Ngụy trang thành nhân viên ngân hàng và tuyên bố rằng tài khoản bất thường và cần được vận hành

## Tham số chân dung người dùng

1. **Tuổi (user_age)**:
- 18-25: Thanh niên
- 26-40: Người lớn
- 41-55: Trung niên
- 56-70: Người cao tuổi

2. **Nhận thức về gian lận (user_awareness)**:
- thấp: Nhận thức về gian lận thấp, dễ tin kẻ lừa đảo
- trung bình: Nhận thức về gian lận trung bình, sẽ nghi ngờ nhưng có thể bị thuyết phục
- cao: Nhận thức về gian lận cao, cảnh giác cao, khó bị lừa

3. **Nghề nghiệp (occupation)**:
Nhiều loại nghề nghiệp, bao gồm sinh viên, giáo viên, kỹ sư, bác sĩ, người đã nghỉ hưu, v.v.

## Người đóng góp

Dự án này được phát triển bởi [tên nhóm hoặc tổ chức của bạn].

## Tuyên bố miễn trừ trách nhiệm

Dự án này chỉ dành cho mục đích nghiên cứu, giáo dục và phòng ngừa gian lận viễn thông. Nghiêm cấm sử dụng nội dung do hệ thống này tạo ra cho bất kỳ mục đích bất hợp pháp hoặc phi đạo đức nào. Người dùng phải chịu hoàn toàn trách nhiệm về việc sử dụng hệ thống này và nội dung do hệ thống tạo ra.

## Giấy phép

[Giấy phép phù hợp, chẳng hạn như MIT, Apache, v.v.]

---

## Câu hỏi thường gặp

### Câu hỏi: Làm thế nào để tôi thêm một loại gian lận mới?

Trả lời: Thêm loại mới vào danh sách `FRAUD_TYPES` trong `config.py`, sau đó thêm mẫu từ nhắc tương ứng vào `agents/prompts/left_prompts.py`.

### Câu hỏi: Làm thế nào để tôi điều chỉnh điều kiện kết thúc của cuộc trò chuyện?

Trả lời: Sửa đổi phần điều kiện kết thúc của `MANAGER_SYSTEM_PROMPT` trong `agents/prompts/manager_prompts.py`.

### Câu hỏi: Làm thế nào để tôi cải thiện hiệu quả tạo?

Trả lời: Tăng giá trị tham số `--workers` có thể cải thiện khả năng xử lý song song, nhưng bạn cần chú ý đến giới hạn lệnh gọi API và mức tiêu thụ tài nguyên hệ thống.

### H: Làm thế nào để tùy chỉnh chân dung người dùng?
A: Thêm hồ sơ người dùng được cài đặt sẵn thông qua các tham số `--user_age`, `--user_awareness` hoặc trong từ điển `USER_PROFILES` trong `config.py`.