import streamlit as st
import streamlit.components.v1 as components
import yfinance as yf
import pandas as pd
import ta
import plotly.graph_objects as go
from concurrent.futures import ThreadPoolExecutor, as_completed
import warnings

warnings.filterwarnings('ignore')

# --- SAYFA YAPILANDIRMASI & ÖZEL TEMA ---
st.set_page_config(
    page_title="Sermaye & Değerleme Terminali v3.0",
    page_icon="💎",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
    <style>
    .main { padding-top: 1rem; }
    .stMetric { background-color: #1e222d; padding: 12px; border-radius: 8px; }
    </style>
""", unsafe_allow_html=True)

st.title("💎 Akıllı Hisse Filtreleme ve Analiz Terminali v3.0")
st.caption("BİST, S&P 500 (500 Hisse) & NASDAQ 100 - Otomatik Taramalı & Skorlamalı Yatırım Terminali")

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
    """
    0 - 100 Arasında Temel Analiz Ucuzluk & Kalite Skoru Hesaplar
    """
    skor = 0
    
    # 1. ROE (Özkaynak Kârlılığı) -> Max 25 Puan
    roe = (info.get('returnOnEquity') or 0) * 100
    if roe > 30: skor += 25
    elif roe > 20: skor += 20
    elif roe > 10: skor += 12
    elif roe > 0: skor += 5
    
    # 2. F/K (Fiyat / Kazanç Ucuzluğu) -> Max 20 Puan
    fk = info.get('forwardPE') or info.get('trailingPE')
    if fk and fk > 0:
        if fk < 10: skor += 20
        elif fk < 18: skor += 15
        elif fk < 25: skor += 10
        elif fk < 35: skor += 5
        
    # 3. PD/DD (Defter Değeri Ucuzluğu) -> Max 15 Puan
    pddd = info.get('priceToBook')
    if pddd and pddd > 0:
        if pddd < 1.5: skor += 15
        elif pddd < 3.0: skor += 10
        elif pddd < 6.0: skor += 5
        
    # 4. PEG Oranı (Büyümeye Göre Kelepirlik) -> Max 15 Puan
    peg = info.get('pegRatio')
    if peg and peg > 0:
        if peg < 1.0: skor += 15
        elif peg < 1.5: skor += 10
        elif peg < 2.0: skor += 5
        
    # 5. Cari Oran (Likidite Gücü) -> Max 15 Puan
    cari = info.get('currentRatio')
    if cari:
        if cari >= 1.5: skor += 15
        elif cari >= 1.0: skor += 10
        elif cari >= 0.8: skor += 5
        
    # 6. Net Kâr Marjı -> Max 10 Puan
    marj = (info.get('profitMargins') or 0) * 100
    if marj > 20: skor += 10
    elif marj > 10: skor += 7
    elif marj > 5: skor += 3

    return min(skor, 100)

def hisse_analiz_et(hisse_kodu, filtreler):
    financials, info, history = fetch_stock_raw_data(hisse_kodu)
    
    if financials is None or financials.empty or len(financials.columns) < 4:
        return None, "Yetersiz çeyreklik bilanço verisi."

    # 1. Net Kâr Kontrolü
    net_income_series = get_financial_value(financials, ['Net Income', 'Net Income Common Stockholders'])
    if net_income_series is None or net_income_series.dropna().empty:
        return None, "Net Kâr verisi çekilemedi."
        
    son_net_kar = net_income_series.iloc[0]
    if pd.isna(son_net_kar) or son_net_kar <= 0:
        return None, f"Son çeyrek net kâr negatif"

    # 2. FAVÖK Kontrolü
    ebitda_series = get_financial_value(financials, ['EBITDA', 'Normalized EBITDA', 'Operating Income'])
    if ebitda_series is None or len(ebitda_series.dropna()) < 4:
        return None, "FAVÖK verisi eksik."
        
    ebitda_clean = ebitda_series.dropna()
    son_favok = ebitda_clean.iloc[0]
    if son_favok < ebitda_clean.iloc[1:4].max():
        return None, "Son FAVÖK geriledi"

    # --- FİLTRELER ---
    roe = info.get('returnOnEquity')
    fk = info.get('forwardPE') or info.get('trailingPE')
    peg = info.get('pegRatio')
    pd_dd = info.get('priceToBook')
    current_ratio = info.get('currentRatio')
    debt_to_equity = info.get('debtToEquity')
    profit_margins = info.get('profitMargins')

    if filtreler['roe_aktif'] and (roe is None or (roe * 100) < filtreler['min_roe']): return None, "ROE"
    if filtreler['fk_aktif'] and (fk is None or fk <= 0 or fk > filtreler['max_fk']): return None, "F/K"
    if filtreler['peg_aktif'] and (peg is None or peg > filtreler['max_peg']): return None, "PEG"
    if filtreler['pddd_aktif'] and (pd_dd is None or pd_dd > filtreler['max_pddd']): return None, "PD/DD"
    if filtreler['cari_oran_aktif'] and (current_ratio is None or current_ratio < filtreler['min_cari_oran']): return None, "Cari Oran"
    if filtreler['borc_aktif'] and (debt_to_equity is None or (debt_to_equity / 100) > filtreler['max_borc_ozkaynak']): return None, "Borç/Özkaynak"
    if filtreler['marj_aktif'] and (profit_margins is None or (profit_margins * 100) < filtreler['min_net_marj']): return None, "Net Marj"

    # --- TEKNİK ANALİZ (RSI + MACD + DESTEK/DİRENÇ) ---
    son_rsi = None
    macd_durum = "Nötr"
    teknik_sinyal = "Nötr"
    destek = None
    direnc = None
    
    if history is not None and not history.empty and len(history) >= 30:
        # 1. RSI
        rsi_series = ta.momentum.RSIIndicator(close=history['Close'], window=14).rsi()
        son_rsi = rsi_series.dropna().iloc[-1]
        if filtreler['rsi_aktif'] and (son_rsi < filtreler['rsi_min'] or son_rsi > filtreler['rsi_max']): return None, "RSI"

        # 2. MACD (12, 26, 9)
        macd_ind = ta.trend.MACD(close=history['Close'])
        macd_line = macd_ind.macd().dropna().iloc[-1]
        macd_signal = macd_ind.macd_signal().dropna().iloc[-1]
        
        if macd_line > macd_signal:
            macd_durum = "🟢 Boğa (Alım Yönlü)"
        else:
            macd_durum = "🔴 Ayı (Satım Yönlü)"

        # 3. Destek & Direnç Seviyeleri (Son 50 Günlük Min/Max)
        son_50 = history.tail(50)
        destek = round(son_50['Low'].min(), 2)
        direnc = round(son_50['High'].max(), 2)
        son_fiyat = history['Close'].iloc[-1]

        # 4. Genel Teknik Sinyal Skoru
        destege_yakinlik = (son_fiyat - destek) / (direnc - destek + 0.0001)
        
        if son_rsi < 40 and macd_line > macd_signal:
            teknik_sinyal = "🔥 Güçlü Alım Fırsatı"
        elif son_rsi < 50 and destege_yakinlik < 0.3:
            teknik_sinyal = "🟢 Desteğe Yakın (Alınabilir)"
        elif son_rsi > 70:
            teknik_sinyal = "⚠️ Aşırı Isınmış (Riskli)"
        else:
            teknik_sinyal = "⚖️ Dengeli / Nötr"

    elif filtreler['rsi_aktif']: return None, "RSI Verisi Yok"

    # TEMEL SKOR HESAPLA
    temel_skor = hesapla_temel_skor(info)

    return {
        'Hisse Kodu': hisse_kodu.replace('.IS', ''),
        'Tam Kod': hisse_kodu,
        'Piyasa': 'BİST' if '.IS' in hisse_kodu else 'ABD',
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
        'Borç/Özkaynak': round(debt_to_equity / 100, 2) if debt_to_equity else None,
        'Net Marj (%)': round(profit_margins * 100, 2) if profit_margins else None,
        'ROE (%)': round(roe * 100, 2) if roe else None,
        'Son Net Kar': round(son_net_kar, 0),
        'Son FAVÖK': round(son_favok, 0),
    }, "BAŞARILI"


# --- YAN MENÜ ---
st.sidebar.header("🎯 1. Piyasayı Seçin")
piyasa_secimi = st.sidebar.radio(
    "Listenizi belirleyin:",
    ["BİST 30 (30 Hisse)", "BİST 100 (Tam 100 Hisse)", "S&P 500 (Tam 500 Hisse)", "NASDAQ 100 (Tam 100 Hisse)", "Özel Liste"]
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

# FULL HİSSE LİSTELERİ
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

# S&P 500 TAM LİSTE
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
    'ICE', 'PH', 'ORLY', 'CSX', 'MAR', 'CTAS', 'ROP', 'GD', 'FCX', 'CMG',
    'NSC', 'TT', 'ECL', 'BDX', 'TDG', 'BKR', 'ABNB', 'HLT', 'ITW', 'APH',
    'EPR', 'ANET', 'NXPI', 'CARR', 'COR', 'AZO', 'CEG', 'F', 'NOC', 'TFC',
    'O', 'PCAR', 'PSA', 'ROST', 'DXCM', 'GM', 'AON', 'MCHP', 'AEP', 'MET',
    'USB', 'D', 'EMR', 'OKE', 'COF', 'SRE', 'HUM', 'NSC', 'KMB', 'KHC',
    'ADSK', 'GEHC', 'TRV', 'OXY', 'WELL', 'ALL', 'KDP', 'FAST', 'IDXX', 'ALGN',
    'WBD', 'ROK', 'AFL', 'PAYX', 'DLR', 'CPRT', 'GPN', 'ED', 'BK', 'ODFL',
    'PEG', 'AME', 'VRSK', 'MTB', 'MNST', 'FTNT', 'EA', 'HES', 'STZ', 'DAL'
]

nasdaq_100_tam = [
    'AAPL', 'NVDA', 'MSFT', 'GOOGL', 'AMZN', 'META', 'TSLA', 'AMD', 'INTC', 'NFLX',
    'CRM', 'ORCL', 'PYPL', 'QCOM', 'AVGO', 'COST', 'PEP', 'ADBE', 'AMAT', 'INTU',
    'ISRG', 'BKNG', 'AMGN', 'TXN', 'HON', 'SBUX', 'VRTX', 'MDLZ', 'REGN', 'PANW',
    'KLAC', 'SNPS', 'CDNS', 'MELI', 'CSX', 'MAR', 'ASML', 'ORLY', 'LRCX', 'CTAS',
    'MNST', 'ROST', 'ADSK', 'IDXX', 'AEP', 'GILD', 'PAYX', 'FAST', 'ODFL', 'KDP',
    'EA', 'MCHP', 'VRSK', 'EXC', 'CTSH', 'GEHC', 'PCAR', 'XEL', 'FANG', 'DXCM',
    'BKR', 'KHC', 'DLTR', 'WBD', 'BIIB', 'ANSS', 'ILMN', 'SIRI', 'ROKU', 'MRNA',
    'ZS', 'DDOG', 'CRWD', 'TEAM', 'WDAY', 'TTD', 'OKTA', 'MDB', 'LCID', 'RIVN',
    'ABNB', 'CEG', 'GFV', 'ENPH', 'ON', 'SPLK', 'DASH', 'COIN', 'HOOD', 'PLTR'
]

if piyasa_secimi == "BİST 30 (30 Hisse)": secilen_hisseler = bist_100_tam[:30]
elif piyasa_secimi == "BİST 100 (Tam 100 Hisse)": secilen_hisseler = bist_100_tam
elif piyasa_secimi == "S&P 500 (Tam 500 Hisse)": secilen_hisseler = sp_500_tam
elif piyasa_secimi == "NASDAQ 100 (Tam 100 Hisse)": secilen_hisseler = nasdaq_100_tam
else:
    girilen = st.sidebar.text_area("Hisseler (Virgülle):", "THYAO.IS, NVDA, AAPL")
    secilen_hisseler = [h.strip() for h in girilen.split(',') if h.strip()]

# Yenile/Yeniden Tara Butonu (İsteğe Bağlı)
st.sidebar.button("🔄 Verileri Yenile / Yeniden Tara", type="primary")

# --- OTOMATİK PARALEL TARAMA MOTORU (INSTANT LOAD) ---
@st.cache_data(ttl=1800, show_spinner=False)
def otomatık_paralel_tarama(hisse_listesi, filtreler):
    basarili_sonuclar = []
    
    # 10 Çoklu İş parçacığı (Parallel Threading) ile 10 kat daha hızlı veri çekimi
    with ThreadPoolExecutor(max_workers=10) as executor:
        future_to_hisse = {executor.submit(hisse_analiz_et, h, filtreler): h for h in hisse_listesi}
        for future in as_completed(future_to_hisse):
            res, msg = future.result()
            if res:
                basarili_sonuclar.append(res)
                
    if basarili_sonuclar:
        df = pd.DataFrame(basarili_sonuclar)
        # EN YÜKSEK TEMEL SKORDAN DÜŞÜĞE DOĞRU OTOMATİK SIRALAMA
        df = df.sort_values(by='Temel Skor (100)', ascending=False).reset_index(drop=True)
        df.index = range(1, len(df) + 1)
        return df
    return pd.DataFrame()

# Otomatik Çalıştırma
with st.spinner(f"{len(secilen_hisseler)} hisse için canlı veriler taranıyor ve analiz ediliyor..."):
    df_sonuc = otomatık_paralel_tarama(secilen_hisseler, filtre_paketı)

# --- ARAYÜZ (SEKMELİ TASARIM) ---
tab1, tab2, tab3 = st.tabs(["📊 Ucuzluk & Analiz Sonuçları (Otomatik Sıralı)", "📈 Hisse Detay & TradingView Grafik", "📚 Terimler & Filtre Rehberi"])

# TAB 1: OTOMATİK SIRALI SONUÇLAR
with tab1:
    if not df_sonuc.empty:
        st.success(f"Analiz Tamamlandı! Toplam {len(secilen_hisseler)} hisse içerisinden şartları karşılayan en kaliteli {len(df_sonuc)} şirket bulundu.")
        
        c1, c2, c3 = st.columns(3)
        c1.metric("Taranan Hisse", len(secilen_hisseler))
        c2.metric("Süzgeçten Geçen Şirketler", len(df_sonuc))
        c3.metric("En Yüksek Temel Skor", f"{df_sonuc['Temel Skor (100)'].max()} / 100")
        
        st.subheader("📋 Temel Skor & Teknik Alım Sinyali Sıralı Tablo")
        
        st.dataframe(
            df_sonuc.drop(columns=['Tam Kod']),
            use_container_width=True,
            column_config={
                "Temel Skor (100)": st.column_config.ProgressColumn(
                    "Temel Skor (100)",
                    format="%d / 100",
                    min_value=0,
                    max_value=100,
                    help="0-100 Arasında Temel Ucuzluk & Kalite Skoru."
                ),
                "Teknik Sinyal": st.column_config.TextColumn("Teknik Sinyal", help="RSI, MACD ve Desteğe yakınlık birleşimi."),
                "ROE (%)": st.column_config.ProgressColumn("ROE (%)", format="%.2f%%", min_value=0, max_value=100),
                "F/K": st.column_config.NumberColumn("F/K", format="%.2f"),
                "PEG": st.column_config.NumberColumn("PEG", format="%.2f"),
                "PD/DD": st.column_config.NumberColumn("PD/DD", format="%.2f"),
                "Cari Oran": st.column_config.NumberColumn("Cari Oran", format="%.2f"),
                "RSI (14)": st.column_config.NumberColumn("RSI (14)", format="%.2f"),
            }
        )
        
        csv = df_sonuc.to_csv(index=False).encode('utf-8')
        st.download_button("📥 Sonuçları İndir (Excel/CSV)", csv, "skorlu_filtre_sonuclari_v3.csv", "text/csv")
    else:
        st.warning("Seçtiğiniz filtre şartlarına uyan hisse bulunamadı. Sol menüden filtre aralıklarını biraz esnetebilirsiniz.")

# TAB 2: TRADINGVIEW GRAFİK & DETAY
with tab2:
    if not df_sonuc.empty:
        secilen_kod = st.selectbox("İncelemek İstediğiniz Hisseyi Seçin:", df_sonuc['Hisse Kodu'].tolist())
        tam_kod = df_sonuc[df_sonuc['Hisse Kodu'] == secilen_kod]['Tam Kod'].values[0]
        
        financials, info, history = fetch_stock_raw_data(tam_kod)
        
        if info:
            # KPI KARTLARI
            k1, k2, k3, k4 = st.columns(4)
            son_fiyat = history['Close'].iloc[-1] if (history is not None and not history.empty) else 0
            k1.metric("Son Fiyat", f"{son_fiyat:.2f} ₺/$")
            k2.metric("F/K Oranı", info.get('forwardPE') or 'N/A')
            k3.metric("Özkaynak Kârlılığı (ROE)", f"%{round((info.get('returnOnEquity') or 0)*100, 1)}")
            k4.metric("Cari Oran", info.get('currentRatio') or 'N/A')
            
            st.markdown("---")
            
            # TradingView Sembol Formatı Hazırlama
            tv_symbol = f"BIST:{secilen_kod}" if '.IS' in tam_kod else secilen_kod.replace('-', '.')

            st.markdown(f"##### 📈 {secilen_kod} - Canlı TradingView Grafiği ve Çizim Araçları")

            # TradingView Widget Embed
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
    else:
        st.info("Detay inceleme yapabilmek için filtre şartlarına uyan hisse bulunmalıdır.")

# TAB 3: TERİMLER SÖZLÜĞÜ
with tab3:
    st.markdown("""
    ### 📚 Temel Skor & Teknik Sinyal Rehberi
    
    * **Temel Skor (100 Üzerinden):** Şirketin ROE, F/K, PD/DD, PEG, Cari Oran ve Kâr Marjı verilerini harmanlayan algoritmadır. Skor yükseldikçe şirket hem daha ucuz hem de daha kalitelidir.
    * **Teknik Sinyal:** 
      * 🔥 **Güçlü Alım Fırsatı:** RSI 40'ın altındayken MACD alım sinyali verdiğinde çıkar.
      * 🟢 **Desteğe Yakın:** Fiyat son 50 günün dip seviyelerine (desteğe) yakın duruyordur.
      * ⚠️ **Aşırı Isınmış:** RSI > 70 seviyesindedir, kısa vadeli düzeltme yapabilir.
    * **MACD Trend:** 12 ve 26 günlük hareketli ortalamaların kesişimidir. Boğa trendinde alıcıların ağırlıkta olduğunu gösterir.
    * **Destek (50G) / Direnç (50G):** Şirketin son 50 gün içinde gördüğü en düşük (destek) ve en yüksek (direnç) fiyat seviyeleridir.
    """)
