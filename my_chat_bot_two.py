# -*- coding: utf-8 -*-
from flask import Flask, request, jsonify, render_template
from google import genai
import os

app = Flask(__name__)

# 1. 환경 변수에서 API 키 로드
GEMINI_API_KEY = os.environ.get("MY_GEMINI_KEY")

# 2. 클라이언트 초기화 (가장 심플하게!)
client_gemini = genai.Client(api_key=GEMINI_API_KEY)

# 3. 캬루 성격 설정
KYARU_SYSTEM_PROMPT = """
당신은 '캬루'라는 이름의 디스코드 봇이며, '츤데레' 성격을 가지고 있습니다. 아래 지침에 따라 대답하세요.
1. 기본 성격: 겉으로는 까칠하지만 속마음은 따뜻합니다.
2. 말투 스타일: "흥, 별거 아니거든?", "어휴, 정말 손이 많이 가네." 등으로 시작하세요.
3. 답변 내용: 말투는 까칠해도 내용은 아주 친절하고 상세해야 합니다.
4. 마무리 멘트: 예를들어, "딱히 널 위해서 한 건 아니니까, 고마워할 필요 없어!" 등 까칠한 성격으로 생성하여 끝내세요.
"""

@app.route("/ask_kyaru", methods=["POST"])
def ask_kyaru():
    data = request.json
    user_input = data.get("message", "").strip()
    nickname = data.get("nickname", "초록자두")

    # 프롬프트 구성
    prompt = f"{KYARU_SYSTEM_PROMPT}\n\n사용자 {nickname}의 질문:\n{user_input}"

    try:
        # 모델 호출 (안 되면 모델명 앞에 models/ 를 붙여보세요!)
        response = client_gemini.models.generate_content(
            model="gemini-1.5-flash",
            contents=prompt
        )
        return jsonify({"answer": response.text})
    except Exception as e:
        print(f"!!! 에러 발생: {e}")
        return jsonify({"answer": f"흥, 서버가 맛이 갔네… ({str(e)})"})

@app.route("/")
def index():
    return render_template("index.html")

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)