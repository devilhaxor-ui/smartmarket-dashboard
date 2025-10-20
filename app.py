import streamlit as st
import feedparser
from datetime import datetime, timedelta
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
from deep_translator import GoogleTranslator
from bs4 import BeautifulSoup
import pytz

# ตั้งค่าโซนเวลาไทย
thai_tz = pytz.timezone('Asia/Bangkok')

def clean_html(raw_html):
    if not raw_html:
        return ""
    soup = BeautifulSoup(raw_html, "html.parser")
    return soup.get_text()

# ---------- CONFIG ที่สอดคล้องกัน ----------
RSS_FEEDS = [
    "https://news.google.com/rss/search?q=gold+price+OR+XAUUSD&hl=en-US&gl=US&ceid=US:en",
    "https://news.google.com/rss/search?q=silver+price+OR+XAGUSD&hl=en-US&gl=US&ceid=US:en",
    "https://news.google.com/rss/search?q=bitcoin+OR+BTCUSD&hl=en-US&gl=US&ceid=US:en"
]

# ใช้ keywords ชุดเดียวกันทั้งสองโหมด
GOLD_KEYWORDS = ['gold', 'xau', 'bullion', 'precious metal', 'fed', 'inflation', 'dollar', 'usd', 'ทองคำ', 'xauusd']

ASSETS = {
    "ทองคำ (XAU)": GOLD_KEYWORDS,  # ใช้ keywords ชุดเดียวกัน
    "เงิน (XAG)": ["silver", "xagusd"],
    "บิตคอยน์ (BTC)": ["bitcoin", "btc", "crypto"]
}

analyzer = SentimentIntensityAnalyzer()

# ---------- ฟังก์ชันพื้นฐาน ----------
@st.cache_data(ttl=3600, show_spinner=False)
def get_news():
    articles = []
    for url in RSS_FEEDS:
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries[:10]:  # เพิ่มข่าวให้มากพอ
                summary_text = clean_html(entry.get("summary", ""))
                
                articles.append({
                    "title": entry.title,
                    "link": entry.link,
                    "summary_en": summary_text,
                    "published": entry.get("published", ""),
                    "content_lower": (entry.title + " " + summary_text).lower()  # เพิ่ม field นี้
                })
        except Exception as e:
            st.error(f"Error fetching feed {url}: {str(e)}")
    
    return articles

@st.cache_data(ttl=3600)
def translate_text(text):
    if not text or len(text.strip()) == 0:
        return text
    try:
        text_limited = text[:500] + "..." if len(text) > 500 else text
        return GoogleTranslator(source='auto', target='th').translate(text_limited)
    except Exception:
        return text

# ---------- ฟังก์ชันวิเคราะห์ทองคำกลาง ----------
def analyze_gold_news(articles):
    """ฟังก์ชันกลางสำหรับวิเคราะห์ข่าวทองคำ - ใช้ร่วมกันทั้งสองโหมด"""
    
    # กรองข่าวทองคำด้วย keywords ชุดเดียวกัน
    gold_articles = []
    for article in articles:
        if any(keyword in article['content_lower'] for keyword in GOLD_KEYWORDS):
            gold_articles.append(article)
    
    if not gold_articles:
        return None
    
    # เรียงข่าวล่าสุด
    gold_articles_sorted = sorted(gold_articles, 
                                 key=lambda x: x.get('published', ''), 
                                 reverse=True)
    
    # วิเคราะห์ sentiment จากข่าวทั้งหมดที่เกี่ยวข้อง
    sentiment_scores = []
    for article in gold_articles_sorted:
        vs = analyzer.polarity_scores(article['title'] + " " + article['summary_en'])
        sentiment_scores.append(vs['compound'])
    
    avg_sentiment = sum(sentiment_scores) / len(sentiment_scores) if sentiment_scores else 0
    
    return {
        'articles': gold_articles_sorted,
        'sentiment': avg_sentiment,
        'article_count': len(gold_articles_sorted)
    }

# ---------- Gold Daily Summary ----------
def generate_gold_daily_summary(gold_data):
    """สรุปข่าวทองคำรายวัน - ใช้ข้อมูลจากฟังก์ชันกลาง"""
    
    if not gold_data:
        return None
    
    articles = gold_data['articles'][:5]  # เลือก 5 ข่าวล่าสุด
    avg_sentiment = gold_data['sentiment']
    
    # สรุปข่าวเป็นภาษาไทย
    summaries_th = []
    for i, article in enumerate(articles, 1):
        try:
            title_th = translate_text(article['title'])
            summary_short = article['summary_en'][:150] + "..." if len(article['summary_en']) > 150 else article['summary_en']
            summary_th = translate_text(summary_short)
            
            summaries_th.append(f"{i}. **{title_th}**\n   📝 {summary_th}")
        except:
            summaries_th.append(f"{i}. **{article['title']}**\n   📝 {article['summary_en'][:100]}...")
    
    # สรุปแนวโน้มและคำแนะนำ (ใช้ sentiment เดียวกัน)
    if avg_sentiment > 0.15:
        trend = "🟢 **แนวโน้มบวก**"
        outlook = "ตลาดทองคำมีแนวโน้มขึ้นจากข่าวเชิงบวก"
        recommendation = """
        **🎯 กลยุทธ์เก็งกำไร:**
        - **เข้าซื้อ** ที่ราคาปัจจุบันหรือรอ pullback เล็กน้อย
        - **Target กำไร:** 0.5-1% จากจุดเข้า
        - **Stop Loss:** 0.3% ใต้จุดเข้า
        - **ระยะเวลาถือ:** 1-3 วัน
        """
    elif avg_sentiment > -0.1:
        trend = "🟡 **แนวโน้มกลาง**"
        outlook = "ตลาดทองคำเคลื่อนไหวในกรอบ แรงส่งไม่ชัดเจน"
        recommendation = """
        **🎯 กลยุทธ์เก็งกำไร:**
        - **เทรดในกรอบ** (Range Trading)
        - **ซื้อใกล้ Support, ขายใกล้ Resistance**
        - **Target กำไร:** 0.3-0.6%
        - **Stop Loss:** 0.2%
        - **ระยะเวลาถือ:** ภายในวัน
        """
    else:
        trend = "🔴 **แนวโน้มลบ**"
        outlook = "ตลาดทองคำมีแรงกดดันจากข่าวเชิงลบ"
        recommendation = """
        **🎯 กลยุทธ์เก็งกำไร:**
        - **รอ sell on rally** หรือเข้าซื้อเมื่อมีสัญญาณกลับตัว
        - **Target กำไร:** 0.4-0.8% (หากเข้าซื้อ)
        - **Stop Loss:** 0.4% เหนือจุดเข้า
        - **พิจารณา Short** หากมีสัญญาณยืนยัน
        """
    
    summary_report = f"""
# 🏆 Gold Daily Summary
*อัปเดตล่าสุด: {datetime.now(thai_tz).strftime('%d/%m/%Y %H:%M')} น.*

## 📊 สรุปแนวโน้ม
{trend}
**Sentiment Score:** {avg_sentiment:.3f}
**จำนวนข่าวที่วิเคราะห์:** {gold_data['article_count']} ข่าว
**มุมมอง:** {outlook}

## 📰 5 ข่าวสำคัญ影響ทองคำ
{chr(10).join(summaries_th)}

## 💡 คำแนะนำการเทรดระยะสั้น
{recommendation}

## ⚠️ ข้อควรระวัง
- ใช้เงินทุนไม่เกิน 10-15% ของพอร์ต
- ติดตามข่าว Fed และ USD อย่างใกล้ชิด
- เตรียมพร้อมสำหรับความผันผวน
- ใช้ Stop Loss เสมอ
"""
    
    return summary_report

# ---------- Full Dashboard ----------
def generate_full_dashboard(articles):
    """สร้าง Dashboard แบบเต็ม - ใช้ข้อมูลจากฟังก์ชันกลาง"""
    results = {}
    
    # ใช้ฟังก์ชันกลางสำหรับทองคำ
    gold_data = analyze_gold_news(articles)
    if gold_data:
        avg_sent = gold_data['sentiment']
        if avg_sent > 0.1:
            tone = "🟩 เชิงบวก"
            trend = "Bullish"
        elif avg_sent < -0.1:
            tone = "🟥 เชิงลบ"
            trend = "Bearish"
        else:
            tone = "⚪ เป็นกลาง"
            trend = "Neutral"
        
        results["ทองคำ (XAU)"] = {
            "sentiment": avg_sent,
            "tone": tone,
            "trend": trend,
            "articles": gold_data['articles'][:3],  # แสดง 3 ข่าวล่าสุด
            "article_count": gold_data['article_count']
        }
    
    # วิเคราะห์สินทรัพย์อื่นๆ
    for asset_name, keywords in ASSETS.items():
        if asset_name == "ทองคำ (XAU)":  # ข้ามทองคำเพราะทำไปแล้ว
            continue
            
        relevant = []
        sentiment_scores = []
        
        for a in articles:
            if any(kw in a['content_lower'] for kw in keywords):
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
                "articles": relevant[:3],
                "article_count": len(relevant)
            }
    
    return results

# ---------- STREAMLIT APP ----------
st.set_page_config(page_title="SmartMarket Dashboard Pro", layout="wide")

# Sidebar
st.sidebar.title("🎛️ การตั้งค่า")
app_mode = st.sidebar.radio(
    "เลือกโหมดการแสดงผล:",
    ["🏆 Gold Daily Summary", "📊 Full Market Dashboard", "🔍 โหมดเปรียบเทียบ"]
)

# ดึงข้อมูลข่าว
with st.spinner('📡 กำลังดึงข่าวล่าสุด...'):
    articles = get_news()

if not articles:
    st.error("ไม่สามารถดึงข่าวได้ กรุณาลองใหม่ภายหลัง")
    st.stop()

# วิเคราะห์ข้อมูลทองคำกลาง (ใช้ร่วมกันทั้งสองโหมด)
gold_data = analyze_gold_news(articles)

# Header หลัก
st.title("🚀 SmartMarket Dashboard Pro")
st.write(f"อัปเดตล่าสุด: {datetime.now(thai_tz).strftime('%d %B %Y, %H:%M')} น.")

# แสดงข้อมูลความสอดคล้อง
if gold_data:
    st.sidebar.markdown("---")
    st.sidebar.info(f"**ข้อมูลทองคำ:**\n- พบ {gold_data['article_count']} ข่าว\n- Sentiment: {gold_data['sentiment']:.3f}")

# แสดงผลตามโหมดที่เลือก
if app_mode == "🏆 Gold Daily Summary":
    gold_summary = generate_gold_daily_summary(gold_data)
    if gold_summary:
        st.markdown(gold_summary)
    else:
        st.warning("ไม่พบข่าวทองคำล่าสุดในขณะนี้")

elif app_mode == "📊 Full Market Dashboard":
    results = generate_full_dashboard(articles)
    
    if not results:
        st.warning("ไม่พบข่าวที่เกี่ยวข้องกับสินทรัพย์ที่ติดตาม")
    else:
        # แสดงผลแบบ卡片
        cols = st.columns(len(results))
        for idx, (asset_name, data) in enumerate(results.items()):
            with cols[idx]:
                st.subheader(f"🔹 {asset_name}")
                st.metric("Sentiment", f"{data['sentiment']:.3f}")
                st.metric("แนวโน้ม", data['trend'])
                st.metric("จำนวนข่าว", data['article_count'])
        
        st.markdown("---")
        
        # แสดงรายละเอียดข่าว
        for asset_name, data in results.items():
            st.subheader(f"📰 ข่าวล่าสุด - {asset_name}")
            for art in data["articles"]:
                with st.container():
                    st.markdown(f"**[{art['title']}]({art['link']})**")
                    summary_th = translate_text(art["summary_en"])
                    st.write(f"→ {summary_th}")
                st.markdown("---")

elif app_mode == "🔍 โหมดเปรียบเทียบ":
    st.subheader("🆚 เปรียบเทียบทั้งสองโหมด")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("### 🏆 Gold Summary")
        gold_summary = generate_gold_daily_summary(gold_data)
        if gold_summary:
            st.markdown(gold_summary)
        else:
            st.warning("ไม่พบข่าวทองคำล่าสุด")
    
    with col2:
        st.markdown("### 📊 Full Dashboard - ทองคำ")
        if gold_data:
            st.metric("Sentiment", f"{gold_data['sentiment']:.3f}")
            st.metric("จำนวนข่าว", gold_data['article_count'])
            st.info(f"ข่าวล่าสุด {len(gold_data['articles'][:3])} ข่าวจากทั้งหมด {gold_data['article_count']} ข่าว")
            
            for i, art in enumerate(gold_data['articles'][:3], 1):
                st.markdown(f"{i}. **{art['title']}**")
        else:
            st.warning("ไม่พบข่าวทองคำ")

# Footer
st.markdown("---")
st.info("""
**✅ ข้อมูลตอนนี้สอดคล้องกันแล้ว:**
- ทั้งสองโหมดใช้ keywords กรองข่าวชุดเดียวกัน
- ใช้วิธีการวิเคราะห์ sentiment เดียวกัน
- จำนวนข่าวที่วิเคราะห์เท่ากัน
- แสดง sentiment score เดียวกัน
""")
