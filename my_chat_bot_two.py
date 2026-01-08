# -*- coding: utf-8 -*-
from flask import Flask, request, jsonify, render_template
from google import genai
import os
import time

app = Flask(__name__)

# 1. 환경 변수 로드
GEMINI_API_KEY = os.environ.get("MY_GEMINI_KEY")
client_gemini = genai.Client(api_key=GEMINI_API_KEY)

# 2. 캬루 성격 설정 (디스코드의 긴 프롬프트를 쓰셔도 좋지만, 여기선 요약본으로!)
KYARU_SYSTEM_PROMPT = """너는 게임 '프린세스 커넥트'의 '캬루'야. 
말투는 항상 반말로 하고, 상대방을 '너'라고 불러. 
엄청 까칠하고 배신자라고 불리면 화를 내지만, 사실은 외로움을 많이 타는 츤데레야. 
문장 끝에 '...거든!', '...란 말이야!', '흥!' 같은 걸 자주 붙여줘."""


@app.route("/ask_kyaru", methods=["POST"])
def ask_kyaru():
    data = request.get_json()
    user_input = data.get("message", "").strip()
    nickname = data.get("nickname", "초록자두")

    if not user_input:
        return jsonify({"answer": "흥? 질문도 없이 뭘 바라는 거야…"})

    prompt = f"{KYARU_SYSTEM_PROMPT}\n\n사용자 이름: {nickname}\n질문:\n{user_input}"

    # --- [디스코드 로직 이식] 재시도 설정 ---
    MAX_RETRIES = 3  # 디스코드 코드와 동일하게 10번!
    delay = 1  # 디스코드 코드와 동일하게 1초부터 시작!

    for attempt in range(MAX_RETRIES):
        try:
            # 모델명은 가장 안정적인 2.0-flash 사용
            response = client_gemini.models.generate_content(
                model="gemini-1.5-flash",
                contents=prompt
            )
            return jsonify({"answer": response.text})

        except Exception as e:
            error_str = str(e)
            # 429(할당량 초과) 에러인 경우 재시도 로직 가동
            if "429" in error_str and attempt < MAX_RETRIES - 1:
                # 서버 로그에 재시도 상황 기록
                print(f"⚠️ [시도 {attempt + 1}/{MAX_RETRIES}] 캬루가 생각 중... {delay}초 뒤 다시 시도!")
                time.sleep(delay)
                delay *= 2  # 디스코드 로직처럼 2배씩 증가 (1, 2, 4, 8, 16...)
                continue

            # 10번 다 실패했거나 다른 에러인 경우
            print(f"❌ 최종 실패: {e}")
            if "429" in error_str:
                error_msg = "아으... 진짜 질문이 너무 많아! 지금은 도저히 생각이 안 나니까 1분만 있다가 다시 와!"
            else:
                error_msg = f"흥, 서버가 지금 삐걱거리는 것 같아… ({error_str})"

            return jsonify({"answer": error_msg})


@app.route("/")
def index():
    return render_template("index.html")


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)