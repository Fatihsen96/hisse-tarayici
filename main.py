import streamlit as st
import yfinance as yf
import pandas as pd
import ta
import plotly.graph_objects as go
import warnings

warnings.filterwarnings('ignore')

# --- SAYFA YAPILANDIRMASI ---
st.set_page_config(
    page_title="Sermaye & Değerleme Tarayıcısı v1.9",
    page_icon="📈",
    layout="wide"
)

st.title("📈 Akıllı Hisse Filtreleme ve Tarama Paneli v1.9")
st.caption("BİST, S&P 500 & NASDAQ 100 - Anlık Bilgi Baloncuklu (Tooltip) Küresel Terminal")

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
    net_income_keys = ['Net Income', 'Net Income Common Stockholders', 'Net Income Including Noncontrolling Interests']
    net_income_series = get_financial_value(financials, net_income_keys)
    
    if net_income_series is None or net_income_series.dropna().empty:
        return None, "Net Kâr verisi çekilemedi."
        
    son_net_kar = net_income_series.iloc[0]
    if pd.isna(son_net_kar) or son_net_kar <= 0:
        return None, f"Son çeyrek net kâr negatif ({son_net_kar:,.0f})"

    # 2. FAVÖK / EBITDA Kontrolü
    ebitda_keys = ['EBITDA', 'Normalized EBITDA', 'Operating Income', 'EBIT']
    ebitda_series = get_financial_value(financials, ebitda_keys)
    
    if ebitda_series is None or len(ebitda_series.dropna()) < 4:
        return None, "FAVÖK/EBITDA verisi eksik."
        
    ebitda_clean = ebitda_series.dropna()
    son_favok = ebitda_clean.iloc[0]
    onceki_3_favok = ebitda_clean.iloc[1:4]
    
    if son_favok < onceki_3_favok.max():
        return None, "Son FAVÖK önceki 3 çeyreğin gerisinde"

    # --- FİLTRELER ---
    roe = info.get('returnOnEquity')
    fk = info.get('forwardPE') or info.get('trailingPE')
    peg = info.get('pegRatio')
    pd_dd = info.get('priceToBook')
    current_ratio = info.get('currentRatio')
    debt_to_equity = info.get('debtToEquity')
    profit_margins = info.get('profitMargins')

    if filtreler['roe_aktif'] and (roe is None or (roe * 100) < filtreler['min_roe']):
        return None, "ROE elendi"

    if filtreler['fk_aktif'] and (fk is None or fk <= 0 or fk > filtreler['max_fk']):
        return None, "F/K elendi"

    if filtreler['peg_aktif'] and (peg is None or peg > filtreler['max_peg']):
        return None, "PEG elendi"

    if filtreler['pddd_aktif'] and (pd_dd is None or pd_dd > filtreler['max_pddd']):
        return None, "PD/DD elendi"

    if filtreler['cari_oran_aktif'] and (current_ratio is None or current_ratio < filtreler['min_cari_oran']):
        return None, "Cari Oran elendi"

    if filtreler['borc_aktif'] and (debt_to_equity is None or (debt_to_equity / 100) > filtreler['max_borc_ozkaynak']):
        return None, "Borç/Özkaynak elendi"

    if filtreler['marj_aktif'] and (profit_margins is None or (profit_margins * 100) < filtreler['min_net_marj']):
        return None, "Net Marj elendi"

    son_rsi = None
    if history is not None and not history.empty and len(history) >= 15:
        rsi_series = ta.momentum.RSIIndicator(close=history['Close'], window=14).rsi()
        son_rsi = rsi_series.dropna().iloc[-1]
        
        if filtreler['rsi_aktif'] and (son_rsi < filtreler['rsi_min'] or son_rsi > filtreler['rsi_max']):
            return None, "RSI elendi"
    elif filtreler['rsi_aktif']:
        return None, "RSI verisi yok"

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


# --- YAN MENÜ VE İNTERAKTİF BİLGİ BALONLARI (TOOLTIPS) ---
st.sidebar.header("🎯 1. Piyasayı Seçin")

piyasa_secimi = st.sidebar.radio(
    "Listenizi belirleyin:",
    ["BİST 30 (30 Hisse)", "BİST 100 (Tam 100 Hisse)", "S&P 500 Devleri (İlk 100)", "NASDAQ 100 (Tam 100 Hisse)", "Özel Liste"],
    help="Hangi borsadaki veya endeksteki hisseleri süzgeçten geçirmek istediğinizi seçin."
)

st.sidebar.header("⚙️ 2. Temel & Teknik Filtreler")

# 1. F/K Filtresi & Tooltip
fk_aktif = st.sidebar.checkbox(
    "F/K Filtresi", 
    value=True,
    help="Fiyat/Kazanç Oranı: Şirket piyasa değerinin yıllık net kârına oranıdır. Şirketin kârına kıyasla ucuz mu pahalı mı olduğunu gösterir."
)
max_fk = st.sidebar.slider(
    "Maksimum F/K", 1.0, 100.0, 35.0, 1.0,
    help="Üst sınır. Genelde 15-35 arası kabul görür. Kâr etmeyen veya kârına göre aşırı pahalanmış şirketleri eler."
) if fk_aktif else 999.0

# 2. PEG Filtresi & Tooltip
peg_aktif = st.sidebar.checkbox(
    "PEG Oranı Filtresi", 
    value=False,
    help="Price/Earnings-to-Growth: F/K oranının kâr büyüme hızına bölünmesidir. PEG < 1 olan şirketler kâr büyümesine göre kelepir kabul edilir."
)
max_peg = st.sidebar.slider(
    "Maksimum PEG", 0.1, 5.0, 1.5, 0.1,
    help="PEG değerinin 1.0 veya 1.5 altında olması şirketin büyüme potansiyelinin fiyata henüz tam yansımadığını gösterir."
) if peg_aktif else 999.0

# 3. PD/DD Filtresi & Tooltip
pddd_aktif = st.sidebar.checkbox(
    "PD/DD Filtresi", 
    value=True,
    help="Piyasa Değeri / Defter Değeri: Şirket borsa değerinin toplam net özkaynaklarına oranıdır. Şirketin varlıklarına göre ederi kadar satılıp satılmadığını söyler."
)
max_pddd = st.sidebar.slider(
    "Maksimum PD/DD", 0.5, 20.0, 10.0, 0.5,
    help="Üst sınır. Sanayi ve gayrimenkulde 1-3 arası, teknoloji ve yazılımda daha yüksek PD/DD oranları normal karşılanabilir."
) if pddd_aktif else 999.0

# 4. ROE Filtresi & Tooltip
roe_aktif = st.sidebar.checkbox(
    "ROE (Özkaynak Kârlılığı)", 
    value=True,
    help="Return on Equity: Şirket yönetiminin ortakların koyduğu öz sermayeyle yüzde kaç net kâr ürettiğidir. Yönetim kalitesinin ve verimliliğin en önemli göstergesidir."
)
min_roe = st.sidebar.slider(
    "Minimum ROE (%)", 0, 100, 10, 5,
    help="Sermayesini enflasyondan hızlı büyütebilen kaliteli şirketleri seçer. Enflasyonist ortamlarda %20+ olması tercih edilir."
) if roe_aktif else -999.0

# 5. Cari Oran Filtresi & Tooltip
cari_oran_aktif = st.sidebar.checkbox(
    "Cari Oran (Likidite)", 
    value=True,
    help="Dönen Varlıklar / Kısa Vadeli Borçlar: Şirketin önümüzdeki 1 yıl içinde ödeyeceği borçları nakdiyle ödeme gücüdür."
)
min_cari_oran = st.sidebar.slider(
    "Minimum Cari Oran", 0.5, 5.0, 1.0, 0.1,
    help="1.0 ve üzeri olması şirketin önümüzdeki 1 yıl içinde nakit krizine girme veya batma riskini ortadan kaldırır."
) if cari_oran_aktif else 0.0

# 6. Borç / Özkaynak Filtresi & Tooltip
borc_aktif = st.sidebar.checkbox(
    "Borç / Özkaynak Oranı", 
    value=False,
    help="Toplam Borçlar / Özkaynaklar: Şirketin ne kadar borçla döndüğünü ölçer. Yüksek borç kriz anlarında risk oluşturur."
)
max_borc_ozkaynak = st.sidebar.slider(
    "Maksimum Borç/Özkaynak", 0.1, 10.0, 2.0, 0.1,
    help="2.0 altında olması şirketin özkaynaklarına kıyasla makul bir borç yükü taşıdığını gösterir."
) if borc_aktif else 999.0

# 7. Net Marj Filtresi & Tooltip
marj_aktif = st.sidebar.checkbox(
    "Net Kâr Marjı (%)", 
    value=False,
    help="Net Kâr / Toplam Satışlar: Şirketin elde ettiği cironun yüzde kaçını cebine kâr olarak koyabildiğini gösterir."
)
min_net_marj = st.sidebar.slider(
    "Minimum Net Marj (%)", 0, 50, 5, 1,
    help="Şirketin fiyatta pazarlık gücü ve maliyet kontrol kapasitesini ölçer. Yüksek marjlı şirketler krizlere dayanıklıdır."
) if marj_aktif else -999.0

# 8. RSI Filtresi & Tooltip
rsi_aktif = st.sidebar.checkbox(
    "RSI (14) Filtresi", 
    value=True,
    help="Relative Strength Index: 14 günlük teknik momentum göstergesi. Fiyatın aşırı alım mı yoksa aşırı satım bölgesinde mi olduğunu söyler."
)
rsi_araligi = st.sidebar.slider(
    "RSI Aralığı", 0, 100, (30, 70),
    help="30-70 arası sağlıklı trenddir. RSI < 30 aşırı ucuz/satılmış bölgeyi, RSI > 70 aşırı pahalı/ısınmış bölgeyi gösterir."
) if rsi_aktif else (0, 100)

filtre_paketı = {
    'fk_aktif': fk_aktif, 'max_fk': max_fk,
    'peg_aktif': peg_aktif, 'max_peg': max_peg,
    'pddd_aktif': pddd_aktif, 'max_pddd': max_pddd,
    'roe_aktif': roe_aktif, 'min_roe': min_roe,
    'cari_oran_aktif': cari_oran_aktif, 'min_cari_oran': min_cari_oran,
    'borc_aktif': borc_aktif, 'max_borc_ozkaynak': max_borc_ozkaynak,
    'marj_aktif': marj_aktif, 'min_net_marj': min_net_marj,
    'rsi_aktif': rsi_aktif, 'rsi_min': rsi_araligi[0], 'rsi_max': rsi_araligi[1]
}

# --- FULL HİSSE LİSTELERİ ---
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

bist_30_listesi = bist_100_tam[:30]

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

if piyasa_secimi == "BİST 30 (30 Hisse)":
    secilen_hisseler = bist_30_listesi
elif piyasa_secimi == "BİST 100 (Tam 100 Hisse)":
    secilen_hisseler = bist_100_tam
elif piyasa_secimi == "S&P 500 Devleri (İlk 100)":
    secilen_hisseler = sp_500_tam
elif piyasa_secimi == "NASDAQ 100 (Tam 100 Hisse)":
    secilen_hisseler = nasdaq_100_tam
else:
    girilen_hisseler = st.sidebar.text_area("Hisse kodlarını virgülle ayırarak yazın:", "THYAO.IS, NVDA, AAPL, EREGL.IS")
    secilen_hisseler = [h.strip() for h in girilen_hisseler.split(',') if h.strip()]

baslat_butonu = st.sidebar.button("🚀 Taramayı Başlat", type="primary")

# --- HESAPLAMA VE İŞLEM BÖLÜMÜ ---
if baslat_butonu:
    st.info(f"Toplam {len(secilen_hisseler)} hisse taranıyor...")
    
    ilerleme_cubugu = st.progress(0)
    basarili_sonuclar = []
    
    for idx, hisse in enumerate(secilen_hisseler):
        veri, mesaj = hisse_analiz_et(hisse, filtre_paketı)
        if veri:
            basarili_sonuclar.append(veri)
        
        ilerleme_cubugu.progress((idx + 1) / len(secilen_hisseler))
    
    if basarili_sonuclar:
        df_sonuc = pd.DataFrame(basarili_sonuclar)
        df_sonuc.index = range(1, len(df_sonuc) + 1)
        st.session_state['sonuc_df'] = df_sonuc
        st.session_state['taranan_sayi'] = len(secilen_hisseler)
    else:
        st.session_state['sonuc_df'] = pd.DataFrame()
        st.session_state['taranan_sayi'] = len(secilen_hisseler)

# --- EKRAN ÇİZİM BÖLÜMÜ ---
if 'sonuc_df' in st.session_state:
    df_sonuc = st.session_state['sonuc_df']
    taranan = st.session_state.get('taranan_sayi', 0)
    
    if not df_sonuc.empty:
        st.success("Tarama başarıyla tamamlandı!")
        
        col1, col2 = st.columns(2)
        col1.metric("Taranan Toplam Hisse", taranan)
        col2.metric("Süzgeçten Geçen Kaliteli Şirketler", len(df_sonuc))
        
        st.subheader("📋 Süzgeçten Geçen Şirketler Tablosu")
        
        # TABLO BAŞLIKLARINA DA HOVER TOOLTIP EKLENDİ
        st.dataframe(
            df_sonuc.drop(columns=['Tam Kod']),
            use_container_width=True,
            column_config={
                "Son Net Kar": st.column_config.NumberColumn("Son Net Kar", format="%.0f ₺/ $", help="Şirketin açıkladığı son çeyreklik net kârı."),
                "Son FAVÖK": st.column_config.NumberColumn("Son FAVÖK", format="%.0f ₺/ $", help="Faiz, Vergi ve Amortisman Öncesi Operasyonel Kâr."),
                "ROE (%)": st.column_config.ProgressColumn(
                    "ROE (%)",
                    format="%.2f%%",
                    min_value=0,
                    max_value=100,
                    help="Özkaynak Kârlılığı (%): Şirket yönetiminin sermayeyi ne oranda büyütebildiğini gösterir."
                ),
                "F/K": st.column_config.NumberColumn("F/K", format="%.2f", help="Fiyat / Kazanç Oranı. Düşük olması kârına göre ucuzluğu gösterir."),
                "PEG": st.column_config.NumberColumn("PEG", format="%.2f", help="PEG < 1.0 büyümesine göre ucuz demektir."),
                "PD/DD": st.column_config.NumberColumn("PD/DD", format="%.2f", help="Piyasa Değeri / Defter Değeri."),
                "Cari Oran": st.column_config.NumberColumn("Cari Oran", format="%.2f", help="> 1.0 olması şirketin likidite gücünün sağlam olduğunu gösterir."),
                "Borç/Özkaynak": st.column_config.NumberColumn("Borç/Özkaynak", format="%.2f", help="Şirketin borçluluk oranı."),
                "Net Marj (%)": st.column_config.NumberColumn("Net Marj (%)", format="%.2f%%", help="Cironun kâra dönüşme oranı."),
                "RSI (14)": st.column_config.NumberColumn("RSI (14)", format="%.2f", help="30-70 arası sağlıklı trend, <30 aşırı ucuz, >70 aşırı pahalı."),
            }
        )
        
        csv = df_sonuc.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="📥 Sonuçları Excel/CSV Olarak İndir",
            data=csv,
            file_name='filtre_sonuclari_v1_9.csv',
            mime='text/csv',
        )

        # --- DETAYLI HİSSE VE GRAFİK MODÜLÜ ---
        st.markdown("---")
        st.subheader("🔍 Hisse Detaylı Grafik ve Bilanço İncelemesi")
        
        hisse_secenekleri = df_sonuc['Hisse Kodu'].tolist()
        secilen_kod = st.selectbox("Grafiğini ve Çeyreklik Gelişimini Görmek İstediğiniz Hisseyi Seçin:", hisse_secenekleri)
        
        tam_kod = df_sonuc[df_sonuc['Hisse Kodu'] == secilen_kod]['Tam Kod'].values[0]
        
        financials, info, history = fetch_stock_raw_data(tam_kod)
        
        if history is not None and not history.empty:
            col_left, col_right = st.columns(2)
            
            with col_left:
                st.markdown(f"##### 📊 {secilen_kod} - 1 Yıllık Fiyat Hareketi (Candlestick)")
                fig = go.Figure(data=[go.Candlestick(
                    x=history.index,
                    open=history['Open'],
                    high=history['High'],
                    low=history['Low'],
                    close=history['Close'],
                    name=secilen_kod
                )])
                fig.update_layout(xaxis_rangeslider_visible=False, height=400, margin=dict(l=20, r=20, t=20, b=20))
                st.plotly_chart(fig, use_container_width=True)
                
            with col_right:
                st.markdown(f"##### 💰 {secilen_kod} - Çeyreklik Net Kâr & FAVÖK Trendi")
                if financials is not None and not financials.empty:
                    ebitda_keys = ['EBITDA', 'Normalized EBITDA', 'Operating Income', 'EBIT']
                    net_keys = ['Net Income', 'Net Income Common Stockholders']
                    
                    eb_series = get_financial_value(financials, ebitda_keys)
                    net_series = get_financial_value(financials, net_keys)
                    
                    if eb_series is not None and net_series is not None:
                        mali_df = pd.DataFrame({
                            'FAVÖK': eb_series.iloc[:4][::-1],
                            'Net Kâr': net_series.iloc[:4][::-1]
                        })
                        mali_df.index = [str(col).split('T')[0] for col in mali_df.index]
                        st.bar_chart(mali_df, height=360)
                    else:
                        st.info("Çeyreklik finansal grafik verisi yetersiz.")
                else:
                    st.info("Bilanço grafiği çekilemedi.")

    else:
        st.warning("Seçtiğiniz kriter kombinasyonuna uyan şirket bulunamadı. Sol menüden filtre sınırlarını esneterek tekrar deneyin.")

else:
    st.write("👈 Sol menüden piyasanızı seçip **'Taramayı Başlat'** butonuna tıklayın.")