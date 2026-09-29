import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import io

# 頁面配置
st.set_page_config(
    page_title="AI 智慧進口貿易與物流管理系統",
    page_icon="🚢",
    layout="wide"
)

# 系統標題
st.title("🚢 AI 智慧進口貿易與物流供應鏈管理系統")
st.caption("針對進口同仁打造：輕鬆搞定貨代比價、國外供應商評比與總落地成本計算")

# -----------------------------------------------------------------------------
# 預設範例資料 (解決無檔案/加密問題)
# -----------------------------------------------------------------------------
df_suppliers_sample = pd.DataFrame({
    '國外廠商名稱': ['Alpha Global Inc.', 'Sakura Trading', 'Rheinland Logistics'],
    '供應商統編/TaxID': ['US987654', 'JP123456', 'DE555666'],
    '國家': ['美國', '日本', '德國'],
    '預計交期天數': [30, 14, 45],
    '實際交期天數': [32, 14, 50],
    '歷史訂單數': [20, 35, 12],
    '不良品退貨次數': [1, 0, 2],
    '平均單價(USD)': [150, 80, 220]
})

df_freight_sample = pd.DataFrame({
    '廠商名稱': ['捷達國際物流', '海順船務', '萬達報關貨代', '遠洋航運'],
    '廠商類型': ['貨代', '船公司', '報關行+貨代', '船公司'],
    '起運港': ['Shanghai', 'Shanghai', 'Shanghai', 'Shanghai'],
    '櫃型': ['40HQ', '40HQ', '40HQ', '40HQ'],
    '海運費_USD': [2100, 1950, 2300, 1880],
    '本地雜費_NTD': [12000, 15000, 9500, 16000],
    '報關費_NTD': [3500, 4000, 3000, 4500],
    '預計航程_天': [12, 15, 11, 16],
    '匯率_USD_NTD': [32.0, 32.0, 32.0, 32.0]
})

# -----------------------------------------------------------------------------
# 側邊欄：資料輸入模式選擇 (避免公司加密鎖檔問題)
# -----------------------------------------------------------------------------
with st.sidebar:
    st.header("📂 資料輸入模式")
    data_mode = st.radio(
        "請選擇資料來源：",
        ["1. 使用系統內建範例", "2. 直接貼上 Excel 表格 (免解密)", "3. 上傳 Excel 檔案 (.xlsx)"]
    )
    
    df_freight = df_freight_sample
    df_suppliers = df_suppliers_sample

    if data_mode == "2. 直接貼上 Excel 表格 (免解密)":
        st.subheader("📋 貼上物流報價資料")
        st.caption("請從 Excel 選取表格複製 (Ctrl+C) 後貼在下方：")
        raw_paste_freight = st.text_area("物流報價複製貼上區域", height=120, placeholder="從 Excel 複製包含標題列的內容...")
        if raw_paste_freight.strip():
            try:
                df_freight = pd.read_csv(io.StringIO(raw_paste_freight), sep='\t')
                st.success("✅ 物流資料讀取成功！")
            except Exception as e:
                st.error("貼上格式錯誤，請確保包含 Excel 欄位標題。")

    elif data_mode == "3. 上傳 Excel 檔案 (.xlsx)":
        uploaded_file = st.file_uploader("上傳未加密 Excel (.xlsx)", type=["xlsx"])
        if uploaded_file:
            try:
                df_freight = pd.read_excel(uploaded_file, sheet_name='物流報價資料')
                df_suppliers = pd.read_excel(uploaded_file, sheet_name='供應商評比資料')
                st.success("✅ 檔案讀取成功！")
            except Exception as e:
                st.error(f"檔案讀取失敗或受鎖檔保護。建議改用模式 2 複製貼上。")

# -----------------------------------------------------------------------------
# 分頁設計 (Tabs)
# -----------------------------------------------------------------------------
tab1, tab2, tab3, tab4 = st.tabs([
    "🚢 貨代與物流報價比價", 
    "🏢 國外供應商綜合評比", 
    "📦 產品總落地成本 (Landed Cost)", 
    "🤖 AI 國貿溝通秘書"
])

# =============================================================================
# TAB 1: 貨代與物流報價比價
# =============================================================================
with tab1:
    st.header("🚢 貨代/船公司/報關行 報價動態比價")
    
    # 確保必要欄位存在
    required_cols = ['海運費_USD', '匯率_USD_NTD', '本地雜費_NTD', '報關費_NTD', '廠商名稱', '預計航程_天']
    if all(col in df_freight.columns for col in required_cols):
        df_freight['海運費_NTD'] = df_freight['海運費_USD'] * df_freight['匯率_USD_NTD']
        df_freight['總落地運費_NTD'] = df_freight['海運費_NTD'] + df_freight['本地雜費_NTD'] + df_freight['報關費_NTD']
        
        col1, col2, col3 = st.columns(3)
        best_price_row = df_freight.loc[df_freight['總落地運費_NTD'].idxmin()]
        fastest_row = df_freight.loc[df_freight['預計航程_天'].idxmin()]
        
        col1.metric("最低總運費方案", f"{best_price_row['廠商名稱']}", f"NT$ {best_price_row['總落地運費_NTD']:,.0f}")
        col2.metric("最快到達方案", f"{fastest_row['廠商名稱']}", f"{fastest_row['預計航程_天']} 天")
        col3.metric("平均總運費", f"NT$ {df_freight['總落地運費_NTD'].mean():,.0f}")

        st.subheader("📊 各家廠商費用結構與總價比較")
        fig_freight = px.bar(
            df_freight, 
            x='廠商名稱', 
            y=['海運費_NTD', '本地雜費_NTD', '報關費_NTD'],
            title="各廠商費用拆解 (NTD)",
            labels={'value': '金額 (NTD)', 'variable': '費用項目'},
            barmode='stack'
        )
        st.plotly_chart(fig_freight, use_container_width=True)

        st.subheader("📋 可直接線上編輯的資料表")
        st.caption("💡 提示：你可以直接點擊下方表格修改數字，圖表會隨修改改變！")
        edited_df = st.data_editor(df_freight, num_rows="dynamic")
    else:
        st.warning("⚠️ 目前貼上或上傳的資料欄位不完整，請切換回「1. 使用系統內建範例」查看標準欄位格式。")

# =============================================================================
# TAB 2: 國外供應商綜合評比
# =============================================================================
with tab2:
    st.header("🏢 國外供應商績效評估 (AHP / 加權評分)")
    
    df_suppliers['交期延遲天數'] = df_suppliers['實際交期天數'] - df_suppliers['預計交期天數']
    df_suppliers['交期得分'] = df_suppliers['交期延遲天數'].apply(lambda x: max(0, 100 - x * 10))
    df_suppliers['不良率_%'] = (df_suppliers['不良品退貨次數'] / df_suppliers['歷史訂單數']) * 100
    df_suppliers['品質得分'] = 100 - (df_suppliers['不良率_%'] * 5)
    df_suppliers['綜合評分'] = (df_suppliers['交期得分'] * 0.5 + df_suppliers['品質得分'] * 0.5).round(1)
    
    def get_grade(score):
        if score >= 90: return 'A級 (優良供應商)'
        elif score >= 75: return 'B級 (觀察中)'
        else: return 'C級 (建議替換/預警)'
    
    df_suppliers['評等'] = df_suppliers['綜合評分'].apply(get_grade)

    st.subheader("🎯 供應商評等與綜合得分")
    fig_supplier = px.bar(
        df_suppliers,
        x='國外廠商名稱',
        y='綜合評分',
        color='評等',
        text='綜合評分',
        title="供應商綜合評分排名",
        color_discrete_map={'A級 (優良供應商)': 'green', 'B級 (觀察中)': 'orange', 'C級 (建議替換/預警)': 'red'}
    )
    st.plotly_chart(fig_supplier, use_container_width=True)

    st.subheader("🕸️ 供應商多維度指標雷達圖")
    selected_supplier = st.selectbox("選擇要查看雷達圖的供應商：", df_suppliers['國外廠商名稱'].unique())
    sup_data = df_suppliers[df_suppliers['國外廠商名稱'] == selected_supplier].iloc[0]

    categories = ['交期表現', '品質表現', '價格優勢']
    price_score = max(0, 100 - (sup_data['平均單價(USD)'] / df_suppliers['平均單價(USD)'].max() * 30))
    
    fig_radar = go.Figure(data=go.Scatterpolar(
        r=[sup_data['交期得分'], sup_data['品質得分'], price_score],
        theta=categories,
        fill='toself'
    ))
    fig_radar.update_layout(polar=dict(radialaxis=dict(visible=True, range=[0, 100])), showlegend=False)
    st.plotly_chart(fig_radar, use_container_width=True)

    st.dataframe(df_suppliers[['國外廠商名稱', '供應商統編/TaxID', '國家', '交期延遲天數', '不良率_%', '綜合評分', '評等']], use_container_width=True)

# =============================================================================
# TAB 3: 產品總落地成本 (Landed Cost) 計算器
# =============================================================================
with tab3:
    st.header("📦 進口產品單件「總落地成本 (Landed Cost)」預估")
    col_a, col_b = st.columns(2)
    
    with col_a:
        po_qty = st.number_input("本次進口總數量 (PCS)", value=1000, step=100)
        unit_fob = st.number_input("商品單件 FOB 價格 (USD)", value=25.0, step=1.0)
        exchange_rate = st.number_input("預估匯率 (USD to NTD)", value=32.0, step=0.1)
        tariff_rate = st.number_input("進口關稅稅率 (%)", value=5.0, step=0.5)

    with col_b:
        selected_forwarder = st.selectbox("選擇運送的貨代/船公司：", df_freight['廠商名稱'].unique())
        f_row = df_freight[df_freight['廠商名稱'] == selected_forwarder].iloc[0]
        shipping_cost_ntd = f_row['海運費_USD'] * f_row['匯率_USD_NTD'] + f_row['本地雜費_NTD'] + f_row['報關費_NTD']
        st.info(f"已帶入 **{selected_forwarder}** 總物流費用：NT$ {shipping_cost_ntd:,.0f}")

    total_fob_ntd = po_qty * unit_fob * exchange_rate
    duty_ntd = (total_fob_ntd + shipping_cost_ntd) * (tariff_rate / 100)
    total_landed_cost_ntd = total_fob_ntd + shipping_cost_ntd + duty_ntd
    unit_landed_cost_ntd = total_landed_cost_ntd / po_qty

    st.divider()
    st.subheader("💡 試算結果")
    res1, res2, res3 = st.columns(3)
    res1.metric("總進口落地成本 (NTD)", f"NT$ {total_landed_cost_ntd:,.0f}")
    res2.metric("單件商品真實落地成本 (NTD)", f"NT$ {unit_landed_cost_ntd:,.2f}")
    res3.metric("物流與關稅溢價比例", f"{((unit_landed_cost_ntd - (unit_fob*exchange_rate)) / (unit_fob*exchange_rate) * 100):,.1f}%")

# =============================================================================
# TAB 4: AI 國貿溝通秘書
# =============================================================================
with tab4:
    st.header("🤖 AI 國貿溝通秘書 (一鍵生成 Mail 草稿)")
    mail_type = st.selectbox("請選擇信件情境：", [
        "1. 向貨代爭取運費折扣 (Freight Negotiation)",
        "2. 向國外供應商反映交期延遲 (Delay Complaint)"
    ])

    if mail_type == "1. 向貨代爭取運費折扣 (Freight Negotiation)":
        target_fw = st.selectbox("選擇目標貨代：", df_freight['廠商名稱'])
        target_price = st.number_input("希望目標總價 (NTD)：", value=70000)
        
        if st.button("🚀 生成議價信草稿"):
            current_price = df_freight[df_freight['廠商名稱']==target_fw]['海運費_USD'].values[0] * 32 + df_freight[df_freight['廠商名稱']==target_fw]['本地雜費_NTD'].values[0] + df_freight[df_freight['廠商名稱']==target_fw]['報關費_NTD'].values[0]
            email_content = f"""Subject: Quotation Inquiry and Price Negotiation - [Our Company Name]\n\nDear {target_fw} Team,\n\nThank you for providing the recent freight quotation.\n\nUpon reviewing the rate breakdown for our upcoming shipment, we noticed that the total landed cost is currently around NTD {current_price:,.0f}. Given our long-term partnership and shipping volume, we were hoping to target a total budget around NTD {target_price:,.0f}.\n\nCould you please review if there is any flexibility to adjust the ocean freight or local charges?\n\nLooking forward to your favorable reply.\n\nBest regards,\n[Your Name]\nImport Department"""
            st.text_area("生成的信件內容 (可直接複製)：", value=email_content, height=250)