import streamlit as st
import streamlit.components.v1 as components
import yfinance as yf
import pandas as pd
import ta
import plotly.graph_objects as go
from concurrent.futures import ThreadPoolExecutor, as_completed
import warnings

warnings.filterwarnings('ignore')

# --- SAYFA YAPILANDIRMASI ---
st.set_page_config(
    page_title="Sermaye Terminali v16.0",
    page_icon="🖤",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- FINTABLES STİL CSS OVERRIDE ---
st.markdown("""
    <style>
    header[data-testid="stHeader"] {
        display: none !important;
        visibility: hidden !important;
        height: 0px !important;
    }
    .block-container {
        padding-top: 1rem !important;
        padding-bottom: 2rem !important;
    }
    .stApp {
        background-color: #0b0b0e !important;
        color: #ffffff !important;
    }

    /* SOL MENÜ (SIDEBAR) - FINTABLES TARZI SEÇİM BARLARI */
    [data-testid="stSidebar"] {
        background-color: #121216 !important;
        border-right: 1px solid #22222a !important;
    }
    [data-testid="stSidebar"] * {
        color: #ffffff !important;
    }
    
    [data-testid="stSidebar"] div[role="radiogroup"] {
        gap: 6px !important;
    }
    [data-testid="stSidebar"] div[role="radiogroup"] label {
        background-color: #181820 !important;
        border: 1px solid #2b2b38 !important;
        border-radius: 6px !important;
        padding: 10px 14px !important;
        margin: 0 !important;
        cursor: pointer !important;
        display: flex !important;
        align-items: center !important;
        width: 100% !important;
        transition: all 0.2s ease !important;
    }
    [data-testid="stSidebar"] div[role="radiogroup"] input[type="radio"] {
        display: none !important;
    }
    [data-testid="stSidebar"] div[role="radiogroup"] label div {
        background: transparent !important;
    }
    [data-testid="stSidebar"] div[role="radiogroup"] label p,
    [data-testid="stSidebar"] div[role="radiogroup"] label span {
        color: #f1f5f9 !important;
        font-weight: 500 !important;
        font-size: 0.92rem !important;
        margin: 0 !important;
    }
    [data-testid="stSidebar"] div[role="radiogroup"] label:hover {
        border-color: #38bdf8 !important;
        background-color: #222230 !important;
    }
    [data-testid="stSidebar"] div[role="radiogroup"] label:hover p,
    [data-testid="stSidebar"] div[role="radiogroup"] label:hover span {
        color: #38bdf8 !important;
    }
    [data-testid="stSidebar"] div[role="radiogroup"] label[data-checked="true"] {
        background-color: #1e293b !important;
        border-color: #38bdf8 !important;
    }
    [data-testid="stSidebar"] div[role="radiogroup"] label[data-checked="true"] p,
    [data-testid="stSidebar"] div[role="radiogroup"] label[data-checked="true"] span {
        color: #38bdf8 !important;
        font-weight: 700 !important;
    }

    /* AÇILIR MENÜ (EXPANDER) */
    div[data-testid="stExpander"] {
        background-color: #18181e !important;
        border: 1px solid #2b2b36 !important;
        border-radius: 8px !important;
        margin-bottom: 10px !important;
    }
    div[data-testid="stExpander"] details summary {
        background-color: #18181e !important;
        color: #ffffff !important;
        border-radius: 8px !important;
    }
    div[data-testid="stExpander"] details summary * {
        color: #ffffff !important;
        font-weight: bold !important;
    }

    /* BİLANÇO TABLOLARI BEYAZ YAZI DÜZELTMESİ */
    [data-testid="stTable"] {
        background-color: #14141a !important;
    }
    [data-testid="stTable"] th {
        color: #a0a0ab !important;
        background-color: #181822 !important;
        font-weight: 600 !important;
    }
    [data-testid="stTable"] td {
        color: #ffffff !important;
        background-color: #14141a !important;
        border-bottom: 1px solid #22222c !important;
    }

    /* BUTONLAR */
    .stButton > button, .stDownloadButton > button {
        background-color: #1e1e28 !important;
        color: #ffffff !important;
        border: 1px solid #333344 !important;
        border-radius: 8px !important;
        font-weight: 600 !important;
        padding: 8px 16px !important;
        width: 100% !important;
    }
    .stButton > button:hover, .stDownloadButton > button:hover {
        background-color: #282836 !important;
        border-color: #38bdf8 !important;
        color: #38bdf8 !important;
    }

    /* SEKMELER */
    .stTabs [data-baseweb="tab-list"] {
        background-color: #121216 !important;
        padding: 6px !important;
        border-radius: 8px !important;
        border: 1px solid #22222a !important;
    }
    .stTabs [data-baseweb="tab"] {
        color: #a0a0ab !important;
        font-weight: 600 !important;
        background-color: transparent !important;
    }
    .stTabs [aria-selected="true"] {
        background-color: #22222c !important;
        color: #38bdf8 !important;
        border-bottom: 2px solid #38bdf8 !important;
    }

    /* HOVER TOOLTIP POP-UP MİMARİSİ */
    .tooltip-container {
        position: relative;
        display: block;
        cursor: pointer;
        width: 100%;
    }
    .fintables-card-tt {
        background-color: #16161c;
        border: 1px solid #262632;
        border-radius: 8px;
        padding: 12px 16px;
        transition: all 0.2s ease;
    }
    .fintables-card-tt:hover {
        border-color: #38bdf8;
        background-color: #1a1a22;
    }
    
    .tooltip-container .tooltip-box {
        visibility: hidden;
        width: 320px;
        background-color: #14141a;
        color: #ffffff;
        text-align: left;
        border-radius: 8px;
        padding: 12px 14px;
        border: 1px solid #333348;
        box-shadow: 0px 10px 25px rgba(0,0,0,0.85);
        position: absolute;
        z-index: 1000;
        bottom: 105%;
        left: 50%;
        transform: translateX(-50%);
        opacity: 0;
        transition: opacity 0.2s ease-in-out, visibility 0.2s ease-in-out;
        font-size: 0.83rem;
        line-height: 1.5;
    }
    .tooltip-container .tooltip-box::after {
        content: "";
        position: absolute;
        top: 100%;
        left: 50%;
        margin-left: -6px;
        border-width: 6px;
        border-style: solid;
        border-color: #14141a transparent transparent transparent;
    }
    .tooltip-container:hover .tooltip-box {
        visibility: visible;
        opacity: 1;
    }

    .tt-row {
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: 4px 0;
        border-bottom: 1px solid #22222e;
    }
    .tt-row:last-child { border-bottom: none; }
    .tt-label { color: #a0a0ab; font-weight: 500; }
    .tt-val-pos {
        color: #34d399; font-weight: bold;
        background-color: rgba(52, 211, 153, 0.12);
        padding: 2px 7px; border-radius: 4px; border: 1px solid rgba(52, 211, 153, 0.3);
    }
    .tt-val-neg {
        color: #f87171; font-weight: bold;
        background-color: rgba(248, 113, 113, 0.12);
        padding: 2px 7px; border-radius: 4px; border: 1px solid rgba(248, 113, 113, 0.3);
    }
    .tt-val-neutral {
        color: #94a3b8; font-weight: bold;
        background-color: rgba(148, 163, 184, 0.12);
        padding: 2px 7px; border-radius: 4px;
    }
    </style>
""", unsafe_allow_html=True)

st.title("🖤 Sermaye & Değerleme Terminali v16.0")
st.caption("BİST & Küresel Piyasalar - Profesyonel Borsa Terminali")

def get_tradingview_symbol(hisse_kodu):
    clean_code = hisse_kodu.replace('.IS', '').upper().replace('-', '.')
    if '.IS' in hisse_kodu or hisse_kodu.endswith('.IS'):
        return f"BIST:{clean_code}"
    return clean_code

def format_para(val):
    if val is None or pd.isna(val): return "N/A"
    abs_v = abs(val)
    if abs_v >= 1e9: return f"{val / 1e9:.2f} mr"
    elif abs_v >= 1e6: return f"{val / 1e6:.2f} mn"
    return f"{val:,.0f}"

@st.cache_data(ttl=3600, show_spinner=False)
def fetch_full_stock_data(hisse_kodu):
    try:
        formatted_code = hisse_kodu.replace('.', '-') if not hisse_kodu.endswith('.IS') else hisse_kodu
        ticker = yf.Ticker(formatted_code)
        financials = ticker.quarterly_financials
        balance_sheet = ticker.quarterly_balance_sheet
        info = ticker.info or {}
        history = ticker.history(period="1y")
        return financials, balance_sheet, info, history
    except Exception:
        return None, None, None, None

def get_row(df, possible_keys):
    if df is None or df.empty: return None
    for k in possible_keys:
        if k in df.index: return df.loc[k]
    return None

def hesapla_fintables_detayli_degisimler(financials):
    rev_s = get_row(financials, ['Total Revenue', 'Operating Revenue'])
    gross_s = get_row(financials, ['Gross Profit'])
    ebitda_s = get_row(financials, ['EBITDA', 'Normalized EBITDA', 'Operating Income'])
    net_inc_s = get_row(financials, ['Net Income', 'Net Income Common Stockholders'])

    degisimler = {
        'satis_yillik': 'N/A', 'satis_ceyreklik': 'N/A',
        'favok_yillik': 'N/A', 'favok_ceyreklik': 'N/A',
        'net_kar_yillik': 'N/A', 'net_kar_ceyreklik': 'N/A',
        'net_marj_yillik_bps': 'N/A', 'net_marj_ceyreklik_bps': 'N/A',
        'brut_marj_yillik_bps': 'N/A', 'brut_marj_ceyreklik_bps': 'N/A',
        'favok_marj_yillik_bps': 'N/A', 'favok_marj_ceyreklik_bps': 'N/A',
    }

    if rev_s is not None and len(rev_s) >= 4:
        r0, r1, r3 = rev_s.iloc[0], rev_s.iloc[1], rev_s.iloc[3]
        if r3 and r3 != 0: degisimler['satis_yillik'] = f"%{(r0 - r3) / abs(r3) * 100:+.1f}"
        if r1 and r1 != 0: degisimler['satis_ceyreklik'] = f"%{(r0 - r1) / abs(r1) * 100:+.1f}"

        if ebitda_s is not None and len(ebitda_s) >= 4:
            e0, e1, e3 = ebitda_s.iloc[0], ebitda_s.iloc[1], ebitda_s.iloc[3]
            if e3 and e3 != 0: degisimler['favok_yillik'] = f"%{(e0 - e3) / abs(e3) * 100:+.1f}"
            if e1 and e1 != 0: degisimler['favok_ceyreklik'] = f"%{(e0 - e1) / abs(e1) * 100:+.1f}"

            m0 = (e0 / r0) * 100 if r0 else 0
            m1 = (e1 / r1) * 100 if r1 else 0
            m3 = (e3 / r3) * 100 if r3 else 0
            degisimler['favok_marj_yillik_bps'] = f"{int((m0 - m3) * 100):+} bps"
            degisimler['favok_marj_ceyreklik_bps'] = f"{int((m0 - m1) * 100):+} bps"

        if gross_s is not None and len(gross_s) >= 4:
            g0, g1, g3 = gross_s.iloc[0], gross_s.iloc[1], gross_s.iloc[3]
            bm0 = (g0 / r0) * 100 if r0 else 0
            bm1 = (g1 / r1) * 100 if r1 else 0
            bm3 = (g3 / r3) * 100 if r3 else 0
            degisimler['brut_marj_yillik_bps'] = f"{int((bm0 - bm3) * 100):+} bps"
            degisimler['brut_marj_ceyreklik_bps'] = f"{int((bm0 - bm1) * 100):+} bps"

        if net_inc_s is not None and len(net_inc_s) >= 4:
            n0, n1, n3 = net_inc_s.iloc[0], net_inc_s.iloc[1], net_inc_s.iloc[3]
            if n3 and n3 != 0: degisimler['net_kar_yillik'] = f"%{(n0 - n3) / abs(n3) * 100:+.1f}"
            if n1 and n1 != 0: degisimler['net_kar_ceyreklik'] = f"%{(n0 - n1) / abs(n1) * 100:+.1f}"
            nm0 = (n0 / r0) * 100 if r0 else 0
            nm1 = (n1 / r1) * 100 if r1 else 0
            nm3 = (n3 / r3) * 100 if r3 else 0
            degisimler['net_marj_yillik_bps'] = f"{int((nm0 - nm3) * 100):+} bps"
            degisimler['net_marj_ceyreklik_bps'] = f"{int((nm0 - nm1) * 100):+} bps"

    return degisimler

def hesapla_fintables_karne_detayli(financials, balance_sheet, info):
    karlilik_detay, buyume_detay, borcluluk_detay = [], [], []

    rev_series = get_row(financials, ['Total Revenue', 'Operating Revenue'])
    net_inc_series = get_row(financials, ['Net Income', 'Net Income Common Stockholders'])
    ebitda_series = get_row(financials, ['EBITDA', 'Normalized EBITDA', 'Operating Income'])
    
    curr_assets = get_row(balance_sheet, ['Current Assets'])
    curr_liab = get_row(balance_sheet, ['Current Liabilities'])
    total_debt = get_row(balance_sheet, ['Total Debt', 'Financial Debt'])
    cash = get_row(balance_sheet, ['Cash And Cash Equivalents'])
    total_assets = get_row(balance_sheet, ['Total Assets'])

    ca_val = curr_assets.iloc[0] if curr_assets is not None and not curr_assets.empty else 0
    cl_val = curr_liab.iloc[0] if curr_liab is not None and not curr_liab.empty else 0
    td_val = total_debt.iloc[0] if total_debt is not None and not total_debt.empty else 0
    cash_val = cash.iloc[0] if cash is not None and not cash.empty else 0
    ta_val = total_assets.iloc[0] if total_assets is not None and not total_assets.empty else 1

    net_borc = td_val - cash_val
    isletme_sermayesi = ca_val - cl_val
    fin_borcluluk_orani = (td_val / ta_val) * 100 if ta_val else 0
    cari_oran = (ca_val / cl_val) if cl_val else 0

    borcluluk_detay.append(("İşletme Sermayesi > 0", isletme_sermayesi > 0))
    borcluluk_detay.append(("Finansal Borçluluk < %50", fin_borcluluk_orani < 50))
    borcluluk_detay.append(("Net Borç < 0 (Nakit Fazlası)", net_borc < 0))
    borcluluk_detay.append(("Dönen Varlıklar > Finansal Borç", ca_val > td_val))
    borcluluk_detay.append(("Cari Oran > 1.5", cari_oran > 1.5))
    borcluluk_detay.append(("Düşük Finansal Borç Riski", fin_borcluluk_orani < 30 or net_borc < 0))

    roe = (info.get('returnOnEquity') or 0) * 100
    net_marj = (info.get('profitMargins') or 0) * 100
    op_marj = (info.get('operatingMargins') or 0) * 100

    karlilik_detay.append(("Özkaynak Kârlılığı (ROE) > %20", roe > 20))
    karlilik_detay.append(("Özkaynak Kârlılığı (ROE) > %10", roe > 10))
    karlilik_detay.append(("Net Kâr Marjı > %15", net_marj > 15))
    karlilik_detay.append(("Net Kâr Marjı > %5", net_marj > 5))
    karlilik_detay.append(("Faaliyet Marjı > %10", op_marj > 10))
    karlilik_detay.append(("Brüt Kâr Marjı > %15", (info.get('grossMargins') or 0) * 100 > 15))

    buyume_detay.append(("Satışlar Çeyreklik Artış", rev_series is not None and len(rev_series) >= 2 and rev_series.iloc[0] > rev_series.iloc[1]))
    buyume_detay.append(("Satışlar Yıllık Artış", rev_series is not None and len(rev_series) >= 4 and rev_series.iloc[0] > rev_series.iloc[3]))
    buyume_detay.append(("FAVÖK Çeyreklik Artış", ebitda_series is not None and len(ebitda_series) >= 2 and ebitda_series.iloc[0] > ebitda_series.iloc[1]))
    buyume_detay.append(("FAVÖK Yıllık Artış", ebitda_series is not None and len(ebitda_series) >= 4 and ebitda_series.iloc[0] > ebitda_series.iloc[3]))
    buyume_detay.append(("Net Kâr Çeyreklik Artış", net_inc_series is not None and len(net_inc_series) >= 2 and net_inc_series.iloc[0] > net_inc_series.iloc[1]))
    buyume_detay.append(("Net Kâr Yıllık Artış", net_inc_series is not None and len(net_inc_series) >= 4 and net_inc_series.iloc[0] > net_inc_series.iloc[3]))

    return {
        'karlilik': sum(1 for _, v in karlilik_detay if v),
        'buyume': sum(1 for _, v in buyume_detay if v),
        'borcluluk': sum(1 for _, v in borcluluk_detay if v),
        'karlilik_detay': karlilik_detay,
        'buyume_detay': buyume_detay,
        'borcluluk_detay': borcluluk_detay
    }

def render_karne_cards_with_tooltip(karne, degisimler):
    def build_karne_tt(title, skor, detay_list):
        items_html = ""
        for name, val in detay_list:
            icon = '<span style="color:#34d399;font-weight:bold;">✓</span>' if val else '<span style="color:#f87171;font-weight:bold;">✗</span>'
            items_html += f'<div class="tt-row"><span class="tt-label">{name}</span>{icon}</div>'
        
        return f'''
        <div class="tooltip-container">
            <div class="fintables-card-tt">
                <div style="color:#a0a0ab;font-size:0.85rem;">{title}</div>
                <div style="color:#38bdf8;font-weight:700;font-size:1.6rem;margin-top:2px;">{skor} / 6</div>
            </div>
            <div class="tooltip-box">
                <div style="font-weight:bold;margin-bottom:6px;border-bottom:1px solid #333344;padding-bottom:4px;color:#38bdf8;">
                    {title} Kriterleri ({skor}/6)
                </div>
                {items_html}
            </div>
        </div>
        '''

    def build_degisim_tt():
        def fmt_val(v_str):
            if v_str == 'N/A': return f'<span class="tt-val-neutral">{v_str}</span>'
            if '-' in str(v_str): return f'<span class="tt-val-neg">{v_str}</span>'
            return f'<span class="tt-val-pos">{v_str}</span>'

        return f'''
        <div class="tooltip-container">
            <div class="fintables-card-tt" style="border-color:#38bdf8;">
                <div style="color:#a0a0ab;font-size:0.85rem;">🔍 Çeyreklik & Yıllık Marj Analizi</div>
                <div style="color:#38bdf8;font-weight:700;font-size:1.0rem;margin-top:6px;">Detayları Gör</div>
            </div>
            <div class="tooltip-box" style="width:310px;">
                <div style="font-weight:bold;margin-bottom:6px;border-bottom:1px solid #333344;padding-bottom:4px;color:#38bdf8;">
                    Çeyreklik & Yıllık Marj Değişimleri
                </div>
                <div class="tt-row"><span class="tt-label">Satışlar Yıllık Değişim</span>{fmt_val(degisimler['satis_yillik'])}</div>
                <div class="tt-row"><span class="tt-label">Satışlar Çeyreklik Değişim</span>{fmt_val(degisimler['satis_ceyreklik'])}</div>
                <div class="tt-row"><span class="tt-label">FAVÖK Yıllık Değişim</span>{fmt_val(degisimler['favok_yillik'])}</div>
                <div class="tt-row"><span class="tt-label">FAVÖK Çeyreklik Değişim</span>{fmt_val(degisimler['favok_ceyreklik'])}</div>
                <div class="tt-row"><span class="tt-label">Brüt Kar Marjı Yıllık Değişim</span>{fmt_val(degisimler['brut_marj_yillik_bps'])}</div>
                <div class="tt-row"><span class="tt-label">Brüt Kar Marjı Çeyreklik Değişim</span>{fmt_val(degisimler['brut_marj_ceyreklik_bps'])}</div>
                <div class="tt-row"><span class="tt-label">FAVÖK Marjı Yıllık Değişim</span>{fmt_val(degisimler['favok_marj_yillik_bps'])}</div>
                <div class="tt-row"><span class="tt-label">FAVÖK Marjı Çeyreklik Değişim</span>{fmt_val(degisimler['favok_marj_ceyreklik_bps'])}</div>
                <div class="tt-row"><span class="tt-label">Net Kar Marjı Yıllık Değişim</span>{fmt_val(degisimler['net_marj_yillik_bps'])}</div>
                <div class="tt-row"><span class="tt-label">Net Kar Marjı Çeyreklik Değişim</span>{fmt_val(degisimler['net_marj_ceyreklik_bps'])}</div>
            </div>
        </div>
        '''

    c1, c2, c3, c4 = st.columns(4)
    with c1: st.markdown(build_karne_tt("Kârlılık Karnesi", karne['karlilik'], karne['karlilik_detay']), unsafe_allow_html=True)
    with c2: st.markdown(build_karne_tt("Büyüme Karnesi", karne['buyume'], karne['buyume_detay']), unsafe_allow_html=True)
    with c3: st.markdown(build_karne_tt("Borçluluk Karnesi", karne['borcluluk'], karne['borcluluk_detay']), unsafe_allow_html=True)
    with c4: st.markdown(build_degisim_tt(), unsafe_allow_html=True)

def ciz_koyu_cubuk_grafik(data_series, baslik, renk="#38bdf8"):
    if data_series is None or data_series.empty: return
    df_plot = pd.DataFrame({'Tarih': [str(x).split('T')[0] for x in data_series.iloc[:4][::-1].index], 'Değer': data_series.iloc[:4][::-1].values})
    fig = go.Figure(data=[go.Bar(x=df_plot['Tarih'], y=df_plot['Değer'], marker_color=renk)])
    fig.update_layout(
        title=dict(text=baslik, font=dict(color="#ffffff", size=14)),
        paper_bgcolor='#16161c', plot_bgcolor='#16161c',
        height=240, margin=dict(l=10, r=10, t=35, b=10),
        xaxis=dict(showgrid=False, tickfont=dict(color="#a0a0ab")),
        yaxis=dict(showgrid=True, gridcolor="#262632", tickfont=dict(color="#a0a0ab"))
    )
    st.plotly_chart(fig, use_container_width=True)

def hesapla_temel_skor(info):
    skor = 0
    roe = (info.get('returnOnEquity') or 0) * 100
    if roe > 30: skor += 25
    elif roe > 20: skor += 20
    elif roe > 10: skor += 12
    elif roe > 0: skor += 5
    
    fk = info.get('forwardPE') or info.get('trailingPE')
    if fk and fk > 0:
        if fk < 10: skor += 20
        elif fk < 18: skor += 15
        elif fk < 25: skor += 10
        elif fk < 35: skor += 5
        
    pddd = info.get('priceToBook')
    if pddd and pddd > 0:
        if pddd < 1.5: skor += 15
        elif pddd < 3.0: skor += 10
        elif pddd < 6.0: skor += 5
        
    peg = info.get('pegRatio')
    if peg and peg > 0:
        if peg < 1.0: skor += 15
        elif peg < 1.5: skor += 10
        elif peg < 2.0: skor += 5
        
    cari = info.get('currentRatio')
    if cari:
        if cari >= 1.5: skor += 15
        elif cari >= 1.0: skor += 10
        elif cari >= 0.8: skor += 5
        
    marj = (info.get('profitMargins') or 0) * 100
    if marj > 20: skor += 10
    elif marj > 10: skor += 7
    elif marj > 5: skor += 3

    return min(skor, 100)

def hisse_detayli_analiz_et(hisse_kodu, filtreler):
    financials, balance_sheet, info, history = fetch_full_stock_data(hisse_kodu)
    
    if financials is None or financials.empty or len(financials.columns) < 4:
        return {
            'Hisse Kodu': hisse_kodu.replace('.IS', ''),
            'Tam Kod': hisse_kodu,
            'Piyasa': 'BİST' if '.IS' in hisse_kodu else 'ABD',
            'Durum': '❌ Elendi',
            'Elenme Nedeni': 'Eksik Bilanço Verisi',
            'Piyasa Değeri': 'N/A', 'Firma Değeri': 'N/A', 'Temel Skor': 0, 'F/K': None, 'PD/DD': None, 'PEG': None,
            'ROE (%)': None, 'Net Marj (%)': None, 'Cari Oran': None, 'Borç/Özkaynak': None, 'RSI (14)': None, 'Teknik Sinyal': 'N/A'
        }

    net_income_series = get_row(financials, ['Net Income', 'Net Income Common Stockholders'])
    son_net_kar = net_income_series.iloc[0] if net_income_series is not None and not net_income_series.dropna().empty else None
    
    ebitda_series = get_row(financials, ['EBITDA', 'Normalized EBITDA', 'Operating Income'])
    son_favok = ebitda_series.iloc[0] if ebitda_series is not None and len(ebitda_series.dropna()) >= 4 else None

    market_cap = info.get('marketCap')
    enterprise_val = info.get('enterpriseValue')
    roe = (info.get('returnOnEquity') or 0) * 100
    fk = info.get('forwardPE') or info.get('trailingPE')
    peg = info.get('pegRatio')
    pd_dd = info.get('priceToBook')
    current_ratio = info.get('currentRatio')
    debt_to_equity = (info.get('debtToEquity') or 0) / 100
    profit_margins = (info.get('profitMargins') or 0) * 100

    son_rsi = None
    macd_durum = "Nötr"
    teknik_sinyal = "Nötr"
    
    if history is not None and not history.empty and len(history) >= 30:
        rsi_series = ta.momentum.RSIIndicator(close=history['Close'], window=14).rsi()
        son_rsi = rsi_series.dropna().iloc[-1]
        
        macd_ind = ta.trend.MACD(close=history['Close'])
        macd_line = macd_ind.macd().dropna().iloc[-1] if not macd_ind.macd().dropna().empty else 0
        macd_signal = macd_ind.macd_signal().dropna().iloc[-1] if not macd_ind.macd_signal().dropna().empty else 0
        macd_durum = "🟢 Boğa" if macd_line > macd_signal else "🔴 Ayı"

        son_50 = history.tail(50)
        destek = round(son_50['Low'].min(), 2)
        direnc = round(son_50['High'].max(), 2)
        son_fiyat = history['Close'].iloc[-1]
        destege_yakinlik = (son_fiyat - destek) / (direnc - destek + 0.0001)

        if son_rsi < 40 and macd_line > macd_signal: teknik_sinyal = "🔥 Güçlü Al"
        elif son_rsi < 50 and destege_yakinlik < 0.3: teknik_sinyal = "🟢 Desteğe Yakın"
        elif son_rsi > 70: teknik_sinyal = "⚠️ Aşırı Isınmış"
        else: teknik_sinyal = "⚖️ Dengeli"

    elenme_nedeni = "Başarılı"
    basarili_mi = True

    if son_net_kar is None or pd.isna(son_net_kar) or son_net_kar <= 0:
        elenme_nedeni = "❌ Net Kâr Negatif"
        basarili_mi = False
    elif ebitda_series is not None and len(ebitda_series.dropna()) >= 4 and son_favok < ebitda_series.dropna().iloc[1:4].max():
        elenme_nedeni = "❌ FAVÖK Geriledi"
        basarili_mi = False
    elif filtreler['roe_aktif'] and (roe < filtreler['min_roe']):
        elenme_nedeni = f"❌ Düşük ROE (%{roe:.1f})"
        basarili_mi = False
    elif filtreler['fk_aktif'] and (fk is None or fk <= 0 or fk > filtreler['max_fk']):
        val_str = f"{fk:.1f}" if fk else 'N/A'
        elenme_nedeni = f"❌ Yüksek/Geçersiz F/K ({val_str})"
        basarili_mi = False
    elif filtreler['peg_aktif'] and (peg is None or peg > filtreler['max_peg']):
        val_str = f"{peg:.1f}" if peg else 'N/A'
        elenme_nedeni = f"❌ Yüksek PEG ({val_str})"
        basarili_mi = False
    elif filtreler['pddd_aktif'] and (pd_dd is None or pd_dd > filtreler['max_pddd']):
        val_str = f"{pd_dd:.1f}" if pd_dd else 'N/A'
        elenme_nedeni = f"❌ Yüksek PD/DD ({val_str})"
        basarili_mi = False
    elif filtreler['cari_oran_aktif'] and (current_ratio is None or current_ratio < filtreler['min_cari_oran']):
        val_str = f"{current_ratio:.1f}" if current_ratio else 'N/A'
        elenme_nedeni = f"❌ Düşük Cari Oran ({val_str})"
        basarili_mi = False
    elif filtreler['borc_aktif'] and (debt_to_equity > filtreler['max_borc_ozkaynak']):
        val_str = f"{debt_to_equity:.1f}" if debt_to_equity else 'N/A'
        elenme_nedeni = f"❌ Yüksek Borç/Özkaynak ({val_str})"
        basarili_mi = False
    elif filtreler['marj_aktif'] and (profit_margins < filtreler['min_net_marj']):
        elenme_nedeni = f"❌ Düşük Net Marj (%{profit_margins:.1f})"
        basarili_mi = False
    elif filtreler['rsi_aktif'] and (son_rsi is None or son_rsi < filtreler['rsi_min'] or son_rsi > filtreler['rsi_max']):
        val_str = f"{son_rsi:.1f}" if son_rsi else 'N/A'
        elenme_nedeni = f"❌ RSI Sınır Dışı ({val_str})"
        basarili_mi = False

    return {
        'Hisse Kodu': hisse_kodu.replace('.IS', ''),
        'Tam Kod': hisse_kodu,
        'Piyasa': 'BİST' if '.IS' in hisse_kodu else 'ABD',
        'Durum': '✅ Geçti' if basarili_mi else '❌ Elendi',
        'Elenme Nedeni': elenme_nedeni,
        'Temel Skor': hesapla_temel_skor(info),
        'Piyasa Değeri': format_para(market_cap),
        'Firma Değeri': format_para(enterprise_val),
        'F/K': round(fk, 2) if fk else 'N/A',
        'PD/DD': round(pd_dd, 2) if pd_dd else 'N/A',
        'PEG': round(peg, 2) if peg else 'N/A',
        'ROE (%)': round(roe, 2) if roe else 'N/A',
        'Net Marj (%)': round(profit_margins, 2) if profit_margins else 'N/A',
        'Cari Oran': round(current_ratio, 2) if current_ratio else 'N/A',
        'Borç/Özkaynak': round(debt_to_equity, 2) if debt_to_equity else 'N/A',
        'RSI (14)': round(son_rsi, 2) if son_rsi else 'N/A',
        'MACD Trend': macd_durum,
        'Teknik Sinyal': teknik_sinyal,
        'Son Net Kâr': format_para(son_net_kar),
        'Son FAVÖK': format_para(son_favok)
    }

# --- SOL SIDEBAR MENÜSÜ ---
st.sidebar.title("🎛️ Terminal Kontrolü")

with st.sidebar.expander("🎯 Piyasa & Endeks Seçimi", expanded=True):
    piyasa_secimi = st.radio(
        "Piyasa Seçimi:",
        ["BİST 30 (30 Hisse)", "BİST 100 (100 Hisse)", "BİST TÜM (150+ Hisse)", "S&P 500 (500 Hisse)", "NASDAQ 100 (100 Hisse)", "Özel Liste"],
        index=0
    )

with st.sidebar.expander("📊 Temel Analiz Filtreleri", expanded=True):
    fk_aktif = st.checkbox("F/K Filtresi", value=True)
    max_fk = st.slider("Maksimum F/K", 1.0, 100.0, 35.0, 1.0) if fk_aktif else 999.0

    peg_aktif = st.checkbox("PEG Oranı Filtresi", value=False)
    max_peg = st.slider("Maksimum PEG", 0.1, 5.0, 1.5, 0.1) if peg_aktif else 999.0

    pddd_aktif = st.checkbox("PD/DD Filtresi", value=True)
    max_pddd = st.slider("Maksimum PD/DD", 0.5, 20.0, 10.0, 0.5) if pddd_aktif else 999.0

    roe_aktif = st.checkbox("ROE (Özkaynak Kârlılığı)", value=True)
    min_roe = st.slider("Minimum ROE (%)", 0, 100, 10, 5) if roe_aktif else -999.0

    cari_oran_aktif = st.checkbox("Cari Oran (Likidite)", value=True)
    min_cari_oran = st.slider("Minimum Cari Oran", 0.5, 5.0, 1.0, 0.1) if cari_oran_aktif else 0.0

    borc_aktif = st.checkbox("Borç / Özkaynak Oranı", value=False)
    max_borc_ozkaynak = st.slider("Maksimum Borç/Özkaynak", 0.1, 10.0, 2.0, 0.1) if borc_aktif else 999.0

    marj_aktif = st.checkbox("Net Kâr Marjı (%)", value=False)
    min_net_marj = st.slider("Minimum Net Marj (%)", 0, 50, 5, 1) if marj_aktif else -999.0

with st.sidebar.expander("⚡ Teknik Analiz Filtreleri", expanded=False):
    rsi_aktif = st.checkbox("RSI (14) Filtresi", value=True)
    rsi_araligi = st.slider("RSI Aralığı", 0, 100, (30, 70)) if rsi_aktif else (0, 100)

filtre_paketı = {
    'fk_aktif': fk_aktif, 'max_fk': max_fk, 'peg_aktif': peg_aktif, 'max_peg': max_peg,
    'pddd_aktif': pddd_aktif, 'max_pddd': max_pddd, 'roe_aktif': roe_aktif, 'min_roe': min_roe,
    'cari_oran_aktif': cari_oran_aktif, 'min_cari_oran': min_cari_oran, 'borc_aktif': borc_aktif,
    'max_borc_ozkaynak': max_borc_ozkaynak, 'marj_aktif': marj_aktif, 'min_net_marj': min_net_marj,
    'rsi_aktif': rsi_aktif, 'rsi_min': rsi_araligi[0], 'rsi_max': rsi_araligi[1]
}

bist_100_tam = [
    'AKBNK.IS', 'ALARK.IS', 'ARCLK.IS', 'ASELS.IS', 'BIMAS.IS', 'BRSAN.IS', 'EKGYO.IS', 'ENKAI.IS', 'EREGL.IS', 'FROTO.IS',
    'GARAN.IS', 'GUBRF.IS', 'HEKTS.IS', 'ISCTR.IS', 'KCHOL.IS', 'KONTR.IS', 'KOZAL.IS', 'MGROS.IS', 'ODAS.IS', 'PETKM.IS',
    'PGSUS.IS', 'SAHOL.IS', 'SASA.IS', 'SISE.IS', 'TCELL.IS', 'THYAO.IS', 'TOASO.IS', 'TUPRS.IS', 'YKBNK.IS', 'OYYAT.IS',
    'AEFES.IS', 'AGHOL.IS', 'AHGAZ.IS', 'AKSA.IS', 'AKSEN.IS', 'ALBRK.IS', 'ALFAS.IS', 'ANHYT.IS', 'ANSGR.IS', 'ASTOR.IS',
    'BERA.IS', 'BFREN.IS', 'BIENP.IS', 'BOBET.IS', 'CANTE.IS', 'CCOLA.IS', 'CIMSA.IS', 'CWENE.IS', 'DOAS.IS', 'DOHOL.IS',
    'EGEEN.IS', 'ECILC.IS', 'EUPWR.IS', 'GENIL.IS', 'GESAN.IS', 'GWSWR.IS', 'HALKB.IS', 'INVEO.IS', 'INVES.IS', 'IPMAN.IS',
    'ISGYO.IS', 'ISMEN.IS', 'IZENR.IS', 'KAYSE.IS', 'KCAER.IS', 'KMPUR.IS', 'KORDS.IS', 'KOZAA.IS', 'KONYA.IS', 'LMKDC.IS',
    'MAVI.IS', 'MIATK.IS', 'MOBTL.IS', 'OTKAR.IS', 'OYAKC.IS', 'PENTAG.IS', 'QUAGR.IS', 'REEDR.IS', 'RUBNS.IS', 'SDTTR.IS',
    'SKBNK.IS', 'SOKM.IS', 'TABGD.IS', 'TAVHL.IS', 'TKFEN.IS', 'TMSN.IS', 'TRGYO.IS', 'TSKB.IS', 'TUKAS.IS', 'TURSG.IS',
    'ULKER.IS', 'VAKBN.IS', 'VESBE.IS', 'VESTL.IS', 'YEOTK.IS', 'ZOREN.IS', 'CMENT.IS', 'EUREK.IS', 'EGEPO.IS', 'KLSER.IS'
]

bist_tum_ekstra = [
    'ADESE.IS', 'ANELE.IS', 'ARDYZ.IS', 'ATSYH.IS', 'AYES.IS', 'BAGFS.IS', 'BANVT.IS', 'BAYRK.IS', 'BIZIM.IS', 'BRYAT.IS',
    'BUCIM.IS', 'BURCE.IS', 'CELHA.IS', 'CEMAS.IS', 'CLEBI.IS', 'DEVA.IS', 'DITAS.IS', 'EGGUB.IS', 'EGPRO.IS', 'EMKEL.IS'
]

bist_tum_tam = bist_100_tam + bist_tum_ekstra

sp_500_tam = [
    'AAPL', 'MSFT', 'NVDA', 'AMZN', 'GOOGL', 'META', 'BRK-B', 'LLY', 'AVGO', 'TSLA',
    'JPM', 'WMT', 'V', 'XOM', 'UNH', 'MA', 'PG', 'COST', 'JNJ', 'HD',
    'ORCL', 'ABBV', 'BAC', 'KO', 'MRK', 'CVX', 'NFLX', 'CRM', 'PEP', 'AMD'
]

nasdaq_100_tam = [
    'AAPL', 'NVDA', 'MSFT', 'GOOGL', 'AMZN', 'META', 'TSLA', 'AMD', 'INTC', 'NFLX',
    'CRM', 'ORCL', 'PYPL', 'QCOM', 'AVGO', 'COST', 'PEP', 'ADBE', 'AMAT', 'INTU'
]

if piyasa_secimi == "BİST 30 (30 Hisse)": secilen_hisseler = bist_100_tam[:30]
elif piyasa_secimi == "BİST 100 (100 Hisse)": secilen_hisseler = bist_100_tam
elif piyasa_secimi == "BİST TÜM (150+ Hisse)": secilen_hisseler = bist_tum_tam
elif piyasa_secimi == "S&P 500 (500 Hisse)": secilen_hisseler = sp_500_tam
elif piyasa_secimi == "NASDAQ 100 (100 Hisse)": secilen_hisseler = nasdaq_100_tam
else:
    girilen = st.sidebar.text_area("Hisseler (Virgülle):", "THYAO.IS, NVDA, AAPL")
    secilen_hisseler = [h.strip() for h in girilen.split(',') if h.strip()]

yenile_tiklandi = st.sidebar.button("🔄 Verileri Yenile / Yeniden Tara", type="primary")

cache_key = f"tarama_{piyasa_secimi}_{str(filtre_paketı)}"

@st.cache_data(ttl=1800, show_spinner=False)
def otomatık_paralel_tarama(hisse_listesi, filtreler):
    tum_sonuclar = []
    with ThreadPoolExecutor(max_workers=10) as executor:
        future_to_hisse = {executor.submit(hisse_detayli_analiz_et, h, filtreler): h for h in hisse_listesi}
        for future in as_completed(future_to_hisse):
            res = future.result()
            if res: tum_sonuclar.append(res)
                
    if tum_sonuclar:
        df = pd.DataFrame(tum_sonuclar)
        df = df.sort_values(by=['Durum', 'Temel Skor'], ascending=[False, False]).reset_index(drop=True)
        return df
    return pd.DataFrame()

if yenile_tiklandi or 'mevcut_cache_key' not in st.session_state or st.session_state['mevcut_cache_key'] != cache_key:
    with st.spinner(f"{piyasa_secimi} taranıyor..."):
        st.session_state['son_tarama_sonucu'] = otomatık_paralel_tarama(secilen_hisseler, filtre_paketı)
        st.session_state['mevcut_cache_key'] = cache_key

df_tum_hisseler = st.session_state['son_tarama_sonucu']

# Oturumda seçilen hisse yönetimi
if 'secilen_aktif_hisse' not in st.session_state:
    st.session_state['secilen_aktif_hisse'] = None

# --- ANA EKRAN SEKMELERİ (TABLOSAL GÖRÜNÜM vs ÖZEL HİSSE SAYFASI) ---
tab_ana1, tab_ana2 = st.tabs(["📊 Terminal Süzgeç & Kategori Tablosu", "📈 Şirket Detay, Canlı Grafik & Bilanço"])

with tab_ana1:
    if not df_tum_hisseler.empty:
        df_gecenler = df_tum_hisseler[df_tum_hisseler['Durum'] == '✅ Geçti'].reset_index(drop=True)
        df_elenenler = df_tum_hisseler[df_tum_hisseler['Durum'] == '❌ Elendi'].reset_index(drop=True)
        
        df_gecenler.index = range(1, len(df_gecenler) + 1)
        df_elenenler.index = range(1, len(df_elenenler) + 1)

        c1, c2, c3 = st.columns(3)
        c1.metric("Taranan Hisse", len(df_tum_hisseler))
        c2.metric("Süzgeçten Geçen", len(df_gecenler))
        c3.metric("Elenen Hisse", len(df_elenenler))
        
        st.markdown("<br>", unsafe_allow_html=True)
        st.info("💡 **İpucu:** Aşağıdaki tablolarda herhangi bir şirketin **satırına tıklayarak** o hisseye özel detay sayfasına anında geçiş yapabilirsiniz.")

        kat_degerleme, kat_karlilik, kat_borcluluk, kat_teknik, kat_elenenler = st.tabs([
            "🏷️ Değerleme", 
            "💰 Kârlılık", 
            "🛡️ Borçluluk & Likidite", 
            "⚡ Teknik Analiz", 
            f"❌ Elenenler ({len(df_elenenler)})"
        ])

        def render_clickable_dataframe(df_source, cols):
            if df_source.empty:
                st.warning("Gösterilecek veri bulunamadı.")
                return
            
            # Görüntülenecek sütunlar
            gosterim_df = df_source[['Hisse Kodu'] + cols].copy()
            
            event = st.dataframe(
                gosterim_df,
                use_container_width=True,
                hide_index=True,
                on_select="rerun",
                selection_mode="single-row"
            )
            
            if event.selection.rows:
                selected_row_idx = event.selection.rows[0]
                tiklanan_hisse = df_source.iloc[selected_row_idx]['Hisse Kodu']
                st.session_state['secilen_aktif_hisse'] = tiklanan_hisse
                st.success(f"🎯 **{tiklanan_hisse}** seçildi! Üst sekmeden **'Şirket Detay, Canlı Grafik & Bilanço'** sayfasına geçiliyor...")
                st.rerun()

        with kat_degerleme:
            st.caption("Süzgeçten geçen şirketlerin piyasa değerleri ve değerleme çarpanları (Tıklayarak inceleyin):")
            render_clickable_dataframe(df_gecenler, ['Piyasa Değeri', 'Firma Değeri', 'F/K', 'PD/DD', 'PEG'])

        with kat_karlilik:
            st.caption("Özkaynak Kârlılığı (ROE), Net Marj, Net Kâr ve FAVÖK büyüklükleri:")
            render_clickable_dataframe(df_gecenler, ['Temel Skor', 'ROE (%)', 'Net Marj (%)', 'Son Net Kâr', 'Son FAVÖK'])

        with kat_borcluluk:
            st.caption("Cari Oran (Likidite) ve Borç/Özkaynak oranları:")
            render_clickable_dataframe(df_gecenler, ['Temel Skor', 'Cari Oran', 'Borç/Özkaynak'])

        with kat_teknik:
            st.caption("Teknik Alım Sinyali, RSI (14) ve MACD Trend Durumu:")
            render_clickable_dataframe(df_gecenler, ['Teknik Sinyal', 'RSI (14)', 'MACD Trend'])

        with kat_elenenler:
            st.caption("Süzgeçten geçemeyen şirketler ve elenme gerekçeleri:")
            render_clickable_dataframe(df_elenenler, ['Elenme Nedeni', 'Piyasa Değeri', 'F/K', 'ROE (%)', 'Cari Oran'])
            
        csv = df_tum_hisseler.to_csv(index=False).encode('utf-8')
        st.download_button("📥 Tüm Raporu İndir (Excel/CSV)", csv, "fintables_terminal_v16.csv", "text/csv")

with tab_ana2:
    if not df_tum_hisseler.empty:
        hisse_listesi = df_tum_hisseler['Hisse Kodu'].tolist()
        
        # Eğer tablodan tıklanmış bir hisse varsa varsayılan olarak onu seç
        default_index = 0
        if st.session_state['secilen_aktif_hisse'] in hisse_listesi:
            default_index = hisse_listesi.index(st.session_state['secilen_aktif_hisse'])

        secilen_hisse = st.selectbox("İncelemek İstediğiniz Şirketi Seçin:", hisse_listesi, index=default_index)
        st.session_state['secilen_aktif_hisse'] = secilen_hisse

        hisse_row = df_tum_hisseler[df_tum_hisseler['Hisse Kodu'] == secilen_hisse].iloc[0]
        tam_kod = hisse_row['Tam Kod']
        
        fin, bal, info, hist = fetch_full_stock_data(tam_kod)
        
        if fin is not None and not fin.empty and bal is not None:
            karne = hesapla_fintables_karne_detayli(fin, bal, info)
            degisimler = hesapla_fintables_detayli_degisimler(fin)
            
            tv_symbol = get_tradingview_symbol(tam_kod)
            st.markdown(f"### 📈 {secilen_hisse} Canlı TradingView Grafiği")
            
            tv_widget_html = f"""
            <div class="tradingview-widget-container" style="height:480px;width:100%">
              <div id="tradingview_chart" style="height:450px;width:100%"></div>
              <script type="text/javascript" src="https://s3.tradingview.com/tv.js"></script>
              <script type="text/javascript">
              new TradingView.widget({{
                "autosize": true, 
                "symbol": "{tv_symbol}", 
                "interval": "D", 
                "timezone": "Europe/Istanbul",
                "theme": "dark", 
                "style": "1", 
                "locale": "tr", 
                "container_id": "tradingview_chart"
              }});
              </script>
            </div>
            """
            components.html(tv_widget_html, height=460)
            st.markdown("---")

            if hisse_row['Durum'] == '✅ Geçti':
                st.success(f"**{secilen_hisse}** süzgeçten başarıyla geçti! Temel Skor: **{hisse_row['Temel Skor']} / 100**")
            else:
                st.error(f"**{secilen_hisse}** süzgeçten elendi. Neden: **{hisse_row['Elenme Nedeni']}**")

            st.markdown(f"## 🏢 {secilen_hisse} Finansal Karnesi ve Özeti")
            
            render_karne_cards_with_tooltip(karne, degisimler)
            
            st.markdown("---")
            
            col_g1, col_g2 = st.columns(2)
            rev = get_row(fin, ['Total Revenue', 'Operating Revenue'])
            gross = get_row(fin, ['Gross Profit'])
            ebitda = get_row(fin, ['EBITDA', 'Normalized EBITDA', 'Operating Income'])
            net_inc = get_row(fin, ['Net Income'])
            
            ca = get_row(bal, ['Current Assets'])
            nca = get_row(bal, ['Total Non Current Assets'])
            ta_val = get_row(bal, ['Total Assets'])
            eq = get_row(bal, ['Stockholders Equity'])
            
            with col_g1:
                st.markdown("##### 📄 Özet Gelir Tablosu")
                if rev is not None and len(rev) >= 2:
                    df_gelir = pd.DataFrame({
                        'Son Çeyrek': [format_para(rev.iloc[0]), format_para(gross.iloc[0] if gross is not None else 0), format_para(ebitda.iloc[0] if ebitda is not None else 0), format_para(net_inc.iloc[0] if net_inc is not None else 0)],
                        'Önceki Çeyrek': [format_para(rev.iloc[1]), format_para(gross.iloc[1] if gross is not None else 0), format_para(ebitda.iloc[1] if ebitda is not None else 0), format_para(net_inc.iloc[1] if net_inc is not None else 0)]
                    }, index=['Satışlar', 'Brüt Kâr', 'FAVÖK', 'Net Dönem Kârı'])
                    st.table(df_gelir)

            with col_g2:
                st.markdown("##### 🏛️ Özet Bilanço")
                if ca is not None and len(ca) >= 2:
                    df_bilanco = pd.DataFrame({
                        'Son Çeyrek': [format_para(ca.iloc[0]), format_para(nca.iloc[0] if nca is not None else 0), format_para(ta_val.iloc[0] if ta_val is not None else 0), format_para(eq.iloc[0] if eq is not None else 0)],
                        'Önceki Çeyrek': [format_para(ca.iloc[1]), format_para(nca.iloc[1] if nca is not None else 0), format_para(ta_val.iloc[1] if ta_val is not None else 0), format_para(eq.iloc[1] if eq is not None else 0)]
                    }, index=['Dönen Varlıklar', 'Duran Varlıklar', 'Toplam Varlıklar', 'Özkaynaklar'])
                    st.table(df_bilanco)

            st.markdown("---")
            
            st.markdown("##### 📊 Çeyreklik Mali Gelişim Grafikleri")
            c_g1, c_g2, c_g3 = st.columns(3)
            
            with c_g1: ciz_koyu_cubuk_grafik(rev, "Çeyreklik Satışlar", "#38bdf8")
            with c_g2: ciz_koyu_cubuk_grafik(ebitda, "Çeyreklik FAVÖK", "#818cf8")
            with c_g3: ciz_koyu_cubuk_grafik(net_inc, "Çeyreklik Net Kâr", "#34d399")
