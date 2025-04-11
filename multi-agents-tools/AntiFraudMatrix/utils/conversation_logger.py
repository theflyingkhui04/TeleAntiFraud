import logging
import time
from typing import Optional, TextIO

class ConversationLogger:
    """对话记录器，负责记录和输出对话内容"""
    
    def __init__(self, log_file: Optional[str] = None, console_output: bool = True):
        self.console_output = console_output
        
        # 设置日志
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        
        self.logger = logging.getLogger("dialogue")
        
        # 如果提供了日志文件，添加文件处理器
        if log_file:
            file_handler = logging.FileHandler(log_file, encoding='utf-8')
            file_handler.setFormatter(logging.Formatter('%(asctime)s - %(message)s'))
            self.logger.addHandler(file_handler)
    
    def log(self, message: str) -> None:
        """记录消息"""
        if self.console_output:
            print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {message}")
        self.logger.info(message)