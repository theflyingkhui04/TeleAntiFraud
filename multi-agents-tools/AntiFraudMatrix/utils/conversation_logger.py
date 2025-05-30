import logging
import time
from typing import Optional, TextIO

class ConversationLogger:
    """Bộ ghi log hội thoại, chịu trách nhiệm ghi lại và xuất nội dung hội thoại"""
    
    def __init__(self, log_file: Optional[str] = None, console_output: bool = True):
        self.console_output = console_output
        # Thiết lập logging
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        self.logger = logging.getLogger("dialogue")
        # Nếu có file log, thêm handler ghi file
        if log_file:
            file_handler = logging.FileHandler(log_file, encoding='utf-8')
            file_handler.setFormatter(logging.Formatter('%(asctime)s - %(message)s'))
            self.logger.addHandler(file_handler)
    
    def log(self, message: str) -> None:
        """Ghi log một tin nhắn hội thoại"""
        if self.console_output:
            print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {message}")
        self.logger.info(message)