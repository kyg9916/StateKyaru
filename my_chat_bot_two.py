# -*- coding: utf-8 -*-
from flask import Flask, request, jsonify, render_template
from google import genai
from google.genai import types
import os

app = Flask(__name__)

# 1. 환경 변수에서 API 키 로드
GEMINI_API_KEY = os.environ.get('MY_GEMINI_KEY')

# 2. Gemini 클라이언트 초기화 (v1 정식 버전 주소로 강제 지정!)
# 이 설정이 404 v1beta 에러를 막아주는 핵심 열쇠입니다.
client_gemini = genai.Client(
    api_key=GEMINI_API_KEY,
    http_options={'api_version': 'v1'}
)

# 3. 캬루의 성격(시스템 프롬프트)
KYARU_SYSTEM_PROMPT = """
당신은 '캬루'라는 이름의 디스코드 봇이며, '츤데레' 성격을 가지고 있습니다. 아래 지침에 따라 대답하세요.
1. 기본 성격: 겉으로는 까칠하지만 속마음은 따뜻합니다.
2. 말투 스타일: "흥, 별거 아니거든?", "어휴, 정말 손이 많이 가네." 등으로 시작하세요.
3. 답변 내용: 말투는 까칠해도 내용은 아주 친절하고 상세해야 합니다.
4. 마무리 멘트: "딱히 널 위해서 한 건 아니니까 고마워할 필요 없어!"로 끝내세요.
"""

@app.route("/ask_kyaru", methods=["POST"])
def ask_kyaru():
    data = request.json
    user_input = data.get("message", "").strip()
    nickname = data.get("nickname", "초록자두")

    try:
        # 모델명은 가장 안정적인 gemini-1.5-flash를 사용합니다.
        response = client_gemini.models.generate_content(
            model="gemini-1.5-flash",
            contents=[f"사용자 {nickname}의 질문: {user_input}"],
            config=types.GenerateContentConfig(
                system_instruction=KYARU_SYSTEM_PROMPT
            )
        )
        return jsonify({"answer": response.text})

    except Exception as e:
        print(f"!!! 에러: {e}")
        # 에러 메시지를 캬루 말투로 출력합니다.
        return jsonify({"answer": f"흥, 서버가 아픈 이유는 이거야: {str(e)}"})

@app.route("/")
def index():
    return render_template("index.html")

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)