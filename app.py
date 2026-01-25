import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
import pandas as pd
import json

# --- Googleスプレッドシートへの接続設定 ---
# どの機能（スコープ）を使うか指定します
SCOPES = [
    'https://www.googleapis.com/auth/spreadsheets',
    'https://www.googleapis.com/auth/drive'
]

try:
    # SecretsからJSON文字列を取得
    creds_json_str = st.secrets["gcp_service_account"]
    creds_dict = json.loads(creds_json_str)
    
    # スコープを含めて認証情報を作成 ◀◀ここを修正しました！
    creds = Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
    gc = gspread.authorize(creds)

    # スプレッドシートを開く
    spreadsheet = gc.open("消防アプリDB")
    worksheet = spreadsheet.worksheet("シート1")
    
    st.success("データベース（スプレッドシート）に接続しました！")

except Exception as e:
    st.error("スプレッドシートへの接続に失敗しました。")
    st.error(e)
    st.stop()

# --- アプリの画面表示 ---
st.title("🚒 消防昇任試験対策アプリ")
st.write("ここにみんなで問題を共有します！")

tab1, tab2, tab3 = st.tabs(["🔥 テストを受ける", "📝 問題を作る", "📊 データを見る"])

with tab1:
    st.header("ランダム5択問題")
    st.write("（ここに問題を表示する機能を後で追加します）")
    data = worksheet.get_all_records()
    if data:
        df = pd.DataFrame(data)
        st.dataframe(df)
    else:
        st.info("まだ問題が登録されていません。")

with tab2:
    st.header("新しい問題を追加する")
    with st.form("new_problem_form", clear_on_submit=True):
        question = st.text_area("問題文を入力してください")
        answer = st.text_input("正解を入力してください")
        submitted = st.form_submit_button("この問題を追加する")
        if submitted:
            # スプレッドシートに書き込み
            worksheet.append_row([question, answer])
            st.success("新しい問題を追加しました！")

with tab3:
    st.header("データベースの全容")
    data_all = worksheet.get_all_records()
    if data_all:
        df_all = pd.DataFrame(data_all)
        st.dataframe(df_all)