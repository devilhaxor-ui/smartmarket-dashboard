import streamlit as st
import feedparser
from datetime import datetime
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
from deep_translator import GoogleTranslator
from bs4 import BeautifulSoup

# ก่อนแปล ให้ล้าง HTML
def clean_html(raw_html):
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

# ---------- FETCH NEWS ----------
@st.cache_data(ttl=3600)
def get_news():
    articles = []
    for url in RSS_FEEDS:
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries:
                # ทำความสะอาด HTML และแปลข่าว
                summary_text = clean_html(entry.get("summary", ""))
                try:
                    summary_th = GoogleTranslator(source='auto', target='th').translate(summary_text)
                except Exception:
                    summary_th = summary_text
                
                articles.append({
                    "title": entry.title,
                    "link": entry.link,
                    "summary": summary_th,
                    "published": entry.get("published", "")
                })
        except Exception as e:
            st.error(f"Error fetching feed {url}: {str(e)}")
    
    return articles

articles = get_news()

# ---------- ANALYZE ----------
results = {}
for asset_name, keywords in ASSETS.items():
    relevant = []
    sentiment_scores = []
    for a in articles:
        text_lower = (a["title"] + " " + a["summary"]).lower()
        if any(kw in text_lower for kw in keywords):
            vs = analyzer.polarity_scores(a["title"] + " " + a["summary"])
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
            "articles": relevant
        }

# ---------- DISPLAY ----------
for asset_name, data in results.items():
    st.subheader(f"🔹 {asset_name}")
    st.write(f"แนวโน้มข่าว: {data['tone']} (sentiment = {data['sentiment']:.2f})")
    st.write("**สรุปข่าว:**")
    for art in data["articles"][:3]:  # แสดงแค่ 3 ข่าวล่าสุด
        st.markdown(f"📰 [{art['title']}]({art['link']})")
        st.write(f"→ {art['summary']}")
    st.markdown("---")

st.subheader("📊 แนวโน้มตลาดโดยรวมวันนี้:")
for asset_name, data in results.items():
    st.write(f"{asset_name} = **{data['trend']}**")

st.caption("🧠 วิเคราะห์ด้วย VADER sentiment + แปลอัตโนมัติจาก Google Translator + ข่าว RSS")
