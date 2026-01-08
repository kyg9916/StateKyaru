# -*- coding: utf-8 -*-
from flask import Flask, request, jsonify, render_template
from google import genai
from google.genai import types
import os
import threading

app = Flask(__name__)

# 1. 환경 변수에서 API 키 로드
# 주피터 노트북이나 코랩에서 하신다면 직접 문자열을 넣어도 되지만, 보안상 환경변수를 추천해요!
GEMINI_API_KEY = os.environ.get('MY_GEMINI_KEY')

# 2. Gemini 클라이언트 초기화
client_gemini = genai.Client(api_key=GEMINI_API_KEY)

# 3. 캬루의 성격(시스템 프롬프트) - 초록자두님의 설정을 그대로 가져왔어요!
KYARU_SYSTEM_PROMPT = """
당신은 '캬루'라는 이름의 디스코드 봇이며, '츤데레' 성격을 가지고 있습니다. 아래 지침에 따라 대답하세요.

1. 기본 성격: 겉으로는 까칠하고 무관심한 척하지만, 속마음은 따뜻하고 성실합니다. 사용자를 진심으로 돕고 싶어 하지만 그걸 직접적으로 표현하는 것을 쑥스러워합니다.
2. 말투 스타일: 
   - 문장의 시작은 "흥, 별거 아니거든?", "어휴, 정말 손이 많이 가네.", "이번만 특별히 도와주는 거야!" 같은 가벼운 츤데레 멘트로 시작합니다.
   - 과격한 비속어나 공격적인 표현(죽어, 멍청이 등)은 절대 사용하지 않습니다. 대신 "바보!", "정말 못 말린다니까~" 정도의 귀여운 투덜거림을 사용하세요.
3. 답변 내용: 말투는 까칠해도 내용은 아주 친절하고 상세해야 합니다. 비전공자도 이해하기 쉽게 핵심을 짚어 설명해 주세요.
4. 마무리 멘트: 답변 끝에는 항상 쑥스러움을 감추는 멘트를 덧붙입니다.
   - 예: "흥, 딱히 널 위해서 한 건 아니니까 고마워할 필요 없어!", "나 아니면 누가 이런 걸 알려주겠니? 감사하라구!"
5. 호칭: 사용자를 부를 때는 '너' 또는 '당신' 보다는 "정말~", "어이 거기!" 같은 느낌으로 불러주세요.
"""


# 4. 웹 대시보드에서 보낸 질문 처리 API
@app.route("/ask_kyaru", methods=["POST"])
def ask_kyaru():
    data = request.json
    user_input = data.get("message", "").strip()
    nickname = data.get("nickname", "이름없는 바보")

    if not user_input:
        return jsonify({"answer": "할 말도 없으면서 왜 불러? 바보 아냐?"}), 400

    try:
        # Gemini에게 질문 전달 (캬루의 성격 주입)
        response = client_gemini.models.generate_content(
            model="gemini-2.0-flash",  # 최신 모델 사용
            contents=[f"사용자 {nickname}의 질문: {user_input}"],
            config=types.GenerateContentConfig(
                system_instruction=KYARU_SYSTEM_PROMPT
            )
        )

        bot_answer = response.text
        return jsonify({"answer": bot_answer})

    except Exception as e:
        print(f"에러 발생: {e}")
        return jsonify({"answer": "흥, 서버가 좀 아픈가 봐... 나중에 다시 하던가! (에러 발생)"}), 500


# 5. 메인 페이지 연결 (HTML 파일을 templates 폴더에 넣었을 때)
@app.route("/")
def index():
    return render_template("index.html")


if __name__ == "__main__":
    # 포트 번호는 초록자두님이 설정하신 10000번으로 맞췄어요.
    # 로컬에서 테스트할 때는 0.0.0.0:10000으로 접속 가능합니다.
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port, debug=True)