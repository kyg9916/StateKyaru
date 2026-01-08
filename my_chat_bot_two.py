# -*- coding: utf-8 -*-
from flask import Flask, request, jsonify, render_template
import os
import time
import requests  # 👈 라이브러리 대신 직접 통신하기 위해 필요해요!

app = Flask(__name__)

# 1. 환경 변수 로드
GEMINI_API_KEY = os.environ.get("MY_GEMINI_KEY")

# 2. 캬루 성격 설정
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

    prompt = f"{KYARU_SYSTEM_PROMPT}\n\n사용자 이름: {nickname}\n질문: {user_input}"

    url = f"https://generativelanguage.googleapis.com/v1/models/gemini-1.0-pro:generateContent?key={GEMINI_API_KEY}"

    headers = {'Content-Type': 'application/json'}
    payload = {
        "contents": [{
            "parts": [{"text": prompt}]
        }]
    }

    MAX_RETRIES = 3
    delay = 1

    for attempt in range(MAX_RETRIES):
        try:
            # 구글 서버에 직접 포스트(POST)를 보냅니다.
            response = requests.post(url, headers=headers, json=payload)
            result = response.json()

            # 성공적으로 답변을 가져왔을 때
            if response.status_code == 200:
                answer = result['candidates'][0]['content']['parts'][0]['text']
                return jsonify({"answer": answer})

            # 429 에러(한도 초과) 처리
            elif response.status_code == 429:
                if attempt < MAX_RETRIES - 1:
                    print(f"⚠️ 한도 초과! {delay}초 뒤 다시 시도...")
                    time.sleep(delay)
                    delay *= 2
                    continue
                return jsonify({"answer": "아으... 진짜 질문이 너무 많아! 1분만 있다가 다시 와!"})

            # 그 외 에러
            else:
                error_msg = result.get('error', {}).get('message', '알 수 없는 에러')
                return jsonify({"answer": f"흥, 서버가 삐걱거려! ({error_msg})"})

        except Exception as e:
            print(f"❌ 오류 발생: {str(e)}")
            return jsonify({"answer": f"흥, 연결이 안 되잖아! ({str(e)})"})


@app.route("/")
def index():
    return render_template("index.html")


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)