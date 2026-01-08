# -*- coding: utf-8 -*-
from flask import Flask, request, jsonify, render_template
from google import genai
import os
import time  # 재시도 대기 시간을 위해 필요해요!

app = Flask(__name__)

# 1. 환경 변수 로드
GEMINI_API_KEY = os.environ.get("MY_GEMINI_KEY")
client_gemini = genai.Client(api_key=GEMINI_API_KEY)

# 2. 캬루 성격 설정
KYARU_SYSTEM_PROMPT = """
당신은 '캬루'라는 이름의 디스코드 봇이며, 츤데레 성격을 가지고 있습니다.
항상 까칠하게 시작해서 친절하게 설명하고, 마지막은 츤데레답게 마무리하세요.
"""


@app.route("/ask_kyaru", methods=["POST"])
def ask_kyaru():
    data = request.get_json()
    user_input = data.get("message", "").strip()
    nickname = data.get("nickname", "초록자두")

    if not user_input:
        return jsonify({"answer": "흥? 질문도 없이 뭘 바라는 거야…"})

    prompt = f"{KYARU_SYSTEM_PROMPT}\n\n사용자 이름: {nickname}\n질문:\n{user_input}"

    # --- 재시도 로직 시작 ---
    MAX_RETRIES = 5  # 최대 5번 재시도
    delay = 1  # 초기 대기 시간 (1초)

    for attempt in range(MAX_RETRIES):
        try:
            response = client_gemini.models.generate_content(
                model="gemini-2.0-flash",
                contents=prompt
            )
            # 성공하면 바로 답변 반환!
            return jsonify({"answer": response.text})

        except Exception as e:
            error_str = str(e)
            # 429 에러이고, 아직 재시도 횟수가 남았다면?
            if "429" in error_str and attempt < MAX_RETRIES - 1:
                print(f"⚠️ [재시도 {attempt + 1}] 할당량 초과! {delay}초 후 다시 시도합니다...")
                time.sleep(delay)  # 대기
                delay *= 2  # 대기 시간을 2배로 늘림 (지수 백오프)
                continue  # 다음 루프로 이동 (재시도)

            # 그 외의 에러이거나 재시도를 다 썼다면?
            print(f"❌ 최종 에러 발생: {e}")
            if "429" in error_str:
                error_msg = "아으... 진짜 질문이 너무 많아! 지금은 도저히 생각이 안 나니까 1분만 있다가 다시 와!"
            else:
                error_msg = f"흥, 서버가 지금 삐걱거리는 것 같아… ({error_str})"

            return jsonify({"answer": error_msg})
    # --- 재시도 로직 끝 ---


@app.route("/")
def index():
    return render_template("index.html")


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)