# TeleAntiFraud-28k

TeleAntiFraud-28k is the first open-source audio-text slow-thinking dataset specifically designed for automated telecom fraud analysis. This dataset integrates audio signals with reasoning-oriented textual analysis, providing high-quality multimodal training data for telecom fraud detection research.

## Dataset Overview

- **Total Samples**: 28,511 rigorously processed speech-text pairs
- **Total Audio Duration**: 307 hours
- **Unique Feature**: Detailed annotations for fraud reasoning
- **Task Categories**: Scenario classification, fraud detection, fraud type classification

## Dataset Construction Strategies

### 1. Privacy-preserved Text-Truth Sample Generation
- Using ASR-transcribed call recordings (with anonymized original audio)
- Ensuring real-world consistency through TTS model regeneration
- Strict adherence to privacy protection standards

### 2. Semantic Enhancement
- LLM-based self-instruction sampling on authentic ASR outputs
- Expanding scenario coverage to improve model generalization
- Enriching the diversity of conversational contexts

### 3. Multi-agent Adversarial Synthesis
- Simulation of emerging fraud tactics
- Generation through predefined communication scenarios and fraud typologies
- Enhancing dataset adaptability to new fraud techniques

## TeleAntiFraud-Bench

We have constructed TeleAntiFraud-Bench, a standardized evaluation benchmark comprising proportionally sampled instances from TeleAntiFraud-28k, to facilitate systematic testing of model performance and reasoning capabilities on telecom fraud detection tasks.

## Model Contribution

We contribute a production-optimized supervised fine-tuning (SFT) model based on Qwen2-Audio, trained on the TeleAntiFraud training set.

## Examples

Explore our dataset examples to better understand the telecom fraud detection capabilities:

- [Case 1: Normal Conversation Analysis](example/case1think.html) - Detailed analysis of a legitimate phone conversation
- [Case 2: Fraud Conversation Analysis](example/case2think.html) - Step-by-step reasoning for detecting a fraudulent call
- [Evaluation Sample](example/eval_sample.html) - Representative sample from our evaluation benchmark
- [Model Output: Normal Conversation](example/result1think.html) - Our model's reasoning process on a legitimate call
- [Model Output: Fraud Detection](example/result2think.html) - Model's analysis and detection of a fraudulent call

## Open-Source Resources

- TeleAntiFraud-28k dataset
- TeleAntiFraud-Bench evaluation benchmark
- Data processing framework (supporting community-driven dataset expansion)
- Qwen2-Audio-based SFT model

## Key Contributions

1. Establishing a foundational framework for multimodal anti-fraud research
2. Addressing critical challenges in data privacy and scenario diversity
3. Providing high-quality training data for telecom fraud detection
4. Open-sourcing data processing tools to enable community collaboration


## Citation

```
@inproceedings{Ma2025TeleAntiFraud28kAA,
  title={TeleAntiFraud-28k: An Audio-Text Slow-Thinking Dataset for Telecom Fraud Detection},
  author={Zhiming Ma and Peidong Wang and Minhua Huang and Jingpeng Wang and Kai Wu and Xiangzhao Lv and Yachun Pang and Yin Yang and Wenjie Tang and Yuchen Kang},
  year={2025},
  url={https://api.semanticscholar.org/CorpusID:277467703}
}
```

