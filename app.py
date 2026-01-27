import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
import pandas as pd
import json
import pdfplumber
from google import genai

# --- 1. 初期設定（スプレッドシート & Gemini） ---
SCOPES = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']

try:
    # スプレッドシートの認証
    creds_json_str = st.secrets["gcp_service_account"]
    creds_dict = json.loads(creds_json_str)
    creds = Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
    gc = gspread.authorize(creds)
    spreadsheet = gc.open("消防アプリDB")
    worksheet = spreadsheet.worksheet("シート1")
    
    # Gemini 2.0 Flashの認証（ショップアプリと同じ最新方式）
    client = genai.Client(api_key=st.secrets["GEMINI_API_KEY"])
    
except Exception as e:
    st.error(f"接続エラー（Secretsの設定を確認してください）: {e}")
    st.stop()

# --- 2. 画面構成 ---
st.title("🚒 消防昇任試験 AI対策アプリ")
st.caption("Model: Gemini 2.0 Flash (Experimental)")

tab1, tab2, tab3 = st.tabs(["🔥 テストを受ける", "🤖 AIで問題を作る", "📊 データベース"])

# --- タブ1: テストを受ける ---
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
        st.info("まだ問題がありません。まずは「AIで問題を作る」から追加しましょう！")

# --- タブ2: AIで問題を作る ---
with tab2:
    st.header("PDF資料から問題を作成")
    uploaded_file = st.file_uploader("PDFファイルをアップロードしてください", type="pdf")
    
    if uploaded_file:
        with pdfplumber.open(uploaded_file) as pdf:
            text_list = [page.extract_text() for page in pdf.pages if page.extract_text()]
            full_text = "".join(text_list)
        
        if full_text:
            st.success("📄 PDFの読み込みに成功しました！")
            if st.button("AIで問題を1問作成する"):
                with st.spinner("最新AI（Gemini 2.0）が問題を作成中..."):
                    # AIへの指示（プロンプト）
                    prompt = f"""
                    あなたは消防昇任試験の専門家です。提供された資料から、重要度の高い5択問題を1問だけ作成してください。
                    回答は必ず以下のJSON形式のリストのみで返してください。余計な挨拶や説明は不要です。
                    [
                      {{"問題": "問題文", "選択肢": "A,B,C,D,E", "正解": "A", "解説": "解説文"}}
                    ]
                    資料:
                    {full_text[:3000]}
                    """
                    try:
                        # Gemini 2.0 Flash を呼び出し
                        response = client.models.generate_content(
                            model="gemini-2.5-flash" 
                            contents=prompt
                        )
                        
                        # 回答をきれいに掃除してJSONとして読み込む
                        res_text = response.text.replace('```json', '').replace('```', '').strip()
                        new_problems = json.loads(res_text)
                        
                        for p in new_problems:
                            worksheet.append_row([p['問題'], p['選択肢'], p['正解'], p['解説']])
                        
                        st.success("✅ 1問追加しました！「テストを受ける」タブを確認してください。")
                        st.balloons()
                    except Exception as e:
                        st.error(f"AIエラーが発生しました。時間を置いてもう一度押してください。")
                        st.write(f"詳細: {e}")
        else:
            st.error("PDFから文字を読み取れませんでした。")

# --- タブ3: データベース表示 ---
with tab3:
    st.header("登録済みの全問題")
    all_data = worksheet.get_all_records()
    if all_data:
        st.dataframe(pd.DataFrame(all_data))
    if st.button("全データを削除（リセット）"):
        worksheet.clear()
        worksheet.append_row(["問題", "選択肢", "正解", "解説"])
        st.rerun()