import os
import time
import csv
import pandas as pd
import torch
import sentencepiece as spm
from transformers import AutoTokenizer, AutoModelForSequenceClassification, AutoModelForCausalLM
import json

# GPU 메모리 초기화
torch.cuda.empty_cache()
torch.cuda.reset_peak_memory_stats()


# KoBERT 토크나이저와 모델 로드
try:
    koBERT_tokenizer = AutoTokenizer.from_pretrained("monologg/kobert", trust_remote_code=True)
except ImportError as e:
    print(f"[ERROR] Missing dependency: {e}")
    print("Please install required packages:\n    pip install protobuf sentencepiece")
    raise
koBERT_model = AutoModelForSequenceClassification.from_pretrained("rkdaldus/ko-sent5-classification")
emotion_labels = {0:"Angry",1:"Fear",2:"Happy",3:"Tender",4:"Sad"}


# Llama 3.2 Korean 모델 로드
LLM_model_id = 'Bllossom/llama-3.2-Korean-Bllossom-3B'

LLM_tokenizer = AutoTokenizer.from_pretrained(LLM_model_id)
LLM_model = AutoModelForCausalLM.from_pretrained(
    LLM_model_id,
    torch_dtype=torch.bfloat16,
    device_map="auto",
)


def get_emotion(text):
    inputs = koBERT_tokenizer(text, return_tensors="pt", padding=True, truncation=True)
    with torch.no_grad():
        outputs = koBERT_model(**inputs)
    logits = outputs.logits
    # 가중치 조정을 통해 긍정적인 감정("Happy": index 2, "Tender": index 3) 강화
    positive_biases = {2: 0.2, 3: 0.1}
    for pos_idx, bias in positive_biases.items():
        logits[:, pos_idx] += bias
    idx = torch.argmax(logits, dim=1).item()
    return emotion_labels[idx]


def parse_emotion():
    base = os.path.dirname(__file__)
    contents_df = pd.read_csv(os.path.join(base, "resource/contents.csv"), encoding="utf8")
    replies_df  = pd.read_csv(os.path.join(base, "resource/reply.csv"),    encoding="utf8")

    # Initialize emotion counter
    emotion_counter = {label: 0 for label in emotion_labels.values()}
    
    out_path = os.path.join(base, "resource/emotions.csv")
    with open(out_path, "w", newline='', encoding="utf8") as fw:
        writer = csv.writer(fw)
        writer.writerow(["post_id","post_emotion","reply_emotions"])
        for _, post in contents_df.iterrows():
            pid = post["id"]
            print(f"[DEBUG] Processing post {pid}")
            pe = get_emotion(post["contents"])
            emotion_counter[pe] += 1
            print(f"[DEBU    from transformers import AutoTokenizer, AutoModelForCausalLMG] Post {pid} emotion: {pe}")
            reps = replies_df[replies_df["id"]==pid]["reply_content"].tolist()
            re_emotions = [get_emotion(r) for r in reps]
            for emo in re_emotions:
                emotion_counter[emo] += 1
            for idx, emo in enumerate(re_emotions, 1):
                print(f"[DEBUG] Reply {idx}/{len(re_emotions)} for post {pid}: {emo}")
            writer.writerow([pid, pe, "|".join(re_emotions)])
    print(f"Saved emotions to {out_path}")
    # Print overall emotion counts
    print("Emotion counts:")
    for emotion, count in emotion_counter.items():
        print(f"{emotion}: {count}")
        
        
def separate_subjects():
    outputs = LLM_model.generate(input_ids, batch_size=1)

    base = os.path.dirname(__file__)
    contents_df = pd.read_csv(os.path.join(base, "resource/contents.csv"), encoding="utf8")
    # posts 데이터를 문자열로 모아 LLM에 전달
    post_texts = "\n".join(f"{row['id']} : {row['contents']}" for _, row in contents_df.iterrows())
    instruction = (
        "주어진 게시글들에서 주제를 분리하고, "
        "같거나 비슷한 주제는 하나로 묶어 아래 형식으로 출력하세요:\n"
        "주제: 게시글ID,게시글ID,...\n"
        "게시글 목록:\n" + post_texts
    )
    messages = [{"role": "user", "content": instruction}]

    input_ids = LLM_tokenizer.apply_chat_template(
        messages,
        add_generation_prompt=True,
        return_tensors="pt"
    ).to(LLM_model.device)

    terminators = [
        LLM_tokenizer.convert_tokens_to_ids("<|end_of_text|>"),
        LLM_tokenizer.convert_tokens_to_ids("<|eot_id|>")
    ]

    outputs = LLM_model.generate(
        input_ids,
        max_new_tokens=1024,
        eos_token_id=terminators,
        do_sample=True,
        temperature=0.6,
        top_p=0.9
    )

    raw = LLM_tokenizer.decode(
        outputs[0][input_ids.shape[-1]:], skip_special_tokens=True
    )
    # 파싱하여 dict 생성
    subjects = {}
    for line in raw.splitlines():
        if ":" in line:
            topic, ids = line.split(":", 1)
            subjects[topic.strip()] = [pid.strip() for pid in ids.split(",") if pid.strip()]
    # JSON 파일로 저장
    subj_path = os.path.join(base, "resource/subjects.json")
    with open(subj_path, "w", encoding="utf8") as f:
        json.dump(subjects, f, ensure_ascii=False, indent=2)
    print(f"[INFO] Subjects saved to {subj_path}")


if __name__ == "__main__":
    print("[INFO] 감정 분석을 시작합니다.")
    parse_emotion()
    print("[INFO] 감정 분석이 완료되었습니다.")
    time.sleep(1)  # 잠시 대기
    print("[INFO] 주제 분리를 시작합니다.")
    separate_subjects()
    print("[INFO] 주제 분리가 완료되었습니다.")


