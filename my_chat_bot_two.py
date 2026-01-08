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

app.route("/ask_kyaru", methods=["POST"])


def ask_kyaru():
    data = request.get_json()
    user_input = data.get("message", "").strip()
    nickname = data.get("nickname", "초록자두")

    if not user_input:
        return jsonify({"answer": "흥? 질문도 없이 뭘 바라는 거야…"})

    prompt = f"{KYARU_SYSTEM_PROMPT}\n\n사용자 이름: {nickname}\n질문:\n{user_input}"

    MAX_RETRIES = 3
    delay = 1

    for attempt in range(MAX_RETRIES):
        try:
            # 2.5-flash 모델 호출
            response = client_gemini.models.generate_content(
                model="gemini-2.5-flash",
                contents=prompt
            )
            return jsonify({"answer": response.text})

        except Exception as e:
            error_str = str(e)

            # --- [에러별 캬루의 맞춤 메시지] ---
            # 1. 할당량 초과 (토큰 다 씀 / 429 에러)
            if "429" in error_str:
                if attempt < MAX_RETRIES - 1:
                    time.sleep(delay)
                    delay *= 2
                    continue
                return jsonify({"answer": "아으... 너 오늘 질문 너무 많이 하는 거 아냐? 내 머릿속이 꽉 찼단 말이야! 1분만 쉬었다가 다시 물어보러 오라고! 흥! 만약에 이게 반복되면 내일해봐! 오늘 할당량 다 채웠으니까!"})

            # 2. 서버 과부하 (오버로드 / 503 혹은 426 에러)
            elif "503" in error_str or "overloaded" in error_str.lower():
                return jsonify({"answer": "지금 서버가 삐걱거리고 있어! 나도 지금 정신이 하나도 없거든? 조금만 이따가 다시 불러줘!"})

            # 3. 그 외 기타 에러
            print(f"❌ 오류 발생: {error_str}")
            return jsonify({"answer": f"흥, 서버가 삐걱거리는 것 같아... 대체 뭘 건드린 거야? ({error_str})"})


@app.route("/")
def index():
    return render_template("index.html")


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)