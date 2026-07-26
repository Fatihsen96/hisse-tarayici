import streamlit as st
import streamlit.components.v1 as components
import yfinance as yf
import pandas as pd
import ta
import plotly.graph_objects as go
from concurrent.futures import ThreadPoolExecutor, as_completed
import warnings

warnings.filterwarnings('ignore')

# --- SAYFA YAPILANDIRMASI & YÜKSEK KONTRAST KOYU TEMA ---
st.set_page_config(
    page_title="Sermaye & Değerleme Terminali v4.0 Pro",
    page_icon="💎",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Yüksek Kontrastlı Özel CSS (Okunabilirlik ve Profesyonel UI)
st.markdown("""
    <style>
    .stApp {
        background-color: #0e1117;
        color: #f3f4f6;
    }
    [data-testid="stSidebar"] {
        background-color: #161b22;
        border-right: 1px solid #30363d;
    }
    /* Metrik Kartları Yüksek Kontrast Düzeltmesi */
    .stMetric {
        background-color: #1f2937 !important;
        border: 1px solid #374151 !important;
        border-radius: 10px !important;
        padding: 15px !important;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.3);
    }
    [data-testid="stMetricLabel"] {
        color: #9ca3af !important;
        font-weight: 600 !important;
        font-size: 0.95rem !important;
    }
    [data-testid="stMetricValue"] {
        color: #38bdf8 !important;
        font-weight: 800 !important;
        font-size: 1.9rem !important;
    }
    .badge-pass {
        background-color: #059669;
        color: white;
        padding: 4px 8px;
        border-radius: 6px;
        font-weight: bold;
    }
    .badge-fail {
        background-color: #dc2626;
        color: white;
        padding: 4px 8px;
        border-radius: 6px;
        font-weight: bold;
    }
    </style>
""", unsafe_allow_html=True)

st.title("💎 Akıllı Hisse Filtreleme ve Analiz Terminali v4.0 Pro")
st.caption("BİST Tüm, S&P 500 & NASDAQ 100 - Şeffaf Süzgeç ve Uzman Analiz Paneli")

# --- VERİ ÇEKME VE ÖNBELLEKLEME ---
@st.cache_data(ttl=3600, show_spinner=False)
def fetch_stock_raw_data(hisse_kodu):
    try:
        formatted_code = hisse_kodu.replace('.', '-') if not hisse_kodu.endswith('.IS') else hisse_kodu
        ticker = yf.Ticker(formatted_code)
        financials = ticker.quarterly_financials
        info = ticker.info or {}
        history = ticker.history(period="1y")
        return financials, info, history
    except Exception:
        return None, None, None

def get_financial_value(df, possible_keys):
    for key in possible_keys:
        if key in df.index:
            return df.loc[key]
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

def hisse_detayli_analiz_et(hisse_kodu, filtreler):
    financials, info, history = fetch_stock_raw_data(hisse_kodu)
    
    if financials is None or financials.empty or len(financials.columns) < 4:
        return {
            'Hisse Kodu': hisse_kodu.replace('.IS', ''),
            'Tam Kod': hisse_kodu,
            'Durum': '❌ Elendi',
            'Elenme Nedeni': 'Yetersiz/Eksik Bilanço Verisi',
            'Temel Skor (100)': 0,
            'Teknik Sinyal': 'Nötr',
            'F/K': None, 'ROE (%)': None, 'Cari Oran': None, 'RSI (14)': None
        }

    # 1. Net Kâr Kontrolü
    net_income_series = get_financial_value(financials, ['Net Income', 'Net Income Common Stockholders'])
    son_net_kar = net_income_series.iloc[0] if net_income_series is not None and not net_income_series.dropna().empty else None
    
    # 2. FAVÖK Kontrolü
    ebitda_series = get_financial_value(financials, ['EBITDA', 'Normalized EBITDA', 'Operating Income'])
    son_favok = ebitda_series.iloc[0] if ebitda_series is not None and len(ebitda_series.dropna()) >= 4 else None

    # Değerleri Çek
    roe = (info.get('returnOnEquity') or 0) * 100
    fk = info.get('forwardPE') or info.get('trailingPE')
    peg = info.get('pegRatio')
    pd_dd = info.get('priceToBook')
    current_ratio = info.get('currentRatio')
    debt_to_equity = (info.get('debtToEquity') or 0) / 100
    profit_margins = (info.get('profitMargins') or 0) * 100

    # RSI & Teknik
    son_rsi = None
    macd_durum = "Nötr"
    teknik_sinyal = "Nötr"
    destek = None
    direnc = None
    
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

        if son_rsi < 40 and macd_line > macd_signal: teknik_sinyal = "🔥 Güçlü Alım"
        elif son_rsi < 50 and destege_yakinlik < 0.3: teknik_sinyal = "🟢 Desteğe Yakın"
        elif son_rsi > 70: teknik_sinyal = "⚠️ Aşırı Isınmış"
        else: teknik_sinyal = "⚖️ Dengeli"

    # ELEME NEDENİ TESPİTİ
    elenme_nedeni = "Başarılı (Süzgeçten Geçti)"
    basarili_mi = True

    if son_net_kar is None or pd.isna(son_net_kar) or son_net_kar <= 0:
        elenme_nedeni = "❌ Net Kâr Negatif / Yok"
        basarili_mi = False
    elif ebitda_series is not None and len(ebitda_series.dropna()) >= 4 and son_favok < ebitda_series.dropna().iloc[1:4].max():
        elenme_nedeni = "❌ Son FAVÖK Geriledi"
        basarili_mi = False
    elif filtreler['roe_aktif'] and (roe < filtreler['min_roe']):
        elenme_nedeni = f"❌ ROE Düşük (%{roe:.1f} < %{filtreler['min_roe']})"
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

    temel_skor = hesapla_temel_skor(info)

    return {
        'Hisse Kodu': hisse_kodu.replace('.IS', ''),
        'Tam Kod': hisse_kodu,
        'Piyasa': 'BİST' if '.IS' in hisse_kodu else 'ABD',
        'Durum': '✅ Geçti' if basarili_mi else '❌ Elendi',
        'Elenme Nedeni': elenme_nedeni,
        'Temel Skor (100)': temel_skor,
        'Teknik Sinyal': teknik_sinyal,
        'RSI (14)': round(son_rsi, 2) if son_rsi else None,
        'MACD Trend': macd_durum,
        'Destek (50G)': destek,
        'Direnç (50G)': direnc,
        'F/K': round(fk, 2) if fk else None,
        'PEG': round(peg, 2) if peg else None,
        'PD/DD': round(pd_dd, 2) if pd_dd else None,
        'Cari Oran': round(current_ratio, 2) if current_ratio else None,
        'Borç/Özkaynak': round(debt_to_equity, 2) if debt_to_equity else None,
        'Net Marj (%)': round(profit_margins, 2) if profit_margins else None,
        'ROE (%)': round(roe, 2) if roe else None,
        'Son Net Kar': round(son_net_kar, 0) if son_net_kar else None,
        'Son FAVÖK': round(son_favok, 0) if son_favok else None,
    }


# --- YAN MENÜ ---
st.sidebar.header("🎯 1. Piyasayı Seçin")
piyasa_secimi = st.sidebar.radio(
    "Listenizi belirleyin:",
    ["BİST 30 (30 Hisse)", "BİST 100 (100 Hisse)", "BİST TÜM (150+ Hisse)", "S&P 500 (500 Hisse)", "NASDAQ 100 (100 Hisse)", "Özel Liste"]
)

st.sidebar.header("⚙️ 2. Temel & Teknik Filtreler")

fk_aktif = st.sidebar.checkbox("F/K Filtresi", value=True, help="Fiyat/Kazanç Oranı.")
max_fk = st.sidebar.slider("Maksimum F/K", 1.0, 100.0, 35.0, 1.0) if fk_aktif else 999.0

peg_aktif = st.sidebar.checkbox("PEG Oranı Filtresi", value=False, help="F/K / Büyüme Oranı.")
max_peg = st.sidebar.slider("Maksimum PEG", 0.1, 5.0, 1.5, 0.1) if peg_aktif else 999.0

pddd_aktif = st.sidebar.checkbox("PD/DD Filtresi", value=True, help="Piyasa Değeri / Defter Değeri.")
max_pddd = st.sidebar.slider("Maksimum PD/DD", 0.5, 20.0, 10.0, 0.5) if pddd_aktif else 999.0

roe_aktif = st.sidebar.checkbox("ROE (Özkaynak Kârlılığı)", value=True, help="Özkaynak Kârlılığı (%).")
min_roe = st.sidebar.slider("Minimum ROE (%)", 0, 100, 10, 5) if roe_aktif else -999.0

cari_oran_aktif = st.sidebar.checkbox("Cari Oran (Likidite)", value=True, help="Kısa Vadeli Borç Ödeme Gücü.")
min_cari_oran = st.sidebar.slider("Minimum Cari Oran", 0.5, 5.0, 1.0, 0.1) if cari_oran_aktif else 0.0

borc_aktif = st.sidebar.checkbox("Borç / Özkaynak Oranı", value=False)
max_borc_ozkaynak = st.sidebar.slider("Maksimum Borç/Özkaynak", 0.1, 10.0, 2.0, 0.1) if borc_aktif else 999.0

marj_aktif = st.sidebar.checkbox("Net Kâr Marjı (%)", value=False)
min_net_marj = st.sidebar.slider("Minimum Net Marj (%)", 0, 50, 5, 1) if marj_aktif else -999.0

rsi_aktif = st.sidebar.checkbox("RSI (14) Filtresi", value=True)
rsi_araligi = st.sidebar.slider("RSI Aralığı", 0, 100, (30, 70)) if rsi_aktif else (0, 100)

filtre_paketı = {
    'fk_aktif': fk_aktif, 'max_fk': max_fk, 'peg_aktif': peg_aktif, 'max_peg': max_peg,
    'pddd_aktif': pddd_aktif, 'max_pddd': max_pddd, 'roe_aktif': roe_aktif, 'min_roe': min_roe,
    'cari_oran_aktif': cari_oran_aktif, 'min_cari_oran': min_cari_oran, 'borc_aktif': borc_aktif,
    'max_borc_ozkaynak': max_borc_ozkaynak, 'marj_aktif': marj_aktif, 'min_net_marj': min_net_marj,
    'rsi_aktif': rsi_aktif, 'rsi_min': rsi_araligi[0], 'rsi_max': rsi_araligi[1]
}

# FULL BİST TÜM HİSSE LİSTESİ
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
    'BUCIM.IS', 'BURCE.IS', 'CELHA.IS', 'CEMAS.IS', 'CLEBI.IS', 'DEVA.IS', 'DITAS.IS', 'EGGUB.IS', 'EGPRO.IS', 'EMKEL.IS',
    'ERBOS.IS', 'ESCOM.IS', 'GSDHO.IS', 'HLGYO.IS', 'INDES.IS', 'JANTS.IS', 'KARSN.IS', 'KARTN.IS', 'KAREL.IS', 'LOGO.IS',
    'NTHOL.IS', 'PARSN.IS', 'POLHO.IS', 'PRKME.IS', 'RYSAS.IS', 'SARKY.IS', 'TGSAS.IS', 'TIRE.IS', 'VERUS.IS', 'YATAS.IS'
]

bist_tum_tam = bist_100_tam + bist_tum_ekstra

sp_500_tam = [
    'AAPL', 'MSFT', 'NVDA', 'AMZN', 'GOOGL', 'META', 'BRK-B', 'LLY', 'AVGO', 'TSLA',
    'JPM', 'WMT', 'V', 'XOM', 'UNH', 'MA', 'PG', 'COST', 'JNJ', 'HD',
    'ORCL', 'ABBV', 'BAC', 'KO', 'MRK', 'CVX', 'NFLX', 'CRM', 'PEP', 'AMD',
    'TMO', 'LIN', 'WFC', 'ADBE', 'MCD', 'CSCO', 'PM', 'GE', 'ABT', 'DIS',
    'TXN', 'INTU', 'AMGN', 'QCOM', 'NOW', 'IBM', 'CAT', 'PFE', 'ISRG', 'VZ',
    'AMAT', 'UBER', 'CMCSA', 'BKNG', 'SPGI', 'AXP', 'GS', 'HON', 'COP', 'LOW',
    'RTX', 'DHR', 'PGR', 'SYK', 'C', 'PLTR', 'TMUS', 'MS', 'LRCX', 'SCHW',
    'PANW', 'REGN', 'VRTX', 'ACN', 'BLK', 'SBUX', 'DE', 'GILD', 'ADP', 'T',
    'BA', 'MDLZ', 'CI', 'NKE', 'LMT', 'INTC', 'TJX', 'MMC', 'ADI', 'EOG',
    'BMY', 'AMT', 'ELV', 'HCA', 'MU', 'MO', 'FI', 'BSX', 'PNC', 'CL',
    'MDT', 'SHW', 'KLAC', 'MCK', 'UPS', 'SNPS', 'CDNS', 'WM', 'SLB', 'MCO',
    'ICE', 'PH', 'ORLY', 'CSX', 'MAR', 'CTAS', 'ROP', 'GD', 'FCX', 'CMG'
]

nasdaq_100_tam = [
    'AAPL', 'NVDA', 'MSFT', 'GOOGL', 'AMZN', 'META', 'TSLA', 'AMD', 'INTC', 'NFLX',
    'CRM', 'ORCL', 'PYPL', 'QCOM', 'AVGO', 'COST', 'PEP', 'ADBE', 'AMAT', 'INTU',
    'ISRG', 'BKNG', 'AMGN', 'TXN', 'HON', 'SBUX', 'VRTX', 'MDLZ', 'REGN', 'PANW',
    'KLAC', 'SNPS', 'CDNS', 'MELI', 'CSX', 'MAR', 'ASML', 'ORLY', 'LRCX', 'CTAS'
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
            if res:
                tum_sonuclar.append(res)
                
    if tum_sonuclar:
        df = pd.DataFrame(tum_sonuclar)
        df = df.sort_values(by=['Durum', 'Temel Skor (100)'], ascending=[False, False]).reset_index(drop=True)
        return df
    return pd.DataFrame()

# Otomatik Taramayı Başlat
with st.spinner(f"{len(secilen_hisseler)} hisse için canlı veriler taranıyor ve analiz ediliyor..."):
    df_tum_hisseler = otomatık_paralel_tarama(secilen_hisseler, filtre_paketı)

# --- ARAYÜZ ---
tab1, tab2, tab3 = st.tabs(["📊 Süzgeç & Şeffaf Analiz Raporu", "📈 Hisse Detay & TradingView Grafik", "📚 Terimler & Filtre Rehberi"])

# TAB 1: SÜZGEÇ VE ŞEFFAF ANALİZ
with tab1:
    if not df_tum_hisseler.empty:
        df_gecenler = df_tum_hisseler[df_tum_hisseler['Durum'] == '✅ Geçti'].reset_index(drop=True)
        df_elenenler = df_tum_hisseler[df_tum_hisseler['Durum'] == '❌ Elendi'].reset_index(drop=True)
        
        df_gecenler.index = range(1, len(df_gecenler) + 1)
        df_elenenler.index = range(1, len(df_elenenler) + 1)

        # YÜKSEK KONTRASTLI METRİK KARTLARI
        c1, c2, c3 = st.columns(3)
        c1.metric("Taranan Toplam Hisse", len(df_tum_hisseler))
        c2.metric("Süzgeçten Geçen Başarılı Şirketler", len(df_gecenler))
        c3.metric("Elenen Şirketler", len(df_elenenler))
        
        st.markdown("---")
        
        # ALT SEKMELER: GEÇENLER VS ELENENLER
        sub_tab1, sub_tab2 = st.tabs([
            f"✅ Süzgeçten Geçen Şirketler ({len(df_gecenler)})", 
            f"❌ Elenen Şirketler ve Elenme Nedenleri ({len(df_elenenler)})"
        ])

        with sub_tab1:
            if not df_gecenler.empty:
                st.success(f"Tebrikler! Süzgeçten başarıyla geçen {len(df_gecenler)} adet yüksek kaliteli şirket listelendi.")
                st.dataframe(
                    df_gecenler.drop(columns=['Tam Kod']),
                    use_container_width=True,
                    column_config={
                        "Temel Skor (100)": st.column_config.ProgressColumn("Temel Skor", format="%d / 100", min_value=0, max_value=100),
                        "ROE (%)": st.column_config.ProgressColumn("ROE (%)", format="%.2f%%", min_value=0, max_value=100),
                        "F/K": st.column_config.NumberColumn("F/K", format="%.2f"),
                        "PD/DD": st.column_config.NumberColumn("PD/DD", format="%.2f"),
                        "Cari Oran": st.column_config.NumberColumn("Cari Oran", format="%.2f"),
                        "RSI (14)": st.column_config.NumberColumn("RSI (14)", format="%.2f"),
                    }
                )
            else:
                st.warning("Seçtiğiniz katı kriterlere uyan şirket bulunamadı. Filtreleri esnetebilirsiniz.")

        with sub_tab2:
            st.info("Aşağıdaki tabloda süzgeçten geçemeyen hisseler ve **tam olarak hangi kriterden elendikleri** detaylıca gösterilmiştir.")
            st.dataframe(
                df_elenenler[['Hisse Kodu', 'Piyasa', 'Elenme Nedeni', 'Temel Skor (100)', 'Teknik Sinyal', 'F/K', 'ROE (%)', 'Cari Oran', 'RSI (14)']],
                use_container_width=True,
                column_config={
                    "Elenme Nedeni": st.column_config.TextColumn("Elenme Nedeni", help="Şirketin süzgeçten geçememesine sebep olan temel/teknik faktör."),
                    "Temel Skor (100)": st.column_config.ProgressColumn("Temel Skor", format="%d / 100", min_value=0, max_value=100),
                }
            )
        
        csv = df_tum_hisseler.to_csv(index=False).encode('utf-8')
        st.download_button("📥 Tüm Raporu İndir (Excel/CSV)", csv, "tum_hisse_analiz_raporu_v4.csv", "text/csv")

# TAB 2: UZMAN SEVİYESİ GRAFİK VE İNCELEME
with tab2:
    if not df_tum_hisseler.empty:
        # Uzmanlar için hem geçen hem elenen tüm hisseler seçilebilir yapıldı
        secilen_kod = st.selectbox("İncelemek İstediğiniz Hisseyi Seçin (Tüm Hisseler):", df_tum_hisseler['Hisse Kodu'].tolist())
        hisse_row = df_tum_hisseler[df_tum_hisseler['Hisse Kodu'] == secilen_kod].iloc[0]
        tam_kod = hisse_row['Tam Kod']
        
        # Durum Rozeti Göster
        if hisse_row['Durum'] == '✅ Geçti':
            st.success(f"**{secilen_kod}** süzgeçten başarıyla geçti! Temel Skor: **{hisse_row['Temel Skor (100)']} / 100**")
        else:
            st.error(f"**{secilen_kod}** süzgeçten elendi. Neden: **{hisse_row['Elenme Nedeni']}**")

        financials, info, history = fetch_stock_raw_data(tam_kod)
        
        if info:
            k1, k2, k3, k4 = st.columns(4)
            son_fiyat = history['Close'].iloc[-1] if (history is not None and not history.empty) else 0
            k1.metric("Son Fiyat", f"{son_fiyat:.2f} ₺/$")
            k2.metric("F/K Oranı", info.get('forwardPE') or info.get('trailingPE') or 'N/A')
            k3.metric("Özkaynak Kârlılığı (ROE)", f"%{round((info.get('returnOnEquity') or 0)*100, 1)}")
            k4.metric("Cari Oran", info.get('currentRatio') or 'N/A')
            
            st.markdown("---")
            tv_symbol = f"BIST:{secilen_kod}" if '.IS' in tam_kod else secilen_kod.replace('-', '.')

            st.markdown(f"##### 📈 {secilen_kod} - Canlı TradingView Grafiği ve Çizim Araçları")

            tv_widget_html = f"""
            <div class="tradingview-widget-container" style="height:550px;width:100%">
              <div id="tradingview_chart" style="height:500px;width:100%"></div>
              <script type="text/javascript" src="https://s3.tradingview.com/tv.js"></script>
              <script type="text/javascript">
              new TradingView.widget(
              {{
                "autosize": true,
                "symbol": "{tv_symbol}",
                "interval": "D",
                "timezone": "Europe/Istanbul",
                "theme": "dark",
                "style": "1",
                "locale": "tr",
                "toolbar_bg": "#f1f3f6",
                "enable_publishing": false,
                "allow_symbol_change": true,
                "show_popup_button": true,
                "popup_width": "1000",
                "popup_height": "650",
                "container_id": "tradingview_chart"
              }}
              );
              </script>
            </div>
            """
            components.html(tv_widget_html, height=520)

            st.markdown("---")
            st.markdown(f"##### 💰 {secilen_kod} - Çeyreklik Net Kâr & FAVÖK Trendi")
            if financials is not None and not financials.empty:
                eb_series = get_financial_value(financials, ['EBITDA', 'Normalized EBITDA', 'Operating Income'])
                net_series = get_financial_value(financials, ['Net Income', 'Net Income Common Stockholders'])
                if eb_series is not None and net_series is not None:
                    mali_df = pd.DataFrame({'FAVÖK': eb_series.iloc[:4][::-1], 'Net Kâr': net_series.iloc[:4][::-1]})
                    mali_df.index = [str(col).split('T')[0] for col in mali_df.index]
                    st.bar_chart(mali_df, height=300)

# TAB 3: TERİMLER SÖZLÜĞÜ
with tab3:
    st.markdown("""
    ### 📚 v4.0 Pro Şeffaf Analiz Rehberi
    
    * **Şeffaf Süzgeç:** Şirketlerin sadece başarılı olanları değil, elenen tüm şirketler elenme gerekçeleriyle (Örn: Net kârın negatif olması, FAVÖK gerilemesi veya F/K yüksekliği) açıkça raporlanır.
    * **BİST TÜM:** BİST 30 ve BİST 100 haricinde Borsa İstanbul'da işlem gören genişletilmiş 150+ şirketi tarar.
    * **Temel Skor (100 Üzerinden):** Finansal rasyoları harmanlayarak şirkete verilen kalite/ucuzluk notudur.
    """)
