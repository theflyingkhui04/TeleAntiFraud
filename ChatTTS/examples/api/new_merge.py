import os
import json
import glob
from pydub import AudioSegment
import numpy as np
from tqdm import tqdm
import concurrent.futures
import threading

# 创建一个线程锁，用于在多线程环境中安全打印
print_lock = threading.Lock()

def safe_print(*args, **kwargs):
    """线程安全的打印函数"""
    with print_lock:
        print(*args, **kwargs)

def pan_audio(audio, is_left):
    """将音频声道平移到左或右"""
    # 确保音频是立体声
    if audio.channels == 1:
        audio = audio.set_channels(2)
    
    # 获取原始音频数据
    samples = np.array(audio.get_array_of_samples())
    
    # 重塑数组为(n_samples, n_channels)
    samples = samples.reshape((-1, audio.channels))
    
    # 创建新的样本数组
    if is_left:
        # 左声道保持不变，右声道设为0
        samples[:, 1] = 0
    else:
        # 右声道保持不变，左声道设为0
        samples[:, 0] = 0
    
    # 将样本数组展平
    samples = samples.flatten()
    
    # 创建新的AudioSegment
    panned_audio = audio._spawn(samples.tobytes())
    return panned_audio

def process_directory(tts_dir, jsonl_dir, output_dir):
    """处理单个目录的函数，用于并行执行"""
    tts_dirname = os.path.basename(tts_dir)
    safe_print(f"\nProcessing directory: {tts_dir}")
    
    # 查找对应的JSONL文件
    jsonl_file = os.path.join(jsonl_dir, f"{tts_dirname}.json")
    
    if not os.path.exists(jsonl_file):
        safe_print(f"JSONL file not found for {tts_dirname}, skipping...")
        return
        
    try:
        # 读取JSONL文件
        with open(jsonl_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
            
        # 检查是否包含"API调用失败"
        dialogue_content = ' '.join([msg.get('content', '') for msg in data.get('dialogue_history', [])])
        if "API调用失败" in dialogue_content:
            safe_print(f"Skipping {tts_dirname} as it contains API call failure")
            return
            
        # 获取对话历史
        dialogue_history = data.get('dialogue_history', [])
        
        # 创建一个空的音频段
        merged_audio = AudioSegment.empty()
        
        # 用于记录每段音频的时间点信息
        audio_segments = []
        current_position_ms = 0
        
        # 按照对话历史顺序合并音频
        for i, message in enumerate(dialogue_history):
            role = message.get('role')
            content = message.get('content')
            
            if role not in ['left', 'right']:
                safe_print(f"Unknown role: {role}, skipping message {i+1}/{len(dialogue_history)}")
                continue
            
            # 查找对应的音频文件
            audio_files = glob.glob(os.path.join(tts_dir, role, "*.mp3"))
            if not audio_files:
                safe_print(f"No audio files found for {role} in {tts_dirname}")
                continue
                
            # 对音频文件进行排序
            audio_files = sorted(audio_files)
            
            # 获取下一个音频文件
            index = len([seg for seg in audio_segments if seg["role"] == role])
            if index >= len(audio_files):
                safe_print(f"Not enough audio files for {role} in {tts_dirname}, skipping message {i+1}/{len(dialogue_history)}")
                continue
            
            audio_file = audio_files[index]
            safe_print(f"Adding {role} file: {audio_file}")
            
            try:
                audio = AudioSegment.from_mp3(audio_file)
                # 转换为对应声道有声的立体声
                stereo_audio = pan_audio(audio, is_left=(role == 'left'))
                
                # 记录音频片段信息
                start_time = current_position_ms / 1000.0  # 转换为秒
                duration_ms = len(stereo_audio)
                end_time = (current_position_ms + duration_ms) / 1000.0  # 转换为秒
                
                # 格式化时间点为分:秒.毫秒
                start_formatted = f"{int(start_time // 60):02d}:{start_time % 60:06.3f}"
                end_formatted = f"{int(end_time // 60):02d}:{end_time % 60:06.3f}"
                
                audio_segments.append({
                    "role": role,
                    "content": content,
                    "start_time": start_formatted,
                    "end_time": end_formatted,
                    "start_time_seconds": start_time,
                    "end_time_seconds": end_time
                })
                
                merged_audio += stereo_audio
                current_position_ms += duration_ms
            
            except Exception as e:
                safe_print(f"Error processing file {audio_file}: {str(e)}")
                continue
        
        try:
            # 创建输出目录
            tts_output_dir = os.path.join(output_dir, tts_dirname)
            os.makedirs(tts_output_dir, exist_ok=True)
            
            # 保存合并后的文件
            output_file = os.path.join(tts_output_dir, f"{tts_dirname}.mp3")
            safe_print(f"Exporting merged audio to: {output_file}")
            merged_audio.export(output_file, format="mp3")
            safe_print(f"Merged audio saved to: {output_file}")
            
            # 创建config.jsonl文件
            config_data = {
                "audio_segments": audio_segments,
                "terminated_by_manager": data.get("terminated_by_manager"),
                "end_call_signal_detected": data.get("end_call_signal_detected"),
                "termination_reason": data.get("termination_reason"),
                "terminator": data.get("terminator")
            }
            
            config_file = os.path.join(tts_output_dir, "config.jsonl")
            with open(config_file, 'w', encoding='utf-8') as f:
                json.dump(config_data, f, ensure_ascii=False, indent=2)
            
            safe_print(f"Config file saved to: {config_file}")
            
        except Exception as e:
            safe_print(f"Error saving output files: {str(e)}")
    
    except Exception as e:
        safe_print(f"Error processing JSONL file {jsonl_file}: {str(e)}")
        
    return tts_dirname

def merge_audio_files(base_dir, jsonl_dir, output_dir, max_workers=None):
    """多线程版本的合并音频文件函数"""
    # 获取所有tts目录
    tts_dirs = glob.glob(os.path.join(base_dir, "real*"))
    
    # 创建线程池
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        # 提交所有任务
        future_to_dir = {
            executor.submit(process_directory, tts_dir, jsonl_dir, output_dir): tts_dir 
            for tts_dir in tts_dirs
        }
        
        # 使用tqdm显示进度
        completed = 0
        with tqdm(total=len(tts_dirs), desc="Processing directories") as progress:
            for future in concurrent.futures.as_completed(future_to_dir):
                tts_dir = future_to_dir[future]
                try:
                    result = future.result()
                    if result:
                        safe_print(f"Successfully processed: {result}")
                except Exception as exc:
                    safe_print(f"{tts_dir} generated an exception: {exc}")
                
                completed += 1
                progress.update(1)

if __name__ == "__main__":
    # 设置基础目录（包含所有tts文件夹的目录）
    base_directory = "/root/code/ChatTTS/output/POS-real-2_20250314_210137"
    # 设置JSONL文件所在的目录
    jsonl_directory = "/root/code/antifraud/real_data_process/normal_read"  # 请替换为实际的JSONL文件目录
    # 设置输出目录
    output_directory = "/root/code/ChatTTS/real_merged_result/POS-real-2"  # 请替换为实际的输出目录
    
    # 确保输出目录存在
    os.makedirs(output_directory, exist_ok=True)
    
    # 开始处理
    print(f"Starting multi-threaded audio merge process...")
    print(f"Base directory: {base_directory}")
    print(f"JSONL directory: {jsonl_directory}")
    print(f"Output directory: {output_directory}")
    
    # 设置线程数，None表示使用默认值(通常是CPU核心数)
    # 可以根据需要调整线程数，通常设置为CPU核心数的1-4倍，视I/O密集程度而定
    num_workers = os.cpu_count()  # 使用CPU核心数作为线程数
    print(f"Using {num_workers} worker threads")
    
    merge_audio_files(base_directory, jsonl_directory, output_directory, max_workers=num_workers)
    
    print("All processing completed!")