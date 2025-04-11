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
import argparse  # 用于解析命令行参数

import ChatTTS
import torch

# 解析命令行参数
def parse_args():
    parser = argparse.ArgumentParser(description='Process text to speech using ChatTTS.')
    
    parser.add_argument('--input_file', type=str, required=True,
                      help='Input JSON file path')
    
    parser.add_argument('--output_dir', type=str, default='./output',
                      help='Base output directory (default: ./output)')
    
    parser.add_argument('--project_name', type=str, default=None,
                      help='Project name (default: derived from input filename)')
    
    parser.add_argument('--host', type=str, default='localhost',
                      help='ChatTTS service host (default: localhost)')
    
    parser.add_argument('--port', type=str, default='8004',
                      help='ChatTTS service port (default: 8000)')
    
    parser.add_argument('--timeout', type=int, default=300,
                      help='Request timeout in seconds (default: 300)')
    
    parser.add_argument('--max_retries', type=int, default=10,
                      help='Maximum number of retries for failed requests (default: 10)')
    
    parser.add_argument('--initial_wait', type=int, default=5,
                      help='Initial wait time between retries in seconds (default: 5)')
    
    parser.add_argument('--max_wait', type=int, default=60,
                      help='Maximum wait time between retries in seconds (default: 60)')
    
    parser.add_argument('--concurrent_limit', type=int, default=5,
                      help='Limit of concurrent connections (default: 5)')
    
    parser.add_argument('--no_timestamp', action='store_true',
                      help='Do not add timestamp to output directory')
    
    return parser.parse_args()

# 初始化Chat对象并加载模型
chat = ChatTTS.Chat()
if not chat.load(source="huggingface"):
    raise RuntimeError("Failed to load ChatTTS models")

async def wait_for_service_ready(status_url, initial_wait):
    """等待服务准备就绪"""
    print("Waiting for service to be ready...")
    while True:
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(status_url, timeout=10) as response:
                    if response.status == 200:
                        status = await response.json()
                        if len(status.get('instances', {})) > 0:
                            print("Service is ready!")
                            return
        except Exception as e:
            print(f"Service not ready yet: {e}")
        print(f"Waiting {initial_wait} seconds before next check...")
        await asyncio.sleep(initial_wait)

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

async def process_text_request(session, body, output_path, index, chattts_url, args):
    """
    处理文本请求，无限重试直到成功
    """
    retry_count = 0
    
    while True:  # 无限循环，直到成功或被外部中断
        try:
            timeout = aiohttp.ClientTimeout(total=args.timeout)
            
            # 记录重试信息
            retry_info = f" (Retry #{retry_count})" if retry_count > 0 else ""
            print(f"Processing request {index}{retry_info}...")
            
            async with session.post(chattts_url, json=body, timeout=timeout) as response:
                if response.status != 200:
                    error_text = await response.text()
                    print(f"Request {index} failed with status {response.status}: {error_text}")
                    retry_count += 1
                    # 使用指数退避策略
                    wait_time = min(args.initial_wait * (2 ** min(retry_count, 6)), args.max_wait)
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
                    wait_time = min(args.initial_wait * (2 ** min(retry_count, 6)), args.max_wait)
                    await asyncio.sleep(wait_time)
                    continue
                    
        except asyncio.TimeoutError:
            print(f"Request {index} timed out after {args.timeout} seconds")
            retry_count += 1
            wait_time = min(args.initial_wait * (2 ** min(retry_count, 6)), args.max_wait)
            print(f"Waiting {wait_time} seconds before retry...")
            await asyncio.sleep(wait_time)
            
        except aiohttp.ClientError as e:
            print(f"Network error for request {index}: {str(e)}")
            retry_count += 1
            wait_time = min(args.initial_wait * (2 ** min(retry_count, 6)), args.max_wait)
            print(f"Waiting {wait_time} seconds before retry...")
            await asyncio.sleep(wait_time)
            
        except Exception as e:
            print(f"Unexpected error for request {index}: {str(e)}")
            retry_count += 1
            wait_time = min(args.initial_wait * (2 ** min(retry_count, 6)), args.max_wait)
            print(f"Waiting {wait_time} seconds before retry...")
            await asyncio.sleep(wait_time)

async def process_texts(texts, speaker_emb, base_path, side, chattts_url, args):
    bodies = []
    
    # 创建所有请求体
    for i, text in enumerate(texts):
        body = process_single_text(text, speaker_emb)
        bodies.append((i, body))

    # 使用aiohttp创建客户端会话，设置较长的超时时间
    timeout = aiohttp.ClientTimeout(total=args.timeout)
    conn = aiohttp.TCPConnector(limit=args.concurrent_limit)  # 限制并发连接数
    async with aiohttp.ClientSession(timeout=timeout, connector=conn) as session:
        # 创建所有任务
        tasks = []
        for i, body in bodies:
            output_path = f"{base_path}/{side}/{i}.mp3"
            task = process_text_request(session, body, output_path, i, chattts_url, args)
            tasks.append(task)

        # 使用tqdm包装任务并等待完成
        results = await tqdm.gather(*tasks, desc=f"Processing {side} texts")

        # 按索引排序结果
        results.sort(key=lambda x: x[0])
        
        # 提取处理后的bodies
        processed_bodies = [body for _, body, _ in results]
        
        return processed_bodies

async def process_json_file(args):
    # 设置URL
    chattts_url = f"http://{args.host}:{args.port}/generate_voice"
    status_url = f"http://{args.host}:{args.port}/status"
    
    # 等待服务准备就绪
    await wait_for_service_ready(status_url, args.initial_wait)
    
    try:
        with open(args.input_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        content = content.replace('\n', '')
        content = content.replace('}{', '}\n{')
        json_strings = content.split('\n')
        
        # 确定项目名称
        if args.project_name:
            project_name = args.project_name
        else:
            # 从输入文件名构建项目名称
            file_name = os.path.basename(args.input_file)
            project_name = os.path.splitext(file_name)[0]
        
        # 创建带时间戳的项目目录（除非指定不加时间戳）
        if args.no_timestamp:
            project_dir = f"{args.output_dir}/{project_name}"
        else:
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            project_dir = f"{args.output_dir}/{project_name}_{timestamp}"
        
        print(f"Project output directory: {project_dir}")
        
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
                
                # 使用新的项目目录作为基础路径
                base_dir = f"{project_dir}/{tts_id}"
                os.makedirs(f"{base_dir}/left", exist_ok=True)
                os.makedirs(f"{base_dir}/right", exist_ok=True)
                
                # 异步处理left和right文本
                left_bodies, right_bodies = await asyncio.gather(
                    process_texts(left_texts, left_speaker, base_dir, "left", chattts_url, args),
                    process_texts(right_texts, right_speaker, base_dir, "right", chattts_url, args)
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
    args = parse_args()
    asyncio.run(process_json_file(args))