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

# ---------- GOLD DAILY SUMMARY FUNCTION ----------
def generate_gold_daily_summary(articles):
    """สรุปข่าวทองคำรายวันแบบกระชับ"""
    
    # กรองข่าวทองคำ
    gold_articles = []
    for article in articles:
        content = (article["title"] + " " + article["summary_en"]).lower()
        gold_keywords = ['gold', 'xau', 'bullion', 'precious metal', 'fed', 'inflation', 'dollar', 'usd', 'ทองคำ']
        
        if any(keyword in content for keyword in gold_keywords):
            gold_articles.append(article)
    
    # เลือก 5 ข่าวล่าสุด
    top_gold_articles = gold_articles[:5]
    
    if not top_gold_articles:
        return None
    
    # วิเคราะห์ Sentiment
    sentiment_scores = []
    for article in top_gold_articles:
        vs = analyzer.polarity_scores(article['title'] + " " + article['summary_en'])
        sentiment_scores.append(vs['compound'])
    
    avg_sentiment = sum(sentiment_scores) / len(sentiment_scores)
    
    # สรุปข่าวเป็นภาษาไทย
    summaries_th = []
    for i, article in enumerate(top_gold_articles, 1):
        try:
            title_th = translate_text(article['title'])
            summary_short = article['summary_en'][:150] + "..." if len(article['summary_en']) > 150 else article['summary_en']
            summary_th = translate_text(summary_short)
            
            summaries_th.append(f"{i}. **{title_th}**\n   📝 {summary_th}")
        except:
            summaries_th.append(f"{i}. **{article['title']}**\n   📝 {article['summary_en'][:100]}...")
    
    # สรุปแนวโน้มและคำแนะนำ
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
    
    # สรุปผลลัพธ์
    summary_report = f"""
# 🏆 Gold Daily Summary
*อัปเดตล่าสุด: {datetime.now(thai_tz).strftime('%d/%m/%Y %H:%M')} น.*

## 📊 สรุปแนวโน้ม
{trend}
**Sentiment Score:** {avg_sentiment:.3f}
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

# ---------- FULL DASHBOARD FUNCTION ----------
def generate_full_dashboard(articles):
    """สร้าง Dashboard แบบเต็ม"""
    results = {}
    
    for asset_name, keywords in ASSETS.items():
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

# Sidebar สำหรับเลือกโหมด
st.sidebar.title("🎛️ การตั้งค่า")
app_mode = st.sidebar.radio(
    "เลือกโหมดการแสดงผล:",
    ["🏆 Gold Daily Summary", "📊 Full Market Dashboard", "🔍 โหมดเปรียบเทียบ"]
)

auto_update = st.sidebar.checkbox("อัปเดตอัตโนมัติทุกชั่วโมง", value=True)
st.sidebar.markdown("---")
st.sidebar.info("""
**คำแนะนำการใช้งาน:**
- 🏆 **Gold Summary**: สำหรับเทรดเดอร์ทองคำระยะสั้น
- 📊 **Full Dashboard**: สำหรับวิเคราะห์หลายสินทรัพย์
- 🔍 **เปรียบเทียบ**: ดูทั้งสองแบบคู่กัน
""")

# Header หลัก
st.title("🚀 SmartMarket Dashboard Pro")
st.write(f"อัปเดตล่าสุด: {datetime.now(thai_tz).strftime('%d %B %Y, %H:%M')} น.")

# ดึงข้อมูลข่าว
with st.spinner('📡 กำลังดึงข่าวล่าสุด...'):
    articles = get_news()

if not articles:
    st.error("ไม่สามารถดึงข่าวได้ กรุณาลองใหม่ภายหลัง")
    st.stop()

# แสดงผลตามโหมดที่เลือก
if app_mode == "🏆 Gold Daily Summary":
    
    col1, col2 = st.columns([3, 1])
    
    with col1:
        gold_summary = generate_gold_daily_summary(articles)
        if gold_summary:
            st.markdown(gold_summary)
        else:
            st.warning("ไม่พบข่าวทองคำล่าสุดในขณะนี้")
    
    with col2:
        st.subheader("📈 ข้อมูลเสริม")
        st.metric("ราคาทองล่าสุด", "1,850 USD", "+12.50")
        st.metric("ดอลลาร์指數", "104.25", "-0.35")
        st.metric("อัตราดอกเบี้ย", "5.25%", "0.00")
        
        st.markdown("---")
        st.subheader("⏰ เทรดตามเวลา")
        st.info("""
        **ช่วงเวลาแนะนำ:**
        - 08:00-10:00: Asian Session
        - 15:00-17:00: European Session  
        - 20:00-22:00: US Session
        """)

elif app_mode == "📊 Full Market Dashboard":
    
    st.info("รวบรวมข่าวล่าสุดเกี่ยวกับทองคำ, เงิน และบิตคอยน์ แล้ววิเคราะห์แนวโน้มเป็น **ภาษาไทย**")
    
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
        gold_summary = generate_gold_daily_summary(articles)
        if gold_summary:
            # แสดงเฉพาะส่วนสำคัญของ Gold Summary
            lines = gold_summary.split('\n')
            for line in lines[:15]:  # แสดงเฉพาะส่วนต้น
                st.markdown(line)
            
            with st.expander("ดูคำแนะนำการเทรดเต็มรูปแบบ"):
                for line in lines[15:]:
                    st.markdown(line)
        else:
            st.warning("ไม่พบข่าวทองคำล่าสุด")
    
    with col2:
        st.markdown("### 📊 Full Dashboard")
        results = generate_full_dashboard(articles)
        
        if results:
            for asset_name, data in results.items():
                st.markdown(f"**{asset_name}**")
                col_a, col_b = st.columns(2)
                with col_a:
                    st.metric("Sentiment", f"{data['sentiment']:.3f}")
                with col_b:
                    st.metric("แนวโน้ม", data['trend'])
                st.progress((data['sentiment'] + 1) / 2)
                st.markdown("---")
        else:
            st.warning("ไม่พบข่าวที่เกี่ยวข้อง")

# Footer และข้อมูลเพิ่มเติม
st.markdown("---")
st.subheader("📋 สรุปการวิเคราะห์วันนี้")

if 'results' not in locals():
    results = generate_full_dashboard(articles)

if results:
    bullish_count = sum(1 for data in results.values() if data['sentiment'] > 0.1)
    bearish_count = sum(1 for data in results.values() if data['sentiment'] < -0.1)
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("สินทรัพย์บวก", bullish_count)
    with col2:
        st.metric("สินทรัพย์ลบ", bearish_count)
    with col3:
        st.metric("สินทรัพย์ทั้งหมด", len(results))
    
    if bullish_count >= 2:
        st.success("**ตลาดวันนี้: Risk-On** - ส่วนใหญ่มีแนวโน้มบวก")
    elif bearish_count >= 2:
        st.error("**ตลาดวันนี้: Risk-Off** - ส่วนใหญ่มีแนวโน้มลบ")
    else:
        st.warning("**ตลาดวันนี้: Mixed** - แนวโน้มผสมผสาน")

# ดาวน์โหลดรายงาน
st.markdown("---")
st.subheader("📥 ดาวน์โหลดรายงาน")

col1, col2 = st.columns(2)
with col1:
    if st.button("ดาวน์โหลด Gold Summary"):
        gold_summary = generate_gold_daily_summary(articles)
        if gold_summary:
            st.download_button(
                label="📥 ดาวน์โหลด",
                data=gold_summary,
                file_name=f"gold_summary_{datetime.now(thai_tz).strftime('%Y%m%d')}.txt",
                mime="text/plain"
            )

with col2:
    if st.button("ดาวน์โหลด Full Report"):
        full_report = "SmartMarket Dashboard Pro Report\n"
        full_report += f"วันที่: {datetime.now(thai_tz).strftime('%d/%m/%Y %H:%M')}\n\n"
        
        results = generate_full_dashboard(articles)
        for asset_name, data in results.items():
            full_report += f"{asset_name}: {data['trend']} (Sentiment: {data['sentiment']:.3f})\n"
        
        st.download_button(
            label="📥 ดาวน์โหลด",
            data=full_report,
            file_name=f"full_report_{datetime.now(thai_tz).strftime('%Y%m%d')}.txt",
            mime="text/plain"
        )

st.caption("🧠 SmartMarket Dashboard Pro - รวมทุกฟังก์ชันในการวิเคราะห์ตลาดการเงิน")
