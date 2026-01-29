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
    
    # 2つのシートを取得
    worksheet_main = spreadsheet.worksheet("シート1")
    worksheet_wrong = spreadsheet.worksheet("復習")
    
    client = genai.Client(api_key=st.secrets["GEMINI_API_KEY"])
except Exception as e:
    st.error(f"接続エラー: {e}")
    st.stop()

st.title("🚒 消防昇任試験 AI対策アプリ")

tab1, tab2, tab3 = st.tabs(["🔥 テストを受ける", "🤖 AIで問題を作る", "📊 データベース"])

# --- タブ1: テストを受ける（復習モード搭載） ---
with tab1:
    mode = st.radio("出題モードを選択", ["通常モード", "復習モード（間違えた問題のみ）"], horizontal=True)
    
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
            options = str(q['選択肢']).split(',')
            
            with st.form("quiz_form"):
                user_choice = st.radio("答えを選んでください", options)
                submit = st.form_submit_button("回答する")
                
                if submit:
                    st.session_state.answered = True
                    correct_letter = str(q['正解']).strip()[0]
                    
                    if user_choice.startswith(correct_letter):
                        st.success("⭕ 正解！！")
                    else:
                        st.error(f"❌ 不正解... 正解は【{q['正解']}】でした。")
                        # 間違えた場合、復習シートに保存（重複チェック付き）
                        wrong_data = worksheet_wrong.get_all_records()
                        if not any(d['問題'] == q['問題'] for d in wrong_data):
                            worksheet_wrong.append_row([q['問題'], q['選択肢'], q['正解'], q['解説']])
                            st.warning("⚠️ この問題を「復習シート」に登録しました。")
                    st.info(f"💡 解説: {q['解説']}")
    else:
        st.info(f"{mode}のデータが空っぽです。")

# --- タブ2: AIで問題を作る（複数問題作成対応） ---
with tab2:
    st.header("PDF資料から問題を作成")
    uploaded_file = st.file_uploader("PDFファイルをアップロードしてください", type="pdf")
    
    if uploaded_file:
        with pdfplumber.open(uploaded_file) as pdf:
            text = "".join([page.extract_text() for page in pdf.pages if page.extract_text()])
        
        if text:
            st.success("📄 PDF読み込み完了")
            # 問題数を選択できるスライダーを追加
            num_q = st.slider("作成する問題数", 1, 5, 1)
            
            if st.button(f"AIで{num_q}問作成する"):
                with st.spinner("AIが試験問題を作成中..."):
                    prompt = f"消防試験の専門家として、資料から5択問題を{num_q}問作成し、必ず以下のJSON形式のリストのみで回答して。 [{{'問題':'','選択肢':'A,B,C,D,E','正解':'A','解説':''}}] 資料: {text[:3000]}"
                    try:
                        response = client.models.generate_content(model="gemini-2.5-flash", contents=prompt)
                        res_text = response.text.replace('```json', '').replace('```', '').strip()
                        new_problems = json.loads(res_text)
                        
                        for p in new_problems:
                            worksheet_main.append_row([p['問題'], p['選択肢'], p['正解'], p['解説']])
                        
                        st.success(f"✅ {len(new_problems)}問追加しました！")
                        st.balloons()
                    except Exception as e:
                        st.error(f"AIエラー: {e}")

# --- タブ3: データベース ---
with tab3:
    st.header("登録済みの全問題")
    st.subheader("メイン問題（シート1）")
    st.dataframe(pd.DataFrame(worksheet_main.get_all_records()))
    
    st.subheader("復習が必要な問題（復習シート）")
    wrong_df = pd.DataFrame(worksheet_wrong.get_all_records())
    st.dataframe(wrong_df)
    
    if st.button("復習リストを空にする"):
        worksheet_wrong.clear()
        worksheet_wrong.append_row(["問題", "選択肢", "正解", "解説"])
        st.rerun()