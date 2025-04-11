import datetime
import json
import os
import zipfile
from io import BytesIO
import random
import numpy as np

import requests
import ChatTTS
import torch

# 初始化Chat对象并加载模型
chat = ChatTTS.Chat()
if not chat.load(source="huggingface"):
    raise RuntimeError("Failed to load ChatTTS models")

chattts_service_host = os.environ.get("CHATTTS_SERVICE_HOST", "localhost")
chattts_service_port = os.environ.get("CHATTTS_SERVICE_PORT", "8000")

CHATTTS_URL = f"http://{chattts_service_host}:{chattts_service_port}/generate_voice"

def sample_random_speaker():
    # 设置种子以确保可重复性
    torch.manual_seed(random.randint(0, 2**32-1))
    # 返回随机说话人embedding并转换为列表
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
        "spk_emb": speaker_emb,  # 这里的speaker_emb已经是列表格式
        "manual_seed": None,
    }
    body["params_infer_code"] = params_infer_code

    return body

def process_json_file(input_file):
    try:
        # 读取文件内容
        with open(input_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # 将内容按照JSON对象分割
        content = content.replace('\n', '')
        content = content.replace('}{', '}\n{')
        json_strings = content.split('\n')
        
        for json_str in json_strings:
            if not json_str.strip():
                continue
                
            try:
                data = json.loads(json_str)
                
                tts_id = data['tts_id']
                left_texts = data['left']
                right_texts = data['right']
                
                # 为left和right生成各自的speaker embedding
                left_speaker = sample_random_speaker()
                right_speaker = sample_random_speaker()
                while right_speaker == left_speaker:
                    right_speaker = sample_random_speaker()
                
                # 创建输出目录
                base_dir = f"./output/{tts_id}"
                os.makedirs(f"{base_dir}/left", exist_ok=True)
                os.makedirs(f"{base_dir}/right", exist_ok=True)
                
                # 处理left texts，每个文本单独处理但使用相同的speaker
                left_bodies = []
                for i, text in enumerate(left_texts):
                    left_body = process_single_text(text, left_speaker)
                    try:
                        response = requests.post(CHATTTS_URL, json=left_body)
                        response.raise_for_status()
                        # 从zip中提取文件并重命名
                        with zipfile.ZipFile(BytesIO(response.content), 'r') as zip_ref:
                            with zip_ref.open('0.mp3') as source, open(f"{base_dir}/left/{i}.mp3", 'wb') as target:
                                target.write(source.read())
                        print(f"Processed left text {i} for {tts_id}")
                        left_bodies.append(left_body)
                    except requests.exceptions.RequestException as e:
                        print(f"Request Error for left text {i} {tts_id}: {e}")
                
                # 处理right texts，每个文本单独处理但使用相同的speaker
                right_bodies = []
                for i, text in enumerate(right_texts):
                    right_body = process_single_text(text, right_speaker)
                    try:
                        response = requests.post(CHATTTS_URL, json=right_body)
                        response.raise_for_status()
                        # 从zip中提取文件并重命名
                        with zipfile.ZipFile(BytesIO(response.content), 'r') as zip_ref:
                            with zip_ref.open('0.mp3') as source, open(f"{base_dir}/right/{i}.mp3", 'wb') as target:
                                target.write(source.read())
                        print(f"Processed right text {i} for {tts_id}")
                        right_bodies.append(right_body)
                    except requests.exceptions.RequestException as e:
                        print(f"Request Error for right text {i} {tts_id}: {e}")
                
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
                    
            except json.JSONDecodeError as e:
                print(f"Error parsing JSON object: {e}")
                print(f"Problematic JSON string: {json_str}")
                
    except Exception as e:
        print(f"Error processing file: {e}")

if __name__ == "__main__":
    input_file = "/root/code/ChatTTS/input_data/input_test-3.jsonl"
    process_json_file(input_file)