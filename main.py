import streamlit as st
import streamlit.components.v1 as components
import yfinance as yf
import pandas as pd
import ta
import plotly.graph_objects as go
from concurrent.futures import ThreadPoolExecutor, as_completed
import warnings

warnings.filterwarnings('ignore')

# --- SAYFA YAPILANDIRMASI & FINTABLES MAT SİYAH TEMA ---
st.set_page_config(
    page_title="Sermaye Terminali v6.0 Fintables Mode",
    page_icon="🖤",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
    <style>
    .stApp { background-color: #0e0e10 !important; color: #ffffff !important; }
    [data-testid="stSidebar"] { background-color: #141416 !important; border-right: 1px solid #222226 !important; }
    
    /* Fintables Stil Kartlar */
    .fintables-card {
        background-color: #161618;
        border: 1px solid #26262a;
        border-radius: 10px;
        padding: 16px;
        margin-bottom: 12px;
    }
    .stMetric {
        background-color: #161618 !important;
        border: 1px solid #26262a !important;
        border-radius: 8px !important;
        padding: 12px !important;
    }
    [data-testid="stMetricLabel"] { color: #888890 !important; font-size: 0.85rem !important; }
    [data-testid="stMetricValue"] { color: #38bdf8 !important; font-weight: 700 !important; font-size: 1.6rem !important; }
    
    /* Sekme Tasarımı */
    .stTabs [data-baseweb="tab-list"] { background-color: #141416; padding: 6px; border-radius: 8px; border: 1px solid #222226; }
    .stTabs [data-baseweb="tab"] { color: #888890 !important; font-weight: 600; border-radius: 6px; }
    .stTabs [aria-selected="true"] { background-color: #222226 !important; color: #ffffff !important; border-bottom: 2px solid #38bdf8 !important; }
    </style>
""", unsafe_allow_html=True)

st.title("🖤 Sermaye & Değerleme Terminali v6.0")
st.caption("Fintables Stil Şirket Karnesi, Özet Bilanço ve Çeyreklik Trend Terminali")

# --- MİLYAR / MİLYON FORMATLAMA ---
def format_para(val):
    if val is None or pd.isna(val): return "N/A"
    abs_v = abs(val)
    if abs_v >= 1e9: return f"{val / 1e9:.2f} mr"
    elif abs_v >= 1e6: return f"{val / 1e6:.2f} mn"
    return f"{val:,.0f}"

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

# --- KARNE HESAPLAMA ALGORİTMASI (KARLILIK, BÜYÜME, BORÇLULUK) ---
def hesapla_fintables_karne(financials, balance_sheet, info):
    karlilik_skor = 0
    buyume_skor = 0
    borcluluk_skor = 0
    
    borcluluk_detay = []
    
    # 1. Bilanço & Gelir Tablosu Serileri
    rev_series = get_row(financials, ['Total Revenue', 'Operating Revenue'])
    net_inc_series = get_row(financials, ['Net Income', 'Net Income Common Stockholders'])
    ebitda_series = get_row(financials, ['EBITDA', 'Normalized EBITDA', 'Operating Income'])
    
    curr_assets = get_row(balance_sheet, ['Current Assets'])
    curr_liab = get_row(balance_sheet, ['Current Liabilities'])
    total_debt = get_row(balance_sheet, ['Total Debt', 'Financial Debt'])
    cash = get_row(balance_sheet, ['Cash And Cash Equivalents'])
    total_assets = get_row(balance_sheet, ['Total Assets'])
    
    # --- BORÇLULUK KARNESİ (6 TEST) ---
    ca_val = curr_assets.iloc[0] if curr_assets is not None and not curr_assets.empty else 0
    cl_val = curr_liab.iloc[0] if curr_liab is not None and not curr_liab.empty else 0
    td_val = total_debt.iloc[0] if total_debt is not None and not total_debt.empty else 0
    cash_val = cash.iloc[0] if cash is not None and not cash.empty else 0
    ta_val = total_assets.iloc[0] if total_assets is not None and not total_assets.empty else 1
    
    net_borc = td_val - cash_val
    isletme_sermayesi = ca_val - cl_val
    fin_borcluluk_orani = (td_val / ta_val) * 100 if ta_val else 0
    cari_oran = (ca_val / cl_val) if cl_val else 0
    
    # Test 1: İşletme Sermayesi > 0
    if isletme_sermayesi > 0: borcluluk_skor += 1; borcluluk_detay.append(("İşletme Sermayesi > 0", True))
    else: borcluluk_detay.append(("İşletme Sermayesi > 0", False))
        
    # Test 2: Finansal Borçluluk < %50
    if fin_borcluluk_orani < 50: borcluluk_skor += 1; borcluluk_detay.append(("Finansal Borçluluk < %50", True))
    else: borcluluk_detay.append(("Finansal Borçluluk < %50", False))
        
    # Test 3: Net Borç < 0
    if net_borc < 0: borcluluk_skor += 1; borcluluk_detay.append(("Net Borç < 0 (Nakit Fazlası)", True))
    else: borcluluk_detay.append(("Net Borç < 0", False))
        
    # Test 4: Dönen Varlıklar > Finansal Borç
    if ca_val > td_val: borcluluk_skor += 1; borcluluk_detay.append(("Dönen Varlıklar > Finansal Borç", True))
    else: borcluluk_detay.append(("Dönen Varlıklar > Finansal Borç", False))
        
    # Test 5: Cari Oran > 1.5
    if cari_oran > 1.5: borcluluk_skor += 1; borcluluk_detay.append(("Cari Oran > 1.5", True))
    else: borcluluk_detay.append(("Cari Oran > 1.5", False))
        
    # Test 6: Borç Yükü Makul
    if fin_borcluluk_orani < 30 or net_borc < 0: borcluluk_skor += 1; borcluluk_detay.append(("Düşük Finansal Borç Riski", True))
    else: borcluluk_detay.append(("Düşük Finansal Borç Riski", False))

    # --- KÂRLILIK VE BÜYÜME KARNESİ ---
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
        'borcluluk': min(borcluluk_skor, 6),
        'borcluluk_detay': borcluluk_detay
    }

def hisse_sorgula(hisse_kodu, filtreler):
    financials, balance_sheet, info, history = fetch_full_stock_data(hisse_kodu)
    if financials is None or financials.empty: return None
    
    fk = info.get('forwardPE') or info.get('trailingPE')
    roe = (info.get('returnOnEquity') or 0) * 100
    
    # Basit eleme
    if filtreler['fk_aktif'] and (fk is None or fk <= 0 or fk > filtreler['max_fk']): return None
    if filtreler['roe_aktif'] and (roe < filtreler['min_roe']): return None
    
    return {
        'Hisse Kodu': hisse_kodu.replace('.IS', ''),
        'Tam Kod': hisse_kodu,
        'Piyasa Değeri': format_para(info.get('marketCap')),
        'F/K': round(fk, 2) if fk else 'N/A',
        'PD/DD': round(info.get('priceToBook', 0), 2) if info.get('priceToBook') else 'N/A',
        'ROE (%)': round(roe, 2),
        'Cari Oran': round(info.get('currentRatio', 0), 2) if info.get('currentRatio') else 'N/A'
    }

# --- SIDEBAR ---
st.sidebar.header("🎯 Piyasayı Seçin")
piyasa = st.sidebar.radio("Endeks:", ["BİST 30 (30 Hisse)", "BİST 100 (100 Hisse)", "S&P 500 (500 Hisse)"])

st.sidebar.header("⚙️ Temel Filtreler")
fk_aktif = st.sidebar.checkbox("F/K Filtresi", value=True)
max_fk = st.sidebar.slider("Maks F/K", 1.0, 100.0, 35.0) if fk_aktif else 999.0
roe_aktif = st.sidebar.checkbox("ROE Filtresi", value=True)
min_roe = st.sidebar.slider("Min ROE (%)", 0, 100, 10) if roe_aktif else -999.0

filtreler = {'fk_aktif': fk_aktif, 'max_fk': max_fk, 'roe_aktif': roe_aktif, 'min_roe': min_roe}

bist_100 = ['THYAO.IS', 'BIMAS.IS', 'AKBNK.IS', 'EREGL.IS', 'GARAN.IS', 'SISE.IS', 'FROTO.IS', 'KCHOL.IS', 'ASELS.IS', 'TUPRS.IS']
sp_500 = ['AAPL', 'MSFT', 'NVDA', 'AMZN', 'GOOGL', 'META', 'TSLA', 'BRK-B', 'JPM', 'UNH']

secilen_liste = bist_100 if "BİST" in piyasa else sp_500

# OTOMATİK TARAMA
with ThreadPoolExecutor(max_workers=5) as ex:
    futs = [ex.submit(hisse_sorgula, h, filtreler) for h in secilen_liste]
    res_list = [f.result() for f in as_completed(futs) if f.result() is not None]

df_tarama = pd.DataFrame(res_list) if res_list else pd.DataFrame()

# --- ARAYÜZ ---
tab_ana1, tab_ana2 = st.tabs(["📊 Süzgeç Tablosu", "📈 Şirket Karnesi & Özet Bilanço (Fintables Stil)"])

with tab_ana1:
    if not df_tarama.empty:
        st.subheader("📋 Süzgeçten Geçen Kaliteli Şirketler")
        st.dataframe(df_tarama, use_container_width=True)
    else:
        st.warning("Filtre şartlarına uyan hisse bulunamadı.")

with tab_ana2:
    secilen_hisse = st.selectbox("İncelemek İstediğiniz Şirketi Seçin:", secilen_liste)
    fin, bal, info, hist = fetch_full_stock_data(secilen_hisse)
    
    if fin is not None and not fin.empty and bal is not None:
        karne = hesapla_fintables_karne(fin, bal, info)
        
        st.markdown(f"## 🏢 {secilen_hisse.replace('.IS', '')} Finansal Karnesi ve Özeti")
        
        # --- KARNE GAUGE / METRİK KARTLARI ---
        k1, k2, k3, k4 = st.columns(4)
        k1.metric("Kârlılık Karnesi", f"{karne['karlilik']} / 6")
        k2.metric("Büyüme Karnesi", f"{karne['buyume']} / 6")
        k3.metric("Borçluluk Karnesi", f"{karne['borcluluk']} / 6")
        k4.metric("Piyasa Değeri", format_para(info.get('marketCap')))
        
        st.markdown("---")
        
        # --- ÖZET BİLANÇO VE GELİR TABLOSU ---
        col_g1, col_g2 = st.columns(2)
        
        rev = get_row(fin, ['Total Revenue', 'Operating Revenue'])
        gross = get_row(fin, ['Gross Profit'])
        ebitda = get_row(fin, ['EBITDA', 'Normalized EBITDA', 'Operating Income'])
        net_inc = get_row(fin, ['Net Income'])
        
        ca = get_row(bal, ['Current Assets'])
        nca = get_row(bal, ['Total Non Current Assets'])
        ta = get_row(bal, ['Total Assets'])
        eq = get_row(bal, ['Stockholders Equity'])
        
        with col_g1:
            st.markdown("##### 📄 Özet Gelir Tablosu (Son Çeyrekler)")
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
                    'Son Çeyrek': [format_para(ca.iloc[0]), format_para(nca.iloc[0] if nca is not None else 0), format_para(ta.iloc[0] if ta is not None else 0), format_para(eq.iloc[0] if eq is not None else 0)],
                    'Önceki Çeyrek': [format_para(ca.iloc[1]), format_para(nca.iloc[1] if nca is not None else 0), format_para(ta.iloc[1] if ta is not None else 0), format_para(eq.iloc[1] if eq is not None else 0)]
                }, index=['Dönen Varlıklar', 'Duran Varlıklar', 'Toplam Varlıklar', 'Özkaynaklar'])
                st.table(df_bilanco)

        st.markdown("---")
        
        # --- 3 ÇEYREKLİK ÇUBUK GRAFİKLER (SATIŞLAR, FAVÖK, NET KÂR) ---
        st.markdown("##### 📊 Çeyreklik Mali Gelişim Grafikleri")
        c_g1, c_g2, c_g3 = st.columns(3)
        
        if rev is not None and len(rev) >= 4:
            with c_g1:
                st.caption("Çeyreklik Satışlar")
                st.bar_chart(rev.iloc[:4][::-1])
        if ebitda is not None and len(ebitda) >= 4:
            with c_g2:
                st.caption("Çeyreklik FAVÖK")
                st.bar_chart(ebitda.iloc[:4][::-1])
        if net_inc is not None and len(net_inc) >= 4:
            with c_g3:
                st.caption("Çeyreklik Net Kâr")
                st.bar_chart(net_inc.iloc[:4][::-1])

        st.markdown("---")
        
        # --- TRADINGVIEW CANLI GRAFİK ---
        tv_symbol = f"BIST:{secilen_hisse.replace('.IS', '')}" if '.IS' in secilen_hisse else secilen_hisse.replace('-', '.')
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
