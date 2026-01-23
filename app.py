import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
import pandas as pd

# --- Googleスプレッドシートへの接続 ---
try:
    # StreamlitのSecretsから認証情報を取得
    creds_dict = st.secrets["gcp_service_account"]
    creds = Credentials.from_service_account_info(creds_dict)
    gc = gspread.authorize(creds)

    # スプレッドシートを開く（ファイル名で指定）
    spreadsheet = gc.open("消防アプリDB")
    worksheet = spreadsheet.worksheet("シート1") # シート名で指定
    
    st.success("データベース（スプレッドシート）に接続しました！")

except Exception as e:
    st.error("スプレッドシートへの接続に失敗しました。")
    st.error(e)
    st.stop() # エラーが出たらここで処理を止める

# --- アプリの画面 ---
st.title("🚒 消防昇任試験対策アプリ")
st.write("ここにみんなで問題を共有します！")

# レイアウトを定義
tab1, tab2, tab3 = st.tabs(["🔥 テストを受ける", "📝 問題を作る", "📊 データを見る"])

# --- タブ1: テストを受ける ---
with tab1:
    st.header("ランダム5択問題")
    st.write("（ここに問題を表示する機能を後で追加します）")
    
    # テストとして、現在のスプレッドシートの中身を表示
    st.subheader("現在の問題リスト")
    data = worksheet.get_all_records()
    if data:
        df = pd.DataFrame(data)
        st.dataframe(df)
    else:
        st.info("まだ問題が登録されていません。")


# --- タブ2: 問題を作る ---
with tab2:
    st.header("新しい問題を追加する")
    
    with st.form("new_problem_form", clear_on_submit=True):
        question = st.text_area("問題文を入力してください")
        answer = st.text_input("正解を入力してください")
        submitted = st.form_submit_button("この問題を追加する")
        
        if submitted:
            # スプレッドシートの最終行に新しい問題を追加
            worksheet.append_row([question, answer])
            st.success("新しい問題を追加しました！")


# --- タB３: データを見る ---
with tab3:
    st.header("データベースの全容")
    st.write("ここではデータベースの全体を見ることができます。")
    data_all = worksheet.get_all_records()
    if data_all:
        df_all = pd.DataFrame(data_all)
        st.dataframe(df_all)