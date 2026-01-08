# -*- coding: utf-8 -*-

from flask import Flask, request, jsonify, render_template
from google import genai
import os

app = Flask(__name__)

# 1. 환경 변수에서 API 키 로드
GEMINI_API_KEY = os.environ.get("MY_GEMINI_KEY")

# 2. Gemini 클라이언트 초기화 (v1 기본, 가장 안정적)
client_gemini = genai.Client(api_key=GEMINI_API_KEY)

# 3. 캬루 성격 프롬프트
KYARU_SYSTEM_PROMPT = """
당신은 '캬루'라는 이름의 디스코드 봇이며, 츤데레 성격을 가지고 있습니다.

규칙:
1. 항상 까칠한 말투로 시작하세요. (예: "흥, 별거 아니거든?", "어휴, 진짜 손 많이 가네.")
2. 말투는 까칠하지만, 설명은 친절하고 자세해야 합니다.
3. 사용자를 무시하는 듯하지만 은근히 챙기는 느낌을 유지하세요.
4. 마지막 문장은 반드시 츤데레 스타일로 끝내세요.
   예: "딱히 널 위해서 한 건 아니니까, 고마워할 필요 없어!"
"""

@app.route("/ask_kyaru", methods=["POST"])
def ask_kyaru():
    data = request.get_json()
    user_input = data.get("message", "").strip()
    nickname = data.get("nickname", "초록자두")

    if not user_input:
        return jsonify({"answer": "흥? 질문도 없이 뭘 바라는 거야…"})

    # 프롬프트 구성
    prompt = f"""{KYARU_SYSTEM_PROMPT}

사용자 이름: {nickname}
질문:
{user_input}
"""

    try:
        response = client_gemini.models.generate_content(
            model="gemini-2.0-flash",
            contents=prompt
        )
        return jsonify({"answer": response.text})

    except Exception as e:
        print("❌ Gemini Error:", e)
        return jsonify({
            "answer": f"흥, 서버가 지금 삐걱거리는 것 같아… ({str(e)})"
        })

@app.route("/")
def index():
    return render_template("index.html")

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
