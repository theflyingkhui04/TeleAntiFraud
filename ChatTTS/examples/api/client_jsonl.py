import datetime
import json
import os
import zipfile
from io import BytesIO
import random
import numpy as np
import asyncio
import aiohttp
from tqdm.asyncio import tqdm
import backoff  # 需要安装: pip install backoff

import ChatTTS
import torch

# 初始化Chat对象并加载模型
chat = ChatTTS.Chat()
if not chat.load(source="huggingface"):
    raise RuntimeError("Failed to load ChatTTS models")

chattts_service_host = os.environ.get("CHATTTS_SERVICE_HOST", "localhost")
chattts_service_port = os.environ.get("CHATTTS_SERVICE_PORT", "8000")

CHATTTS_URL = f"http://{chattts_service_host}:{chattts_service_port}/generate_voice"
STATUS_URL = f"http://{chattts_service_host}:{chattts_service_port}/status"

# 配置常量
MAX_RETRIES = 10
INITIAL_WAIT = 5  # 初始等待时间（秒）
MAX_WAIT = 60    # 最大等待时间（秒）
REQUEST_TIMEOUT = 300  # 请求超时时间（秒）

async def wait_for_service_ready():
    """等待服务准备就绪"""
    print("Waiting for service to be ready...")
    while True:
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(STATUS_URL, timeout=10) as response:
                    if response.status == 200:
                        status = await response.json()
                        if len(status.get('instances', {})) > 0:
                            print("Service is ready!")
                            return
        except Exception as e:
            print(f"Service not ready yet: {e}")
        print(f"Waiting {INITIAL_WAIT} seconds before next check...")
        await asyncio.sleep(INITIAL_WAIT)

def sample_random_speaker():
    torch.manual_seed(random.randint(0, 2**32-1))
    speaker_emb = chat.sample_random_speaker()
    if isinstance(speaker_emb, torch.Tensor):
        speaker_emb = speaker_emb.detach().cpu().numpy()
    if isinstance(speaker_emb, np.ndarray):
        speaker_emb = speaker_emb.tolist()
    return speaker_emb

def add_spaces_to_text(text):
    return ' '.join(list(text))

def process_single_text(text, speaker_emb):
    processed_text = add_spaces_to_text(text)
    
    body = {
        "text": [processed_text],
        "stream": False,
        "lang": None,
        "skip_refine_text": True,
        "refine_text_only": False,
        "use_decoder": True,
        "do_text_normalization": True,
        "do_homophone_replacement": False,
    }

    params_refine_text = {
        "prompt": "",
        "top_P": 0.7,
        "top_K": 20,
        "temperature": 0.7,
        "repetition_penalty": 1,
        "max_new_token": 384,
        "min_new_token": 0,
        "show_tqdm": True,
        "ensure_non_empty": True,
        "stream_batch": 24,
    }
    body["params_refine_text"] = params_refine_text

    params_infer_code = {
        "prompt": "[speed_5]",
        "top_P": 0.1,
        "top_K": 20,
        "temperature": 0.3,
        "repetition_penalty": 1.05,
        "max_new_token": 2048,
        "min_new_token": 0,
        "show_tqdm": True,
        "ensure_non_empty": True,
        "stream_batch": True,
        "spk_emb": speaker_emb,
        "manual_seed": None,
    }
    body["params_infer_code"] = params_infer_code

    return body

async def process_text_request(session, body, output_path, index):
    """
    处理文本请求，无限重试直到成功
    """
    retry_count = 0
    
    while True:  # 无限循环，直到成功或被外部中断
        try:
            timeout = aiohttp.ClientTimeout(total=REQUEST_TIMEOUT)
            
            # 记录重试信息
            retry_info = f" (Retry #{retry_count})" if retry_count > 0 else ""
            print(f"Processing request {index}{retry_info}...")
            
            async with session.post(CHATTTS_URL, json=body, timeout=timeout) as response:
                if response.status != 200:
                    error_text = await response.text()
                    print(f"Request {index} failed with status {response.status}: {error_text}")
                    retry_count += 1
                    # 使用指数退避策略
                    wait_time = min(INITIAL_WAIT * (2 ** min(retry_count, 6)), MAX_WAIT)
                    print(f"Waiting {wait_time} seconds before retry...")
                    await asyncio.sleep(wait_time)
                    continue
                
                content = await response.read()
                
                # 确保目录存在
                os.makedirs(os.path.dirname(output_path), exist_ok=True)
                
                # 从zip中提取文件并保存
                try:
                    with zipfile.ZipFile(BytesIO(content), 'r') as zip_ref:
                        with zip_ref.open('0.mp3') as source, open(output_path, 'wb') as target:
                            target.write(source.read())
                    print(f"Successfully processed request {index} and saved to {output_path}")
                    return index, body, None
                except zipfile.BadZipFile:
                    print(f"Request {index} returned invalid zip content, retrying...")
                    retry_count += 1
                    wait_time = min(INITIAL_WAIT * (2 ** min(retry_count, 6)), MAX_WAIT)
                    await asyncio.sleep(wait_time)
                    continue
                    
        except asyncio.TimeoutError:
            print(f"Request {index} timed out after {REQUEST_TIMEOUT} seconds")
            retry_count += 1
            wait_time = min(INITIAL_WAIT * (2 ** min(retry_count, 6)), MAX_WAIT)
            print(f"Waiting {wait_time} seconds before retry...")
            await asyncio.sleep(wait_time)
            
        except aiohttp.ClientError as e:
            print(f"Network error for request {index}: {str(e)}")
            retry_count += 1
            wait_time = min(INITIAL_WAIT * (2 ** min(retry_count, 6)), MAX_WAIT)
            print(f"Waiting {wait_time} seconds before retry...")
            await asyncio.sleep(wait_time)
            
        except Exception as e:
            print(f"Unexpected error for request {index}: {str(e)}")
            retry_count += 1
            wait_time = min(INITIAL_WAIT * (2 ** min(retry_count, 6)), MAX_WAIT)
            print(f"Waiting {wait_time} seconds before retry...")
            await asyncio.sleep(wait_time)

async def process_texts(texts, speaker_emb, base_path, side):
    bodies = []
    
    # 创建所有请求体
    for i, text in enumerate(texts):
        body = process_single_text(text, speaker_emb)
        bodies.append((i, body))

    # 使用aiohttp创建客户端会话，设置较长的超时时间
    timeout = aiohttp.ClientTimeout(total=REQUEST_TIMEOUT)
    conn = aiohttp.TCPConnector(limit=5)  # 限制并发连接数
    async with aiohttp.ClientSession(timeout=timeout, connector=conn) as session:
        # 创建所有任务
        tasks = []
        for i, body in bodies:
            output_path = f"{base_path}/{side}/{i}.mp3"
            task = process_text_request(session, body, output_path, i)
            tasks.append(task)

        # 使用tqdm包装任务并等待完成
        results = await tqdm.gather(*tasks, desc=f"Processing {side} texts")

        # 按索引排序结果
        results.sort(key=lambda x: x[0])
        
        # 提取处理后的bodies
        processed_bodies = [body for _, body, _ in results]
        
        return processed_bodies

async def process_json_file(input_file):
    # 等待服务准备就绪
    await wait_for_service_ready()
    
    try:
        with open(input_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        content = content.replace('\n', '')
        content = content.replace('}{', '}\n{')
        json_strings = content.split('\n')
        
        # 添加总体进度条
        for json_str in tqdm(json_strings, desc="Processing JSON objects"):
            if not json_str.strip():
                continue
                
            try:
                data = json.loads(json_str)
                
                tts_id = data['tts_id']
                left_texts = data['left']
                right_texts = data['right']
                
                print(f"\nProcessing tts_id: {tts_id}")
                
                left_speaker = sample_random_speaker()
                right_speaker = sample_random_speaker()
                while right_speaker == left_speaker:
                    right_speaker = sample_random_speaker()
                
                base_dir = f"./output-9/{tts_id}"
                os.makedirs(f"{base_dir}/left", exist_ok=True)
                os.makedirs(f"{base_dir}/right", exist_ok=True)
                
                # 异步处理left和right文本
                left_bodies, right_bodies = await asyncio.gather(
                    process_texts(left_texts, left_speaker, base_dir, "left"),
                    process_texts(right_texts, right_speaker, base_dir, "right")
                )
                
                # 保存请求参数
                query_data = {
                    "left_speaker": left_speaker,
                    "right_speaker": right_speaker,
                    "left_queries": left_bodies,
                    "right_queries": right_bodies
                }
                
                with open(f"{base_dir}/query.jsonl", 'w', encoding='utf-8') as f:
                    json.dump(query_data, f, ensure_ascii=False, indent=2)
                    f.write('\n')
                
                print(f"Successfully completed processing for tts_id: {tts_id}")
                    
            except json.JSONDecodeError as e:
                print(f"Error parsing JSON object: {e}")
                print(f"Problematic JSON string: {json_str}")
                
    except Exception as e:
        print(f"Error processing file: {e}")
        raise  # 重新抛出异常，以便可以看到完整的错误堆栈

if __name__ == "__main__":
    input_file = "/root/code/ChatTTS/input_data/input_test-9.jsonl"
    asyncio.run(process_json_file(input_file))