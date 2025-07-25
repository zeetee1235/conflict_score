import sys
import os
sys.path.insert(0, os.path.dirname(__file__))
import time
import csv
import pandas as pd
import torch
import sentencepiece as spm
from transformers import AutoTokenizer, AutoModelForSequenceClassification, AutoModelForCausalLM
import json
import re
import random
import asyncio
import logging

from config import API_KEYS, MODEL_NAME, GENERATION_CONFIG, DEFAULT_BOT_SETTINGS
from database_manager import DatabaseManager
from bot import DcinsideBot
from dc_api_manager import DcApiManager

## 로깅 설정
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def setup_device():
    if torch.cuda.is_available():
        torch.cuda.empty_cache()
        torch.cuda.reset_peak_memory_stats()
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"[INFO] Using device: {device}")
    return device

device = setup_device()

def load_kobert(device):
    try:
        tokenizer = AutoTokenizer.from_pretrained("monologg/kobert", trust_remote_code=True)
    except ImportError as e:
        print(f"[ERROR] Missing dependency: {e}")
        print("Please install required packages:\n    pip install protobuf sentencepiece")
        raise
    model = AutoModelForSequenceClassification.from_pretrained("rkdaldus/ko-sent5-classification")
    model.to(device)
    labels = {0:"Angry",1:"Fear",2:"Happy",3:"Tender",4:"Sad"}
    return tokenizer, model, labels

koBERT_tokenizer, koBERT_model, emotion_labels = load_kobert(device)


def load_llama():
    model_id = 'Bllossom/llama-3.2-Korean-Bllossom-3B'
    tokenizer = AutoTokenizer.from_pretrained(model_id)
    tokenizer.pad_token = tokenizer.eos_token
    model = AutoModelForCausalLM.from_pretrained(
        model_id,
        torch_dtype=torch.bfloat16,
        device_map="auto",
    )
    model.config.pad_token_id = tokenizer.pad_token_id
    return tokenizer, model

LLM_tokenizer, LLM_model = load_llama()


def get_emotion(text: str) -> str:
    inputs = koBERT_tokenizer(text, return_tensors="pt", padding=True, truncation=True).to(device)
    with torch.no_grad():
        outputs = koBERT_model(**inputs)
    logits = outputs.logits
    # 긍정 감정 강화
    positive_biases = {2: 0.1, 3: 0.1}
    for pos_idx, bias in positive_biases.items():
        logits[:, pos_idx] += bias
    idx = torch.argmax(logits, dim=1).item()
    return emotion_labels[idx]


def parse_emotion() -> None:
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
            print(f"[DEBUG] Post {pid} emotion: {pe}")
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
        
        
def separate_subjects() -> None:
    base = os.path.dirname(__file__)
    contents_df = pd.read_csv(os.path.join(base, "resource/contents.csv"), encoding="utf8")
    reply_df = pd.read_csv(os.path.join(base, "resource/reply.csv"), encoding="utf8")
    
    all_subjects = []
    BATCH_SIZE = 10  # Process 10 posts at a time
    
    print(f"[INFO] Processing {len(contents_df)} posts in batches of {BATCH_SIZE} to separate subjects.")

    for i in range(0, len(contents_df), BATCH_SIZE):
        batch_df = contents_df.iloc[i:i+BATCH_SIZE]
        print(f"[INFO] Processing batch {i//BATCH_SIZE + 1}/{(len(contents_df) + BATCH_SIZE - 1)//BATCH_SIZE}")

        instruction = "다음은 여러 커뮤니티 게시글과 댓글 내용의 묶음이야. 각 게시글의 주제를 알려줘. 응답은 반드시 JSON 형식이어야 해. JSON 형식은 {\"subjects\": [\"주제1\", \"주제2\"]}와 같이 모든 주제를 하나의 리스트에 담아 응답해줘. 응답에는 JSON 외의 다른 내용이 포함되어서는 안 돼.\\n\\n"
        
        batch_full_text = ""
        for index, row in batch_df.iterrows():
            post_id = row['id']
            batch_full_text += f"--- 게시글 시작 (ID: {post_id}) ---\\n"
            batch_full_text += f"게시글: {row['contents']}\\n"
            
            replies = reply_df[reply_df['id'] == post_id]
            for r_index, r_row in replies.iterrows():
                batch_full_text += f"댓글: {r_row['reply_content']}\\n"
            batch_full_text += f"--- 게시글 끝 (ID: {post_id}) ---\\n\\n"

        instruction += batch_full_text

        messages = [{"role": "user", "content": instruction}]

        prompt_string = LLM_tokenizer.apply_chat_template(
            messages,
            tokenize=False,
            add_generation_prompt=True
        )
        inputs = LLM_tokenizer(
            prompt_string,
            return_tensors="pt",
            padding=True,
            truncation=True,
            max_length=4096,
            return_attention_mask=True
        )

        inputs_on_device = {k: v.to(LLM_model.device) for k, v in inputs.items()}

        terminators = [
            LLM_tokenizer.eos_token_id,
            LLM_tokenizer.convert_tokens_to_ids("<|eot_id|>")
        ]

        outputs = LLM_model.generate(
            **inputs_on_device,
            pad_token_id=LLM_tokenizer.pad_token_id,
            max_new_tokens=1024, # Increased tokens for batch summary
            eos_token_id=terminators,
            do_sample=True,
            temperature=0.6,
            top_p=0.9,
        )

        input_length = inputs_on_device['input_ids'].shape[1]
        raw = LLM_tokenizer.decode(outputs[0][input_length:], skip_special_tokens=True)
        
        print(f"[DEBUG] Raw output for batch starting at index {i}: {raw}")

        try:
            # More robust JSON extraction
            json_match = re.search(r'\{.*\}', raw, re.DOTALL)
            if json_match:
                json_str = json_match.group(0)
                parsed_json = json.loads(json_str)
                if 'subjects' in parsed_json and isinstance(parsed_json['subjects'], list):
                    all_subjects.extend(parsed_json['subjects'])
                else:
                    print(f"[WARNING] 'subjects' key not found or not a list in JSON for batch {i}")
            else:
                print(f"[ERROR] No JSON object found in the output for batch {i}: {raw}")
                
        except json.JSONDecodeError as e:
            print(f"[ERROR] Failed to parse JSON for batch {i}. Error: {e}. Raw output: {raw}")

    # Create a unique list of subjects
    unique_subjects = sorted(list(set(all_subjects)))
    
    # Save the final aggregated list to CSV
    output_path = os.path.join(base, "resource/subjects.csv")
    with open(output_path, "w", newline='', encoding="utf8") as f:
        writer = csv.writer(f)
        writer.writerow(["subject"])
        for subject in unique_subjects:
            writer.writerow([subject])
            
    print(f"[INFO] All batches processed. Unique subjects saved to {output_path}")


def generate_post(user_prompt: str) -> None:
    base = os.path.dirname(__file__)
    emotions_path = os.path.join(base, "resource/emotions.csv")
    
    if not os.path.exists(emotions_path):
        print("[ERROR] emotions.csv not found. Please run emotion analysis first.")
        return

    # Determine the dominant mood
    emotions_df = pd.read_csv(emotions_path)
    all_emotions = emotions_df['post_emotion'].tolist()
    for r_emotions in emotions_df['reply_emotions'].dropna():
        all_emotions.extend(r_emotions.split('|'))
    
    dominant_emotion = pd.Series(all_emotions).mode()[0]
    print(f"[INFO] Dominant mood of the community is '{dominant_emotion}'.")

    # Load existing posts and replies to provide as examples
    contents_df = pd.read_csv(os.path.join(base, "resource/contents.csv"), encoding="utf8")
    reply_df = pd.read_csv(os.path.join(base, "resource/reply.csv"), encoding="utf8")

    example_text = "다음은 이 커뮤니티의 실제 게시글과 댓글의 예시입니다. 이 스타일과 분위기를 참고하여 글을 작성해주세요.\\n\\n"
    
    # Sample 2 posts to use as few-shot examples
    num_samples = min(2, len(contents_df))
    if num_samples > 0:
        for i, (_, post) in enumerate(contents_df.sample(n=num_samples).iterrows(), 1):
            example_text += f"--- 예시 {i} ---\\n"
            example_text += f"게시글: {post['contents']}\\n"
            
            replies = reply_df[reply_df['id'] == post['id']]
            for r_idx, (_, reply) in enumerate(replies.iterrows(), 1):
                example_text += f"댓글 {r_idx}: {reply['reply_content']}\\n"
            example_text += f"--- 예시 끝 ---\\n\\n"

    # Create a prompt for the LLM
    num_replies = random.randint(1, 3)
    instruction = (
        f"당신은 온라인 커뮤니티의 분위기를 잘 파악하여 사람들을 {user_prompt}로 이끌어야 합니다. "
        f"이 커뮤니티의 전반적인 분위기는 '{dominant_emotion}'입니다. "
        f"{example_text}"
        f"이제, 이 분위기를 잘 살려서 다음 주제에 대한 새로운 게시글 1개와 그에 대한 댓글 {num_replies}개를 작성해주세요. "
        f"응답은 반드시 JSON 형식이어야 하며, 키는 'new_post'와 'new_replies' (댓글 {num_replies}개를 담은 리스트)를 포함해야 합니다.\\n\\n"
        f"주제: {user_prompt}"
    )

    messages = [{"role": "user", "content": instruction}]

    prompt_string = LLM_tokenizer.apply_chat_template(
        messages,
        tokenize=False,
        add_generation_prompt=True
    )
    inputs = LLM_tokenizer(
        prompt_string,
        return_tensors="pt",
        padding=True,
        truncation=True,
        max_length=4096,
        return_attention_mask=True
    )

    inputs_on_device = {k: v.to(LLM_model.device) for k, v in inputs.items()}

    terminators = [
        LLM_tokenizer.eos_token_id,
        LLM_tokenizer.convert_tokens_to_ids("<|eot_id|>")
    ]

    outputs = LLM_model.generate(
        **inputs_on_device,
        pad_token_id=LLM_tokenizer.pad_token_id,
        max_new_tokens=1024,
        eos_token_id=terminators,
        do_sample=True,
        temperature=0.7,
        top_p=0.9,
    )

    input_length = inputs_on_device['input_ids'].shape[1]
    raw = LLM_tokenizer.decode(outputs[0][input_length:], skip_special_tokens=True)
    
    print("\n--- 생성된 글 ---")
    try:
        json_match = re.search(r'\{.*\}', raw, re.DOTALL)
        if json_match:
            json_str = json_match.group(0)
            parsed_json = json.loads(json_str)
            
            if 'new_post' in parsed_json:
                print(f"게시글: {parsed_json['new_post']}\n")
            if 'new_replies' in parsed_json and isinstance(parsed_json['new_replies'], list):
                for i, reply in enumerate(parsed_json['new_replies'], 1):
                    print(f"댓글 {i}: {reply}")
        else:
            print("생성된 내용에서 JSON 형식을 찾지 못했습니다. 원본 응답:")
            print(raw)
            
    except json.JSONDecodeError:
        print("생성된 JSON을 파싱하는 데 실패했습니다. 원본 응답:")
        print(raw)
    print("----------------\n")

async def run_gallery_bot(api_key: str, bot_settings: dict) -> None:
    """
    갤러리 봇을 실행합니다.

    :param api_key: API 키
    :param bot_settings: 봇 설정
    """
    bot_settings.update({'api_key': api_key})

    # DcApiManager 객체 생성
    dc_api_manager = DcApiManager(
        board_id=bot_settings['board_id'],
        username=bot_settings['username'],
        password=bot_settings['password']
    )

    # DatabaseManager 객체 생성
    db_managers = {
        'crawling': DatabaseManager(f"data/{bot_settings['board_id']}_crawling.db", "crawling"),
        'data': DatabaseManager(f"data/{bot_settings['board_id']}_data.db", "data"),
        'memory': DatabaseManager(f"data/{bot_settings['board_id']}_memory.db", "memory"),
    }

    try:
        # 데이터베이스 연결
        await asyncio.gather(*[db_manager.connect() for db_manager in db_managers.values()])

        # GptApiManager 객체 생성 (로컬 Llama 모델 사용)
        # GptApiManager 객체 생성: 로컬 Llama 모델 사용
        

        # DcinsideBot 객체 생성
        bot = DcinsideBot(
            api_manager=dc_api_manager,
            db_managers=db_managers,
            
            persona=bot_settings['persona'],
            settings=bot_settings
        )

        await bot.get_trending_topics()
        await bot.record_gallery_information()

        start_time = time.time()

        async def article_task():
            while True:
                trending_topics = await bot.get_trending_topics()
                memory_data = await bot.memory_db.load_memory(bot.settings['board_id']) if bot.settings.get('load_memory_enabled', True) else ""
                await bot.write_article(trending_topics, memory_data)
                await asyncio.sleep(bot.settings['article_interval'])

        async def comment_task():
            while True:
                doc_info = await dc_api_manager.get_random_document_info()
                if doc_info:
                    doc_id, document_title = doc_info
                    await bot.write_comment(doc_id, document_title)
                else:
                    logging.error("문서 ID나 제목을 가져오지 못했습니다.")
                await asyncio.sleep(bot.settings['comment_interval'])

        await asyncio.gather(article_task(), comment_task())

        if bot.settings.get('use_time_limit', False) and (time.time() - start_time) > bot.settings['max_run_time']:
            return

    except Exception as e:
        logging.error(f"봇 실행 중 오류 발생: {e}")

    finally:
        await asyncio.gather(*[db_manager.close() for db_manager in db_managers.values()])
        await dc_api_manager.close()  # 세션 명시적으로 종료

async def main():
    if not API_KEYS:
        logging.error("API_KEYS가 .env 파일에 설정되지 않았습니다. 프로그램을 종료합니다.")
        return

    current_api_key_index = 0
    yjrs_bot = DEFAULT_BOT_SETTINGS.copy()
    yjrs_bot.update({'board_id': 'yjrs'})

    while True:
        current_api_key = API_KEYS[current_api_key_index]
        try:
            await run_gallery_bot(current_api_key, yjrs_bot)
        except Exception as e:
            logging.error(f"run_gallery_bot 오류: {e}")
        await asyncio.sleep(900)  # 15분 대기
        current_api_key_index = (current_api_key_index + 1) % len(API_KEYS)

def interactive_post_generation():
    print("\n[INFO] 지금부터 프롬프트를 입력하여 게시글 생성을 시작할 수 있습니다.")
    print("[INFO] 종료하려면 'exit' 또는 'quit'을 입력하세요.")
    while True:
        user_prompt = input("게시글 주제를 입력하세요 > ")
        if user_prompt.lower() in ['exit', 'quit']:
            print("프로그램을 종료합니다.")
            break
        if not user_prompt:
            continue
        generate_post(user_prompt)

if __name__ == "__main__":
    print("[INFO] 감정 분석을 시작합니다.")
    parse_emotion()
    print("[INFO] 감정 분석이 완료되었습니다.")
    time.sleep(1)
    print("[INFO] 주제 분리를 시작합니다.")
    separate_subjects()
    print("[INFO] 주제 분리가 완료되었습니다.")

    # 비동기 봇 실행 (원한다면 주석 해제)
    asyncio.run(main())

    # 인터랙티브 게시글 생성 루프
    interactive_post_generation()
    print("[INFO] 게시글 생성이 완료되었습니다. 프로그램을 종료합니다.")


