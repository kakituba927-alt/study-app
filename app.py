import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
import pandas as pd
import json
import pdfplumber
from google import genai
from PIL import Image # 画像処理用に追加
import re

# --- 1. 初期設定 ---
SCOPES = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']

try:
    creds_json_str = st.secrets["gcp_service_account"]
    creds_dict = json.loads(creds_json_str)
    creds = Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
    gc = gspread.authorize(creds)
    spreadsheet = gc.open("消防アプリDB")
    worksheet_main = spreadsheet.worksheet("シート1")
    worksheet_wrong = spreadsheet.worksheet("復習")
    client = genai.Client(api_key=st.secrets["GEMINI_API_KEY"])
except Exception as e:
    st.error(f"接続エラー: {e}")
    st.stop()

st.title("🚒 消防昇任試験 AI対策アプリ")
tab1, tab2, tab3 = st.tabs(["🔥 テストを受ける", "🤖 AIで問題を作る", "📊 データベース"])

# --- タブ1: テストを受ける ---
with tab1:
    mode = st.radio("出題モードを選択", ["通常モード", "復習モード"], horizontal=True)
    target_ws = worksheet_main if mode == "通常モード" else worksheet_wrong
    data = target_ws.get_all_records()

    if data:
        df = pd.DataFrame(data)
        if st.button("次の問題を表示"):
            st.session_state.q = df.sample(1).iloc[0]
            st.session_state.answered = False

        if "q" in st.session_state:
            q = st.session_state.q
            st.subheader(f"問題: {q['問題']}")
            opt_raw = str(q['選択肢'])
            if ',' in opt_raw:
                options = opt_raw.split(',')
            else:
                options = re.split(r'\s*(?=[A-E][.．])', opt_raw)
                options = [opt.strip() for opt in options if opt.strip()]

            with st.form("quiz_form"):
                user_choice = st.radio("答えを選んでください", options)
                submit = st.form_submit_button("回答する")
                if submit:
                    st.session_state.answered = True
                    correct_letter = str(q['正解']).strip()[0].upper()
                    if user_choice.strip().startswith(correct_letter):
                        st.success("⭕ 正解！！")
                    else:
                        st.error(f"❌ 不正解... 正解は【{q['正解']}】でした。")
                        wrong_data = worksheet_wrong.get_all_records()
                        if not any(d['問題'] == q['問題'] for d in wrong_data):
                            worksheet_wrong.append_row([q['問題'], opt_raw, q['正解'], q['解説']])
                    st.info(f"💡 解説: {q['解説']}")
    else:
        st.info(f"{mode}のデータがありません。")

# --- タブ2: AIで問題を作る（PDFと画像の両方に対応） ---
with tab2:
    st.header("資料から問題を作成")
    # jpg, png, jpeg を追加
    uploaded_file = st.file_uploader("PDFまたは写真(画像)をアップロードしてください", type=["pdf", "jpg", "png", "jpeg"])
    
    if uploaded_file:
        content_for_ai = []
        
        if uploaded_file.type == "application/pdf":
            # PDFの処理
            with pdfplumber.open(uploaded_file) as pdf:
                text = "".join([p.extract_text() for p in pdf.pages if p.extract_text()])
            content_for_ai.append(text)
            st.success("📄 PDFの文字読み込みに成功しました！")
        else:
            # 画像の処理
            img = Image.open(uploaded_file)
            content_for_ai.append(img)
            st.image(img, caption="アップロードされた写真", use_container_width=True)
            st.success("📸 写真の読み込みに成功しました！")
        
        num_q = st.slider("作成する問題数", 1, 5, 1)
        if st.button(f"AIで{num_q}問作成する"):
            with st.spinner("AIが資料を分析して問題を作成中..."):
                prompt = f"""
                あなたは消防試験の専門家です。提供された資料（テキストまたは画像）から重要度の高い5択問題を{num_q}問作成してください。
                【重要】選択肢は必ず「A:〇〇,B:〇〇,C:〇〇,D:〇〇,E:〇〇」のように、各項目をカンマ(,)で区切ってください。
                必ず以下のJSON形式のリストのみで回答してください。
                [
                  {{"問題": "問題文", "選択肢": "A:..,B:..,C:..,D:..,E:..", "正解": "A", "解説": "解説文"}}
                ]
                """
                try:
                    # AIにテキストまたは画像を渡す
                    response = client.models.generate_content(
                        model="gemini-2.5-flash",
                        contents=content_for_ai + [prompt]
                    )
                    res_text = response.text.replace('```json', '').replace('```', '').strip()
                    new_problems = json.loads(res_text)
                    for p in new_problems:
                        worksheet_main.append_row([p['問題'], p['選択肢'], p['正解'], p['解説']])
                    st.success(f"✅ {len(new_problems)}問の問題をデータベースに追加しました！")
                    st.balloons()
                except Exception as e:
                    st.error(f"AIエラーが発生しました。時間を置いてもう一度試してください。\n{e}")

# --- タブ3: データベース ---
with tab3:
    if st.button("メイン問題をリセット"):
        worksheet_main.clear()
        worksheet_main.append_row(["問題", "選択肢", "正解", "解説"])
        st.rerun()
    st.subheader("現在の問題リスト")
    st.dataframe(pd.DataFrame(worksheet_main.get_all_records()))