import streamlit as st
import pandas as pd
import re

# 頁面配置
st.set_page_config(
    page_title="AI 智慧進口貿易與物流管理系統",
    page_icon="🚢",
    layout="wide"
)

# 系統標題
st.title("🚢 AI 智慧進口貿易與物流自動化系統")
st.caption("專為進口國貿同仁打造：Email 報價自動解析 ➔ 落地成本平攤算力 ➔ 智慧決策議價")

# -----------------------------------------------------------------------------
# 預設範例資料與初始化
# -----------------------------------------------------------------------------
if 'customs_df' not in st.session_state:
    st.session_state.customs_df = pd.DataFrame([
        {"報關行名稱": "OO報關行", "報關費_NTD": 1700, "傳輸費_NTD": 300},
        {"報關行名稱": "XX報關行", "報關費_NTD": 1500, "傳輸費_NTD": 400},
        {"報關行名稱": "OX報關行", "報關費_NTD": 1300, "傳輸費_NTD": 500}
    ])

sample_email_1 = """
Hi Team,
以下為上海到基隆 40HQ 報價：
- 船公司：捷達國際物流 (Jieda Logistics)
- 海運費 (Ocean Freight): USD 2,100 / 40HQ
- 本地雜費 (THC/Handling/Doc): NTD 12,000
- 預計航程 (Transit Time): 12 天
- 適用匯率：32.0
請確認是否安排裝船。
"""

sample_email_2 = """
Dear Cargo Team,
最新的海運費用如下：
海順船務 (Ocean Shun Shipping)
40HQ 櫃型
Ocean Freight: USD 1,950
Local Charges in Taiwan: NTD 15,000
Transit Time: 15 days
Exchange rate reference: 32.0
"""

sample_email_3 = """
【萬達報關貨代】上海-基隆 40HQ 快速直達船優惠專案報價
海運費：USD 1,850 / 40HQ
台灣本地雜費：NTD 11,500
預計航程：11 天
計費匯率：32.0
"""

df_suppliers_sample = pd.DataFrame({
    '國外廠商名稱': ['Alpha Global Inc.', 'Sakura Trading', 'Rheinland Logistics'],
    '國家': ['美國', '日本', '德國'],
    '預計交期天數': [30, 14, 45],
    '實際交期天數': [32, 14, 50],
    '歷史訂單數': [20, 35, 12],
    '不良品退貨次數': [1, 0, 2],
    '平均單價(USD)': [150, 80, 220]
})

# 初始化 Session State 儲存動態解析後的貨代資料
if 'freight_list' not in st.session_state:
    st.session_state.freight_list = [
        {
            '廠商名稱': '捷達國際物流',
            '櫃型': '40HQ',
            '海運費_USD': 2100.0,
            '匯率_USD_NTD': 32.0,
            '本地雜費_NTD': 12000.0,
            '配合報關行': 'OO報關行',
            '預計航程_天': 12
        },
        {
            '廠商名稱': '海順船務',
            '櫃型': '40HQ',
            '海運費_USD': 1950.0,
            '匯率_USD_NTD': 32.0,
            '本地雜費_NTD': 15000.0,
            '配合報關行': 'XX報關行',
            '預計航程_天': 15
        }
    ]

# 增強版文字 Parsing 函數
def parse_freight_text(text):
    vendor = "新貨代/報價單"
    if "捷達" in text or "Jieda" in text: 
        vendor = "捷達國際物流"
        customs_default = "OO報關行"
    elif "海順" in text or "Ocean Shun" in text: 
        vendor = "海順船務"
        customs_default = "XX報關行"
    elif "萬達" in text or "Wanda" in text: 
        vendor = "萬達通運"
        customs_default = "OX報關行"
    else:
        lines = [l.strip() for l in text.split('\n') if l.strip()]
        vendor = lines[0][:15] if lines else "新貨代"
        customs_default = "OO報關行"

    # 1. 抓取海運費 (USD)
    usd_match = re.search(r'(?:Ocean|Freight|海運費|USD|\$)\s*:?\s*USD?\s*([\d,]+(?:\.\d+)?)', text, re.IGNORECASE)
    ocean_usd = float(usd_match.group(1).replace(',', '')) if usd_match else 2000.0

    # 2. 抓取匯率
    rate_match = re.search(r'(?:匯率|Exchange Rate|Ex Rate|Rate)\s*:?\s*([\d\.]+)', text, re.IGNORECASE)
    exchange_rate = float(rate_match.group(1)) if rate_match else 32.0

    # 3. 多項 TW Local 費用關鍵字自動掃描與加總
    local_keywords = [
        r'THC', r'吊櫃費', r'文件費', r'Doc', r'Handling', r'手續費', 
        r'電放費', r'Telex', r'封條費', r'Seal', r' CFS', r'併櫃費', 
        r'本地雜費', r'Local Charges', r'Local Fee', r'報關費'
    ]
    
    total_local_ntd = 0.0
    found_local = False

    for line in text.split('\n'):
        for kw in local_keywords:
            if re.search(kw, line, re.IGNORECASE):
                amount_match = re.search(r'(?:NTD|NT\$|\$|\:\s*)\s*([\d,]+)', line, re.IGNORECASE)
                if amount_match:
                    val = float(amount_match.group(1).replace(',', ''))
                    if val < 50000:  # 過濾避免抓到總海運費
                        total_local_ntd += val
                        found_local = True
                break

    if not found_local:
        total_local_ntd = 12000.0

    # 4. 抓取航程天數
    days_match = re.search(r'(\d+)\s*(?:天|days)', text, re.IGNORECASE)
    days = int(days_match.group(1)) if days_match else 14

    return {
        '廠商名稱': vendor,
        '櫃型': '40HQ',
        '海運費_USD': ocean_usd,
        '匯率_USD_NTD': exchange_rate,
        '本地雜費_NTD': total_local_ntd,
        '配合報關行': customs_default,
        '預計航程_天': days
    }
# -----------------------------------------------------------------------------
# 分頁設計 (Tabs)
# -----------------------------------------------------------------------------
tab1, tab2, tab3, tab4 = st.tabs([
    "⚡ Email 報價文字自動解析與比價", 
    "🏢 國外供應商綜合評比", 
    "📦 產品總落地成本 (Landed Cost)", 
    "🤖 AI 國貿溝通秘書"
])

# =============================================================================
# TAB 1: Email 報價文字自動解析與比價
# =============================================================================
with tab1:
    st.header("⚡ 貨代 & 報關行 組合報價與總金額比價")
    st.caption("💡 實務功能：上方提供報關行費用參考表；下方僅保留一個總費用試算明細表！")

    # -------------------------------------------------------------------------
    # 區塊 1：報關行收費標準參考表（常駐查閱、可自由修改）
    # -------------------------------------------------------------------------
    st.subheader("📑 1. 報關行收費標準參考表 (隨時查閱與修改備查)")
    edited_customs_df = st.data_editor(
        st.session_state.customs_df,
        num_rows="dynamic",
        key="customs_editor",
        use_container_width=True
    )
    st.session_state.customs_df = edited_customs_df

    # 將報關行資料轉換為字典，供下方總金額表自動對照連動
    customs_map = edited_customs_df.set_index("報關行名稱").to_dict(orient="index")
    customs_options = list(customs_map.keys()) if customs_map else ["OO報關行"]

    st.divider()

    # -------------------------------------------------------------------------
    # 區塊 2：Email 報價解析與輸入
    # -------------------------------------------------------------------------
    st.subheader("✉️ 2. 貼上貨代 Email 報價文字")
    col_input, col_preset = st.columns([2, 1])
    
    with col_input:
        raw_email_input = st.text_area(
            "請將貨代業務寄來的 Email 報價文字直接貼在下方：", 
            height=130,
            placeholder="貼上文字範例：\n萬達報關貨代 40HQ 報價\nOcean Freight: USD 1,850\nLocal Fee: NTD 11,500\nTransit Time: 11 days"
        )
        if st.button("🚀 執行 AI 文字解析並加入比較表"):
            if raw_email_input.strip():
                parsed_data = parse_freight_text(raw_email_input)
                st.session_state.freight_list.append(parsed_data)
                st.success(f"✅ 成功提取【{parsed_data['廠商名稱']}】報價！已自動帶入下方比價表。")
                st.rerun()
            else:
                st.warning("請先輸入或貼上 Email 文字。")

    with col_preset:
        st.write("**📋 快速測試範例：**")
        col_btn1, col_btn2 = st.columns(2)
        with col_btn1:
            if st.button("載入捷達 Email"):
                st.session_state.freight_list.append(parse_freight_text(sample_email_1))
                st.rerun()
            if st.button("載入萬達 Email"):
                st.session_state.freight_list.append(parse_freight_text(sample_email_3))
                st.rerun()
        with col_btn2:
            if st.button("載入海順 Email"):
                st.session_state.freight_list.append(parse_freight_text(sample_email_2))
                st.rerun()
            if st.button("🔄 重置比價表"):
                st.session_state.freight_list = st.session_state.freight_list[:2]
                st.rerun()

    st.divider()

    # -------------------------------------------------------------------------
    # 區塊 3：單一組合報價與【總金額】動態互動表
    # -------------------------------------------------------------------------
    st.subheader("📋 3. 貨代 + 報關行 組合報價與【總金額】明細表 (唯一加總表)")
    st.caption("💡 說明：在「配合報關行」下拉選單切換報關行，系統會自動帶入對應的報關費與傳輸費，並直接在最右側試算出【總金額_NTD】！")

    # 準備基礎資料表並帶入最新計算
    df_freight = pd.DataFrame(st.session_state.freight_list)

    if '配合報關行' not in df_freight.columns:
        df_freight['配合報關行'] = customs_options[0] if customs_options else "OO報關行"

    # 動態計算：讀取上方參考表帶入報關費與傳輸費，並算出總金額
    df_freight['報關費_NTD'] = df_freight['配合報關行'].apply(
        lambda x: customs_map.get(x, {}).get('報關費_NTD', 0) if x in customs_map else 0
    )
    df_freight['傳輸費_NTD'] = df_freight['配合報關行'].apply(
        lambda x: customs_map.get(x, {}).get('傳輸費_NTD', 0) if x in customs_map else 0
    )
    df_freight['海運費_NTD'] = df_freight['海運費_USD'] * df_freight['匯率_USD_NTD']
    df_freight['總金額_NTD'] = df_freight['海運費_NTD'] + df_freight['本地雜費_NTD'] + df_freight['報關費_NTD'] + df_freight['傳輸費_NTD']

    # 欄位順序調整
    display_cols = [
        '廠商名稱', '櫃型', '海運費_USD', '匯率_USD_NTD', '海運費_NTD', 
        '本地雜費_NTD', '配合報關行', '報關費_NTD', '傳輸費_NTD', 
        '預計航程_天', '總金額_NTD'
    ]
    final_cols = [c for c in display_cols if c in df_freight.columns]

    # 唯一的動態加總編輯表
    edited_df = st.data_editor(
        df_freight[final_cols], 
        num_rows="dynamic", 
        key="freight_single_interactive_table",
        use_container_width=True,
        column_config={
            "配合報關行": st.column_config.SelectboxColumn(
                "配合報關行",
                options=customs_options,
                required=True,
                help="下拉選擇報關行，自動對照帶入費用"
            ),
            "海運費_USD": st.column_config.NumberColumn("海運費 (USD)", format="$%.2f"),
            "匯率_USD_NTD": st.column_config.NumberColumn("匯率", format="%.2f"),
            "海運費_NTD": st.column_config.NumberColumn("海運費 (NTD)", format="$%d", disabled=True),
            "本地雜費_NTD": st.column_config.NumberColumn("本地雜費 (NTD)", format="$%d"),
            "報關費_NTD": st.column_config.NumberColumn("報關費 (NTD)", format="$%d", disabled=True),
            "傳輸費_NTD": st.column_config.NumberColumn("傳輸費 (NTD)", format="$%d", disabled=True),
            "總金額_NTD": st.column_config.NumberColumn("【總金額_NTD】", format="$%d", disabled=True)
        }
    )

    # 若使用者在表格內即時修改了資料或切換了報關行，更新 Session State
    for idx, row in edited_df.iterrows():
        if idx < len(st.session_state.freight_list):
            st.session_state.freight_list[idx]['廠商名稱'] = row['廠商名稱']
            st.session_state.freight_list[idx]['櫃型'] = row['櫃型']
            st.session_state.freight_list[idx]['海運費_USD'] = row['海運費_USD']
            st.session_state.freight_list[idx]['匯率_USD_NTD'] = row['匯率_USD_NTD']
            st.session_state.freight_list[idx]['本地雜費_NTD'] = row['本地雜費_NTD']
            st.session_state.freight_list[idx]['配合報關行'] = row['配合報關行']
            st.session_state.freight_list[idx]['預計航程_天'] = row['預計航程_天']

    st.divider()

    # 指標卡片 (顯示最低價與平均金額)
    if not edited_df.empty and '總金額_NTD' in edited_df.columns:
        col1, col2, col3 = st.columns(3)
        best_price_row = edited_df.loc[edited_df['總金額_NTD'].idxmin()]
        fastest_row = edited_df.loc[edited_df['預計航程_天'].idxmin()]
        
        col1.metric(
            "💡 最便宜組合方案", 
            f"{best_price_row['廠商名稱']} + {best_price_row['配合報關行']}", 
            f"NT$ {best_price_row['總金額_NTD']:,.0f}"
        )
        col2.metric("⚡ 最快航程方案", f"{fastest_row['廠商名稱']}", f"{fastest_row['預計航程_天']} 天")
        col3.metric("📊 各組合平均總金額", f"NT$ {edited_df['總金額_NTD'].mean():,.0f}")

# =============================================================================
# TAB 2: 國外供應商綜合評比
# =============================================================================
with tab2:
    st.header("🏢 國外供應商績效評估 (AHP / 加權評分)")
    df_suppliers = df_suppliers_sample.copy()
    
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
    st.dataframe(df_suppliers[['國外廠商名稱', '國家', '交期延遲天數', '不良率_%', '綜合評分', '評等']], use_container_width=True)

# =============================================================================
# TAB 3: 產品總落地成本 (Landed Cost) 計算器
# =============================================================================
with tab3:
    st.header("📦 進口產品單件「總落地成本 (Landed Cost)」平攤算力")
    st.caption("💡 解決計算機痛點：精準將海運費、本地雜費、關稅平攤至單件商品，算出真正的保本賣價。")
    
    col_a, col_b = st.columns(2)
    
    with col_a:
        po_qty = st.number_input("本次進口總數量 (PCS)", value=1000, step=100)
        unit_fob = st.number_input("商品單件 FOB 價格 (USD)", value=25.0, step=1.0)
        exchange_rate = st.number_input("預估匯率 (USD to NTD)", value=32.0, step=0.1)
        tariff_rate = st.number_input("進口關稅稅率 (%)", value=5.0, step=0.5)

    with col_b:
        selected_forwarder = st.selectbox("選擇運送的貨代/船公司方案：", edited_df['廠商名稱'].unique(), key="tab3_fw_select")
        f_row = edited_df[edited_df['廠商名稱'] == selected_forwarder].iloc[0]
        
        shipping_cost_ntd = f_row['總金額_NTD']
        st.info(f"已自動帶入 **{selected_forwarder}** (+{f_row['配合報關行']}) 總物流費用：NT$ {shipping_cost_ntd:,.0f}")

    total_fob_ntd = po_qty * unit_fob * exchange_rate
    duty_ntd = (total_fob_ntd + shipping_cost_ntd) * (tariff_rate / 100)
    total_landed_cost_ntd = total_fob_ntd + shipping_cost_ntd + duty_ntd
    unit_landed_cost_ntd = total_landed_cost_ntd / po_qty

    st.divider()
    st.subheader("💡 平攤試算結果")
    res1, res2, res3 = st.columns(3)
    res1.metric("總進口落地成本 (NTD)", f"NT$ {total_landed_cost_ntd:,.0f}")
    res2.metric("單件商品真實落地成本 (NTD)", f"NT$ {unit_landed_cost_ntd:,.2f}")
    res3.metric("物流與關稅附加比例", f"{((unit_landed_cost_ntd - (unit_fob*exchange_rate)) / (unit_fob*exchange_rate) * 100):,.1f}%")

# =============================================================================
# TAB 4: AI 國貿溝通秘書
# =============================================================================
with tab4:
    st.header("🤖 AI 國貿溝通秘書 (根據比價劣勢自動生成談判信)")
    st.caption("💡 解決真實痛點：自動抓出該貨代的偏高費用（如本地雜費或海運費），一鍵生成精準議價信！")

    col_fw, col_lang, col_format = st.columns(3)

    with col_fw:
        target_fw = st.selectbox("1. 選擇談判目標貨代：", edited_df['廠商名稱'].unique(), key="tab4_fw_select")
    with col_lang:
        msg_lang = st.radio("2. 選擇信件語言：", ["繁體中文", "English"], horizontal=True)
    with col_format:
        msg_style = st.radio("3. 選擇發送管道格式：", ["正式 Email", "LINE / 微信 簡短訊息"], horizontal=True)

    fw_info = edited_df[edited_df['廠商名稱'] == target_fw].iloc[0]

    # 判斷偏高費用項目
    highest_item_zh = "本地雜費 (THC/文件費)" if fw_info['本地雜費_NTD'] > 12000 else "海運費 (Ocean Freight)"
    highest_item_en = "Local Charges" if fw_info['本地雜費_NTD'] > 12000 else "Ocean Freight"

    if st.button("🚀 AI 生成精準談判內容"):
        if msg_lang == "繁體中文":
            if msg_style == "正式 Email":
                email_content = f"""主旨：【詢價與議價確認】關於近期 40HQ 進口櫃海運報價 - [貴司名稱]

{target_fw} 業務團隊 您好：

感謝貴司先前提供上海至基隆的 40HQ 海運報價。

經我司內部評估，發現貴司的【{highest_item_zh}】（目前報價為 NT$ {fw_info['本地雜費_NTD']:,.0f}）稍高於我司本季的預算編列。

考慮到雙方長期穩定的合作關係與我司後續持續的出貨量，想請教此部分費用是否有微調或折讓的空間？

若價格能符合預算，我們非常希望能將本次運價優先安排給貴司承攬。

期待您的回覆，感謝！

順頌 商祺

[您的姓名 / 公司名稱]
進口物流部"""
            else:  # LINE / 微信 簡短訊息
                email_content = f"""{target_fw} 業務您好！感謝先前的 40HQ 報價。我們評估後很希望交給你們跑，但發現【{highest_item_zh}】稍微超出我們預算一點點，想問一下這部分有沒有優惠空間呢？如果可以的話我們這兩天就直接下單，再麻煩您幫忙確認一下，謝謝！"""

        else:  # English
            if msg_style == "正式 Email":
                email_content = f"""Subject: Rate Inquiry and Negotiation for Upcoming Shipment - [Our Company Name]

Dear {target_fw} Team,

Thank you for providing your recent rate quote for the 40HQ shipment.

After evaluating your quote alongside our budget, we noticed that your {highest_item_en} (currently quoted at NTD {fw_info['本地雜費_NTD']:,.0f}) is slightly higher than our target allocation.

Given our regular shipping volume and long-term partnership, could you please review if there is any flexibility to adjust the {highest_item_en}?

We would love to finalize the booking with your team if we can align on the cost.

Looking forward to your swift response.

Best regards,
[Your Name]
Import Logistics Department"""
            else:  # LINE / 微信 簡短訊息
                email_content = f"""Hi {target_fw} team, thanks for the 40HQ quote! We’d love to book with you, but the {highest_item_en} is slightly over our budget. Is there any flexibility on this rate? If we can align on price, we can confirm the booking right away. Thanks!"""

        st.subheader("📋 生成的溝通文字 (可直接複製發送)：")
        st.text_area("", value=email_content, height=280)
