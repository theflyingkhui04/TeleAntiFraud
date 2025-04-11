import io
import os
import sys
import zipfile
from typing import Optional
from contextlib import asynccontextmanager

from fastapi import FastAPI, BackgroundTasks
from fastapi.responses import StreamingResponse
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import torch

if sys.platform == "darwin":
    os.environ["PYTORCH_ENABLE_MPS_FALLBACK"] = "1"

now_dir = os.getcwd()
sys.path.append(now_dir)

import ChatTTS
from tools.audio import pcm_arr_to_mp3_view
from tools.logger import get_logger
from tools.normalizer.en import normalizer_en_nemo_text
from tools.normalizer.zh import normalizer_zh_tn

logger = get_logger("Command")

# 全局chat实例池
chat_pool = []
MAX_POOL_SIZE = 3  # 根据服务器资源调整

@asynccontextmanager
async def get_chat_instance():
    """从池中获取chat实例的异步上下文管理器"""
    if not chat_pool:
        chat = ChatTTS.Chat(get_logger("ChatTTS"))
        chat.normalizer.register("en", normalizer_en_nemo_text())
        chat.normalizer.register("zh", normalizer_zh_tn())
        if not chat.load(source="huggingface"):
            raise RuntimeError("Failed to load models")
    else:
        chat = chat_pool.pop()
    try:
        yield chat
    finally:
        if len(chat_pool) < MAX_POOL_SIZE:
            chat_pool.append(chat)
        # 清理GPU内存
        torch.cuda.empty_cache()

class ChatTTSParams(BaseModel):
    text: list[str]
    stream: bool = False
    lang: Optional[str] = None
    skip_refine_text: bool = False
    refine_text_only: bool = False
    use_decoder: bool = True
    do_text_normalization: bool = True
    do_homophone_replacement: bool = False
    params_refine_text: ChatTTS.Chat.RefineTextParams = None
    params_infer_code: ChatTTS.Chat.InferCodeParams

app = FastAPI()

@app.on_event("startup")
async def startup_event():
    """初始化chat实例池"""
    for _ in range(MAX_POOL_SIZE):
        chat = ChatTTS.Chat(get_logger("ChatTTS"))
        chat.normalizer.register("en", normalizer_en_nemo_text())
        chat.normalizer.register("zh", normalizer_zh_tn())
        if chat.load(source="huggingface"):
            chat_pool.append(chat)
        else:
            logger.error("Models load failed.")
            sys.exit(1)
    logger.info(f"Initialized {len(chat_pool)} ChatTTS instances")

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request, exc: RequestValidationError):
    logger.error(f"Validation error: {exc.errors()}")
    return JSONResponse(status_code=422, content={"detail": exc.errors()})

async def cleanup_resources(buf):
    """清理资源的异步函数"""
    buf.close()
    torch.cuda.empty_cache()

@app.post("/generate_voice")
async def generate_voice(params: ChatTTSParams, background_tasks: BackgroundTasks):
    logger.info("Text input: %s", str(params.text))
    
    async with get_chat_instance() as chat:
        # 设置音频种子
        if params.params_infer_code.manual_seed is not None:
            torch.manual_seed(params.params_infer_code.manual_seed)
            params.params_infer_code.spk_emb = chat.sample_random_speaker()

        # 文本处理
        if params.params_refine_text:
            text = chat.infer(
                text=params.text, 
                skip_refine_text=False, 
                refine_text_only=True
            )
            logger.info(f"Refined text: {text}")
        else:
            text = params.text

        logger.info("Use speaker:")
        logger.info(params.params_infer_code.spk_emb)

        # 语音推理
        logger.info("Start voice inference.")
        wavs = chat.infer(
            text=text,
            stream=params.stream,
            lang=params.lang,
            skip_refine_text=params.skip_refine_text,
            use_decoder=params.use_decoder,
            do_text_normalization=params.do_text_normalization,
            do_homophone_replacement=params.do_homophone_replacement,
            params_infer_code=params.params_infer_code,
            params_refine_text=params.params_refine_text,
        )
        logger.info("Inference completed.")

        # 创建ZIP文件
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "a", compression=zipfile.ZIP_DEFLATED, allowZip64=False) as f:
            for idx, wav in enumerate(wavs):
                f.writestr(f"{idx}.mp3", pcm_arr_to_mp3_view(wav))
        logger.info("Audio generation successful.")
        buf.seek(0)

        # 添加资源清理任务
        background_tasks.add_task(cleanup_resources, buf)

        response = StreamingResponse(buf, media_type="application/zip")
        response.headers["Content-Disposition"] = "attachment; filename=audio_files.zip"
        return response