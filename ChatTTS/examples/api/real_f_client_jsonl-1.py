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
import backoff
import argparse
import base64

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
    
    parser.add_argument('--port', type=str, default='8006',
                      help='ChatTTS service port (default: 8006)')
    
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
    
    parser.add_argument('--resume', action='store_true',
                      help='Resume processing from existing output directory')
    
    parser.add_argument('--resume_dir', type=str, default=None,
                      help='Specific directory to resume from (if --resume is set)')
    
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
    """生成随机说话人嵌入"""
    torch.manual_seed(random.randint(0, 2**32-1))
    speaker_emb = chat.sample_random_speaker()
    if isinstance(speaker_emb, torch.Tensor):
        speaker_emb = speaker_emb.detach().cpu().numpy()
    if isinstance(speaker_emb, np.ndarray):
        speaker_emb = speaker_emb.tolist()
    
    # 直接返回列表
    return speaker_emb

def process_single_text(text, speaker_emb):
    """处理单个文本，生成请求体"""
    # 不对文本做特殊处理，保留原始文本
    processed_text = text
    
    # 基本参数
    body = {
        "text": [processed_text],
        "stream": False,
        "lang": None,
        "skip_refine_text": False,
        "refine_text_only": False,
        "use_decoder": True,
        "do_text_normalization": True,
        "do_homophone_replacement": False,
    }

    # 创建RefineTextParams对象
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

    # 创建InferCodeParams对象
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
        "spk_emb": speaker_emb,  # 直接使用列表
        "manual_seed": None,
    }
    body["params_infer_code"] = params_infer_code

    return body

async def process_text_request(session, body, output_path, index, chattts_url, args):
    """处理文本请求，无限重试直到成功"""
    # 检查文件是否已经存在且有效
    if os.path.exists(output_path) and os.path.getsize(output_path) > 1024:  # 假设小于1KB的文件是无效的
        print(f"File already exists and valid: {output_path}, skipping...")
        return index, body, None
        
    retry_count = 0
    
    while True:  # 无限循环，直到成功或被外部中断
        try:
            timeout = aiohttp.ClientTimeout(total=args.timeout)
            
            # 记录重试信息
            retry_info = f" (Retry #{retry_count})" if retry_count > 0 else ""
            print(f"Processing request {index}{retry_info}...")

            # 打印spk_emb信息用于调试
            spk_emb = body["params_infer_code"]["spk_emb"]
            spk_type = type(spk_emb).__name__
            spk_len = len(spk_emb) if isinstance(spk_emb, list) else "unknown"
            print(f"Request {index} spk_emb type: {spk_type}, length: {spk_len}")
            
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
                print(f"Received response for request {index}, size: {len(content)} bytes")
                
                # 确保目录存在
                os.makedirs(os.path.dirname(output_path), exist_ok=True)
                
                # 从zip中提取文件并保存
                try:
                    with zipfile.ZipFile(BytesIO(content), 'r') as zip_ref:
                        # 打印ZIP文件内容
                        file_list = zip_ref.namelist()
                        print(f"ZIP contents for request {index}: {file_list}")
                        
                        # 寻找0.mp3文件
                        mp3_file = "0.mp3"
                        if mp3_file in file_list:
                            with zip_ref.open(mp3_file) as source, open(output_path, 'wb') as target:
                                mp3_data = source.read()
                                print(f"Extracting {mp3_file}, size: {len(mp3_data)} bytes")
                                target.write(mp3_data)
                                
                            # 验证生成的文件大小
                            file_size = os.path.getsize(output_path)
                            print(f"Saved file size: {file_size} bytes")
                            
                            if file_size < 1024:
                                print(f"Warning: Generated file is very small ({file_size} bytes), may be empty")
                        else:
                            print(f"Error: {mp3_file} not found in ZIP file")
                            retry_count += 1
                            wait_time = min(args.initial_wait * (2 ** min(retry_count, 6)), args.max_wait)
                            await asyncio.sleep(wait_time)
                            continue
                            
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

def load_speakers_from_query(query_file):
    """从query.jsonl文件加载speaker嵌入"""
    if not os.path.exists(query_file):
        return None, None
        
    try:
        with open(query_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return data.get('left_speaker'), data.get('right_speaker')
    except Exception as e:
        print(f"Error loading speakers from {query_file}: {e}")
        return None, None

def find_missing_files(base_dir, texts, side):
    """查找缺失的或大小为0的文件"""
    missing_indices = []
    for i in range(len(texts)):
        file_path = f"{base_dir}/{side}/{i}.mp3"
        if not os.path.exists(file_path) or os.path.getsize(file_path) < 1024:  # 假设小于1KB的文件是无效的
            missing_indices.append(i)
    return missing_indices

async def process_specific_texts(texts, indices, speaker_emb, base_path, side, chattts_url, args):
    """处理指定索引的文本"""
    bodies = []
    
    # 创建指定索引的请求体
    for i in indices:
        if i < len(texts):
            body = process_single_text(texts[i], speaker_emb)
            bodies.append((i, body))

    # 使用aiohttp创建客户端会话
    timeout = aiohttp.ClientTimeout(total=args.timeout)
    conn = aiohttp.TCPConnector(limit=args.concurrent_limit)
    async with aiohttp.ClientSession(timeout=timeout, connector=conn) as session:
        # 创建任务
        tasks = []
        for i, body in bodies:
            output_path = f"{base_path}/{side}/{i}.mp3"
            task = process_text_request(session, body, output_path, i, chattts_url, args)
            tasks.append(task)

        # 执行任务
        results = await tqdm.gather(*tasks, desc=f"Processing specific {side} texts")
        
        # 按索引排序结果
        results.sort(key=lambda x: x[0])
        
        # 提取处理后的bodies
        processed_bodies = [body for _, body, _ in results]
        
        return processed_bodies

async def resume_processing(project_dir, input_file, chattts_url, args):
    """从现有项目目录恢复处理"""
    print(f"Resuming processing from {project_dir}")
    
    processed_tts_ids = set()
    
    try:
        # 加载原始JSON数据
        with open(input_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        content = content.replace('\n', '')
        content = content.replace('}{', '}\n{')
        json_strings = content.split('\n')
        
        # 遍历项目目录中的每个tts_id文件夹
        for item in os.listdir(project_dir):
            tts_dir = os.path.join(project_dir, item)
            if not os.path.isdir(tts_dir):
                continue
                
            print(f"\nChecking directory: {tts_dir}")
            
            try:
                tts_id = int(os.path.basename(tts_dir))
                processed_tts_ids.add(tts_id)
            except ValueError:
                # 如果目录名不是整数，跳过
                continue
            
            # 查找匹配的JSON数据
            tts_id = os.path.basename(tts_dir)
            matching_data = None
            
            for json_str in json_strings:
                if not json_str.strip():
                    continue
                    
                try:
                    data = json.loads(json_str)
                    if str(data['tts_id']) == tts_id:
                        matching_data = data
                        break
                except Exception:
                    continue
            
            if not matching_data:
                print(f"No matching data found for tts_id {tts_id}, skipping...")
                continue
                
            # 加载speakers
            query_file = os.path.join(tts_dir, "query.jsonl")
            left_speaker, right_speaker = load_speakers_from_query(query_file)
            
            if not left_speaker or not right_speaker:
                print(f"No speaker information found for tts_id {tts_id}, generating new speakers...")
                left_speaker = sample_random_speaker()
                right_speaker = sample_random_speaker()
                while right_speaker == left_speaker:
                    right_speaker = sample_random_speaker()
            
            # 查找缺失的文件
            left_texts = matching_data['left']
            right_texts = matching_data['right']
            
            left_missing = find_missing_files(tts_dir, left_texts, "left")
            right_missing = find_missing_files(tts_dir, right_texts, "right")
            
            if not left_missing and not right_missing:
                print(f"All files for tts_id {tts_id} are already processed, skipping...")
                continue
                
            print(f"Found {len(left_missing)} missing left files and {len(right_missing)} missing right files")
            
            # 处理缺失的文件
            left_bodies = []
            right_bodies = []
            
            if left_missing:
                missing_texts = [left_texts[i] for i in left_missing]
                print(f"Processing {len(missing_texts)} missing left texts...")
                left_bodies = await process_specific_texts(
                    left_texts, left_missing, left_speaker, tts_dir, "left", chattts_url, args
                )
                
            if right_missing:
                missing_texts = [right_texts[i] for i in right_missing]
                print(f"Processing {len(missing_texts)} missing right texts...")
                right_bodies = await process_specific_texts(
                    right_texts, right_missing, right_speaker, tts_dir, "right", chattts_url, args
                )
            
            # 更新query.jsonl
            if left_bodies or right_bodies:
                try:
                    # 如果query.jsonl存在，加载现有数据
                    if os.path.exists(query_file):
                        with open(query_file, 'r', encoding='utf-8') as f:
                            query_data = json.load(f)
                    else:
                        query_data = {
                            "left_speaker": left_speaker,
                            "right_speaker": right_speaker,
                            "left_queries": [],
                            "right_queries": []
                        }
                    
                    # 更新缺失文件的请求数据
                    if left_bodies:
                        # 确保left_queries列表足够长
                        while len(query_data.get("left_queries", [])) < max(left_missing) + 1:
                            query_data.setdefault("left_queries", []).append(None)
                        
                        # 更新特定位置的请求数据
                        for i, body in zip(left_missing, left_bodies):
                            if i < len(query_data["left_queries"]):
                                query_data["left_queries"][i] = body
                            else:
                                query_data["left_queries"].append(body)
                    
                    if right_bodies:
                        # 确保right_queries列表足够长
                        while len(query_data.get("right_queries", [])) < max(right_missing) + 1:
                            query_data.setdefault("right_queries", []).append(None)
                        
                        # 更新特定位置的请求数据
                        for i, body in zip(right_missing, right_bodies):
                            if i < len(query_data["right_queries"]):
                                query_data["right_queries"][i] = body
                            else:
                                query_data["right_queries"].append(body)
                    
                    # 保存更新后的query.jsonl
                    with open(query_file, 'w', encoding='utf-8') as f:
                        json.dump(query_data, f, ensure_ascii=False, indent=2)
                        f.write('\n')
                    
                    print(f"Updated query.jsonl for tts_id {tts_id}")
                    
                except Exception as e:
                    print(f"Error updating query.jsonl for tts_id {tts_id}: {e}")
        
        return processed_tts_ids
            
    except Exception as e:
        print(f"Error during resume processing: {e}")
        raise

def get_project_name(args):
    """获取项目名称，优先使用命令行参数指定的名称，否则从输入文件名派生"""
    if args.project_name:
        return args.project_name
    else:
        file_name = os.path.basename(args.input_file)
        return os.path.splitext(file_name)[0]

async def process_json_file(args):
    # 设置URL
    chattts_url = f"http://{args.host}:{args.port}/generate_voice"
    status_url = f"http://{args.host}:{args.port}/status"
    
    # 等待服务准备就绪
    await wait_for_service_ready(status_url, args.initial_wait)
    
    # 读取输入文件
    try:
        with open(args.input_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        content = content.replace('\n', '')
        content = content.replace('}{', '}\n{')
        json_strings = content.split('\n')
        json_objects = []
        
        for json_str in json_strings:
            if not json_str.strip():
                continue
            try:
                data = json.loads(json_str)
                json_objects.append(data)
            except json.JSONDecodeError as e:
                print(f"Error parsing JSON object: {e}")
                print(f"Problematic JSON string: {json_str}")
                
        if not json_objects:
            print("No valid JSON objects found in input file!")
            return
            
    except Exception as e:
        print(f"Error reading input file: {e}")
        raise
    
    # 确定项目名称
    project_name = get_project_name(args)
    
    # 处理恢复模式
    processed_tts_ids = set()
    project_dir = None
    
    if args.resume:
        resume_dir = None
        if args.resume_dir:
            # 如果指定了恢复目录，检查它是否存在
            if not os.path.exists(args.resume_dir):
                print(f"Resume directory {args.resume_dir} does not exist!")
                return
            resume_dir = args.resume_dir
        else:
            # 没有指定恢复目录，查找最新的项目目录
            if not os.path.exists(args.output_dir):
                print(f"Output directory {args.output_dir} does not exist!")
                return
            
            # 查找匹配的项目目录
            matching_dirs = []
            for item in os.listdir(args.output_dir):
                item_path = os.path.join(args.output_dir, item)
                if os.path.isdir(item_path) and item.startswith(project_name):
                    matching_dirs.append(item_path)
            
            if not matching_dirs:
                print(f"No matching project directories found for {project_name}")
                # 不返回，而是以非恢复模式继续
                print("Continuing in normal mode...")
            else:
                # 按修改时间排序，选择最新的
                resume_dir = max(matching_dirs, key=os.path.getmtime)
                print(f"Resuming from latest directory: {resume_dir}")
        
        # 如果找到了恢复目录，执行恢复操作
        if resume_dir:
            processed_tts_ids = await resume_processing(resume_dir, args.input_file, chattts_url, args)
            
            # 检查是否所有tts_id都已处理
            all_tts_ids = {data['tts_id'] for data in json_objects}
            if all_tts_ids.issubset(processed_tts_ids):
                print("All tts_ids have been processed. Exiting...")
                return
            
            # 继续处理剩余的JSON对象
            print("Continuing with remaining unprocessed tts_ids...")
            
            # 使用已存在的目录
            project_dir = resume_dir
    
    # 如果没有设置project_dir（非恢复模式或恢复模式但没找到目录）
    if not project_dir:
        # 创建新的项目目录
        if args.no_timestamp:
            project_dir = f"{args.output_dir}/{project_name}"
        else:
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            project_dir = f"{args.output_dir}/{project_name}_{timestamp}"
        
        print(f"Project output directory: {project_dir}")
        os.makedirs(project_dir, exist_ok=True)
    
    # 处理所有未处理的JSON对象
    # 排序以确保按tts_id顺序处理
    sorted_json_objects = sorted(json_objects, key=lambda x: x['tts_id'])
    
    # 添加总体进度条
    remaining_objects = [obj for obj in sorted_json_objects if obj['tts_id'] not in processed_tts_ids]
    print(f"Processing {len(remaining_objects)} remaining JSON objects...")
    
    for data in tqdm(remaining_objects, desc="Processing JSON objects"):
        try:
            tts_id = data['tts_id']
            left_texts = data['left']
            right_texts = data['right']
            
            print(f"\nProcessing tts_id: {tts_id}")
            
            left_speaker = sample_random_speaker()
            right_speaker = sample_random_speaker()
            while right_speaker == left_speaker:
                right_speaker = sample_random_speaker()
            
            # 使用项目目录作为基础路径
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
            
            # 添加到已处理集合
            processed_tts_ids.add(tts_id)
                
        except Exception as e:
            print(f"Error processing tts_id {data.get('tts_id', 'unknown')}: {e}")
            # 继续处理下一个对象
            continue
    
    print("All processing completed!")

if __name__ == "__main__":
    args = parse_args()
    asyncio.run(process_json_file(args))