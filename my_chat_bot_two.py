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

    # 💡 [필살기] 구글이 좋아하는 모든 모델 이름을 리스트로 만듭니다.
    # v1과 v1beta 주소 모두에서 잘 작동하는 이름들입니다.
    model_candidates = [
        "gemini-1.5-flash",
        "gemini-1.5-pro",
        "gemini-1.0-pro",
        "models/gemini-1.5-flash",
        "models/gemini-1.5-pro",
        "models/gemini-1.0-pro"
    ]

    headers = {'Content-Type': 'application/json'}
    payload = {"contents": [{"parts": [{"text": prompt}]}]}

    # 모델 후보군을 하나씩 다 찔러봅니다!
    for model_name in model_candidates:
        # 주소를 v1beta로 고정해서 가장 넓은 범위를 탐색합니다.
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={GEMINI_API_KEY}"

        try:
            print(f"🔍 {model_name} 모델로 시도 중...")
            response = requests.post(url, headers=headers, json=payload, timeout=10)
            result = response.json()

            if response.status_code == 200:
                answer = result['candidates'][0]['content']['parts'][0]['text']
                print(f"✅ {model_name} 모델 연결 성공!")
                return jsonify({"answer": answer})

            # 만약 404 에러(못 찾음)라면 다음 모델 이름으로 넘어갑니다.
            elif response.status_code == 404:
                print(f"❌ {model_name}은(는) 없대요. 다음 모델로!")
                continue

            # 한도 초과(429) 시 잠시 대기
            elif response.status_code == 429:
                return jsonify({"answer": "아으... 진짜 질문이 너무 많아! 잠시만 쉬었다 오라고!"})

        except Exception as e:
            print(f"🔥 에러 발생: {str(e)}")
            continue

    # 모든 모델이 다 실패했을 때 (이럴 일은 거의 없습니다!)
    return jsonify({"answer": "흥, 구글이 문을 다 잠갔나 봐... 모델이 하나도 안 보여! 좀 이따 다시 해보자!"})

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