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

# ฟังก์ชันให้คำแนะนำตาม sentiment
def get_trading_recommendation(sentiment_score, asset_name, num_articles):
    """ให้คำแนะนำในการเทรดตาม sentiment"""
    
    # ตรวจสอบความน่าเชื่อถือของข้อมูล
    confidence = "สูง" if num_articles >= 5 else "ปานกลาง" if num_articles >= 3 else "ต่ำ"
    
    if sentiment_score > 0.2:
        return {
            "action": "🟢 **พิจารณาซื้อ**",
            "reason": f"ข่าวส่วนใหญ่เป็นเชิงบวก ({sentiment_score:.2f})",
            "suggestion": "อาจเป็นโอกาสดีสำหรับการเปิด Long Position",
            "risk": "เสี่ยงปานกลาง - ติดตาม stop loss",
            "confidence": confidence
        }
    elif sentiment_score > 0.1:
        return {
            "action": "🟡 **รอสัญญาณยืนยัน**",
            "reason": f"ข่าวมีแนวโน้มเชิงบวกเล็กน้อย ({sentiment_score:.2f})",
            "suggestion": "อาจพิจารณาซื้อเมื่อมีสัญญาณทางเทคนิค confirm",
            "risk": "เสี่ยงต่ำถึงปานกลาง",
            "confidence": confidence
        }
    elif sentiment_score > -0.1:
        return {
            "action": "⚪ **ระวัง Sideway**",
            "reason": f"ข่าวเป็นกลาง ({sentiment_score:.2f})",
            "suggestion": "ตลาดอาจเคลื่อนที่ใน sideways, โฟกัสที่ range trading",
            "risk": "เสี่ยงต่ำ แต่โอกาสทำกำไรจำกัด",
            "confidence": confidence
        }
    elif sentiment_score > -0.2:
        return {
            "action": "🟠 **พิจารณาลดพอร์ต**",
            "reason": f"ข่าวมีแนวโน้มเชิงลบเล็กน้อย ({sentiment_score:.2f})",
            "suggestion": "พิจารณา take profit บางส่วนหรือตั้ง tight stop loss",
            "risk": "เสี่ยงปานกลาง",
            "confidence": confidence
        }
    else:
        return {
            "action": "🔴 **ระวังการ correction**",
            "reason": f"ข่าวส่วนใหญ่เป็นเชิงลบ ({sentiment_score:.2f})",
            "suggestion": "อาจพิจารณา Short Position หรือรอซื้อที่ระดับ support",
            "risk": "เสี่ยงสูง - ควรใช้ position size เล็ก",
            "confidence": confidence
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
            for entry in feed.entries[:8]:
                summary_text = clean_html(entry.get("summary", ""))
                
                articles.append({
                    "title": entry.title,
                    "link": entry.link,
                    "summary_en": summary_text,
                    "published": entry.get("published", "")
                })
        except Exception as e:
            st.error(f"Error fetching feed {url}: {str(e)}")
    
    return articles

# ---------- OPTIMIZED TRANSLATION ----------
@st.cache_data(ttl=3600)
def translate_text(text):
    if not text or len(text.strip()) == 0:
        return text
    try:
        text_limited = text[:500] + "..." if len(text) > 500 else text
        return GoogleTranslator(source='auto', target='th').translate(text_limited)
    except Exception:
        return text

# ---------- MAIN PROCESS ----------
with st.spinner('📡 กำลังดึงข่าวล่าสุด...'):
    articles = get_news()

if not articles:
    st.error("ไม่สามารถดึงข่าวได้ กรุณาลองใหม่ภายหลัง")
    st.stop()

# ---------- ANALYZE ----------
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
        
        # คำแนะนำการเทรด
        recommendation = get_trading_recommendation(avg_sent, asset_name, len(relevant))
        
        results[asset_name] = {
            "sentiment": avg_sent,
            "tone": tone,
            "trend": trend,
            "articles": relevant[:4],
            "recommendation": recommendation,
            "article_count": len(relevant)
        }
    
    progress_bar.progress((i + 1) / len(ASSETS))

status_text.text("✅ การวิเคราะห์เสร็จสิ้น!")
progress_bar.empty()

# ---------- DISPLAY RESULTS WITH RECOMMENDATIONS ----------
if not results:
    st.warning("ไม่พบข่าวที่เกี่ยวข้องกับสินทรัพย์ที่ติดตาม")
    st.stop()

# แสดงผลแบบละเอียดสำหรับแต่ละสินทรัพย์
for asset_name, data in results.items():
    st.subheader(f"🔹 {asset_name}")
    
    # สรุป sentiment
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Sentiment Score", f"{data['sentiment']:.3f}")
    with col2:
        st.metric("แนวโน้ม", data['trend'])
    with col3:
        st.metric("จำนวนข่าว", data['article_count'])
    
    # คำแนะนำการเทรด
    rec = data['recommendation']
    with st.expander(f"📋 คำแนะนำการเทรด ({rec['confidence']} confidence)", expanded=True):
        st.markdown(f"**การดำเนินการ:** {rec['action']}")
        st.markdown(f"**เหตุผล:** {rec['reason']}")
        st.markdown(f"**คำแนะนำ:** {rec['suggestion']}")
        st.markdown(f"**ระดับความเสี่ยง:** {rec['risk']}")
        st.markdown(f"**ความน่าเชื่อถือของข้อมูล:** {rec['confidence']} (จาก {data['article_count']} ข่าว)")
    
    # แสดงข่าว
    st.write("**ข่าวล่าสุด:**")
    for art in data["articles"]:
        with st.container():
            st.markdown(f"📰 **[{art['title']}]({art['link']})**")
            summary_th = translate_text(art["summary_en"])
            st.write(f"→ {summary_th}")
        st.markdown("---")

# ---------- OVERALL MARKET SUMMARY ----------
st.subheader("📊 สรุปแนวโน้มตลาดและกลยุทธ์")

# นับจำนวนสินทรัพย์ในแต่ละแนวโน้ม
bullish_count = sum(1 for data in results.values() if data['sentiment'] > 0.1)
bearish_count = sum(1 for data in results.values() if data['sentiment'] < -0.1)
neutral_count = len(results) - bullish_count - bearish_count

col1, col2, col3 = st.columns(3)
with col1:
    st.metric("Bullish", bullish_count)
with col2:
    st.metric("Bearish", bearish_count)
with col3:
    st.metric("Neutral", neutral_count)

# กลยุทธ์รวมตามสภาวะตลาด
if bullish_count >= 2:
    st.success("**🎯 กลยุทธ์รวม: Risk-On** - ตลาดส่วนใหญ่มีแนวโน้มบวก พิจารณาเพิ่ม exposure")
elif bearish_count >= 2:
    st.error("**🎯 กลยุทธ์รวม: Risk-Off** - ตลาดส่วนใหญ่มีแนวโน้มลบ ควรระมัดระวังและลด position")
else:
    st.warning("**🎯 กลยุทธ์รวม: Selective** - ตลาดผสมผสาน เลือกเทรดเฉพาะสินทรัพย์ที่มีแนวโน้มชัดเจน")

# คำแนะนำทั่วไป
st.info("""
**📝 หมายเหตุสำคัญ:**
- การวิเคราะห์นี้มาจากข่าวล่าสุดเท่านั้น **ควรใช้ร่วมกับการวิเคราะห์ทางเทคนิค**
- Sentiment เป็นเพียงตัวบ่งชี้แนวโน้ม ไม่ใช่สัญญาณซื้อ-ขาย
- **จัดการความเสี่ยงเสมอ** โดยใช้ stop loss และ proper position sizing
- ข้อมูลมีอายุ 1 ชั่วโมง (อัปเดตอัตโนมัติ)
""")

st.caption("🧠 วิเคราะห์ด้วย VADER sentiment + แปลอัตโนมัติจาก Google Translator + ข่าว RSS")
