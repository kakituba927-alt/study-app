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
    # スプレッドシート認証
    creds_json_str = st.secrets["gcp_service_account"]
    creds_dict = json.loads(creds_json_str)
    creds = Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
    gc = gspread.authorize(creds)
    spreadsheet = gc.open("消防アプリDB")
    worksheet = spreadsheet.worksheet("シート1")
    
    # Gemini認証（ショップアプリと同じ最新方式）
    client = genai.Client(api_key=st.secrets["GEMINI_API_KEY"])
    
except Exception as e:
    st.error(f"接続エラー: {e}")
    st.stop()

# --- 2. 画面構成 ---
st.title("🚒 消防昇任試験 AI対策アプリ")

tab1, tab2, tab3 = st.tabs(["🔥 テストを受ける", "🤖 AIで問題を作る", "📊 データベース"])

# --- タブ1: テスト ---
with tab1:
    st.header("試験に挑戦")
    data = worksheet.get_all_records()
    if data:
        df = pd.DataFrame(data)
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
        st.info("まだ問題が登録されていません。AIに作らせてみましょう！")

# --- タブ2: 問題作成 ---
with tab2:
    st.header("PDF資料から問題を作成")
    uploaded_file = st.file_uploader("PDFファイルをアップロードしてください", type="pdf")
    
    if uploaded_file:
        with pdfplumber.open(uploaded_file) as pdf:
            text_list = [page.extract_text() for page in pdf.pages if page.extract_text()]
            full_text = "".join(text_list)
        
        if full_text:
            st.write("📄 PDFの文字読み込みに成功しました！")
            num_questions = st.slider("作成する問題数", 1, 5, 1)
            
            if st.button(f"AIで{num_questions}問作成する"):
                with st.spinner("AIが試験問題を作成中..."):
                    prompt = f"""
                    あなたは消防昇任試験の専門家です。以下の資料から5択問題を{num_questions}問作成してください。
                    必ず以下のJSON形式のリストのみで回答してください。
                    [
                      {{"問題": "問題文", "選択肢": "A,B,C,D,E", "正解": "A", "解説": "解説文"}}
                    ]
                    資料:
                    {full_text[:3000]}
                    """
                    try:
                        # ショップアプリと同じ呼び出し方
                        response = client.models.generate_content(model="gemini-1.5-flash", contents=prompt)
                        
                        # AIの回答をクリーニングして保存
                        text_res = response.text.replace('```json', '').replace('```', '').strip()
                        new_problems = json.loads(text_res)
                        
                        for p in new_problems:
                            worksheet.append_row([p['問題'], p['選択肢'], p['正解'], p['解説']])
                        
                        st.success(f"✅ {len(new_problems)}問の問題をデータベースに追加しました！")
                        st.balloons() # お祝いの風船
                    except Exception as e:
                        st.error("AIがうまく回答できませんでした。もう一度ボタンを押してください。")
                        st.write(e)
        else:
            st.error("PDFから文字を読み取れませんでした。画像形式のPDF（スキャンしたもの）ではないか確認してください。")

# --- タブ3: データ確認 ---
with tab3:
    st.header("登録済みの全問題")
    all_data = worksheet.get_all_records()
    if all_data:
        st.dataframe(pd.DataFrame(all_data))
    if