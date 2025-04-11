import io
import os
import sys
import zipfile
from typing import Optional, Dict, List, Any
from contextlib import asynccontextmanager
import asyncio
from collections import deque
import psutil
import GPUtil
import threading

from fastapi import FastAPI, BackgroundTasks, HTTPException
from fastapi.responses import StreamingResponse
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, validator
import torch
import numpy as np

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

# 配置参数
TOTAL_VRAM = 80  # 总显存（GB）
INSTANCE_VRAM = 15  # 每个实例占用显存（GB）
MAX_POOL_SIZE = min(12, int(TOTAL_VRAM * 0.9 // INSTANCE_VRAM))  # 保留10%显存余量
MAX_POOL_SIZE = 2

class ChatInstance:
    def __init__(self, id: int):
        self.id = id
        self.chat = None
        self.busy = False
        self.last_used = 0
        self.total_requests = 0
        self.failed_requests = 0
        
    def initialize(self):
        """同步初始化方法"""
        logger.info("Initializing instance " + str(self.id))
        self.chat = ChatTTS.Chat(get_logger("ChatTTS_" + str(self.id)))
        self.chat.normalizer.register("en", normalizer_en_nemo_text())
        self.chat.normalizer.register("zh", normalizer_zh_tn())
        if not self.chat.load(source="huggingface"):
            raise RuntimeError("Failed to load models for instance " + str(self.id))
        logger.info("Instance " + str(self.id) + " initialized successfully")
        return self

class InstancePool:
    def __init__(self):
        self.instances: Dict[int, ChatInstance] = {}
        self.available = deque()
        self.lock = asyncio.Lock()
        self.initialized = False
        self.initialization_event = asyncio.Event()
        
    def initialize_pool(self):
        """同步初始化所有实例"""
        logger.info("Starting pool initialization...")
        for i in range(MAX_POOL_SIZE):
            try:
                instance = ChatInstance(i).initialize()
                self.instances[i] = instance
                self.available.append(i)
                logger.info("Instance " + str(i) + " added to pool")
            except Exception as e:
                logger.error("Failed to initialize instance " + str(i) + ": " + str(e))
                raise
        
        logger.info("Successfully initialized " + str(len(self.instances)) + " ChatTTS instances")
        self.initialized = True
        self.initialization_event.set()

    async def wait_for_initialization(self):
        """等待初始化完成"""
        await self.initialization_event.wait()

    async def get_instance(self):
        """获取一个可用实例"""
        if not self.initialized:
            await self.wait_for_initialization()
        
        async with self.lock:
            while True:
                if not self.available:
                    await asyncio.sleep(0.1)
                    continue
                
                instance_id = self.available.popleft()
                instance = self.instances[instance_id]
                if not instance.busy:
                    instance.busy = True
                    instance.last_used = asyncio.get_event_loop().time()
                    instance.total_requests += 1
                    return instance
                
                self.available.append(instance_id)

    def release_instance(self, instance: ChatInstance):
        """释放实例"""
        instance.busy = False
        self.available.append(instance.id)

class ChatTTSParams(BaseModel):
    text: List[str]
    stream: bool = False
    lang: Optional[str] = None
    skip_refine_text: bool = False
    refine_text_only: bool = False
    use_decoder: bool = True
    do_text_normalization: bool = True
    do_homophone_replacement: bool = False
    params_refine_text: Optional[ChatTTS.Chat.RefineTextParams] = None
    params_infer_code: ChatTTS.Chat.InferCodeParams

    # 使用验证器
    @validator('text')
    def validate_text(cls, v):
        # 只检查text列表是否为空
        if not v:
            raise ValueError("Text list cannot be empty")
        
        # 即使所有文本都是空字符串，也允许通过验证
        return v

app = FastAPI()
instance_pool = InstancePool()

@app.on_event("startup")
async def startup_event():
    """服务启动事件"""
    def init_pool():
        try:
            instance_pool.initialize_pool()
        except Exception as e:
            logger.error("Failed to initialize pool: " + str(e))
            sys.exit(1)
    
    # 使用线程执行同步初始化
    init_thread = threading.Thread(target=init_pool)
    init_thread.start()

@app.get("/ready")
async def ready():
    """检查服务是否准备就绪"""
    try:
        await asyncio.wait_for(instance_pool.wait_for_initialization(), timeout=1.0)
        return {"status": "ready", "instances": len(instance_pool.instances)}
    except asyncio.TimeoutError:
        return {"status": "initializing"}

@app.get("/status")
async def get_status():
    """获取服务状态"""
    if not instance_pool.initialized:
        await instance_pool.wait_for_initialization()
    gpu = GPUtil.getGPUs()[0]
    return {
        "instances": {
            i: {
                "busy": inst.busy,
                "total_requests": inst.total_requests,
                "failed_requests": inst.failed_requests
            } for i, inst in instance_pool.instances.items()
        },
        "gpu_status": {
            "vram_used": str(round(gpu.memoryUsed, 1)) + "GB",
            "vram_util": str(round(gpu.memoryUtil*100, 1)) + "%"
        },
        "cpu_status": {
            "cpu_percent": str(round(psutil.cpu_percent(), 1)) + "%"
        }
    }

def format_validation_error(error) -> List[Dict[str, Any]]:
    """格式化验证错误，确保返回的是可JSON序列化的格式"""
    result = []
    for e in error:
        error_info = {
            "loc": e.get("loc", []),
            "msg": str(e.get("msg", "")),
            "type": e.get("type", "")
        }
        result.append(error_info)
    return result

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request, exc: RequestValidationError):
    """处理请求验证错误，确保返回内容是JSON可序列化的"""
    logger.error("Validation error: " + str(exc))
    try:
        errors = format_validation_error(exc.errors())
        return JSONResponse(status_code=422, content={"detail": errors})
    except Exception as e:
        logger.error(f"Error formatting validation error: {e}")
        return JSONResponse(
            status_code=422, 
            content={"detail": [{"msg": "Invalid input. Please check your request."}]}
        )

async def cleanup_resources(buf, instance: ChatInstance):
    """清理资源的异步函数"""
    buf.close()
    torch.cuda.empty_cache()
    instance_pool.release_instance(instance)

def create_empty_audio():
    """创建空白音频的MP3数据"""
    try:
        # 创建一个短的非零音频（0.1秒）- 确保有足够的样本且非零值
        sample_rate = 16000  # 假设采样率为16kHz
        duration = 0.1  # 0.1秒
        num_samples = int(sample_rate * duration)
        # 使用非零值，创建一个极小振幅的正弦波而不是零数组
        t = np.linspace(0, duration, num_samples, endpoint=False)
        empty_wav = 0.001 * np.sin(2 * np.pi * 440 * t)  # 440Hz的极小振幅正弦波
        
        # 添加日志以检查数组
        logger.info(f"Empty audio array shape: {empty_wav.shape}, min: {empty_wav.min()}, max: {empty_wav.max()}")
        
        return pcm_arr_to_mp3_view(empty_wav.astype(np.float32))
    except Exception as e:
        logger.error(f"Error creating empty audio: {e}")
        # 如果出错，返回预先生成的静音MP3数据
        return b'ID3\x03\x00\x00\x00\x00\x00#TSSE\x00\x00\x00\x0f\x00\x00\x03Lavf58.29.100\x00\x00\x00\x00\x00\x00\x00\x00\x00\xff\xf3\x84\xc0\x00\x00\x00\x00\x00\x00\x00\x00\x00Info\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00Lavf58.29.100\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00'

@app.post("/generate_voice")
async def generate_voice(params: ChatTTSParams, background_tasks: BackgroundTasks):
    """生成语音的主要接口"""
    logger.info("Text input: " + str(params.text))
    
    str_params_text = str(params.text)
    # 检查是否有非空文本
    has_non_empty_text = False
    if str_params_text != str(['']):
        logger.info("Checking for non-empty text...")
        for text in params.text:
            if text and text.strip():
                has_non_empty_text = True
                break

    if str_params_text == str(['']):
        logger.info("All texts are empty. Creating empty audio files.")
        has_non_empty_text=False
    
    # 创建一个包含空音频文件的ZIP
    if not has_non_empty_text:
        logger.info("All texts are empty. Creating empty audio files directly.")
        buf = io.BytesIO()
        try:
            with zipfile.ZipFile(buf, "a", compression=zipfile.ZIP_DEFLATED, allowZip64=False) as f:
                empty_audio_data = create_empty_audio()
                for i in range(len(params.text)):
                    f.writestr(f"{i}.mp3", empty_audio_data)
            
            logger.info("Created empty audio files for all text indices.")
            buf.seek(0)
            
            response = StreamingResponse(buf, media_type="application/zip")
            response.headers["Content-Disposition"] = "attachment; filename=audio_files.zip"
            
            # 添加资源清理任务
            background_tasks.add_task(lambda b: b.close(), buf)
            
            return response
        except Exception as e:
            logger.error(f"Error creating empty audio files: {e}")
            raise HTTPException(status_code=500, detail=f"Error creating empty audio files: {str(e)}")

    # 获取实例
    instance = await instance_pool.get_instance()
    logger.info("Using instance " + str(instance.id))
    
    try:
        # 设置音频种子
        if params.params_infer_code.manual_seed is not None:
            torch.manual_seed(params.params_infer_code.manual_seed)
            params.params_infer_code.spk_emb = instance.chat.sample_random_speaker()

        # 创建文本到索引的映射和非空文本列表
        non_empty_texts = []
        text_to_original_idx = {}
        for i, text in enumerate(params.text):
            if text and text.strip():
                text_to_original_idx[len(non_empty_texts)] = i
                non_empty_texts.append(text)
        
        logger.info(f"Processing {len(non_empty_texts)} non-empty texts out of {len(params.text)} total texts")
        
        # 文本处理
        if params.params_refine_text and non_empty_texts:
            text = instance.chat.infer(
                text=non_empty_texts, 
                skip_refine_text=False, 
                refine_text_only=True
            )
            logger.info("Refined text: " + str(text))
        else:
            text = non_empty_texts

        logger.info("Use speaker:")
        logger.info(str(params.params_infer_code.spk_emb))

        # 语音推理 - 只处理非空文本
        if non_empty_texts:
            logger.info("Start voice inference.")
            wavs = instance.chat.infer(
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
        else:
            wavs = []
        
        # 创建ZIP文件
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "a", compression=zipfile.ZIP_DEFLATED, allowZip64=False) as f:
            # 为所有索引创建MP3文件
            empty_audio_data = create_empty_audio()
            
            # 首先为所有位置添加空音频
            for i in range(len(params.text)):
                f.writestr(f"{i}.mp3", empty_audio_data)
            
            # 然后用非空文本的音频替换对应位置
            for wav_idx, original_idx in text_to_original_idx.items():
                if wav_idx < len(wavs):  # 确保索引有效
                    wav_data = pcm_arr_to_mp3_view(wavs[wav_idx])
                    if wav_data:  # 确保MP3数据有效
                        f.writestr(f"{original_idx}.mp3", wav_data)
        
        logger.info("Audio generation successful.")
        buf.seek(0)

        # 添加资源清理任务
        background_tasks.add_task(cleanup_resources, buf, instance)

        response = StreamingResponse(buf, media_type="application/zip")
        response.headers["Content-Disposition"] = "attachment; filename=audio_files.zip"
        return response
        
    except Exception as e:
        instance.failed_requests += 1
        instance_pool.release_instance(instance)
        logger.error("Error in generate_voice: " + str(e))
        raise HTTPException(status_code=500, detail=f"Error generating voice: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8004)