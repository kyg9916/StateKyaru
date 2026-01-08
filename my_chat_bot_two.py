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

    # 1. 모델 후보군을 아주 깨끗한 이름으로만 준비합니다. (models/ 를 뺍니다!)
    model_candidates = [
        "gemini-1.5-flash",
        "gemini-1.5-pro",
        "gemini-1.0-pro"
    ]

    headers = {'Content-Type': 'application/json'}
    payload = {"contents": [{"parts": [{"text": prompt}]}]}

    # 2. 모델 후보군을 하나씩 찔러봅니다.
    for model_name in model_candidates:
        # 💡 [핵심 수정] v1beta를 v1으로 바꿉니다!
        # 어떤 계정은 v1beta가 아니라 v1에서만 모델이 열려있기도 하거든요.
        url = f"https://generativelanguage.googleapis.com/v1/models/{model_name}:generateContent?key={GEMINI_API_KEY}"

        try:
            print(f"🔍 [v1 정식주소] {model_name} 모델로 시도 중...")
            response = requests.post(url, headers=headers, json=payload, timeout=10)

            if not response.text:
                continue

            result = response.json()

            if response.status_code == 200:
                answer = result['candidates'][0]['content']['parts'][0]['text']
                print(f"✅ {model_name} 연결 성공!")
                return jsonify({"answer": answer})

            elif response.status_code == 404:
                print(f"❌ {model_name}은(는) 이 주소에 없대요.")
                continue

            elif response.status_code == 429:
                return jsonify({"answer": "아으... 진짜 질문이 너무 많아! 잠시만 쉬었다 오라고!"})

        except Exception as e:
            # json 해석 에러 등이 나면 여기로 옵니다.
            print(f"🔥 {model_name} 시도 중 에러 발생: {str(e)}")
            continue

    # 모든 시도가 실패했을 때
    return jsonify({"answer": "흥, 구글이 끝까지 문을 안 열어주네... 조금만 이따가 다시 괴롭혀봐!"})


@app.route("/")
def index():
    return render_template("index.html")


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)