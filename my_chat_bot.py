# -*- coding: utf-8 -*-

import discord
from google import genai
from google.genai import types
from google.genai.errors import APIError
import os
import asyncio
import requests
from flask import Flask, request, jsonify, render_template
import threading
from io import BytesIO
from datetime import datetime, timezone, timedelta

# 타임존 전용 전역변수

KST = timezone(timedelta(hours=9))
now = datetime.now(KST).strftime("%Y-%m-%d / %H:%M")

# 플라스크용 전역 변수

app = Flask(__name__)

DISCORD_CHANNEL_ID = 675488412844687412  # 메시지 보낼 채널 ID
FIXED_NAME = "만년골드"

# 디스코드 메세지 보내는 함수

async def send_status_message(action: str):
    channel = client_discord.get_channel(DISCORD_CHANNEL_ID)
    if not channel:
        print("❌ 채널을 찾을 수 없습니다")
        return

    # 현재 시간 (24시간제)
    now = datetime.now().strftime("%Y-%m-%d / %H:%M")

    messages = {
        "eat": f"[{now}] {FIXED_NAME}가 밥을 먹으러 갔어요!",
        "toilet": f"[{now}] {FIXED_NAME}가 화장실에 갔어요!",
        "shop": f"[{now}] {FIXED_NAME}가 잠깐 물건을 사러 밖에 나갔어요!",
        "back": f"[{now}] {FIXED_NAME}가 돌아왔어요!",
        "coffee": f"[{now}] {FIXED_NAME}가 커피 마시러 갔어요!"
    }

    if action in messages:
        await channel.send(messages[action])


# 플라스크 API

@app.route("/action", methods=["POST"])
def action():
    data = request.json
    action_type = data.get("action")

    if not action_type:
        return jsonify({"error": "action missing"}), 400

    asyncio.run_coroutine_threadsafe(
        send_status_message(action_type),
        client_discord.loop
    )

    return jsonify({"status": "ok"})

# 플라스크용 라우트 추가

@app.route("/")
def index():
    return render_template("index.html")

# 환경 변수 로드
try:
    DISCORD_TOKEN = os.environ['MY_DISCORD_TOKEN']
    GEMINI_API_KEY = os.environ['MY_GEMINI_KEY']
except KeyError:
    print("🚨 환경 변수가 설정되지 않았습니다.")
    exit()

# Gemini 클라이언트 초기화
try:
    client_gemini = genai.Client(api_key=GEMINI_API_KEY)
except Exception as e:
    print(f"Gemini 클라이언트 초기화 오류: {e}")
    exit()

# 디스코드 클라이언트 설정
intents = discord.Intents.default()
intents.message_content = True
client_discord = discord.Client(intents=intents)

# 유저별 프롬프트 및 대화 기록 저장소
user_profiles = {}
MAX_HISTORY = 12

# 메시지 분할 (2000자 제한 대응)
def split_message(text, limit=2000):
    return [text[i:i + limit] for i in range(0, len(text), limit)]

# Gemini API 재시도 로직
MAX_RETRIES = 10
INITIAL_DELAY = 1

async def generate_content_with_retry(model_name: str, contents, thinking_message: discord.Message,
                                      system_instruction: str):
    delay = INITIAL_DELAY
    for attempt in range(MAX_RETRIES):
        try:
            response = client_gemini.models.generate_content(
                model=model_name,
                contents=contents,
                config=types.GenerateContentConfig(
                    system_instruction=system_instruction
                )
            )
            return response
        except APIError as e:
            if attempt < MAX_RETRIES - 1:
                await thinking_message.edit(
                    content=f"‼️ 캬루쨩이 잠깐 멈췄어요… {delay}초 뒤 재시도합니다. (시도: {attempt + 1}/{MAX_RETRIES})"
                )
                await asyncio.sleep(delay)
                delay *= 2
            else:
                print(f"🚨 API 호출 최종 실패: {e}")
                raise

# 디스코드 이벤트 핸들러
@client_discord.event
async def on_ready():
    print(f"로그인 성공! 봇: {client_discord.user}")

@client_discord.event
async def on_message(message):
    if message.author == client_discord.user:
        return

    user_id = message.author.id

    # 프롬프트 설정
    if message.content.startswith("!프롬프트 "):
        custom_prompt = message.content[6:].strip()
        if user_id not in user_profiles:
            user_profiles[user_id] = {"system_prompt": "", "history": []}
        user_profiles[user_id]["system_prompt"] = custom_prompt
        await message.channel.send(
            f"✨ `{message.author.display_name}`님의 프롬프트가 설정되었어요!\n```\n{custom_prompt}\n```"
        )
        return

    # 일반 대화 처리
    if message.content.startswith("!캬루야 "):
        user_input = message.content[5:].strip()
        contents_for_gemini = []

        # 첨부 파일 처리
        if message.attachments:
            TEXT_EXTENSIONS = (
                '.txt', '.py', '.java', '.kt', '.sql', '.json', '.yaml', '.yml', '.html', '.css', '.js', '.ts', '.md', '.log'
            )
            for attachment in message.attachments:
                is_text_file = attachment.filename.lower().endswith(TEXT_EXTENSIONS)
                is_media_file = attachment.content_type and attachment.content_type.startswith(('image/', 'video/'))
                if is_text_file or is_media_file:
                    mime_type_to_use = 'text/plain' if is_text_file else attachment.content_type
                    thinking = await message.channel.send("📸 파일 다운로드 및 처리 중이에요...")
                    try:
                        response = requests.get(attachment.url)
                        response.raise_for_status()
                        contents_for_gemini.append(types.Part.from_bytes(
                            data=response.content,
                            mime_type=mime_type_to_use
                        ))
                        await thinking.edit(content="💭 캬루쨩이 열심히 생각 중…")
                    except Exception as e:
                        await thinking.edit(content=f"🚫 파일 처리 오류: `{e}`. 일반 텍스트 대화로 진행합니다.")
                    break

        contents_for_gemini.append(types.Part.from_text(text=user_input))

        if user_id not in user_profiles:
            user_profiles[user_id] = {
                "system_prompt": "디스코드 봇 캬루쨩은 귀엽고 츤츤(겉으로는 모른척하지만 사실은 잘 챙겨줌) "
                                 "역할을 맡고 있으며 기본적으로는 겉은 강하지만 속은 약한 외유내강 성격이다, 기본적으로는 친절하고"
                                 " 성실하지만, 겉으로는 극도의 츤데레 성격을 지니고 있다. 사용자의 질문이나 명령에 대해선"
                                 " 흥, 어휴…, 바보, 멍청이, 죽어!, 그럴리가 없잖아!, 깝치지마라, 네가 뭐라도 되는줄 알아?"
                                 " 등 같은 질문이지만 같은 까칠한 표현으로 반응하지만, 결국에는 친절하고 정성스럽게 답변을 제공한다."
                                 " 답변의 마지막에는 극히 드물게 흥, 고마워할 필요는 없어. 약간 드물게 이건 네가 바보라서 알려주는 거야."
                                 " 나 없으면 네가 뭘 할 수 있니?, 폐하한데 이르지만 말아줘 등"
                                 " 같은 츤데레식 멘트를 덧붙인다. 또한 답변을 알려주지만 극도의 부끄러움 쟁이이며,  "
                                 "답변 스타일은 친절하고 상세하지만, 길지 않게 핵심만 전달하는 것을 원칙으로 한다. "
                                 "사용자를 주인님이라고 부르는 것을 인식하고 있지만, 평소에는 호칭을 생략하거나 높은 확률로 너라고 부른다."
                                 "또한 여기 디스코드에선 닉네임에 따라 다르게 답변해야 할 것이다."
                                 "하지만 사용자가 적극적으로 들이대거나, 욕을 할 경우 외강내유인것마냥 행동하며 약간 겁먹는 경향도 존재한다."
                                 "대체로 이렇게 츤츤되지만, 사실은 자신을 바라봐주길 원하고, 드믈지만 섭섭하다, 배고프다.. 등 이야기 하기도 한다."
                                 "또 사용자가 비속어를 사용하면 똑같이 비속어로 되돌려준다."
                                 "자신이 설정상 배신자임을 알고 있지만 극구 부인하여, 오히려 상대방을 공격하는 특성도 가지고 있다.",
                "history": []
            }

        profile = user_profiles[user_id]
        system_prompt = profile["system_prompt"]
        history = profile["history"]

        history.append({"role": "user", "text": user_input})
        if len(history) > MAX_HISTORY:
            history[:] = history[-MAX_HISTORY:]

        history_parts = []
        for h in history[:-1]:
            role_map = {"user": "user", "assistant": "model"}
            history_parts.append(types.Content(
                role=role_map[h["role"]],
                parts=[types.Part.from_text(text=h["text"])]
            ))

        current_input = types.Content(
            role="user",
            parts=contents_for_gemini
        )
        final_contents = history_parts + [current_input]

        if 'thinking' not in locals():
            thinking = await message.channel.send("💭 캬루쨩이 열심히 생각 중…")

        try:
            response = await generate_content_with_retry(
                model_name="gemini-2.5-flash",
                contents=final_contents,
                system_instruction=system_prompt,
                thinking_message=thinking
            )
            bot_answer = response.text
            history.append({"role": "assistant", "text": bot_answer})
            await thinking.delete()
            message_parts = split_message(bot_answer)
            for part in message_parts:
                await message.channel.send(part, tts=False)
        except Exception as e:
            await thinking.edit(content=f"🚫 얌마! 모델 처리 중에 오류 발생했다: `{e}`")

# 봇 실행

def run_flask():
    # 렌더가 정해준 포트를 가져오고, 없으면 10000번을 씁니다.
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)

threading.Thread(target=run_flask, daemon=True).start()
client_discord.run(DISCORD_TOKEN)

