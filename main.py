import streamlit as st
import streamlit.components.v1 as components
import yfinance as yf
import pandas as pd
import ta
from concurrent.futures import ThreadPoolExecutor, as_completed
import warnings

warnings.filterwarnings('ignore')

# --- SAYFA YAPILANDIRMASI & MAT SİYAH (TRUE DARK) TEMA ---
st.set_page_config(
    page_title="Sermaye & Değerleme Terminali v5.0",
    page_icon="🖤",
    layout="wide",
    initial_sidebar_state="expanded"
)

# FINTABLES/PROFESYONEL BANT TARZI CSS
st.markdown("""
    <style>
    /* Ana Arka Plan ve Metinler */
    .stApp {
        background-color: #121212 !important;
        color: #ffffff !important;
    }
    [data-testid="stSidebar"] {
        background-color: #181818 !important;
        border-right: 1px solid #2a2a2a !important;
    }
    
    /* Sekme (Tab) Tasarımı */
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
        background-color: #181818;
        padding: 8px;
        border-radius: 8px;
        border: 1px solid #282828;
    }
    .stTabs [data-baseweb="tab"] {
        color: #a0a0a0 !important;
        font-weight: 600;
        border-radius: 6px;
        padding: 8px 16px;
    }
    .stTabs [aria-selected="true"] {
        background-color: #282828 !important;
        color: #ffffff !important;
        border-bottom: 2px solid #38bdf8 !important;
    }
    
    /* Metrik Kartları */
    .stMetric {
        background-color: #181818 !important;
        border: 1px solid #2a2a2a !important;
        border-radius: 8px !important;
        padding: 12px !important;
    }
    [data-testid="stMetricLabel"] { color: #888888 !important; }
    [data-testid="stMetricValue"] { color: #38bdf8 !important; font-weight: 700 !important; }
    
    /* Dataframe Tablo Özelleştirmeleri */
    .stDataFrame {
        border: 1px solid #282828;
        border-radius: 8px;
    }
    </style>
""", unsafe_allow_html=True)

st.title("🖤 Sermaye ve Değerleme Terminali v5.0")
st.caption("BİST Tüm, S&P 500 & NASDAQ 100 - Profesyonel Kategorize Analiz Ekranı")

# --- SAYI FORMATLAMA (Milyar / Milyon) ---
def format_para_birimi(val):
    if val is None or pd.isna(val): return "N/A"
    abs_val = abs(val)
    if abs_val >= 1e9:
        return f"{val / 1e9:.2f} mr"
    elif abs_val >= 1e6:
        return f"{val / 1e6:.2f} mn"
    return f"{val:,.0f}"

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
            'Elenme Nedeni': 'Eksik Bilanço Verisi',
            'Piyasa Cap': 'N/A', 'Temel Skor': 0, 'F/K': None, 'PD/DD': None, 'PEG': None,
            'ROE (%)': None, 'Net Marj (%)': None, 'Cari Oran': None, 'Borç/Özkaynak': None, 'RSI (14)': None, 'Teknik Sinyal': 'N/A'
        }

    # Bilanço Verileri
    net_income_series = get_financial_value(financials, ['Net Income', 'Net Income Common Stockholders'])
    son_net_kar = net_income_series.iloc[0] if net_income_series is not None and not net_income_series.dropna().empty else None
    
    ebitda_series = get_financial_value(financials, ['EBITDA', 'Normalized EBITDA', 'Operating Income'])
    son_favok = ebitda_series.iloc[0] if ebitda_series is not None and len(ebitda_series.dropna()) >= 4 else None

    # Değerleme ve Büyüklük Rasyoları
    market_cap = info.get('marketCap')
    enterprise_val = info.get('enterpriseValue')
    roe = (info.get('returnOnEquity') or 0) * 100
    fk = info.get('forwardPE') or info.get('trailingPE')
    peg = info.get('pegRatio')
    pd_dd = info.get('priceToBook')
    current_ratio = info.get('currentRatio')
    debt_to_equity = (info.get('debtToEquity') or 0) / 100
    profit_margins = (info.get('profitMargins') or 0) * 100

    # RSI & Teknik Analiz
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

    # ELEME KONTROLLERİ
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
        'Piyasa Değeri': format_para_birimi(market_cap),
        'Firma Değeri': format_para_birimi(enterprise_val),
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
        'Son Net Kâr': format_para_birimi(son_net_kar),
        'Son FAVÖK': format_para_birimi(son_favok)
    }

# --- YAN MENÜ ---
st.sidebar.header("🎯 1. Piyasayı Seçin")
piyasa_secimi = st.sidebar.radio(
    "Listenizi belirleyin:",
    ["BİST 30 (30 Hisse)", "BİST 100 (100 Hisse)", "BİST TÜM (150+ Hisse)", "S&P 500 (500 Hisse)", "NASDAQ 100 (100 Hisse)", "Özel Liste"]
)

st.sidebar.header("⚙️ 2. Temel & Teknik Filtreler")

fk_aktif = st.sidebar.checkbox("F/K Filtresi", value=True)
max_fk = st.sidebar.slider("Maksimum F/K", 1.0, 100.0, 35.0, 1.0) if fk_aktif else 999.0

peg_aktif = st.sidebar.checkbox("PEG Oranı Filtresi", value=False)
max_peg = st.sidebar.slider("Maksimum PEG", 0.1, 5.0, 1.5, 0.1) if peg_aktif else 999.0

pddd_aktif = st.sidebar.checkbox("PD/DD Filtresi", value=True)
max_pddd = st.sidebar.slider("Maksimum PD/DD", 0.5, 20.0, 10.0, 0.5) if pddd_aktif else 999.0

roe_aktif = st.sidebar.checkbox("ROE (Özkaynak Kârlılığı)", value=True)
min_roe = st.sidebar.slider("Minimum ROE (%)", 0, 100, 10, 5) if roe_aktif else -999.0

cari_oran_aktif = st.sidebar.checkbox("Cari Oran (Likidite)", value=True)
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
            if res:
                tum_sonuclar.append(res)
                
    if tum_sonuclar:
        df = pd.DataFrame(tum_sonuclar)
        df = df.sort_values(by=['Durum', 'Temel Skor'], ascending=[False, False]).reset_index(drop=True)
        return df
    return pd.DataFrame()

# Tarama Yürütücü
with st.spinner(f"{len(secilen_hisseler)} hisse taranıyor..."):
    df_tum_hisseler = otomatık_paralel_tarama(secilen_hisseler, filtre_paketı)

# --- ARAYÜZ (KATEGORİZE TABLOLAR) ---
tab_ana1, tab_ana2, tab_ana3 = st.tabs(["📊 Terminal Tablo Görünümü", "📈 Interactive TradingView", "📚 Rehber"])

with tab_ana1:
    if not df_tum_hisseler.empty:
        df_gecenler = df_tum_hisseler[df_tum_hisseler['Durum'] == '✅ Geçti'].reset_index(drop=True)
        df_elenenler = df_tum_hisseler[df_tum_hisseler['Durum'] == '❌ Elendi'].reset_index(drop=True)
        
        df_gecenler.index = range(1, len(df_gecenler) + 1)
        df_elenenler.index = range(1, len(df_elenenler) + 1)

        # ÜST METRİK KARTLARI
        c1, c2, c3 = st.columns(3)
        c1.metric("Taranan Hisse", len(df_tum_hisseler))
        c2.metric("Süzgeçten Geçen", len(df_gecenler))
        c3.metric("Elenen Hisse", len(df_elenenler))
        
        st.markdown("<br>", unsafe_allow_html=True)
        
        # FİNTABLES TARZI KATEGORİ SEKMELERİ
        kat_degerleme, kat_karlilik, kat_borcluluk, kat_teknik, kat_elenenler = st.tabs([
            "🏷️ Değerleme", 
            "💰 Kârlılık", 
            "🛡️ Borçluluk & Likidite", 
            "⚡ Teknik Analiz", 
            f"❌ Elenenler ({len(df_elenenler)})"
        ])

        # Sütun Gruplandırmaları
        with kat_degerleme:
            st.caption("Süzgeçten geçen şirketlerin piyasa büyüklükleri ve değerleme çarpanları:")
            st.dataframe(
                df_gecenler[['Hisse Kodu', 'Piyasa', 'Temel Skor', 'Piyasa Değeri', 'Firma Değeri', 'F/K', 'PD/DD', 'PEG']],
                use_container_width=True
            )

        with kat_karlilik:
            st.caption("Şirketlerin kâr marjları ve sermaye büyüme verileri:")
            st.dataframe(
                df_gecenler[['Hisse Kodu', 'Temel Skor', 'ROE (%)', 'Net Marj (%)', 'Son Net Kâr', 'Son FAVÖK']],
                use_container_width=True
            )

        with kat_borcluluk:
            st.caption("Likidite oranları ve finansal borçluluk durumu:")
            st.dataframe(
                df_gecenler[['Hisse Kodu', 'Temel Skor', 'Cari Oran', 'Borç/Özkaynak']],
                use_container_width=True
            )

        with kat_teknik:
            st.caption("Momentum, MACD sinyali ve alım noktası değerlendirmesi:")
            st.dataframe(
                df_gecenler[['Hisse Kodu', 'Teknik Sinyal', 'RSI (14)', 'MACD Trend']],
                use_container_width=True
            )

        with kat_elenenler:
            st.caption("Süzgeçten geçemeyen şirketler ve detaylı elenme sebepleri:")
            st.dataframe(
                df_elenenler[['Hisse Kodu', 'Elenme Nedeni', 'Piyasa Değeri', 'F/K', 'ROE (%)', 'Cari Oran', 'RSI (14)']],
                use_container_width=True
            )
            
        csv = df_tum_hisseler.to_csv(index=False).encode('utf-8')
        st.download_button("📥 Tüm Raporu İndir (Excel/CSV)", csv, "fintables_stil_terminal_v5.csv", "text/csv")

# TAB 2: TRADINGVIEW GRAFİK
with tab_ana2:
    if not df_tum_hisseler.empty:
        secilen_kod = st.selectbox("İncelemek İstediğiniz Hisseyi Seçin:", df_tum_hisseler['Hisse Kodu'].tolist())
        hisse_row = df_tum_hisseler[df_tum_hisseler['Hisse Kodu'] == secilen_kod].iloc[0]
        tam_kod = hisse_row['Tam Kod']
        
        if hisse_row['Durum'] == '✅ Geçti':
            st.success(f"**{secilen_kod}** süzgeçten başarıyla geçti! Temel Skor: **{hisse_row['Temel Skor']} / 100**")
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

            st.markdown(f"##### 📈 {secilen_kod} - Canlı TradingView Grafiği")

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
                "container_id": "tradingview_chart"
              }}
              );
              </script>
            </div>
            """
            components.html(tv_widget_html, height=520)

# TAB 3: REHBER
with tab_ana3:
    st.markdown("""
    ### 📚 v5.0 Fintables Stil Terminal Rehberi
    * **Değerleme:** Piyasa Değeri, Firma Değeri, F/K, PD/DD ve PEG rasyolarını gruplar.
    * **Kârlılık:** Özkaynak Kârlılığı (ROE), Net Marj, Çeyreklik Kâr ve FAVÖK rakamlarını sunar.
    * **Borçluluk:** Likidite riskini ölçen Cari Oran ve Borç/Özkaynak oranlarını içerir.
    * **Büyüklük Formatı:** Rakamlar `mr` (Milyar) ve `mn` (Milyon) olarak okunması kolay formatta sunulur.
    """)
