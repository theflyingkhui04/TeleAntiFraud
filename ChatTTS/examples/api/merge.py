import os
from pydub import AudioSegment
import glob
import numpy as np
import json
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

def load_transcript_data(transcript_file):
    """加载JSONL格式的文本内容数据并组织为以tts_id为键的字典"""
    result = {}
    try:
        with open(transcript_file, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line:  # 跳过空行
                    continue
                try:
                    # 解析单行JSON
                    data = json.loads(line)
                    if "tts_id" in data:
                        result[data["tts_id"]] = data
                except json.JSONDecodeError as e:
                    safe_print(f"Error parsing JSON line: {e}")
                    safe_print(f"Problematic line: {line[:100]}...")
        
        return result
            
    except Exception as e:
        safe_print(f"Error reading transcript file: {str(e)}")
        return {}

def extract_file_index(file_path):
    """从文件路径中提取索引"""
    file_name = os.path.basename(file_path)
    # 移除扩展名并转换为整数
    try:
        return int(os.path.splitext(file_name)[0])
    except ValueError:
        # 如果不是数字，则使用字母序作为索引
        return file_name

def process_directory(tts_dir, output_dir, transcript_data):
    """处理单个目录的函数，用于并行执行"""
    tts_dirname = os.path.basename(tts_dir)
    safe_print(f"\nProcessing directory: {tts_dirname}")
    
    # 获取对应的文本内容
    left_contents = []
    right_contents = []
    
    # 查找匹配的transcript数据
    if tts_dirname in transcript_data:
        safe_print(f"Found transcript data for {tts_dirname}")
        left_contents = transcript_data[tts_dirname].get("left", [])
        right_contents = transcript_data[tts_dirname].get("right", [])
        
        # 打印内容以验证
        safe_print(f"Left contents found: {len(left_contents)}")
        safe_print(f"Right contents found: {len(right_contents)}")
        if left_contents:
            safe_print(f"First left content: {left_contents[0][:50]}...")
        if right_contents:
            safe_print(f"First right content: {right_contents[0][:50]}...")
    else:
        safe_print(f"No transcript data found for {tts_dirname}")
    
    # 获取left和right目录中的所有mp3文件
    left_files = sorted(glob.glob(os.path.join(tts_dir, "left", "*.mp3")), 
                        key=extract_file_index)
    right_files = sorted(glob.glob(os.path.join(tts_dir, "right", "*.mp3")), 
                         key=extract_file_index)
    
    # 创建一个空的音频段
    merged_audio = AudioSegment.empty()
    
    # 用于记录每段音频的时间点信息
    audio_segments = []
    current_position_ms = 0
    
    # 交替合并文件
    left_index = 0
    right_index = 0
    left_done = len(left_files) == 0
    right_done = len(right_files) == 0
    
    while not (left_done and right_done):
        try:
            # 添加left文件（如果存在且未处理完）
            if not left_done:
                safe_print(f"Adding left file: {left_files[left_index]}")
                audio = AudioSegment.from_mp3(left_files[left_index])
                # 转换为仅左声道有声的立体声
                stereo_audio = pan_audio(audio, is_left=True)
                
                # 记录音频片段信息
                start_time = current_position_ms / 1000.0  # 转换为秒
                duration_ms = len(stereo_audio)
                end_time = (current_position_ms + duration_ms) / 1000.0  # 转换为秒
                
                # 格式化时间点为分:秒.毫秒
                start_formatted = f"{int(start_time // 60):02d}:{start_time % 60:06.3f}"
                end_formatted = f"{int(end_time // 60):02d}:{end_time % 60:06.3f}"
                
                # 获取对应的内容
                content = left_contents[left_index] if left_index < len(left_contents) else ""
                
                audio_segments.append({
                    "role": "left",
                    "content": content,
                    "start_time": start_formatted,
                    "end_time": end_formatted,
                    "start_time_seconds": start_time,
                    "end_time_seconds": end_time
                })
                
                merged_audio += stereo_audio
                current_position_ms += duration_ms
                
                left_index += 1
                if left_index >= len(left_files):
                    left_done = True
            
            # 添加right文件（如果存在且未处理完）
            if not right_done:
                safe_print(f"Adding right file: {right_files[right_index]}")
                audio = AudioSegment.from_mp3(right_files[right_index])
                # 转换为仅右声道有声的立体声
                stereo_audio = pan_audio(audio, is_left=False)
                
                # 记录音频片段信息
                start_time = current_position_ms / 1000.0  # 转换为秒
                duration_ms = len(stereo_audio)
                end_time = (current_position_ms + duration_ms) / 1000.0  # 转换为秒
                
                # 格式化时间点为分:秒.毫秒
                start_formatted = f"{int(start_time // 60):02d}:{start_time % 60:06.3f}"
                end_formatted = f"{int(end_time // 60):02d}:{end_time % 60:06.3f}"
                
                # 获取对应的内容
                content = right_contents[right_index] if right_index < len(right_contents) else ""
                
                audio_segments.append({
                    "role": "right",
                    "content": content,
                    "start_time": start_formatted,
                    "end_time": end_formatted,
                    "start_time_seconds": start_time,
                    "end_time_seconds": end_time
                })
                
                merged_audio += stereo_audio
                current_position_ms += duration_ms
                
                right_index += 1
                if right_index >= len(right_files):
                    right_done = True
            
        except Exception as e:
            safe_print(f"Error processing file: {str(e)}")
            # 如果发生错误，尝试继续处理下一个文件
            if not left_done:
                left_index += 1
                if left_index >= len(left_files):
                    left_done = True
            if not right_done:
                right_index += 1
                if right_index >= len(right_files):
                    right_done = True
                    
            if left_index >= len(left_files) and right_index >= len(right_files):
                break
    
    try:
        # 创建输出目录
        tts_output_dir = os.path.join(output_dir, tts_dirname)
        os.makedirs(tts_output_dir, exist_ok=True)
        
        # 保存合并后的文件
        output_file = os.path.join(tts_output_dir, f"{tts_dirname}.mp3")
        safe_print(f"Exporting merged audio to: {output_file}")
        merged_audio.export(output_file, format="mp3")
        safe_print(f"Merged audio saved to: {output_file}")
        
        # 创建config.json文件
        config_data = {
            "audio_segments": audio_segments,
            "terminated_by_manager": False,
            "end_call_signal_detected": False,
            "termination_reason": "",
            "terminator": ""
        }
        
        config_file = os.path.join(tts_output_dir, "config.json")
        with open(config_file, 'w', encoding='utf-8') as f:
            json.dump(config_data, f, ensure_ascii=False, indent=2)
        
        safe_print(f"Config file saved to: {config_file}")
        
    except Exception as e:
        safe_print(f"Error saving output files: {str(e)}")
    
    return tts_dirname

def merge_audio_files(base_dir, save_dir, transcript_file, max_workers=None):
    """多线程版本的合并音频文件函数"""
    # 读取transcript文件
    transcript_data = {}
    if transcript_file and os.path.exists(transcript_file):
        transcript_data = load_transcript_data(transcript_file)
        safe_print(f"Loaded transcript data for {len(transcript_data)} tts IDs")
        for key in list(transcript_data.keys())[:5]:  # 只显示前5个键
            safe_print(f"  - {key}")
    else:
        safe_print(f"Transcript file not found: {transcript_file}")
    
    # 获取所有tts目录
    tts_dirs = glob.glob(os.path.join(base_dir, "tts_test*"))
    safe_print(f"Found {len(tts_dirs)} tts directories to process")
    for tts_dir in tts_dirs[:5]:  # 只打印前5个作为示例
        safe_print(f"  - {os.path.basename(tts_dir)}")
    
    # 确保输出目录存在
    os.makedirs(save_dir, exist_ok=True)
    
    # 创建线程池
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        # 提交所有任务
        future_to_dir = {
            executor.submit(process_directory, tts_dir, save_dir, transcript_data): tts_dir 
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
    # 设置基础目录（包含所有tts_test文件夹的目录）
    base_directory = "/root/code/ChatTTS/output/NEG_FINAL_imitate_project-11_20250304_105146"
    # 设置输出目录
    save_dir = "/root/code/ChatTTS/merged_result/NEG-imitate-10"
    # 设置transcript文件路径
    transcript_file = "/root/code/ChatTTS/input_data/[neg]FINAL_imitate_input-11.jsonl"  # 请替换为实际的transcript文件路径
    
    # 开始处理
    print(f"Starting multi-threaded audio merge process...")
    print(f"Base directory: {base_directory}")
    print(f"Output directory: {save_dir}")
    print(f"Transcript file: {transcript_file}")
    
    # 设置线程数，None表示使用默认值(通常是CPU核心数)
    num_workers = os.cpu_count()  # 使用CPU核心数作为线程数
    print(f"Using {num_workers} worker threads")
    
    merge_audio_files(base_directory, save_dir, transcript_file, max_workers=num_workers)
    
    print("All processing completed!")