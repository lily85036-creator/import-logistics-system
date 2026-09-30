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
st.title("🚢 進出口物流報價比價與 AI 溝通系統")
st.caption("Email 報價自動解析 ➔ 海運雜費與報關整合 ➔ AI 自動議價信生成")

# -----------------------------------------------------------------------------
# 1. 預設範例與解析函式（優先載入）
# -----------------------------------------------------------------------------
sample_email_1 = """
Hi Team,
以下為上海到基隆 40HQ 報價：
- 船公司：捷達國際物流 (Jieda Logistics)
- 數量：2 櫃
- 海運費 (Ocean Freight): USD 2,100 / 40HQ
- 本地雜費 (THC/Handling/Doc): NTD 12,000
- 預計航程 (Transit Time): 12 天
- 適用匯率：32.0
請確認是否安排裝船。
"""

sample_email_2 = """
【空運詢報價】PVG -> TPE 國際空運專案
貨代：萬達通運
件數 (Cartons): 10 箱
單箱尺寸：60 x 50 x 40 cm
實際毛重 (GW): 180 KGS
Air Freight: USD 3.5 / KG
FSC: USD 0.3 / KG
SSC: USD 0.1 / KG
Taiwan Local Charge: NTD 6,500
預計航程：2 天
匯率：32.0
"""

sample_email_3 = """
【快遞專線】HKG -> TPE 商業快遞
貨代：順豐/DHL快遞代理
實際毛重 (GW): 250 KGS
體積 (CBM): 2.2 CBM
Air Freight: USD 4.2 / KG
Taiwan Local Charge: NTD 3,500
預計航程：1 天
匯率：32.0
"""

def parse_freight_text(text):
    is_air = bool(re.search(r'(?:Air|空運|PVG|TPE|HKG|Express|快遞)', text, re.IGNORECASE))
    mode_label = "Air Cargo" if is_air else "40HQ"

    if "捷達" in text or "Jieda" in text: 
        vendor = "捷達國際物流"
        customs_default = "OO報關行"
    elif "萬達" in text or "Wanda" in text: 
        vendor = "萬達通運"
        customs_default = "OX報關行"
    elif "快遞" in text or "DHL" in text or "順豐" in text:
        vendor = "順豐/快遞專線"
        customs_default = "XX報關行"
    else:
        lines = [l.strip() for l in text.split('\n') if l.strip()]
        vendor = lines[0][:15] if lines else "新貨代/報價單"
        customs_default = "OO報關行"

    rate_match = re.search(r'(?:匯率|Exchange Rate|Rate)\s*:?\s*([\d\.]+)', text, re.IGNORECASE)
    exchange_rate = float(rate_match.group(1)) if rate_match else 32.0

    # 海運櫃數
    if not is_air:
        ctn_match = re.search(r'(\d+)\s*(?:櫃|ctn|container)', text, re.IGNORECASE)
        containers_cnt = int(ctn_match.group(1)) if ctn_match else 1
    else:
        containers_cnt = 0

    # 尺寸、箱數、毛重、CBM 解析
    gw_kg, cbm_val = 0.0, 0.0
    pcs_cnt = 1
    length_cm, width_cm, height_cm = 0.0, 0.0, 0.0
    divisor = 6000

    if is_air:
        gw_match = re.search(r'(?:GW|Gross Weight|毛重|重量)\s*:?\s*([\d,]+(?:\.\d+)?)\s*KGS?', text, re.IGNORECASE)
        gw_kg = float(gw_match.group(1).replace(',', '')) if gw_match else 180.0

        pcs_match = re.search(r'(\d+)\s*(?:箱|件|Cartons|ctns|pcs)', text, re.IGNORECASE)
        if pcs_match:
            pcs_cnt = int(pcs_match.group(1))

        dim_match = re.search(r'(\d+(?:\.\d+)?)\s*[*xX×]\s*(\d+(?:\.\d+)?)\s*[*xX×]\s*(\d+(?:\.\d+)?)', text)
        if dim_match:
            length_cm = float(dim_match.group(1))
            width_cm = float(dim_match.group(2))
            height_cm = float(dim_match.group(3))

        cbm_match = re.search(r'(?:CBM|體積)\s*:?\s*([\d,]+(?:\.\d+)?)', text, re.IGNORECASE)
        if cbm_match:
            cbm_val = float(cbm_match.group(1).replace(',', ''))

        if "快遞" in text or "Express" in text or "DHL" in text:
            divisor = 5000

        base_rate_match = re.search(r'(?:Air Freight|Freight Rate|運費)\s*:?\s*(?:USD|\$)?\s*([\d\.]+)', text, re.IGNORECASE)
        fsc_match = re.search(r'FSC\s*:?\s*(?:USD|\$)?\s*([\d\.]+)', text, re.IGNORECASE)
        ssc_match = re.search(r'SSC\s*:?\s*(?:USD|\$)?\s*([\d\.]+)', text, re.IGNORECASE)

        base_rate = float(base_rate_match.group(1)) if base_rate_match else 3.5
        fsc = float(fsc_match.group(1)) if fsc_match else 0.0
        ssc = float(ssc_match.group(1)) if ssc_match else 0.0

        unit_usd = base_rate + fsc + ssc
    else:
        usd_match = re.search(r'(?:Ocean Freight|Ocean|Freight)\s*:?\s*(?:USD|\$)?\s*([\d,]+(?:\.\d+)?)', text, re.IGNORECASE)
        unit_usd = float(usd_match.group(1).replace(',', '')) if usd_match else 2100.0

    local_keywords = [r'THC', r'Doc', r'Handling', r'Local Charge', r'本地雜費', r'提單費', r'卡車費']
    total_local_ntd = 0.0
    found_local = False

    for line in text.split('\n'):
        if any(re.search(kw, line, re.IGNORECASE) for kw in local_keywords):
            amount_match = re.search(r'(?:NTD|NT\$|\$|\:\s*)\s*([\d,]+)', line, re.IGNORECASE)
            if amount_match:
                val = float(amount_match.group(1).replace(',', ''))
                if val < 50000:
                    total_local_ntd += val
                    found_local = True

    if not found_local:
        total_local_ntd = 6500.0 if is_air else 12000.0

    days_match = re.search(r'(\d+)\s*(?:天|days)', text, re.IGNORECASE)
    days = int(days_match.group(1)) if days_match else (2 if is_air else 12)

    return {
        '廠商名稱': vendor,
        '櫃型': mode_label,
        '櫃數': containers_cnt,
        '毛重_KG': gw_kg,
        '箱數_PCS': pcs_cnt,
        '長_cm': length_cm,
        '寬_cm': width_cm,
        '高_cm': height_cm,
        '體積_CBM': cbm_val,
        '材積除數': divisor,
        '運費單價_USD': unit_usd,
        '匯率_USD_NTD': exchange_rate,
        '本地雜費_NTD': total_local_ntd,
        '配合報關行': customs_default,
        '預計航程_天': days
    }

# -----------------------------------------------------------------------------
# 2. Session State 初始化
# -----------------------------------------------------------------------------
if 'customs_df' not in st.session_state:
    st.session_state.customs_df = pd.DataFrame([
        {"報關行名稱": "OO報關行", "報關費_NTD": 1700, "第二櫃起單櫃報關費_NTD": 400, "傳輸費_NTD": 300},
        {"報關行名稱": "XX報關行", "報關費_NTD": 1500, "第二櫃起單櫃報關費_NTD": 450, "傳輸費_NTD": 400},
        {"報關行名稱": "OX報關行", "報關費_NTD": 1300, "第二櫃起單櫃報關費_NTD": 500, "傳輸費_NTD": 500}
    ])

if 'freight_list' not in st.session_state:
    st.session_state.freight_list = [
        parse_freight_text(sample_email_1),
        parse_freight_text(sample_email_2)
    ]

# -----------------------------------------------------------------------------
# 3. 分頁設計
# -----------------------------------------------------------------------------
tab1, tab2, tab3 = st.tabs([
    "⚡ 運費與報價自動比價 (含空運長寬高試算)", 
    "📦 供應商與貨代績效評鑑 (AHP/加權評分)", 
    "🤖 AI 國貿溝通秘書"
])

# =============================================================================
# TAB 1: 運費與報價自動比價
# =============================================================================
with tab1:
    st.header("⚡ 貨代 & 報關行 組合報價與總金額比價")
    
    st.subheader("📑 1. 報關行收費標準參考表")
    edited_customs_df = st.data_editor(
        st.session_state.customs_df,
        num_rows="dynamic",
        key="customs_editor",
        use_container_width=True,
        column_config={
            "報關費_NTD": st.column_config.NumberColumn("首櫃報關費 (NTD)", format="$%d"),
            "第二櫃起單櫃報關費_NTD": st.column_config.NumberColumn("第二櫃起單櫃報關費 (NTD)", format="$%d"),
            "傳輸費_NTD": st.column_config.NumberColumn("傳輸費 (NTD/票)", format="$%d", help="無論幾櫃，單票僅收一次")
        }
    )
    st.session_state.customs_df = edited_customs_df
    customs_map = edited_customs_df.set_index("報關行名稱").to_dict(orient="index")
    customs_options = list(customs_map.keys()) if customs_map else ["OO報關行"]

    st.divider()

    st.subheader("✉️ 2. 貼上貨代 Email 報價文字")
    col_input, col_preset = st.columns([2, 1])
    
    with col_input:
        raw_email_input = st.text_area(
            "請貼上 Email 報價文字（支援長寬高、尺寸、GW與CBM）：", 
            height=120,
            placeholder="範例：上海到基隆 40HQ 報價，數量：2櫃，Ocean Freight: USD 2,100..."
        )
        if st.button("🚀 執行 AI 文字解析並加入比較表"):
            if raw_email_input.strip():
                parsed_data = parse_freight_text(raw_email_input)
                st.session_state.freight_list.append(parsed_data)
                st.success(f"✅ 成功提取【{parsed_data['廠商名稱']}】報價！")
                st.rerun()

    with col_preset:
        st.write("**📋 範例載入：**")
        if st.button("載入捷達 (海運 - 2櫃)"):
            st.session_state.freight_list.append(parse_freight_text(sample_email_1))
            st.rerun()
        if st.button("載入萬達 (空運 - 60x50x40cm)"):
            st.session_state.freight_list.append(parse_freight_text(sample_email_2))
            st.rerun()
        if st.button("🔄 重置比價表"):
            st.session_state.freight_list = [
                parse_freight_text(sample_email_1),
                parse_freight_text(sample_email_2)
            ]
            st.rerun()

    st.divider()

    st.subheader("📋 3. 貨代組合報價與【計費重量】比價明細表")
    st.caption("""
    💡 **最新計費規則**：
    - **海運報關費**：第 1 櫃收取【首櫃報關費】，第 2 櫃起每櫃加收【第二櫃起單櫃報關費】。
    - **傳輸費**：以「單票」計算，**不會**因為櫃數增加而重複收取。
    - **空運計費**：比較「實際毛重」與「材積重量（尺寸或 CBM 換算）」，取較重者計價。
    """)

    df_freight = pd.DataFrame(st.session_state.freight_list)

    if not df_freight.empty:
        if '配合報關行' not in df_freight.columns:
            df_freight['配合報關行'] = customs_options[0] if customs_options else "OO報關行"

        def compute_air_metrics(row):
            if row['櫃型'] == 'Air Cargo':
                gw = float(row.get('毛重_KG', 0))
                pcs = float(row.get('箱數_PCS', 1))
                l = float(row.get('長_cm', 0))
                w = float(row.get('寬_cm', 0))
                h = float(row.get('高_cm', 0))
                cbm = float(row.get('體積_CBM', 0))
                divisor = float(row.get('材積除數', 6000))
                
                if divisor <= 0:
                    divisor = 6000

                if l > 0 and w > 0 and h > 0:
                    vol_weight = (l * w * h * pcs) / divisor
                elif cbm > 0:
                    vol_weight = cbm * (1000000.0 / divisor)
                else:
                    vol_weight = 0.0

                chargeable_weight = max(gw, vol_weight)
                is_light_cargo = vol_weight > gw
                return pd.Series([round(vol_weight, 2), round(chargeable_weight, 2), "⚠️ 泡貨(取材積)" if is_light_cargo else "⚖️ 重貨(取毛重)"])
            else:
                return pd.Series([0.0, 0.0, "🚢 海運整櫃"])

        df_freight[['材積重量_KG', '計費重量_KG', '計費型態']] = df_freight.apply(compute_air_metrics, axis=1)

        def calc_customs_fee(row):
            c_info = customs_map.get(row['配合報關行'], {})
            base_fee = c_info.get('報關費_NTD', 0)
            extra_fee = c_info.get('第二櫃起單櫃報關費_NTD', 0)
            
            if row['櫃型'] == 'Air Cargo':
                return base_fee 
            else:
                cnt = row['櫃數']
                if cnt <= 1:
                    return base_fee * max(1, cnt)
                else:
                    return base_fee + (cnt - 1) * extra_fee

        def calc_transfer_fee(row):
            c_info = customs_map.get(row['配合報關行'], {})
            return c_info.get('傳輸費_NTD', 0)

        df_freight['報關費_NTD'] = df_freight.apply(calc_customs_fee, axis=1)
        df_freight['傳輸費_NTD'] = df_freight.apply(calc_transfer_fee, axis=1)

        def calc_freight_ntd(row):
            if row['櫃型'] == 'Air Cargo':
                return row['計費重量_KG'] * row['運費單價_USD'] * row['匯率_USD_NTD']
            else:
                return row['運費單價_USD'] * row['櫃數'] * row['匯率_USD_NTD']

        df_freight['運費總額_NTD'] = df_freight.apply(calc_freight_ntd, axis=1)
        df_freight['總金額_NTD'] = df_freight['運費總額_NTD'] + df_freight['本地雜費_NTD'] + df_freight['報關費_NTD'] + df_freight['傳輸費_NTD']

        display_cols = [
            '廠商名稱', '櫃型', '櫃數', '毛重_KG', '箱數_PCS', '長_cm', '寬_cm', '高_cm', 
            '體積_CBM', '材積除數', '材積重量_KG', '計費重量_KG', '計費型態',
            '運費單價_USD', '匯率_USD_NTD', '運費總額_NTD', '本地雜費_NTD', 
            '配合報關行', '報關費_NTD', '傳輸費_NTD', '預計航程_天', '總金額_NTD'
        ]
        final_cols = [c for c in display_cols if c in df_freight.columns]

        edited_df = st.data_editor(
            df_freight[final_cols], 
            num_rows="dynamic", 
            key="freight_interactive_table",
            use_container_width=True,
            column_config={
                "櫃型": st.column_config.SelectboxColumn("運輸型態", options=["40HQ", "20GP", "Air Cargo"], required=True),
                "櫃數": st.column_config.NumberColumn("櫃數 (海運)", min_value=0, step=1),
                "毛重_KG": st.column_config.NumberColumn("毛重 (KG)", format="%.1f kg"),
                "箱數_PCS": st.column_config.NumberColumn("箱數", min_value=1, step=1),
                "長_cm": st.column_config.NumberColumn("長 (cm)", format="%.1f"),
                "寬_cm": st.column_config.NumberColumn("寬 (cm)", format="%.1f"),
                "高_cm": st.column_config.NumberColumn("高 (cm)", format="%.1f"),
                "體積_CBM": st.column_config.NumberColumn("體積 (CBM)", format="%.2f CBM"),
                "材積除數": st.column_config.SelectboxColumn("材積除數", options=[6000, 5000]),
                "材積重量_KG": st.column_config.NumberColumn("材積重量 (KG)", format="%.2f kg", disabled=True),
                "計費重量_KG": st.column_config.NumberColumn("計費重量 (KG)", format="%.2f kg", disabled=True),
                "計費型態": st.column_config.TextColumn("計費狀態", disabled=True),
                "運費單價_USD": st.column_config.NumberColumn("單價 (USD)", format="$%.2f"),
                "匯率_USD_NTD": st.column_config.NumberColumn("匯率", format="%.2f"),
                "運費總額_NTD": st.column_config.NumberColumn("運費總額 (NTD)", format="$%d", disabled=True),
                "本地雜費_NTD": st.column_config.NumberColumn("本地雜費 (NTD)", format="$%d"),
                "配合報關行": st.column_config.SelectboxColumn("配合報關行", options=customs_options, required=True),
                "報關費_NTD": st.column_config.NumberColumn("報關費 (NTD)", format="$%d", disabled=True, help="首櫃全額 + 第二櫃起累加"),
                "傳輸費_NTD": st.column_config.NumberColumn("傳輸費 (NTD)", format="$%d", disabled=True, help="單票收費一次"),
                "總金額_NTD": st.column_config.NumberColumn("【總金額_NTD】", format="$%d", disabled=True)
            }
        )

        # 覆蓋更新 session_state
        raw_columns = ['廠商名稱', '櫃型', '櫃數', '毛重_KG', '箱數_PCS', '長_cm', '寬_cm', '高_cm', '體積_CBM', '材積除數', '運費單價_USD', '匯率_USD_NTD', '本地雜費_NTD', '配合報關行', '預計航程_天']
        st.session_state.freight_list = edited_df[raw_columns].to_dict(orient='records')

        st.divider()

        col1, col2, col3 = st.columns(3)
        best_price_row = edited_df.loc[edited_df['總金額_NTD'].idxmin()]
        fastest_row = edited_df.loc[edited_df['預計航程_天'].idxmin()]
        
        col1.metric("💡 最便宜總金額方案", f"{best_price_row['廠商名稱']}", f"NT$ {best_price_row['總金額_NTD']:,.0f}")
        col2.metric("⚡ 最快時效方案", f"{fastest_row['廠商名稱']}", f"{fastest_row['預計航程_天']} 天")
        col3.metric("📊 平均總物流費用", f"NT$ {edited_df['總金額_NTD'].mean():,.0f}")

# =============================================================================
# TAB 2: 供應商與貨代績效評鑑
# =============================================================================
with tab2:
    st.header("🏢 供應商 / 貨代服務績效綜合評估")
    st.caption("💡 透過「交期準時率」、「品質/服務滿意度」與「價格競爭力」進行多維度加權評分，建立長期合作名單。")

    if 'supplier_eval_df' not in st.session_state:
        st.session_state.supplier_eval_df = pd.DataFrame([
            {"廠商名稱": "捷達國際物流", "類別": "貨代/船務", "交期準時率(%)": 95, "配合度與服務(1-10)": 9, "異常處理速度(1-10)": 8, "價格優勢(1-10)": 7},
            {"廠商名稱": "萬達通運", "類別": "貨代/船務", "交期準時率(%)": 90, "配合度與服務(1-10)": 8, "異常處理速度(1-10)": 9, "價格優勢(1-10)": 8},
            {"廠商名稱": "順豐/快遞專線", "類別": "快遞/專線", "交期準時率(%)": 98, "配合度與服務(1-10)": 9, "異常處理速度(1-10)": 7, "價格優勢(1-10)": 5},
            {"廠商名稱": "Alpha Global Inc.", "類別": "國外供應商", "交期準時率(%)": 85, "配合度與服務(1-10)": 7, "異常處理速度(1-10)": 6, "價格優勢(1-10)": 9}
        ])

    st.subheader("📊 1. 評分權重設定 (%)")
    w_col1, w_col2, w_col3, w_col4 = st.columns(4)
    w_delivery = w_col1.number_input("交期準時權重 (%)", value=30, step=5)
    w_service = w_col2.number_input("服務配合度權重 (%)", value=25, step=5)
    w_issue = w_col3.number_input("異常處理權重 (%)", value=25, step=5)
    w_price = w_col4.number_input("價格優勢權重 (%)", value=20, step=5)

    total_weight = w_delivery + w_service + w_issue + w_price
    if total_weight != 100:
        st.warning(f"⚠️ 當前權重總和為 {total_weight}%，建議調整為 100% 以確保計分精準。")

    st.subheader("📝 2. 廠商績效資料編輯表")
    edited_supp_df = st.data_editor(
        st.session_state.supplier_eval_df,
        num_rows="dynamic",
        key="supplier_editor",
        use_container_width=True,
        column_config={
            "交期準時率(%)": st.column_config.NumberColumn("交期準時率 (%)", min_value=0, max_value=100, format="%d%%"),
            "配合度與服務(1-10)": st.column_config.NumberColumn("配合度 (1-10)", min_value=1, max_value=10, step=1),
            "異常處理速度(1-10)": st.column_config.NumberColumn("異常處理 (1-10)", min_value=1, max_value=10, step=1),
            "價格優勢(1-10)": st.column_config.NumberColumn("價格優勢 (1-10)", min_value=1, max_value=10, step=1),
        }
    )
    st.session_state.supplier_eval_df = edited_supp_df

    if not edited_supp_df.empty:
        calc_df = edited_supp_df.copy()
        calc_df['綜合得分'] = (
            (calc_df['交期準時率(%)'] * (w_delivery / 100)) +
            (calc_df['配合度與服務(1-10)'] * 10 * (w_service / 100)) +
            (calc_df['異常處理速度(1-10)'] * 10 * (w_issue / 100)) +
            (calc_df['價格優勢(1-10)'] * 10 * (w_price / 100))
        ).round(1)

        def get_grade(score):
            if score >= 85: return "🥇 A級 (優良/優先合作)"
            elif score >= 70: return "🥈 B級 (合格/持續觀察)"
            else: return "⚠️ C級 (劣評/建議替換)"

        calc_df['評鑑等級'] = calc_df['綜合得分'].apply(get_grade)

        st.subheader("🏆 3. 綜合評鑑結果排行榜")
        st.dataframe(
            calc_df[['廠商名稱', '類別', '綜合得分', '評鑑等級']].sort_values(by='綜合得分', ascending=False),
            use_container_width=True
        )

# =============================================================================
# TAB 3: AI 國貿溝通秘書
# =============================================================================
with tab3:
    st.header("🤖 AI 國貿溝通秘書")
    
    if 'freight_list' in st.session_state and len(st.session_state.freight_list) > 0:
        fw_names = [item['廠商名稱'] for item in st.session_state.freight_list if '廠商名稱' in item]
        target_fw = st.selectbox("選擇談判目標貨代：", options=fw_names)
        
        fw_info = next((item for item in st.session_state.freight_list if item.get('廠商名稱') == target_fw), None)
        
        if fw_info and st.button("🚀 生成談判 Email"):
            local_fee = fw_info.get('本地雜費_NTD', 0)
            email_content = f"""主旨：【運費確認】關於近期報價 - 議價申請

{target_fw} 業務團隊 您好：

感謝貴公司提供的報價。經評估後發現本次【本地雜費】（NT$ {local_fee:,.0f}）稍微高出預算。
考量我們後續有穩定的出貨需求，請問該費用是否有微調或給予折扣的空間？

若價格能進行微調，我們將優先安排交給貴公司承攬，期待您的回覆！

順頌 商祺"""
            st.text_area("生成內容：", value=email_content, height=220)
    else:
        st.info("💡 請先至 TAB 1 解析或載入貨代報價資料，才能在此產生談判信件。")