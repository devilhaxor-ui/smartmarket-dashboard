import streamlit as st
import feedparser
from datetime import datetime
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
from deep_translator import GoogleTranslator
from bs4 import BeautifulSoup
import time

# ก่อนแปล ให้ล้าง HTML
def clean_html(raw_html):
    if not raw_html:
        return ""
    soup = BeautifulSoup(raw_html, "html.parser")
    return soup.get_text()

# ---------- CONFIG ----------
RSS_FEEDS = [
    "https://news.google.com/rss/search?q=gold+price+OR+XAUUSD&hl=en-US&gl=US&ceid=US:en",
    "https://news.google.com/rss/search?q=silver+price+OR+XAGUSD&hl=en-US&gl=US&ceid=US:en",
    "https://news.google.com/rss/search?q=bitcoin+OR+BTCUSD&hl=en-US&gl=US&ceid=US:en"
]

ASSETS = {
    "ทองคำ (XAU)": ["gold", "xauusd", "bullion"],
    "เงิน (XAG)": ["silver", "xagusd"],
    "บิตคอยน์ (BTC)": ["bitcoin", "btc", "crypto"]
}

analyzer = SentimentIntensityAnalyzer()
st.set_page_config(page_title="SmartMarket Daily Dashboard", layout="centered")

st.title("🌞 SmartMarket Daily Dashboard")
st.write(f"อัปเดตล่าสุด: {datetime.now().strftime('%d %B %Y, %H:%M')} น.")
st.info("รวบรวมข่าวล่าสุดเกี่ยวกับทองคำ, เงิน และบิตคอยน์ แล้ววิเคราะห์แนวโน้มเป็น **ภาษาไทย**")

# ---------- OPTIMIZED FETCH NEWS ----------
@st.cache_data(ttl=3600, show_spinner=False)
def get_news():
    articles = []
    for url in RSS_FEEDS:
        try:
            feed = feedparser.parse(url)
            # จำกัดข่าวล่าสุด 8 ข่าวต่อ feed เพื่อลดจำนวน
            for entry in feed.entries[:8]:
                summary_text = clean_html(entry.get("summary", ""))
                
                articles.append({
                    "title": entry.title,
                    "link": entry.link,
                    "summary_en": summary_text,  # เก็บภาษาอังกฤษไว้ก่อน
                    "published": entry.get("published", "")
                })
        except Exception as e:
            st.error(f"Error fetching feed {url}: {str(e)}")
    
    return articles

# ---------- OPTIMIZED TRANSLATION ----------
@st.cache_data(ttl=3600)
def translate_text(text):
    """แปลข้อความแบบแคชและมี error handling"""
    if not text or len(text.strip()) == 0:
        return text
    try:
        # จำกัดความยาวข้อความเพื่อป้องกัน error ในการแปล
        text_limited = text[:500] + "..." if len(text) > 500 else text
        return GoogleTranslator(source='auto', target='th').translate(text_limited)
    except Exception:
        return text  # ถ้าแปลไม่ได้ return ต้นฉบับ

# ---------- MAIN PROCESS WITH PROGRESS ----------
with st.spinner('📡 กำลังดึงข่าวล่าสุด...'):
    articles = get_news()

if not articles:
    st.error("ไม่สามารถดึงข่าวได้ กรุณาลองใหม่ภายหลัง")
    st.stop()

# ---------- ANALYZE WITH PROGRESS ----------
results = {}
progress_bar = st.progress(0)
status_text = st.empty()

for i, (asset_name, keywords) in enumerate(ASSETS.items()):
    status_text.text(f"🔍 กำลังวิเคราะห์ข่าวเกี่ยวกับ {asset_name}...")
    relevant = []
    sentiment_scores = []
    
    for a in articles:
        text_lower = (a["title"] + " " + a["summary_en"]).lower()
        if any(kw in text_lower for kw in keywords):
            # ใช้ภาษาอังกฤษในการวิเคราะห์ sentiment (แม่นยำกว่า)
            vs = analyzer.polarity_scores(a["title"] + " " + a["summary_en"])
            sentiment_scores.append(vs["compound"])
            relevant.append(a)
    
    if sentiment_scores:
        avg_sent = sum(sentiment_scores) / len(sentiment_scores)
        if avg_sent > 0.1:
            tone = "🟩 เชิงบวก"
            trend = "Bullish"
        elif avg_sent < -0.1:
            tone = "🟥 เชิงลบ"
            trend = "Bearish"
        else:
            tone = "⚪ เป็นกลาง"
            trend = "Neutral"
        results[asset_name] = {
            "sentiment": avg_sent,
            "tone": tone,
            "trend": trend,
            "articles": relevant[:4]  # จำกัดแสดงแค่ 4 ข่าว
        }
    
    progress_bar.progress((i + 1) / len(ASSETS))

status_text.text("✅ การวิเคราะห์เสร็จสิ้น!")
progress_bar.empty()

# ---------- DISPLAY RESULTS ----------
if not results:
    st.warning("ไม่พบข่าวที่เกี่ยวข้องกับสินทรัพย์ที่ติดตาม")
    st.stop()

for asset_name, data in results.items():
    st.subheader(f"🔹 {asset_name}")
    st.write(f"แนวโน้มข่าว: {data['tone']} (sentiment = {data['sentiment']:.2f})")
    st.write("**สรุปข่าว:**")
    
    for art in data["articles"]:
        with st.container():
            col1, col2 = st.columns([3, 1])
            with col1:
                st.markdown(f"📰 **[{art['title']}]({art['link']})**")
                # แปลเฉพาะตอนแสดงผล และเฉพาะข่าวที่เกี่ยวข้องจริงๆ
                summary_th = translate_text(art["summary_en"])
                st.write(f"→ {summary_th}")
            with col2:
                st.write("")
            
        st.markdown("---")

st.subheader("📊 แนวโน้มตลาดโดยรวมวันนี้:")
for asset_name, data in results.items():
    st.write(f"{asset_name} = **{data['trend']}**")

st.caption("🧠 วิเคราะห์ด้วย VADER sentiment + แปลอัตโนมัติจาก Google Translator + ข่าว RSS")
