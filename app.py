import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
import pandas as pd
import json
import pdfplumber
from google import genai

# --- 1. 初期設定 ---
try:
    creds_dict = json.loads(st.secrets["gcp_service_account"])
    creds = Credentials.from_service_account_info(creds_dict, scopes=['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive'])
    gc = gspread.authorize(creds)
    worksheet = gc.open("消防アプリDB").worksheet("シート1")
    client = genai.Client(api_key=st.secrets["GEMINI_API_KEY"])
except Exception as e:
    st.error(f"接続エラー: {e}")
    st.stop()

st.title("🚒 消防昇任試験 AI対策アプリ")
tab1, tab2, tab3 = st.tabs(["🔥 テスト", "🤖 問題作成", "📊 データベース"])

# --- タブ1: テスト (不具合修正版) ---
with tab1:
    data = worksheet.get_all_records()
    if data:
        # 「次の問題を表示」ボタン
        if st.button("次の問題を表示"):
            st.session_state.q = pd.DataFrame(data).sample(1).iloc[0]
            st.session_state.answered = False # 回答状態をリセット

        # 問題が選択されている場合の表示
        if "q" in st.session_state:
            q = st.session_state.q
            st.subheader(f"問題: {q['問題']}")
            
            # 選択肢を分割して表示
            options = str(q['選択肢']).split(',')
            
            # 回答フォーム
            with st.form("quiz_form"):
                user_choice = st.radio("答えを選んでください", options)
                submit = st.form_submit_button("回答する")
                
                if submit:
                    st.session_state.answered = True
                    # 判定ロジック：ユーザーの選択肢の「1文字目」とAIの「正解」が一致するか確認
                    correct_letter = str(q['正解']).strip()[0] # "A" などを取得
                    if user_choice.startswith(correct_letter):
                        st.success("⭕ 正解！！")
                    else:
                        st.error(f"❌ 不正解... 正解は【{q['正解']}】でした。")
                    st.info(f"💡 解説: {q['解説']}")
    else:
        st.info("まだ問題がありません。「問題作成」タブでPDFから作成してください。")

# --- タブ2: 問題作成 (現状維持) ---
with tab2:
    f = st.file_uploader("資料(PDF)をアップロード", type="pdf")
    if f:
        with pdfplumber.open(f) as pdf:
            text = "".join([p.extract_text() for p in pdf.pages if p.extract_text()])
        if text:
            st.success("PDF読み込み完了！")
            if st.button("AIで問題を1問作成"):
                with st.spinner("AIが問題を作成中..."):
                    prompt = f"消防試験の専門家として資料から5択問題を1問作り、JSON形式 [{{'問題':'','選択肢':'A,B,C,D,E','正解':'A','解説':''}}] で回答して。資料: {text[:2500]}"
                    try:
                        response = client.models.generate_content(model="gemini-2.5-flash", contents=prompt)
                        res_text = response.text.replace('```json', '').replace('```', '').strip()
                        item = json.loads(res_text)[0]
                        worksheet.append_row([item['問題'], item['選択肢'], item['正解'], item['解説']])
                        st.success("✅ 成功！「テスト」タブを確認してください。")
                        st.balloons()
                    except Exception as e:
                        st.error(f"AIエラー: {e}")

# --- タブ3: データベース (現状維持) ---
with tab3:
    all_d = worksheet.get_all_records()
    if all_d:
        st.dataframe(pd.DataFrame(all_d))
    if st.button("全データを削除"):
        worksheet.clear()
        worksheet.append_row(["問題", "選択肢", "正解", "解説"])
        st.success("リセットしました。")
        st.rerun()