import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
import pandas as pd
import json
import pdfplumber
from google import genai
from PIL import Image
import re

# --- 1. 初期設定（スプレッドシート & Gemini） ---
SCOPES = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']

try:
    creds_json_str = st.secrets["gcp_service_account"]
    creds_dict = json.loads(creds_json_str)
    creds = Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
    gc = gspread.authorize(creds)
    spreadsheet = gc.open("消防アプリDB")
    
    # シートの取得
    worksheet_main = spreadsheet.worksheet("シート1")
    worksheet_wrong = spreadsheet.worksheet("復習")
    
    # Gemini認証
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
        
        # ジャンル絞り込み機能
        if "ジャンル" in df.columns:
            genre_list = [g for g in df["ジャンル"].unique() if g]
            genres = ["すべて"] + sorted(list(set(genre_list)))
            selected_genre = st.selectbox("ジャンルで絞り込む", genres)
            if selected_genre != "すべて":
                df = df[df["ジャンル"] == selected_genre]
        
        if not df.empty:
            if st.button("次の問題を表示"):
                st.session_state.q = df.sample(1).iloc[0]
                st.session_state.answered = False

            if "q" in st.session_state:
                q = st.session_state.q
                st.info(f"分野: {q.get('ジャンル', '未設定')}")
                st.markdown(f"### **問題**\n{q['問題']}")
                
                opt_raw = str(q['選択肢'])
                if ',' in opt_raw:
                    options = opt_raw.split(',')
                else:
                    options = re.split(r'\s*(?=[A-E][.．:])', opt_raw)
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
                            if mode == "通常モード":
                                wrong_data = worksheet_wrong.get_all_records()
                                if not any(d['問題'] == q['問題'] for d in wrong_data):
                                    # 復習シートにも5項目で保存
                                    worksheet_wrong.append_row([q['問題'], opt_raw, q['正解'], q['解説'], q.get('ジャンル', '')])
                                    st.warning("⚠️ 復習シートに自動登録しました。")
                        st.info(f"💡 解説:\n{q['解説']}")
    else:
        st.info(f"{mode}のデータがありません。")

# --- タブ2: AIで問題を作る ---
with tab2:
    st.header("資料から問題を作成")
    problem_type = st.selectbox("作成する問題の形式", ["条文の虫食い（穴埋め）", "普通の実務・理論問題"])
    uploaded_file = st.file_uploader("PDFまたは写真をアップロード", type=["pdf", "jpg", "png", "jpeg"])
    
    if uploaded_file:
        content_for_ai = []
        if uploaded_file.type == "application/pdf":
            with pdfplumber.open(uploaded_file) as pdf:
                text = "".join([p.extract_text() for p in pdf.pages if p.extract_text()])
            content_for_ai.append(text)
        else:
            img = Image.open(uploaded_file)
            content_for_ai.append(img)
            st.image(img, caption="アップロード画像", use_container_width=True)
        
        num_q = st.slider("作成する問題数", 1, 5, 1)
        if st.button(f"AIで{num_q}問作成する"):
            with st.spinner("AIが試験問題を作成中..."):
                type_instr = "条文の重要な用語を（ ）にした穴埋め問題" if problem_type == "条文の虫食い（穴埋め）" else "実務に基づいた5択の知識問題"
                prompt = f"""
                あなたは消防試験の専門家です。資料から、重要度の高い{type_instr}を{num_q}問作成してください。
                【ルール】
                1. 選択肢は「A:〇〇,B:〇〇,C:〇〇,D:〇〇,E:〇〇」のようにカンマで区切る。
                2. 正解は「A」のようにアルファベット1文字で指定。
                3. 解説には根拠となる条文等を記載。
                4. ジャンルを「消防法」「救急」「憲法」「火災防ぎょ」「消防組織法」「時事」などから1つ選び、必ず付与。
                回答は必ず以下のJSON形式のリストのみで返す。
                [
                  {{"問題": "...", "選択肢": "...", "正解": "A", "解説": "...", "ジャンル": "..."}}
                ]
                """
                try:
                    response = client.models.generate_content(model="gemini-2.5-flash", contents=content_for_ai + [prompt])
                    res_text = response.text.replace('```json', '').replace('```', '').strip()
                    new_problems = json.loads(res_text)
                    for p in new_problems:
                        # 5項目を保存
                        worksheet_main.append_row([p['問題'], p['選択肢'], p['正解'], p['解説'], p.get('ジャンル', '未分類')])
                    st.success(f"✅ {len(new_problems)}問追加しました！")
                    st.balloons()
                except Exception as e:
                    st.error(f"AIエラー: {e}")

# --- タブ3: データベース ---
with tab3:
    st.header("登録済みの全問題")
    
    col1, col2 = st.columns(2)
    with col1:
        if st.button("メイン問題をリセット"):
            worksheet_main.clear()
            # ★ここで「ジャンル」を含めて見出しを再作成します★
            worksheet_main.append_row(["問題", "選択肢", "正解", "解説", "ジャンル"])
            st.rerun()
    with col2:
        if st.button("復習リストを空にする"):
            worksheet_wrong.clear()
            # ★ここも「ジャンル」を含めます★
            worksheet_wrong.append_row(["問題", "選択肢", "正解", "解説", "ジャンル"])
            st.rerun()

    st.subheader("メイン問題リスト")
    data_main = worksheet_main.get_all_records()
    if data_main:
        st.dataframe(pd.DataFrame(data_main))