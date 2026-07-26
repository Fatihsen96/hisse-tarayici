import streamlit as st
import yfinance as yf
import pandas as pd
import ta
import plotly.graph_objects as go
import warnings

warnings.filterwarnings('ignore')

# --- SAYFA YAPILANDIRMASI & ÖZEL TEMA ---
st.set_page_config(
    page_title="Sermaye & Değerleme Terminali v2.0",
    page_icon="💎",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Koyu / Şık Tasarım Dokunuşları (Custom CSS)
st.markdown("""
    <style>
    .main { padding-top: 1rem; }
    .stMetric { background-color: #1e222d; padding: 12px; border-radius: 8px; }
    </style>
""", unsafe_allow_html=True)

st.title("💎 Akıllı Hisse Filtreleme ve Analiz Terminali v2.0")
st.caption("BİST, S&P 500 & NASDAQ 100 - Profesyonel Mobil Uyumlu Yatırım Paneli")

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
        return None, f"Son çeyrek net kâr negatif ({son_net_kar:,.0f})"

    # 2. FAVÖK Kontrolü
    ebitda_series = get_financial_value(financials, ['EBITDA', 'Normalized EBITDA', 'Operating Income'])
    if ebitda_series is None or len(ebitda_series.dropna()) < 4:
        return None, "FAVÖK verisi eksik."
        
    ebitda_clean = ebitda_series.dropna()
    son_favok = ebitda_clean.iloc[0]
    if son_favok < ebitda_clean.iloc[1:4].max():
        return None, "Son FAVÖK önceki 3 çeyreğin gerisinde"

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

    son_rsi = None
    if history is not None and not history.empty and len(history) >= 15:
        rsi_series = ta.momentum.RSIIndicator(close=history['Close'], window=14).rsi()
        son_rsi = rsi_series.dropna().iloc[-1]
        if filtreler['rsi_aktif'] and (son_rsi < filtreler['rsi_min'] or son_rsi > filtreler['rsi_max']): return None, "RSI"
    elif filtreler['rsi_aktif']: return None, "RSI Verisi Yok"

    return {
        'Hisse Kodu': hisse_kodu.replace('.IS', ''),
        'Tam Kod': hisse_kodu,
        'Piyasa': 'BİST' if '.IS' in hisse_kodu else 'ABD',
        'Son Net Kar': round(son_net_kar, 0),
        'Son FAVÖK': round(son_favok, 0),
        'F/K': round(fk, 2) if fk else None,
        'PEG': round(peg, 2) if peg else None,
        'PD/DD': round(pd_dd, 2) if pd_dd else None,
        'Cari Oran': round(current_ratio, 2) if current_ratio else None,
        'Borç/Özkaynak': round(debt_to_equity / 100, 2) if debt_to_equity else None,
        'Net Marj (%)': round(profit_margins * 100, 2) if profit_margins else None,
        'ROE (%)': round(roe * 100, 2) if roe else None,
        'RSI (14)': round(son_rsi, 2) if son_rsi else None
    }, "BAŞARILI"


# --- YAN MENÜ ---
st.sidebar.header("🎯 1. Piyasayı Seçin")
piyasa_secimi = st.sidebar.radio(
    "Listenizi belirleyin:",
    ["BİST 30 (30 Hisse)", "BİST 100 (Tam 100 Hisse)", "S&P 500 Devleri (İlk 100)", "NASDAQ 100 (Tam 100 Hisse)", "Özel Liste"]
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

sp_500_tam = [
    'AAPL', 'NVDA', 'MSFT', 'GOOGL', 'AMZN', 'META', 'TSLA', 'BRK-B', 'UNH', 'JNJ',
    'JPM', 'XOM', 'V', 'PG', 'MA', 'HD', 'CVX', 'MRK', 'ABBV', 'COST',
    'PEP', 'KO', 'LLY', 'BAC', 'WMT', 'MCD', 'CSCO', 'ACN', 'ABT', 'ADBE',
    'AMGN', 'AON', 'AFL', 'AXP', 'BA', 'BMY', 'CAT', 'CL', 'CMCSA', 'COP',
    'CRM', 'DHR', 'DIS', 'EOG', 'FCX', 'GE', 'GILD', 'GS', 'HON', 'IBM',
    'INTC', 'INTU', 'ISRG', 'KMB', 'KHC', 'LIN', 'LMT', 'LOW', 'LRCX', 'MAR',
    'MDLZ', 'MDT', 'MET', 'MMM', 'MO', 'MS', 'MSI', 'NEE', 'NKE', 'NOC',
    'ORCL', 'PYPL', 'QCOM', 'RTX', 'SBUX', 'SCHW', 'SO', 'SPGI', 'T', 'TFC',
    'TMO', 'TMUS', 'TXN', 'USB', 'UPS', 'VZ', 'WFC', 'WMB', 'AMT', 'BKNG',
    'PFE', 'LOW', 'AMAT', 'DE', 'NOW', 'EL', 'GEHC', 'PLTR', 'UBER', 'PANW'
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
elif piyasa_secimi == "S&P 500 Devleri (İlk 100)": secilen_hisseler = sp_500_tam
elif piyasa_secimi == "NASDAQ 100 (Tam 100 Hisse)": secilen_hisseler = nasdaq_100_tam
else:
    girilen = st.sidebar.text_area("Hisseler (Virgülle):", "THYAO.IS, NVDA, AAPL")
    secilen_hisseler = [h.strip() for h in girilen.split(',') if h.strip()]

baslat_butonu = st.sidebar.button("🚀 Taramayı Başlat", type="primary")

# --- TARAMA İŞLEMİ ---
if baslat_butonu:
    st.info(f"Toplam {len(secilen_hisseler)} hisse taranıyor...")
    bar = st.progress(0)
    basarili = []
    
    for idx, hisse in enumerate(secilen_hisseler):
        veri, _ = hisse_analiz_et(hisse, filtre_paketı)
        if veri: basarili.append(veri)
        bar.progress((idx + 1) / len(secilen_hisseler))
    
    if basarili:
        df_sonuc = pd.DataFrame(basarili)
        df_sonuc.index = range(1, len(df_sonuc) + 1)
        st.session_state['sonuc_df'] = df_sonuc
        st.session_state['taranan_sayi'] = len(secilen_hisseler)
    else:
        st.session_state['sonuc_df'] = pd.DataFrame()
        st.session_state['taranan_sayi'] = len(secilen_hisseler)

# --- ARAYÜZ (SEKMELİ/TABBED TASARIM) ---
tab1, tab2, tab3 = st.tabs(["📊 Tarama & Süzgeç Sonuçları", "📈 Hisse Detay & Grafik", "📚 Terimler & Filtre Rehberi"])

# TAB 1: SONUÇLAR
with tab1:
    if 'sonuc_df' in st.session_state and not st.session_state['sonuc_df'].empty:
        df_sonuc = st.session_state['sonuc_df']
        taranan = st.session_state.get('taranan_sayi', 0)
        
        st.success("Tarama Tamamlandı!")
        c1, c2 = st.columns(2)
        c1.metric("Taranan Hisse", taranan)
        c2.metric("Süzgeçten Geçen Şirketler", len(df_sonuc))
        
        st.dataframe(
            df_sonuc.drop(columns=['Tam Kod']),
            use_container_width=True,
            column_config={
                "ROE (%)": st.column_config.ProgressColumn("ROE (%)", format="%.2f%%", min_value=0, max_value=100),
                "F/K": st.column_config.NumberColumn("F/K", format="%.2f"),
                "PEG": st.column_config.NumberColumn("PEG", format="%.2f"),
                "PD/DD": st.column_config.NumberColumn("PD/DD", format="%.2f"),
                "Cari Oran": st.column_config.NumberColumn("Cari Oran", format="%.2f"),
                "RSI (14)": st.column_config.NumberColumn("RSI (14)", format="%.2f"),
            }
        )
        
        csv = df_sonuc.to_csv(index=False).encode('utf-8')
        st.download_button("📥 Sonuçları İndir (Excel/CSV)", csv, "filtre_sonuclari_v2.csv", "text/csv")
    else:
        st.info("👈 Sol menüden filtrenizi ayarlayıp **'Taramayı Başlat'** butonuna tıklayın.")

# TAB 2: GRAFİK & DETAY
with tab2:
    if 'sonuc_df' in st.session_state and not st.session_state['sonuc_df'].empty:
        df_hafiza = st.session_state['sonuc_df']
        secilen_kod = st.selectbox("İncelemek İstediğiniz Hisseyi Seçin:", df_hafiza['Hisse Kodu'].tolist())
        tam_kod = df_hafiza[df_hafiza['Hisse Kodu'] == secilen_kod]['Tam Kod'].values[0]
        
        financials, info, history = fetch_stock_raw_data(tam_kod)
        
        if history is not None and not history.empty:
            # KPI KARTLARI
            k1, k2, k3, k4 = st.columns(4)
            k1.metric("Son Fiyat", f"{history['Close'].iloc[-1]:.2f} ₺/$")
            k2.metric("F/K Oranı", info.get('forwardPE') or 'N/A')
            k3.metric("Özkaynak Kârlılığı (ROE)", f"%{round((info.get('returnOnEquity') or 0)*100, 1)}")
            k4.metric("Cari Oran", info.get('currentRatio') or 'N/A')
            
            st.markdown("---")
            col_l, col_r = st.columns(2)
            
            with col_l:
                st.markdown(f"##### 📊 {secilen_kod} - 1 Yıllık Candlestick Grafik")
                fig = go.Figure(data=[go.Candlestick(
                    x=history.index, open=history['Open'], high=history['High'],
                    low=history['Low'], close=history['Close'], name=secilen_kod
                )])
                fig.update_layout(xaxis_rangeslider_visible=False, height=380, margin=dict(l=10, r=10, t=10, b=10))
                st.plotly_chart(fig, use_container_width=True)
                
            with col_r:
                st.markdown(f"##### 💰 {secilen_kod} - Çeyreklik Net Kâr & FAVÖK")
                if financials is not None and not financials.empty:
                    eb_series = get_financial_value(financials, ['EBITDA', 'Normalized EBITDA', 'Operating Income'])
                    net_series = get_financial_value(financials, ['Net Income', 'Net Income Common Stockholders'])
                    if eb_series is not None and net_series is not None:
                        mali_df = pd.DataFrame({'FAVÖK': eb_series.iloc[:4][::-1], 'Net Kâr': net_series.iloc[:4][::-1]})
                        mali_df.index = [str(col).split('T')[0] for col in mali_df.index]
                        st.bar_chart(mali_df, height=340)
    else:
        st.info("Detay inceleme yapabilmek için önce Tab 1 ekranından tarama yapmalısınız.")

# TAB 3: TERİMLER SÖZLÜĞÜ
with tab3:
    st.markdown("""
    ### 📚 Temel & Teknik Analiz Terimleri Rehberi
    
    * **ROE (Özkaynak Kârlılığı):** Yönetimin ortakların koyduğu parayla ne kadar net kâr ürettiğini gösterir. Yüksek ROE = Güçlü Yönetim.
    * **F/K (Fiyat / Kazanç):** Şirket fiyatının yıllık kârına oranıdır. Düşük olması ucuzluğa işaret eder.
    * **PEG Oranı:** F/K'nın kâr büyümesine oranıdır. $PEG < 1.0$ ise şirket büyümesine göre kelepir kabul edilir.
    * **Cari Oran:** Şirketin 1 yılda ödeyeceği borçları nakdiyle ödeme kapasitesidir. $Cari\ Oran \ge 1.0$ olmalıdır.
    * **RSI (14):** Teknik momentum göstergesidir. $RSI < 30$ aşırı ucuz, $RSI > 70$ aşırı ısınmış bölgeyi gösterir.
    """)
