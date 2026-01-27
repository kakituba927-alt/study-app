import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
import pandas as pd
import json
import pdfplumber
from google import genai

# --- 1. 初期設定 ---
SCOPES = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']

try:
    creds_json_str = st.secrets["gcp_service_account"]
    creds_dict = json.loads(creds_json_str)
    creds = Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
    gc = gspread.authorize(creds)
    spreadsheet = gc.open("消防アプリDB")
    worksheet = spreadsheet.worksheet("シート1")
    client = genai.Client(api_key=st.secrets["GEMINI_API_KEY"])
except Exception as e:
    st.error(f"接続エラー: {e}")
    st.stop()

st.title("🚒 消防昇任試験 AI対策アプリ")

tab1, tab2, tab3 = st.tabs(["🔥 テストを受ける", "🤖 AIで問題を作る", "📊 データベース"])

# --- タブ1: テスト ---
with tab1:
    st.header("試験に挑戦")
    data = worksheet.get_all_records()
    if data:
        df = pd.DataFrame(data)
        # 必要な列がすべて揃っているか確認
        required_cols = ["問題", "選択肢", "正解", "解説"]
        if all(col in df.columns for col in required_cols):
            if st.button("次の問題を表示"):
                st.session_state.current_q = df.sample(1).iloc[0]
                st.session_state.answered = False

            if "current_q" in st.session_state:
                q = st.session_state.current_q
                st.subheader(f"問題: {q['問題']}")
                options = str(q['選択肢']).split(',')
                user_choice = st.radio("答えを選んでください", options, key="quiz_radio")
                
                if st.button("回答する"):
                    st.session_state.answered = True
                
                if st.session_state.get('answered'):
                    if user_choice == str(q['正解']):
                        st.success("⭕ 正解！")
                    else:
                        st.error(f"❌ 不正解... 正解は【{q['正解']}】でした。")
                    st.info(f"💡 解説: {q['解説']}")
        else:
            st.warning("スプレッドシートの1行目に『問題, 選択肢, 正解, 解説』という見出しが必要です。")
    else:
        st.info("まだ問題がありません。まずは『AIで問題を作る』から追加してください。")

# --- タブ2: 問題作成 ---
with tab2:
    st.header("PDF資料から問題を作成")
    uploaded_file = st.file_uploader("PDFファイルをアップロードしてください", type="pdf")
    if uploaded_file:
        with pdfplumber.open(uploaded_file) as pdf:
            text_list = [page.extract_text() for page in pdf.pages if page.extract_text()]
            full_text = "".join(text_list)
        
        if full_text:
            st.success("📄 PDF読み込み完了")
            if st.button("AIで1問作成する"):
                with st.spinner("AIが問題を作成中..."):
                    prompt = f"消防昇任試験の専門家として、資料から5択問題を1問作り、JSON形式 [{{'問題':'','選択肢':'A,B,C,D,E','正解':'A','解説':''}}] で回答して。資料: {full_text[:3000]}"
                    try:
                        response = client.models.generate_content(model="gemini-2.5-flash", contents=prompt)
                        res_text = response.text.replace('```json', '').replace('```', '').strip()
                        new_problems = json.loads(res_text)
                        for p in new_problems:
                            worksheet.append_row([p['問題'], p['選択肢'], p['正解'], p['解説']])
                        st.success("✅ 1問追加しました！「テストを受ける」タブを確認してください。")
                        st.balloons()
                    except Exception as e:
                        st.error(f"AIエラー: {e}")

# --- タブ3: データベース ---
with tab3:
    st.header("登録済みの全問題")
    all_data = worksheet.get_all_records()
    if all_data:
        st.dataframe(pd.DataFrame(all_data))
    if st.button("全データを削除"):
        worksheet.clear()
        worksheet.append_row(["問題", "選択肢", "正解", "解説"])
        st.rerun()