import streamlit as st
import pandas as pd
import re
import unicodedata

# 頁面配置
st.set_page_config(
    page_title="進出口物流報價比價與評鑑系統",
    page_icon="🚢",
    layout="wide"
)

# 系統標題
st.title("🚢 進出口物流報價比價與評鑑系統")
st.caption("報價自動解析與比價 ➔ 貨代／報關行績效評鑑 ➔ AI 議價信生成")

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
單箱尺寸：50 x 40 x 40 cm
總毛重：120 KGS
Air Freight: NTD 85 / KG
FSC: NTD 15 / KG
Taiwan Local Charge: NTD 4,000
預計航程：2 天
匯率：1.0
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

sample_email_4 = """
【海運併櫃報價】Shanghai (PVG) to Keelung Port (散貨專案)
貨代：捷達國際物流
裝運類型：海運併櫃 (LCL Freight)
貨物明細：精密儀器零配件
包裝數量：8 木箱 (8 Cases)
總體積 (CBM): 3.5 CBM
總毛重 (GW): 1,250 KGS
Ocean Freight: USD 35.00 / CBM
CFS 併櫃費: NTD 2,800
THC 碼頭處理費: NTD 1,800
Doc Fee 文件費: NTD 1,500
Handling 手續費: NTD 1,200
預計航程 (Transit Time): 8 天
適用匯率 (USD/NTD): 32.00
"""

# 標籤與數字之間允許的「雜訊」：括號註解、冒號、空白（不跨行、不含數字）
_GAP = r'[^\d\n]{0,25}?'
_NUM = r'([\d,]+(?:\.\d+)?)'
_CUR = r'(USD|US\$|NTD|NT\$|TWD|\$)'


def _find_num(labels, text, default=None):
    """找「標籤 ... 數字」，容許括號、全半形冒號等雜訊。"""
    m = re.search(rf'(?:{labels}){_GAP}{_NUM}', text, re.IGNORECASE)
    return float(m.group(1).replace(',', '')) if m else default


def _find_charge(labels, text, rate, need_cur=False):
    """找費用並統一換算成 USD；need_cur=True 時數字前必須有幣別字樣。"""
    cur_part = _CUR if need_cur else _CUR + '?'
    m = re.search(rf'(?:{labels}){_GAP}{cur_part}\s*{_NUM}', text, re.IGNORECASE)
    if not m:
        return 0.0
    cur = (m.group(1) or 'USD').upper()
    val = float(m.group(2).replace(',', ''))
    if cur in ('NTD', 'NT$', 'TWD'):
        return val / rate if rate else val
    return val


def _find_cbm(text):
    """體積：先找「體積/Volume」標籤；再找「數字 + CBM」。不會把「USD 35 / CBM」的單價誤當體積。"""
    v = _find_num(r'體積|Volume', text)
    if v is None:
        m = re.search(rf'{_NUM}\s*CBM', text, re.IGNORECASE)
        v = float(m.group(1).replace(',', '')) if m else 0.0
    return v


_LOCAL_KW = (r'THC|Doc|Handling|Local Charge|本地雜費|提單費|卡車費|文件費|倉儲|換單費|'
             r'AWB Fee|Terminal Fee|CFS|併櫃費|手續費|碼頭處理費')


def _sum_local_charges(text, rate):
    """加總本地雜費（NTD）。不依賴換行，單行貼上也能逐項抓到；USD 項目會換成 NTD。"""
    total, found = 0.0, False
    for m in re.finditer(rf'(?:{_LOCAL_KW}){_GAP}{_CUR}?\s*{_NUM}', text, re.IGNORECASE):
        if re.search(r'報關費|Customs Clearance', m.group(0), re.IGNORECASE):
            continue
        cur = (m.group(1) or 'NTD').upper()
        val = float(m.group(2).replace(',', ''))
        if cur in ('USD', 'US$'):
            val *= rate
        if val < 50000:
            total += val
            found = True
    return total, found


def parse_freight_text(text):
    # 全形轉半形（：→:、（）→() 等）
    text = unicodedata.normalize('NFKC', text)

    # --- 運輸型態判斷 ---
    strong_air = bool(re.search(r'Air Freight|Air Cargo|\bAir\b|空運|Express|快遞|AWB|航空', text, re.IGNORECASE))
    weak_air = bool(re.search(r'PVG|TPE|HKG', text, re.IGNORECASE))
    is_lcl = bool(re.search(r'LCL|並櫃|併櫃|拼櫃|拼箱|散貨|CFS', text, re.IGNORECASE))
    is_sea = is_lcl or bool(re.search(r'海運|Ocean|Sea Freight|\b(?:20|40)\s*(?:GP|HQ)\b|FCL|櫃', text, re.IGNORECASE))
    is_air = strong_air or (weak_air and not is_sea)

    if is_air:
        mode_label = "Air Cargo"
    elif is_lcl:
        mode_label = "LCL"
    else:
        mode_label = "40HQ"

    if "捷達" in text or "Jieda" in text:
        vendor = "捷達國際物流"
        customs_default = "OO報關行"
    elif "萬達" in text or "Wanda" in text:
        vendor = "萬達通運"
        customs_default = "OX報關行"
    elif "快遞" in text or "DHL" in text or "順豐" in text:
        vendor = "順豐/快遞專線"
        customs_default = "AA空運報關行"
    else:
        lines = [l.strip() for l in text.split('\n') if l.strip()]
        vendor = lines[0][:15] if lines else "新貨代/報價單"
        customs_default = "AA空運報關行" if is_air else "OO報關行"

    if is_air:
        customs_default = "AA空運報關行"

    exchange_rate = _find_num(r'匯率|Exchange Rate|FX Rate|Rate of Exchange', text)
    if not exchange_rate:
        only_ntd = bool(re.search(r'NTD|NT\$|TWD', text)) and not re.search(r'USD|US\$', text)
        exchange_rate = 1.0 if only_ntd else 32.0

    if mode_label == "40HQ":
        ctn_match = re.search(r'(\d+)\s*(?:櫃|ctn|container)', text, re.IGNORECASE)
        containers_cnt = int(ctn_match.group(1)) if ctn_match else 1
    else:
        containers_cnt = 0

    gw_kg, cbm_val = 0.0, 0.0
    pcs_cnt = 1
    length_cm, width_cm, height_cm = 0.0, 0.0, 0.0
    divisor = 6000

    if is_air or is_lcl:
        gw_kg = _find_num(r'Gross Weight|GW|毛重|重量', text, 0.0)

        pcs_match = re.search(r'(\d+)\s*(?:木箱|箱|件|Cases?|Cartons?|ctns?|pcs|Pallets?|板)', text, re.IGNORECASE)
        if pcs_match:
            pcs_cnt = int(pcs_match.group(1))

        dim_match = re.search(r'(\d+(?:\.\d+)?)\s*[*xX×]\s*(\d+(?:\.\d+)?)\s*[*xX×]\s*(\d+(?:\.\d+)?)', text)
        if dim_match:
            length_cm = float(dim_match.group(1))
            width_cm = float(dim_match.group(2))
            height_cm = float(dim_match.group(3))

        cbm_val = _find_cbm(text)

    if is_air:
        if re.search(r'快遞|Express|DHL|FedEx|UPS', text, re.IGNORECASE):
            divisor = 5000

        base_rate = _find_charge(r'Air Freight|Freight Rate|空運費|運費', text, exchange_rate)
        fsc = _find_charge(r'FSC|燃油附加費', text, exchange_rate)
        ssc = _find_charge(r'SSC|安全附加費', text, exchange_rate)
        unit_usd = base_rate + fsc + ssc
    else:
        sea_labels = r'Ocean Freight|海運費|Sea Freight'
        unit_usd = (_find_charge(sea_labels, text, exchange_rate, need_cur=True)
                    or _find_charge(sea_labels + r'|Ocean', text, exchange_rate))
        if unit_usd == 0.0 and not is_lcl:
            unit_usd = 2100.0

    total_local_ntd, found_local = _sum_local_charges(text, exchange_rate)
    if not found_local:
        total_local_ntd = 2200.0 if is_air else 12000.0

    days_match = re.search(r'(\d+)\s*(?:天|days?)', text, re.IGNORECASE)
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
        {"報關行名稱": "AA空運報關行", "報關費_NTD": 1350, "第二櫃起單櫃報關費_NTD": 0, "傳輸費_NTD": 450},
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
            "報關費_NTD": st.column_config.NumberColumn("首櫃/單票報關費 (NTD)", format="$%d"),
            "第二櫃起單櫃報關費_NTD": st.column_config.NumberColumn("第二櫃起單櫃報關費 (NTD)", format="$%d"),
            "傳輸費_NTD": st.column_config.NumberColumn("傳輸費 (NTD/票)", format="$%d", help="無論幾櫃，單票僅收一次")
        }
    )
    st.session_state.customs_df = edited_customs_df
    customs_map = edited_customs_df.set_index("報關行名稱").to_dict(orient="index")
    customs_options = list(customs_map.keys()) if customs_map else ["AA空運報關行"]

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
        if st.button("載入萬達 (空運 - 50x40x40cm)"):
            st.session_state.freight_list.append(parse_freight_text(sample_email_2))
            st.rerun()
        if st.button("載入捷達 (海運併櫃 LCL)"):
            st.session_state.freight_list.append(parse_freight_text(sample_email_4))
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
    - **併櫃(LCL)計費**：單價為 USD/CBM，以 W/M 計費，取「體積 CBM」與「毛重(噸)」較大者；報關費、傳輸費以單票計算。
    """)

    df_freight = pd.DataFrame(st.session_state.freight_list)

    if not df_freight.empty:
        if '配合報關行' not in df_freight.columns:
            df_freight['配合報關行'] = customs_options[0] if customs_options else "AA空運報關行"

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
                return pd.Series([round(vol_weight, 2), round(chargeable_weight, 2), "⚠️ 泡貨(取材積)" if is_light_cargo else "⚖️ 重貨(取毛重)", 0.0])
            elif row['櫃型'] == 'LCL':
                gw = float(row.get('毛重_KG', 0))
                pcs = float(row.get('箱數_PCS', 1))
                l = float(row.get('長_cm', 0))
                w = float(row.get('寬_cm', 0))
                h = float(row.get('高_cm', 0))
                cbm = float(row.get('體積_CBM', 0))
                if cbm <= 0 and l > 0 and w > 0 and h > 0:
                    cbm = l * w * h * pcs / 1000000.0
                weight_ton = gw / 1000.0
                chargeable_cbm = max(cbm, weight_ton)
                label = "📦 併櫃(取體積CBM)" if cbm >= weight_ton else "⚖️ 併櫃(取重量噸)"
                return pd.Series([0.0, 0.0, label, round(chargeable_cbm, 3)])
            else:
                return pd.Series([0.0, 0.0, "🚢 海運整櫃", 0.0])

        df_freight[['材積重量_KG', '計費重量_KG', '計費型態', '計費CBM']] = df_freight.apply(compute_air_metrics, axis=1)

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
            elif row['櫃型'] == 'LCL':
                return row['計費CBM'] * row['運費單價_USD'] * row['匯率_USD_NTD']
            else:
                return row['運費單價_USD'] * row['櫃數'] * row['匯率_USD_NTD']

        df_freight['運費總額_NTD'] = df_freight.apply(calc_freight_ntd, axis=1)
        df_freight['總金額_NTD'] = df_freight['運費總額_NTD'] + df_freight['本地雜費_NTD'] + df_freight['報關費_NTD'] + df_freight['傳輸費_NTD']

        display_cols = [
            '廠商名稱', '櫃型', '櫃數', '毛重_KG', '箱數_PCS', '長_cm', '寬_cm', '高_cm', 
            '體積_CBM', '材積除數', '材積重量_KG', '計費重量_KG', '計費CBM', '計費型態',
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
                "櫃型": st.column_config.SelectboxColumn("運輸型態", options=["40HQ", "20GP", "LCL", "Air Cargo"], required=True),
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
                "計費CBM": st.column_config.NumberColumn("計費體積 (CBM)", format="%.2f", disabled=True, help="併櫃 W/M：體積CBM 與毛重(噸) 取較大者"),
                "計費型態": st.column_config.TextColumn("計費狀態", disabled=True),
                "運費單價_USD": st.column_config.NumberColumn("單價 (USD/KG｜USD/CBM｜USD/櫃)", format="$%.2f"),
                "匯率_USD_NTD": st.column_config.NumberColumn("匯率", format="%.2f"),
                "運費總額_NTD": st.column_config.NumberColumn("運費總額 (NTD)", format="$%d", disabled=True),
                "本地雜費_NTD": st.column_config.NumberColumn("本地雜費 (NTD)", format="$%d"),
                "配合報關行": st.column_config.SelectboxColumn("配合報關行", options=customs_options, required=True),
                "報關費_NTD": st.column_config.NumberColumn("報關費 (NTD)", format="$%d", disabled=True, help="首櫃全額 + 第二櫃起累加"),
                "傳輸費_NTD": st.column_config.NumberColumn("傳輸費 (NTD)", format="$%d", disabled=True, help="單票收費一次"),
                "總金額_NTD": st.column_config.NumberColumn("【總金額_NTD】", format="$%d", disabled=True)
            }
        )

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
# TAB 2: 供應商/貨代與報關行 分組獨立評鑑
# =============================================================================
with tab2:
    st.header("🏢 供應商 / 貨代 與 報關行 分組獨立績效評估")
    st.caption("💡 報關與物流屬性不同，本區塊分為「貨代與供應商」及「報關行」兩個獨立表格進行權重評分與排序。")

    # -------------------------------------------------------------------------
    # 預設資料初始化
    # -------------------------------------------------------------------------
    if "df_vendors" not in st.session_state:
        st.session_state.df_vendors = pd.DataFrame([
            {"廠商名稱": "捷達國際物流", "類別": "貨代/船務", "交期準時率(%)": 95, "服務與配合度(1-10)": 9, "異常處理(1-10)": 8, "價格優勢(1-10)": 7},
            {"廠商名稱": "萬達通運", "類別": "貨代/船務", "交期準時率(%)": 90, "服務與配合度(1-10)": 8, "異常處理(1-10)": 9, "價格優勢(1-10)": 8},
            {"廠商名稱": "順豐/快遞專線", "類別": "快遞/專線", "交期準時率(%)": 96, "服務與配合度(1-10)": 9, "異常處理(1-10)": 7, "價格優勢(1-10)": 5},
            {"廠商名稱": "Alpha Global Inc.", "類別": "國外供應商", "交期準時率(%)": 85, "服務與配合度(1-10)": 7, "異常處理(1-10)": 6, "價格優勢(1-10)": 9},
        ])

    if "df_customs_eval" not in st.session_state:
        st.session_state.df_customs_eval = pd.DataFrame([
            {"報關行名稱": "AA空運報關行", "順利當日放行率(%)": 98, "單證精確度/無錯單(1-10)": 9, "查驗與異常處理(1-10)": 9, "收費合理性(1-10)": 8},
            {"報關行名稱": "OO報關行", "順利當日放行率(%)": 92, "單證精確度/無錯單(1-10)": 8, "查驗與異常處理(1-10)": 8, "收費合理性(1-10)": 9},
            {"報關行名稱": "XX報關行", "順利當日放行率(%)": 85, "單證精確度/無錯單(1-10)": 7, "查驗與異常處理(1-10)": 7, "收費合理性(1-10)": 8},
        ])

    # =========================================================================
    # 第一部分：貨代與國外供應商評鑑
    # =========================================================================
    st.subheader("📦 表格一：貨代與國外供應商 績效評鑑 (Vendors & Logistics)")
    
    with st.expander("⚙️ 設定【貨代與供應商】評分權重 (%)", expanded=False):
        vc1, vc2, vc3, vc4 = st.columns(4)
        vw_del = vc1.number_input("交期準時權重 (%)", value=30, min_value=0, max_value=100, step=5, key="vw_del")
        vw_srv = vc2.number_input("服務配合度權重 (%)", value=25, min_value=0, max_value=100, step=5, key="vw_srv")
        vw_iss = vc3.number_input("異常處理權重 (%)", value=25, min_value=0, max_value=100, step=5, key="vw_iss")
        vw_prc = vc4.number_input("價格優勢權重 (%)", value=20, min_value=0, max_value=100, step=5, key="vw_prc")
        
        v_tot_w = vw_del + vw_srv + vw_iss + vw_prc
        v_norm = 100.0 / v_tot_w if v_tot_w > 0 else 1.0
        if v_tot_w != 100:
            st.warning(f"⚠️ 當前權重總和為 {v_tot_w}%，計算時會自動歸一化修正。")

    with st.expander("📖 評分標準參考（評分前請先閱讀）", expanded=False):
        st.markdown("""
**① 交期準時率 (%)**：統計期間內「準時到貨／準時出貨票數 ÷ 總票數 × 100」，直接填百分比。
建議基準：**95% 以上**＝優、**90–94%**＝良、**80–89%**＝待改善、**80% 以下**＝不佳。

**②～④ 為 1–10 分主觀評分，請依下表對照：**

| 分數 | ② 服務與配合度 | ③ 異常處理 | ④ 價格優勢 |
|---|---|---|---|
| **9–10** | 主動回報進度、當天回覆，能配合急單與臨時變更 | 事前預警，當日提出解決方案並負責善後 | 明顯低於市場行情（建議：比同類報價平均低 10% 以上） |
| **7–8** | 回覆及時，偶爾需要提醒 | 異常發生後即時通知並協助處理 | 略低於市場行情 |
| **5–6** | 需多次追問才有回覆 | 事後才通知，處理速度普通 | 與市場行情相當 |
| **3–4** | 回覆慢，常需自行追蹤進度 | 需催促才處理，結果不理想 | 略高於市場行情 |
| **1–2** | 無回應或常推諉 | 不處理或推卸責任 | 明顯偏高（建議：比平均高 10% 以上） |

**綜合得分與等級**：百分比項目直接計分，1–10 分項目 × 10 換算後，依上方權重加總。
**A 級 ≥ 85 分**（主力合作）、**B 級 70–84.9 分**（持續觀察）、**C 級 < 70 分**（考慮替換）。
**關鍵指標規則**：交期準時率 **低於 70%** 直接評為 C 級；**70–79%** 時，即使總分達 85 分以上，等級最高只給 B 級。
""")
        st.caption("※ 百分比與價格的建議門檻僅供參考，可依公司實際標準調整。")

    edited_v_df = st.data_editor(
        st.session_state.df_vendors,
        num_rows="dynamic",
        key="vendor_editor",
        use_container_width=True,
        column_config={
            "廠商名稱": st.column_config.TextColumn("廠商名稱", required=True),
            "類別": st.column_config.SelectboxColumn("類別", options=["貨代/船務", "快遞/專線", "國外供應商", "其他"], required=True),
            "交期準時率(%)": st.column_config.NumberColumn("交期準時率 (%)", min_value=0, max_value=100, format="%d%%", help="準時票數 ÷ 總票數 × 100。95%以上優、90–94良、80–89待改善、80以下不佳"),
            "服務與配合度(1-10)": st.column_config.NumberColumn("服務配合度 (1-10)", min_value=1, max_value=10, help="9–10 主動回報/當天回覆；5–6 需多次追問；1–2 無回應或推諉"),
            "異常處理(1-10)": st.column_config.NumberColumn("異常處理 (1-10)", min_value=1, max_value=10, help="9–10 事前預警並負責善後；5–6 事後才通知；1–2 不處理或推卸"),
            "價格優勢(1-10)": st.column_config.NumberColumn("價格優勢 (1-10)", min_value=1, max_value=10, help="9–10 明顯低於行情；5–6 與行情相當；1–2 明顯偏高"),
        }
    )
    st.session_state.df_vendors = edited_v_df

    if not edited_v_df.empty:
        v_calc = edited_v_df.copy()
        v_calc["綜合得分"] = (
            (v_calc["交期準時率(%)"].fillna(0) * (vw_del / 100)) +
            (v_calc["服務與配合度(1-10)"].fillna(0) * 10 * (vw_srv / 100)) +
            (v_calc["異常處理(1-10)"].fillna(0) * 10 * (vw_iss / 100)) +
            (v_calc["價格優勢(1-10)"].fillna(0) * 10 * (vw_prc / 100))
        ) * v_norm
        v_calc["綜合得分"] = v_calc["綜合得分"].round(1)

        def get_v_grade(score, on_time):
            # 關鍵指標：交期準時率 <70% 直接 C 級；70–79% 最高只給 B 級
            on_time = 0 if pd.isna(on_time) else on_time
            if on_time < 70:
                return "⚠️ C級 (準時率低於70%，直接降為C級)"
            if score >= 85:
                if on_time < 80:
                    return "🥈 B級 (準時率未達80%，由A級降級)"
                return "🥇 A級 (主力合作)"
            elif score >= 70: return "🥈 B級 (持續觀察)"
            else: return "⚠️ C級 (考慮替換)"

        v_calc["評鑑等級"] = v_calc.apply(lambda r: get_v_grade(r["綜合得分"], r["交期準時率(%)"]), axis=1)
        v_sorted = v_calc.sort_values(by="綜合得分", ascending=False)

        st.write("🏆 **貨代/供應商 評鑑排行榜：**")
        st.dataframe(
            v_sorted[["廠商名稱", "類別", "交期準時率(%)", "綜合得分", "評鑑等級"]],
            use_container_width=True,
            hide_index=True
        )

    st.divider()

    # =========================================================================
    # 第二部分：報關行專用評鑑
    # =========================================================================
    st.subheader("🛃 表格二：專用配合報關行 績效評鑑 (Customs Brokers)")
    st.caption("💡 報關行獨立指標：關注**通關速度**、**報關單證正確率**與**海關查驗協助**。")

    with st.expander("⚙️ 設定【報關行】專用評分權重 (%)", expanded=False):
        cc1, cc2, cc3, cc4 = st.columns(4)
        cw_rel = cc1.number_input("當日放行率權重 (%)", value=35, min_value=0, max_value=100, step=5, key="cw_rel")
        cw_doc = cc2.number_input("單證精確度權重 (%)", value=25, min_value=0, max_value=100, step=5, key="cw_doc")
        cw_chk = cc3.number_input("查驗/異常處理權重 (%)", value=25, min_value=0, max_value=100, step=5, key="cw_chk")
        cw_fee = cc4.number_input("收費合理性權重 (%)", value=15, min_value=0, max_value=100, step=5, key="cw_fee")

        c_tot_w = cw_rel + cw_doc + cw_chk + cw_fee
        c_norm = 100.0 / c_tot_w if c_tot_w > 0 else 1.0
        if c_tot_w != 100:
            st.warning(f"⚠️ 當前權重總和為 {c_tot_w}%，計算時會自動歸一化修正。")

    with st.expander("📖 評分標準參考（評分前請先閱讀）", expanded=False):
        st.markdown("""
**① 順利當日放行率 (%)**：統計期間內「投單後未被扣關、當日放行票數 ÷ 總票數 × 100」，直接填百分比。
建議基準：**95% 以上**＝優、**90–94%**＝良、**80–89%**＝待改善、**80% 以下**＝不佳。

**②～④ 為 1–10 分主觀評分，請依下表對照：**

| 分數 | ② 單證精確度／無錯單 | ③ 查驗與異常處理 | ④ 收費合理性 |
|---|---|---|---|
| **9–10** | 近期無錯單、免補件，HS Code 歸類正確 | 遇抽驗或開櫃能即時配合，主動協調海關 | 低於市場行情，且無額外加收項目 |
| **7–8** | 偶有小錯，可當日更正不影響放行 | 配合順暢，回覆及時 | 價格合理，費用項目透明 |
| **5–6** | 時有補件，偶爾影響通關時程 | 需催促才配合，處理速度普通 | 與市場行情相當 |
| **3–4** | 錯單頻繁，造成延誤或罰款風險 | 協調緩慢，導致貨物延誤 | 偏高或常有額外加收 |
| **1–2** | 重大錯誤造成罰款或退運 | 難以聯繫或不配合查驗 | 明顯偏高或收費不透明 |

**綜合得分與等級**：百分比項目直接計分，1–10 分項目 × 10 換算後，依上方權重加總。
**A 級 ≥ 85 分**（優先指定報關）、**B 級 70–84.9 分**（維持配合）、**C 級 < 70 分**（建議更換）。
**關鍵指標規則**：當日放行率 **低於 70%** 直接評為 C 級；**70–79%** 時，即使總分達 85 分以上，等級最高只給 B 級；兩者清關建議都會亮紅燈。
""")
        st.caption("※ 百分比的建議門檻僅供參考，可依公司實際標準調整。")

    edited_c_df = st.data_editor(
        st.session_state.df_customs_eval,
        num_rows="dynamic",
        key="customs_eval_editor",
        use_container_width=True,
        column_config={
            "報關行名稱": st.column_config.TextColumn("報關行名稱", required=True),
            "順利當日放行率(%)": st.column_config.NumberColumn("當日放行率 (%)", min_value=0, max_value=100, format="%d%%", help="當日放行票數 ÷ 總票數 × 100。95%以上優、90–94良、80–89待改善、80以下不佳"),
            "單證精確度/無錯單(1-10)": st.column_config.NumberColumn("單證精確度 (1-10)", min_value=1, max_value=10, help="9–10 無錯單免補件；5–6 時有補件；1–2 重大錯誤致罰款或退運"),
            "查驗與異常處理(1-10)": st.column_config.NumberColumn("查驗應變力 (1-10)", min_value=1, max_value=10, help="9–10 抽驗/開櫃即時配合；5–6 需催促；1–2 難聯繫或不配合"),
            "收費合理性(1-10)": st.column_config.NumberColumn("收費合理性 (1-10)", min_value=1, max_value=10, help="9–10 低於行情且無額外加收；5–6 與行情相當；1–2 明顯偏高或不透明"),
        }
    )
    st.session_state.df_customs_eval = edited_c_df

    if not edited_c_df.empty:
        c_calc = edited_c_df.copy()
        c_calc["綜合得分"] = (
            (c_calc["順利當日放行率(%)"].fillna(0) * (cw_rel / 100)) +
            (c_calc["單證精確度/無錯單(1-10)"].fillna(0) * 10 * (cw_doc / 100)) +
            (c_calc["查驗與異常處理(1-10)"].fillna(0) * 10 * (cw_chk / 100)) +
            (c_calc["收費合理性(1-10)"].fillna(0) * 10 * (cw_fee / 100))
        ) * c_norm
        c_calc["綜合得分"] = c_calc["綜合得分"].round(1)

        def get_c_grade(score, rel):
            # 關鍵指標：當日放行率 <70% 直接 C 級；70–79% 最高只給 B 級
            rel = 0 if pd.isna(rel) else rel
            if rel < 70:
                return "⚠️ C級 (放行率低於70%，直接降為C級)"
            if score >= 85:
                if rel < 80:
                    return "🥈 B級 (放行率未達80%，由A級降級)"
                return "🥇 A級 (優先指定報關)"
            elif score >= 70: return "🥈 B級 (維持配合)"
            else: return "⚠️ C級 (錯單率高/建議更換)"

        def get_c_advice(row):
            score = row["綜合得分"]
            rel = row["順利當日放行率(%)"]
            doc = row["單證精確度/無錯單(1-10)"]
            rel = 0 if pd.isna(rel) else rel
            doc = 0 if pd.isna(doc) else doc

            # 先檢查關鍵指標，避免其他項目的高分掩蓋放行率問題
            if rel < 70:
                return "🔴 當日放行率低於70%，已列為C級。貨物常被卡關，建議儘速釐清原因並洽詢備用報關行。"
            if rel < 80:
                return "🔴 當日放行率低於80%，貨物常被卡關，需先釐清原因（文件不齊或查驗頻繁）再決定是否續用。"
            if score >= 85:
                if rel < 90:
                    return "🟡 整體表現佳，但當日放行率仍有改善空間，建議追蹤卡關原因。"
                elif doc <= 7:
                    return "🟡 整體表現佳，但單證精確度偏低，建議加強投單前核對。"
                return "🟢 清關效率極佳，建議作為主要報關行並爭取優先通關服務。"
            elif score >= 70:
                if rel < 90:
                    return "🟡 當日放行率偏低，需關注是否常因文件齊全度問題導致卡關。"
                elif doc <= 7:
                    return "🟡 錯單率偏高，建議加強投單前的 HS Code 與單證核對。"
                else:
                    return "🟡 表現合格，維持定期評鑑。"
            else:
                return "🔴 通關品質欠佳，建議洽詢其他備用報關行進行替換。"

        c_calc["評鑑等級"] = c_calc.apply(lambda r: get_c_grade(r["綜合得分"], r["順利當日放行率(%)"]), axis=1)
        c_calc["清關改善建議"] = c_calc.apply(get_c_advice, axis=1)
        c_sorted = c_calc.sort_values(by="綜合得分", ascending=False)

        st.write("🏆 **報關行 評鑑排行榜：**")
        st.dataframe(
            c_sorted[["報關行名稱", "順利當日放行率(%)", "綜合得分", "評鑑等級", "清關改善建議"]],
            use_container_width=True,
            hide_index=True
        )

        # 匯出兩者合併報告或單獨匯出
        c_csv = c_sorted.to_csv(index=False).encode("utf-8-sig")
        st.download_button(
            label="📥 下載報關行評鑑報告 (CSV)",
            data=c_csv,
            file_name="customs_broker_evaluation_report.csv",
            mime="text/csv",
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