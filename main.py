import streamlit as st
import streamlit.components.v1 as components
import yfinance as yf
import pandas as pd
import ta
import plotly.graph_objects as go
from concurrent.futures import ThreadPoolExecutor, as_completed
import warnings

warnings.filterwarnings('ignore')

# --- SAYFA YAPILANDIRMASI & KOYU TEMA ---
st.set_page_config(
    page_title="Sermaye Terminali v7.0 Full",
    page_icon="🖤",
    layout="wide",
    initial_sidebar_state="expanded"
)

# GÖZÜ YORMAYAN YÜKSEK KONTRASTLI CSS & AKORDEON MENÜ STİLİ
st.markdown("""
    <style>
    .stApp { background-color: #0e0e10 !important; color: #f1f5f9 !important; }
    header[data-testid="stHeader"] { background-color: #0e0e10 !important; }
    
    /* Sol Menü & Akordeon (Expander) Düzeltmesi */
    [data-testid="stSidebar"] {
        background-color: #141418 !important;
        border-right: 1px solid #26262a !important;
    }
    [data-testid="stSidebar"] * { color: #ffffff !important; }
    [data-testid="stSidebar"] .stMarkdown p, 
    [data-testid="stSidebar"] label, 
    [data-testid="stSidebar"] span {
        color: #f1f5f9 !important;
        font-weight: 500 !important;
    }
    
    /* Expander (Açılır Başlıklar) Stili */
    [data-testid="stSidebar"] .streamlit-expanderHeader {
        background-color: #1c1c22 !important;
        border: 1px solid #2e2e38 !important;
        border-radius: 8px !important;
        font-weight: bold !important;
        color: #38bdf8 !important;
    }
    
    /* Metrik Kartları */
    .stMetric {
        background-color: #161618 !important;
        border: 1px solid #26262a !important;
        border-radius: 8px !important;
        padding: 12px !important;
    }
    [data-testid="stMetricLabel"] { color: #94a3b8 !important; font-size: 0.85rem !important; }
    [data-testid="stMetricValue"] { color: #38bdf8 !important; font-weight: 700 !important; font-size: 1.6rem !important; }
    
    /* Sekme (Tab) Tasarımı */
    .stTabs [data-baseweb="tab-list"] { background-color: #141418; padding: 6px; border-radius: 8px; border: 1px solid #26262a; }
    .stTabs [data-baseweb="tab"] { color: #94a3b8 !important; font-weight: 600; border-radius: 6px; }
    .stTabs [aria-selected="true"] { background-color: #222226 !important; color: #ffffff !important; border-bottom: 2px solid #38bdf8 !important; }
    
    .stDataFrame { border: 1px solid #26262a; border-radius: 8px; }
    </style>
""", unsafe_allow_html=True)

st.title("🖤 Sermaye & Değerleme Terminali v7.0")
st.caption("BİST & Küresel Piyasalar - Kapsamlı Akordeon Filtreli & Skorlamalı Terminal")

# --- MİLYAR / MİLYON FORMATLAMA ---
def format_para(val):
    if val is None or pd.isna(val): return "N/A"
    abs_v = abs(val)
    if abs_v >= 1e9: return f"{val / 1e9:.2f} mr"
    elif abs_v >= 1e6: return f"{val / 1e6:.2f} mn"
    return f"{val:,.0f}"

# --- KOYU TEMALI PLOTLY GRAFİK ---
def ciz_koyu_cubuk_grafik(data_series, baslik, renk="#38bdf8"):
    if data_series is None or data_series.empty: return
    df_plot = pd.DataFrame({'Tarih': [str(x).split('T')[0] for x in data_series.iloc[:4][::-1].index], 'Değer': data_series.iloc[:4][::-1].values})
    fig = go.Figure(data=[go.Bar(x=df_plot['Tarih'], y=df_plot['Değer'], marker_color=renk)])
    fig.update_layout(
        title=dict(text=baslik, font=dict(color="#f1f5f9", size=14)),
        paper_bgcolor='#161618', plot_bgcolor='#161618',
        height=260, margin=dict(l=10, r=10, t=35, b=10),
        xaxis=dict(showgrid=False, tickfont=dict(color="#94a3b8")),
        yaxis=dict(showgrid=True, gridcolor="#26262a", tickfont=dict(color="#94a3b8"))
    )
    st.plotly_chart(fig, use_container_width=True)

# --- VERİ ÇEKME MOTORU ---
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

def hesapla_fintables_karne(financials, balance_sheet, info):
    karlilik_skor = 0
    buyume_skor = 0
    borcluluk_skor = 0
    
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
    
    if isletme_sermayesi > 0: borcluluk_skor += 1
    if fin_borcluluk_orani < 50: borcluluk_skor += 1
    if net_borc < 0: borcluluk_skor += 1
    if ca_val > td_val: borcluluk_skor += 1
    if cari_oran > 1.5: borcluluk_skor += 1
    if fin_borcluluk_orani < 30 or net_borc < 0: borcluluk_skor += 1

    roe = (info.get('returnOnEquity') or 0) * 100
    net_marj = (info.get('profitMargins') or 0) * 100
    
    if roe > 20: karlilik_skor += 2
    elif roe > 10: karlilik_skor += 1
    if net_marj > 15: karlilik_skor += 2
    elif net_marj > 5: karlilik_skor += 1
    if info.get('operatingMargins', 0) > 0.1: karlilik_skor += 2

    if rev_series is not None and len(rev_series) >= 2 and rev_series.iloc[0] > rev_series.iloc[-1]: buyume_skor += 2
    if ebitda_series is not None and len(ebitda_series) >= 2 and ebitda_series.iloc[0] > ebitda_series.iloc[-1]: buyume_skor += 2
    if net_inc_series is not None and len(net_inc_series) >= 2 and net_inc_series.iloc[0] > net_inc_series.iloc[-1]: buyume_skor += 2

    return {
        'karlilik': min(karlilik_skor, 6),
        'buyume': min(buyume_skor, 6),
        'borcluluk': min(borcluluk_skor, 6)
    }

def hisse_detayli_analiz_et(hisse_kodu, filtreler):
    financials, balance_sheet, info, history = fetch_full_stock_data(hisse_kodu)
    
    if financials is None or financials.empty or len(financials.columns) < 4:
        return {
            'Hisse Kodu': hisse_kodu.replace('.IS', ''),
            'Tam Kod': hisse_kodu,
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

    # TÜM FİLTRELERİN KONTROLÜ
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
        elenme_nedeni = f"❌ Yüksek/Geçersiz F/K ({fk if fk else 'N/A'})"
        basarili_mi = False
    elif filtreler['peg_aktif'] and (peg is None or peg > filtreler['max_peg']):
        elenme_nedeni = f"❌ Yüksek PEG ({peg if peg else 'N/A'})"
        basarili_mi = False
    elif filtreler['pddd_aktif'] and (pd_dd is None or pd_dd > filtreler['max_pddd']):
        elenme_nedeni = f"❌ Yüksek PD/DD ({pd_dd if pd_dd else 'N/A'})"
        basarili_mi = False
    elif filtreler['cari_oran_aktif'] and (current_ratio is None or current_ratio < filtreler['min_cari_oran']):
        elenme_nedeni = f"❌ Düşük Cari Oran ({current_ratio if current_ratio else 'N/A'})"
        basarili_mi = False
    elif filtreler['borc_aktif'] and (debt_to_equity > filtreler['max_borc_ozkaynak']):
        elenme_nedeni = f"❌ Yüksek Borç/Özkaynak ({debt_to_equity:.2f})"
        basarili_mi = False
    elif filtreler['marj_aktif'] and (profit_margins < filtreler['min_net_marj']):
        elenme_nedeni = f"❌ Düşük Net Marj (%{profit_margins:.1f})"
        basarili_mi = False
    elif filtreler['rsi_aktif'] and (son_rsi is None or son_rsi < filtreler['rsi_min'] or son_rsi > filtreler['rsi_max']):
        elenme_nedeni = f"❌ RSI Sınır Dışı ({round(son_rsi, 1) if son_rsi else 'N/A'})"
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
        'F/K': round(fk, 2) if fk else None,
        'PD/DD': round(pd_dd, 2) if pd_dd else None,
        'PEG': round(peg, 2) if peg else None,
        'ROE (%)': round(roe, 2) if roe else None,
        'Net Marj (%)': round(profit_margins, 2) if profit_margins else None,
        'Cari Oran': round(current_ratio, 2) if current_ratio else None,
        'Borç/Özkaynak': round(debt_to_equity, 2) if debt_to_equity else None,
        'RSI (14)': round(son_rsi, 2) if son_rsi else None,
        'MACD Trend': macd_durum,
        'Teknik Sinyal': teknik_sinyal,
        'Son Net Kâr': format_para(son_net_kar),
        'Son FAVÖK': format_para(son_favok)
    }

# --- SOL SIDEBAR AKORDEON (EXPANDER) MENÜ YAPISI ---
st.sidebar.title("🎛️ Terminal Kontrolü")

# 1. PİYASA SEÇİMİ AÇILIR MENÜSÜ
with st.sidebar.expander("🎯 1. Piyasa & Endeks Seçimi", expanded=True):
    piyasa_secimi = st.radio(
        "Listenizi belirleyin:",
        ["BİST 30 (30 Hisse)", "BİST 100 (100 Hisse)", "BİST TÜM (150+ Hisse)", "S&P 500 (500 Hisse)", "NASDAQ 100 (100 Hisse)", "Özel Liste"]
    )

# 2. TEMEL ANALİZ FİLTRELERİ AÇILIR MENÜSÜ
with st.sidebar.expander("📊 2. Temel Analiz Filtreleri", expanded=True):
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

# 3. TEKNİK ANALİZ FİLTRELERİ AÇILIR MENÜSÜ
with st.sidebar.expander("⚡ 3. Teknik Analiz Filtreleri", expanded=False):
    rsi_aktif = st.checkbox("RSI (14) Filtresi", value=True)
    rsi_araligi = st.slider("RSI Aralığı", 0, 100, (30, 70)) if rsi_aktif else (0, 100)

filtre_paketı = {
    'fk_aktif': fk_aktif, 'max_fk': max_fk, 'peg_aktif': peg_aktif, 'max_peg': max_peg,
    'pddd_aktif': pddd_aktif, 'max_pddd': max_pddd, 'roe_aktif': roe_aktif, 'min_roe': min_roe,
    'cari_oran_aktif': cari_oran_aktif, 'min_cari_oran': min_cari_oran, 'borc_aktif': borc_aktif,
    'max_borc_ozkaynak': max_borc_ozkaynak, 'marj_aktif': marj_aktif, 'min_net_marj': min_net_marj,
    'rsi_aktif': rsi_aktif, 'rsi_min': rsi_araligi[0], 'rsi_max': rsi_araligi[1]
}

# HİSSE LİSTELERİ
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

st.sidebar.button("🔄 Verileri Yenile / Yeniden Tara", type="primary")

# --- PARALEL TARAMA MOTORU ---
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

# Tarama Yürütücü
with st.spinner(f"{len(secilen_hisseler)} hisse taranıyor..."):
    df_tum_hisseler = otomatık_paralel_tarama(secilen_hisseler, filtre_paketı)

# --- ARAYÜZ (KATEGORİZE TABLOLAR VE FINTABLES MODU) ---
tab_ana1, tab_ana2 = st.tabs(["📊 Terminal Süzgeç & Kategori Tablosu", "📈 Şirket Karnesi & Özet Bilanço (Fintables Mode)"])

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
        
        kat_degerleme, kat_karlilik, kat_borcluluk, kat_teknik, kat_elenenler = st.tabs([
            "🏷️ Değerleme", 
            "💰 Kârlılık", 
            "🛡️ Borçluluk & Likidite", 
            "⚡ Teknik Analiz", 
            f"❌ Elenenler ({len(df_elenenler)})"
        ])

        with kat_degerleme:
            st.caption("Süzgeçten geçen şirketlerin piyasa değerleri, F/K, PD/DD ve PEG oranları:")
            st.dataframe(
                df_gecenler[['Hisse Kodu', 'Piyasa', 'Temel Skor', 'Piyasa Değeri', 'Firma Değeri', 'F/K', 'PD/DD', 'PEG']],
                use_container_width=True
            )

        with kat_karlilik:
            st.caption("Şirketlerin Özkaynak Kârlılığı (ROE), Net Marjı, Son Net Kârı ve FAVÖK büyüklükleri:")
            st.dataframe(
                df_gecenler[['Hisse Kodu', 'Temel Skor', 'ROE (%)', 'Net Marj (%)', 'Son Net Kâr', 'Son FAVÖK']],
                use_container_width=True
            )

        with kat_borcluluk:
            st.caption("Cari Oran (Likidite) ve Borç/Özkaynak oranları:")
            st.dataframe(
                df_gecenler[['Hisse Kodu', 'Temel Skor', 'Cari Oran', 'Borç/Özkaynak']],
                use_container_width=True
            )

        with kat_teknik:
            st.caption("Teknik Alım Sinyali, RSI (14) ve MACD Trend Durumu:")
            st.dataframe(
                df_gecenler[['Hisse Kodu', 'Teknik Sinyal', 'RSI (14)', 'MACD Trend']],
                use_container_width=True
            )

        with kat_elenenler:
            st.caption("Süzgeçten geçemeyen şirketler ve detaylı elenme nedenleri:")
            st.dataframe(
                df_elenenler[['Hisse Kodu', 'Elenme Nedeni', 'Piyasa Değeri', 'F/K', 'ROE (%)', 'Cari Oran', 'RSI (14)']],
                use_container_width=True
            )
            
        csv = df_tum_hisseler.to_csv(index=False).encode('utf-8')
        st.download_button("📥 Tüm Raporu İndir (Excel/CSV)", csv, "tum_hisse_analiz_raporu_v7.csv", "text/csv")

with tab_ana2:
    if not df_tum_hisseler.empty:
        secilen_hisse = st.selectbox("İncelemek İstediğiniz Şirketi Seçin (Tüm Hisseler):", df_tum_hisseler['Hisse Kodu'].tolist())
        hisse_row = df_tum_hisseler[df_tum_hisseler['Hisse Kodu'] == secilen_hisse].iloc[0]
        tam_kod = hisse_row['Tam Kod']
        
        fin, bal, info, hist = fetch_full_stock_data(tam_kod)
        
        if fin is not None and not fin.empty and bal is not None:
            karne = hesapla_fintables_karne(fin, bal, info)
            
            if hisse_row['Durum'] == '✅ Geçti':
                st.success(f"**{secilen_hisse}** süzgeçten başarıyla geçti! Temel Skor: **{hisse_row['Temel Skor']} / 100**")
            else:
                st.error(f"**{secilen_hisse}** süzgeçten elendi. Neden: **{hisse_row['Elenme Nedeni']}**")

            st.markdown(f"## 🏢 {secilen_hisse} Finansal Karnesi ve Özeti")
            
            k1, k2, k3, k4 = st.columns(4)
            k1.metric("Kârlılık Karnesi", f"{karne['karlilik']} / 6")
            k2.metric("Büyüme Karnesi", f"{karne['buyume']} / 6")
            k3.metric("Borçluluk Karnesi", f"{karne['borcluluk']} / 6")
            k4.metric("Piyasa Değeri", format_para(info.get('marketCap')))
            
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

            st.markdown("---")
            
            tv_symbol = f"BIST:{secilen_hisse}" if '.IS' in tam_kod else secilen_hisse.replace('-', '.')
            st.markdown(f"##### 📈 {secilen_hisse} Canlı TradingView Grafiği")
            
            tv_widget_html = f"""
            <div class="tradingview-widget-container" style="height:480px;width:100%">
              <div id="tradingview_chart" style="height:450px;width:100%"></div>
              <script type="text/javascript" src="https://s3.tradingview.com/tv.js"></script>
              <script type="text/javascript">
              new TradingView.widget({{
                "autosize": true, "symbol": "{tv_symbol}", "interval": "D", "timezone": "Europe/Istanbul",
                "theme": "dark", "style": "1", "locale": "tr", "container_id": "tradingview_chart"
              }});
              </script>
            </div>
            """
            components.html(tv_widget_html, height=460)
