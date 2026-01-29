import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
import pandas as pd
import json
import pdfplumber
from google import genai
import re # 区切り処理のために追加

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
            
            # --- 選択肢の区切り処理（強化版） ---
            opt_raw = str(q['選択肢'])
            # カンマ、改行、または A. B. C. のパターンで分割する
            if ',' in opt_raw:
                options = opt_raw.split(',')
            else:
                # A. や B. という文字の前で分割する魔法の命令
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
                            st.warning("⚠️ 復習シートに登録しました。")
                    st.info(f"💡 解説: {q['解説']}")
    else:
        st.info(f"{mode}のデータがありません。")

# --- タブ2: AIで問題を作る ---
with tab2:
    uploaded_file = st.file_uploader("PDFファイルをアップロードしてください", type="pdf")
    if uploaded_file:
        with pdfplumber.open(uploaded_file) as pdf:
            text = "".join([p.extract_text() for p in pdf.pages if p.extract_text()])
        if text:
            st.success("📄 PDF読み込み完了")
            num_q = st.slider("作成する問題数", 1, 5, 1)
            if st.button(f"AIで{num_q}問作成する"):
                with st.spinner("AIが試験問題を作成中..."):
                    # プロンプトを強化：カンマ区切りを強調
                    prompt = f"""
                    消防試験の専門家として、資料から5択問題を{num_q}問作成してください。
                    【重要】選択肢は必ず「A:〇〇,B:〇〇,C:〇〇,D:〇〇,E:〇〇」のように、各項目をカンマ(,)で区切ってください。
                    必ず以下のJSON形式のリストのみで回答してください。
                    [
                      {{"問題": "問題文", "選択肢": "A:..,B:..,C:..,D:..,E:..", "正解": "A", "解説": "解説文"}}
                    ]
                    資料:
                    {text[:3000]}
                    """
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
    if st.button("メイン問題をリセット(全削除)"):
        worksheet_main.clear()
        worksheet_main.append_row(["問題", "選択肢", "正解", "解説"])
        st.success("メインデータベースを空にしました。")
        st.rerun()
    st.subheader("メイン問題リスト")
    st.dataframe(pd.DataFrame(worksheet_main.get_all_records()))