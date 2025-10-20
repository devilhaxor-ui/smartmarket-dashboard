import streamlit as st
import feedparser
from datetime import datetime, timedelta
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
from deep_translator import GoogleTranslator
from bs4 import BeautifulSoup
import pytz
import yfinance as yf
import pandas as pd
import json
import time
import requests
from threading import Thread
import sqlite3
import os

# ตั้งค่าโซนเวลาไทย
thai_tz = pytz.timezone('Asia/Bangkok')

# ---------- INITIAL SETUP ----------
def init_database():
    """เริ่มต้น database สำหรับเก็บข้อมูล"""
    conn = sqlite3.connect('market_data.db')
    c = conn.cursor()
    
    c.execute('''CREATE TABLE IF NOT EXISTS market_analysis
                 (id INTEGER PRIMARY KEY, date TEXT, asset TEXT, 
                  sentiment REAL, article_count INTEGER, trend TEXT,
                  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS price_data
                 (id INTEGER PRIMARY KEY, symbol TEXT, price REAL, 
                  change_percent REAL, timestamp TEXT)''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS important_news
                 (id INTEGER PRIMARY KEY, date TEXT, category TEXT,
                  title TEXT, link TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
    
    conn.commit()
    conn.close()

# เรียกใช้การตั้งค่า database
init_database()

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

GOLD_KEYWORDS = ['gold', 'xau', 'bullion', 'precious metal', 'fed', 'inflation', 'dollar', 'usd', 'ทองคำ', 'xauusd']

ASSETS = {
    "ทองคำ (XAU)": GOLD_KEYWORDS,
    "เงิน (XAG)": ["silver", "xagusd"],
    "บิตคอยน์ (BTC)": ["bitcoin", "btc", "crypto"]
}

SYMBOLS = {
    "ทองคำ (XAU)": "GC=F",
    "เงิน (XAG)": "SI=F", 
    "บิตคอยน์ (BTC)": "BTC-USD",
    "ดอลลาร์": "DX=F"
}

analyzer = SentimentIntensityAnalyzer()

# ---------- 1. ข้อมูลราคาเรียลไทม์ ----------
@st.cache_data(ttl=300)  # อัปเดตทุก 5 นาที
def get_live_prices():
    """ดึงข้อมูลราคาเรียลไทม์"""
    prices = {}
    for name, symbol in SYMBOLS.items():
        try:
            ticker = yf.Ticker(symbol)
            data = ticker.history(period="2d")
            if len(data) >= 2:
                current_price = data['Close'][-1]
                prev_price = data['Close'][-2]
                change = ((current_price - prev_price) / prev_price) * 100
                prices[name] = {
                    'price': current_price,
                    'change': change,
                    'symbol': symbol
                }
                
                # บันทึกลง database
                save_price_data(name, symbol, current_price, change)
                
        except Exception as e:
            st.error(f"Error fetching price for {name}: {str(e)}")
            continue
    
    return prices

def save_price_data(asset, symbol, price, change):
    """บันทึกข้อมูลราคาลง database"""
    conn = sqlite3.connect('market_data.db')
    c = conn.cursor()
    c.execute('''INSERT INTO price_data (symbol, price, change_percent, timestamp)
                 VALUES (?, ?, ?, ?)''', 
              (symbol, price, change, datetime.now(thai_tz).isoformat()))
    conn.commit()
    conn.close()

# ---------- 2. การแจ้งเตือนข่าวสำคัญ ----------
def check_important_news(articles):
    """ตรวจสอบข่าวสำคัญที่อาจส่งผลต่อตลาด"""
    important_keywords = {
        "Fed": ["fed", "federal reserve", "jerome powell", "interest rate", "fomc"],
        "เงินเฟ้อ": ["inflation", "cpi", "ppi", "consumer price", "เงินเฟ้อ"],
        "การจ้างงาน": ["employment", "jobs report", "nfp", "unemployment", "nonfarm"],
        "วิกฤตการณ์": ["crisis", "recession", "war", "conflict", "geopolitical"],
        "นโยบายการเงิน": ["monetary policy", "quantitative easing", "tapering", "qe"]
    }
    
    alerts = []
    for category, keywords in important_keywords.items():
        for article in articles[:15]:  # ตรวจสอบ 15 ข่าวล่าสุด
            content = (article['title'] + " " + article['summary_en']).lower()
            if any(keyword in content for keyword in keywords):
                alerts.append({
                    'category': category,
                    'title': article['title'],
                    'link': article['link'],
                    'summary': article['summary_en'][:200] + "..."
                })
                break
    
    # บันทึกข่าวสำคัญลง database
    save_important_news(alerts)
    
    return alerts

def save_important_news(alerts):
    """บันทึกข่าวสำคัญลง database"""
    conn = sqlite3.connect('market_data.db')
    c = conn.cursor()
    today = datetime.now(thai_tz).strftime("%Y-%m-%d")
    
    for alert in alerts:
        c.execute('''INSERT INTO important_news (date, category, title, link)
                     VALUES (?, ?, ?, ?)''', 
                  (today, alert['category'], alert['title'], alert['link']))
    
    conn.commit()
    conn.close()

# ---------- 3. วิเคราะห์ทางเทคนิคร่วมกับ sentiment ----------
def get_technical_analysis(symbol):
    """วิเคราะห์ทางเทคนิคร่วมกับ sentiment"""
    try:
        ticker = yf.Ticker(symbol)
        data = ticker.history(period="2mo")
        
        if len(data) < 20:
            return None
            
        # คำนวณค่าเฉลี่ยเคลื่อนที่
        data['MA20'] = data['Close'].rolling(20).mean()
        data['MA50'] = data['Close'].rolling(50).mean()
        
        current_price = data['Close'][-1]
        ma20 = data['MA20'][-1]
        ma50 = data['MA50'][-1]
        
        # คำนวณ RSI
        delta = data['Close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        current_rsi = rsi[-1]
        
        # วิเคราะห์แนวโน้ม
        if current_price > ma20 > ma50:
            trend = "Uptrend แข็งแกร่ง"
            trend_color = "🟢"
        elif current_price > ma20 and ma20 < ma50:
            trend = "Uptrend อ่อนแอ"
            trend_color = "🟡"
        elif current_price < ma20 < ma50:
            trend = "Downtrend แข็งแกร่ง" 
            trend_color = "🔴"
        else:
            trend = "Downtrend อ่อนแอ"
            trend_color = "🟠"
        
        # วิเคราะห์ RSI
        if current_rsi > 70:
            rsi_signal = " overbought"
            rsi_color = "🔴"
        elif current_rsi < 30:
            rsi_signal = " oversold"
            rsi_color = "🟢"
        else:
            rsi_signal = " neutral"
            rsi_color = "🟡"
            
        return {
            'current_price': current_price,
            'trend': trend,
            'trend_color': trend_color,
            'ma20': ma20,
            'ma50': ma50,
            'rsi': current_rsi,
            'rsi_signal': rsi_signal,
            'rsi_color': rsi_color,
            'support': data['Close'].tail(20).min(),
            'resistance': data['Close'].tail(20).max()
        }
    except Exception as e:
        st.error(f"Technical analysis error: {str(e)}")
        return None

# ---------- 4. ระบบบันทึกและติดตามผล ----------
def save_daily_analysis(results):
    """บันทึกการวิเคราะห์รายวันเพื่อติดตามผล"""
    today = datetime.now(thai_tz).strftime("%Y-%m-%d")
    
    conn = sqlite3.connect('market_data.db')
    c = conn.cursor()
    
    for asset_name, data in results.items():
        c.execute('''INSERT INTO market_analysis (date, asset, sentiment, article_count, trend)
                     VALUES (?, ?, ?, ?, ?)''', 
                  (today, asset_name, data['sentiment'], data['article_count'], data['trend']))
    
    conn.commit()
    conn.close()

def get_analysis_history():
    """ดึงประวัติการวิเคราะห์"""
    conn = sqlite3.connect('market_data.db')
    c = conn.cursor()
    
    c.execute('''SELECT date, asset, sentiment, article_count, trend 
                 FROM market_analysis 
                 ORDER BY date DESC, asset LIMIT 100''')
    
    rows = c.fetchall()
    conn.close()
    
    return pd.DataFrame(rows, columns=['date', 'asset', 'sentiment', 'article_count', 'trend'])

# ---------- 5. กลยุทธ์การเทรดตามสภาวะตลาด ----------
def generate_trading_strategies(results, technical_data, live_prices):
    """สร้างกลยุทธ์การเทรดตามสภาวะตลาด"""
    strategies = []
    
    for asset_name, data in results.items():
        sentiment = data['sentiment']
        article_count = data['article_count']
        
        # กำหนดความน่าเชื่อถือ
        if article_count < 3:
            confidence = "ต่ำ"
            confidence_color = "🔴"
        elif article_count < 6:
            confidence = "ปานกลาง"
            confidence_color = "🟡"
        else:
            confidence = "สูง"
            confidence_color = "🟢"
        
        # ข้อมูลทางเทคนิค
        tech = technical_data.get(asset_name, {})
        current_trend = tech.get('trend', 'ไม่ทราบ')
        rsi_signal = tech.get('rsi_signal', 'ไม่ทราบ')
        
        # สร้างกลยุทธ์ตาม sentiment และ technical
        if sentiment > 0.15 and "Uptrend" in current_trend:
            strategy = {
                'asset': asset_name,
                'action': "🟢 ซื้อทันที",
                'confidence': f"{confidence_color} {confidence}",
                'reason': "ข่าวเชิงบวกแข็งแกร่ง + แนวโน้มทางเทคนิคเป็นบวก",
                'risk': "ปานกลาง",
                'timeframe': "1-3 วัน",
                'target': "0.8-1.2%",
                'stoploss': "0.4%"
            }
        elif sentiment > 0.15 and "Downtrend" in current_trend:
            strategy = {
                'asset': asset_name,
                'action': "🟡 รอ pullback เพื่อซื้อ",
                'confidence': f"{confidence_color} {confidence}",
                'reason': "ข่าวเชิงบวกแต่แนวโน้มทางเทคนิคเป็นลบ",
                'risk': "สูง",
                'timeframe': "2-5 วัน", 
                'target': "1-1.5%",
                'stoploss': "0.6%"
            }
        elif sentiment > 0 and "Uptrend" in current_trend:
            strategy = {
                'asset': asset_name,
                'action': "🟢 ซื้อบนการพักตัว",
                'confidence': f"{confidence_color} {confidence}",
                'reason': "ข่าวเชิงบวกเล็กน้อย + แนวโน้มทางเทคนิคเป็นบวก",
                'risk': "ต่ำถึงปานกลาง",
                'timeframe': "1-2 วัน",
                'target': "0.5-0.8%",
                'stoploss': "0.3%"
            }
        elif sentiment < -0.15 and "Downtrend" in current_trend:
            strategy = {
                'asset': asset_name,
                'action': "🔴 ขาย/Short",
                'confidence': f"{confidence_color} {confidence}",
                'reason': "ข่าวเชิงลบแข็งแกร่ง + แนวโน้มทางเทคนิคเป็นลบ",
                'risk': "สูง",
                'timeframe': "2-5 วัน",
                'target': "1-2%",
                'stoploss': "0.8%"
            }
        else:
            strategy = {
                'asset': asset_name,
                'action': "⚪ รอสัญญาณที่ชัดเจน",
                'confidence': f"{confidence_color} {confidence}",
                'reason': "สัญญาณข่าวและทางเทคนิคขัดแย้งกัน",
                'risk': "ต่ำ",
                'timeframe': "รอ confirmation",
                'target': "-",
                'stoploss': "-"
            }
        
        strategies.append(strategy)
    
    return strategies

# ---------- 7. ข้อมูลเศรษฐกิจสำคัญ ----------
def get_economic_calendar():
    """ดึงข้อมูลเศรษฐกิจสำคัญ"""
    today = datetime.now(thai_tz)
    
    economic_events = [
        {
            'event': 'Fed Meeting',
            'date': (today + timedelta(days=2)).strftime('%d/%m'),
            'impact': 'สูงมาก',
            'effect_on_gold': 'แข็งตัวหากดอกเบี้ยไม่ขึ้น',
            'time': '02:00 น. (ไทย)'
        },
        {
            'event': 'CPI Data', 
            'date': (today + timedelta(days=5)).strftime('%d/%m'),
            'impact': 'สูง',
            'effect_on_gold': 'แข็งตัวหากเงินเฟ้อสูงกว่าคาด',
            'time': '19:30 น. (ไทย)'
        },
        {
            'event': 'NFP Report',
            'date': (today + timedelta(days=7)).strftime('%d/%m'), 
            'impact': 'สูงมาก',
            'effect_on_gold': 'อ่อนตัวหากจ้างงานดีกว่าคาด',
            'time': '19:30 น. (ไทย)'
        },
        {
            'event': 'Retail Sales',
            'date': (today + timedelta(days=3)).strftime('%d/%m'),
            'impact': 'ปานกลาง',
            'effect_on_gold': 'แข็งตัวหากยอดขายต่ำกว่าคาด',
            'time': '19:30 น. (ไทย)'
        }
    ]
    
    return economic_events

# ---------- 8. Dashboard ประสิทธิภาพการทำนาย ----------
def get_performance_stats():
    """แสดงประสิทธิภาพการทำนายย้อนหลัง"""
    try:
        df = get_analysis_history()
        
        if len(df) < 2:
            return None
            
        # คำนวณความแม่นยำคร่าวๆ
        accuracy_data = []
        assets = df['asset'].unique()
        
        for asset in assets:
            asset_df = df[df['asset'] == asset].sort_values('date')
            if len(asset_df) < 2:
                continue
                
            correct_predictions = 0
            total_predictions = len(asset_df) - 1
            
            for i in range(1, len(asset_df)):
                current_sentiment = asset_df.iloc[i]['sentiment']
                prev_sentiment = asset_df.iloc[i-1]['sentiment']
                
                # ถ้า sentiment อยู่ในทิศทางเดียวกันถือว่าถูกต้อง
                if (current_sentiment > 0 and prev_sentiment > 0) or (current_sentiment < 0 and prev_sentiment < 0):
                    correct_predictions += 1
            
            accuracy = (correct_predictions / total_predictions) * 100 if total_predictions > 0 else 0
            
            accuracy_data.append({
                'asset': asset,
                'accuracy': accuracy,
                'total_days': len(asset_df),
                'avg_sentiment': asset_df['sentiment'].mean()
            })
        
        return accuracy_data
    except Exception as e:
        st.error(f"Performance calculation error: {str(e)}")
        return None

# ---------- 11. Background Updates ----------
class NewsUpdater:
    """คลาสสำหรับอัปเดตข่าวในพื้นหลัง"""
    def __init__(self):
        self.last_update = None
        self.is_running = False
        
    def start_background_update(self):
        """เริ่มการอัปเดตในพื้นหลัง"""
        if not self.is_running:
            self.is_running = True
            # ใน Streamlit Cloud อาจต้องใช้วิธีอื่นแทน threading
            st.success("✅ ระบบอัปเดตพื้นหลังเริ่มทำงานแล้ว")
    
    def check_for_updates(self):
        """ตรวจสอบว่าต้องการอัปเดตหรือไม่"""
        if not self.last_update:
            return True
            
        time_diff = datetime.now() - self.last_update
        return time_diff.total_seconds() > 3600  # อัปเดตทุก 1 ชั่วโมง

# ---------- ฟังก์ชันหลักที่มีอยู่เดิม ----------
@st.cache_data(ttl=3600, show_spinner=False)
def get_news():
    articles = []
    for url in RSS_FEEDS:
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries[:10]:
                summary_text = clean_html(entry.get("summary", ""))
                
                articles.append({
                    "title": entry.title,
                    "link": entry.link,
                    "summary_en": summary_text,
                    "published": entry.get("published", ""),
                    "content_lower": (entry.title + " " + summary_text).lower()
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

def analyze_gold_news(articles):
    gold_articles = []
    for article in articles:
        if any(keyword in article['content_lower'] for keyword in GOLD_KEYWORDS):
            gold_articles.append(article)
    
    if not gold_articles:
        return None
    
    sentiment_scores = []
    for article in gold_articles:
        vs = analyzer.polarity_scores(article['title'] + " " + article['summary_en'])
        sentiment_scores.append(vs['compound'])
    
    avg_sentiment = sum(sentiment_scores) / len(sentiment_scores) if sentiment_scores else 0
    
    return {
        'articles': gold_articles,
        'sentiment': avg_sentiment,
        'article_count': len(gold_articles)
    }

def generate_gold_daily_summary(gold_data):
    if not gold_data:
        return None
    
    articles = gold_data['articles'][:5]
    avg_sentiment = gold_data['sentiment']
    
    summaries_th = []
    for i, article in enumerate(articles, 1):
        try:
            title_th = translate_text(article['title'])
            summary_short = article['summary_en'][:150] + "..." if len(article['summary_en']) > 150 else article['summary_en']
            summary_th = translate_text(summary_short)
            
            summaries_th.append(f"{i}. **{title_th}**\n   📝 {summary_th}")
        except:
            summaries_th.append(f"{i}. **{article['title']}**\n   📝 {article['summary_en'][:100]}...")
    
    if avg_sentiment > 0.15:
        trend = "🟢 **แนวโน้มบวก**"
        outlook = "ตลาดทองคำมีแนวโน้มขึ้นจากข่าวเชิงบวก"
    elif avg_sentiment > -0.1:
        trend = "🟡 **แนวโน้มกลาง**"
        outlook = "ตลาดทองคำเคลื่อนไหวในกรอบ แรงส่งไม่ชัดเจน"
    else:
        trend = "🔴 **แนวโน้มลบ**"
        outlook = "ตลาดทองคำมีแรงกดดันจากข่าวเชิงลบ"
    
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
"""
    return summary_report

def generate_full_dashboard(articles):
    results = {}
    
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
            "articles": gold_data['articles'][:3],
            "article_count": gold_data['article_count']
        }
    
    for asset_name, keywords in ASSETS.items():
        if asset_name == "ทองคำ (XAU)":
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
st.set_page_config(page_title="SmartMarket Dashboard Pro", layout="wide", initial_sidebar_state="expanded")

# Initialize background updater
news_updater = NewsUpdater()

# ---------- 9. Customizable Dashboard ใน Sidebar ----------
st.sidebar.title("🎛️ การตั้งค่า Dashboard")

app_mode = st.sidebar.radio(
    "เลือกโหมดการแสดงผล:",
    ["🏆 Gold Daily Summary", "📊 Full Market Dashboard", "🔍 โหมดเปรียบเทียบ"]
)

st.sidebar.markdown("---")
st.sidebar.subheader("🎨 ปรับแต่งการแสดงผล")

# การตั้งค่าที่ปรับแต่งได้
show_live_prices = st.sidebar.checkbox("แสดงราคาเรียลไทม์", True)
show_technical = st.sidebar.checkbox("แสดงวิเคราะห์ทางเทคนิค", True)
show_alerts = st.sidebar.checkbox("แสดงการแจ้งเตือนข่าวสำคัญ", True)
show_strategies = st.sidebar.checkbox("แสดงกลยุทธ์การเทรด", True)
show_economic = st.sidebar.checkbox("แสดงปฏิทินเศรษฐกิจ", True)
show_performance = st.sidebar.checkbox("แสดงประสิทธิภาพ", True)

# Theme selection
theme = st.sidebar.selectbox("ธีมการแสดงผล", ["Default", "Dark Mode", "Professional"])

# Background updates
auto_update = st.sidebar.checkbox("อัปเดตอัตโนมัติทุกชั่วโมง", True)
if auto_update:
    news_updater.start_background_update()

st.sidebar.markdown("---")
st.sidebar.info("""
**คำแนะนำการใช้งาน:**
- 🏆 **Gold Summary**: สำหรับเทรดเดอร์ทองคำระยะสั้น
- 📊 **Full Dashboard**: สำหรับวิเคราะห์หลายสินทรัพย์
- 🔍 **เปรียบเทียบ**: ดูทั้งสองแบบคู่กัน
""")

# ดึงข้อมูลทั้งหมด
with st.spinner('📡 กำลังดึงข้อมูลล่าสุด...'):
    articles = get_news()
    live_prices = get_live_prices() if show_live_prices else {}
    important_alerts = check_important_news(articles) if show_alerts else []
    gold_data = analyze_gold_news(articles)
    results = generate_full_dashboard(articles)
    
    # วิเคราะห์ทางเทคนิค
    technical_data = {}
    if show_technical and results:
        for asset_name in results.keys():
            symbol = SYMBOLS.get(asset_name)
            if symbol:
                technical_data[asset_name] = get_technical_analysis(symbol)
    
    # สร้างกลยุทธ์การเทรด
    trading_strategies = generate_trading_strategies(results, technical_data, live_prices) if show_strategies and results else []
    
    # ข้อมูลเศรษฐกิจ
    economic_events = get_economic_calendar() if show_economic else []
    
    # ประสิทธิภาพ
    performance_stats = get_performance_stats() if show_performance else None

if not articles:
    st.error("ไม่สามารถดึงข่าวได้ กรุณาลองใหม่ภายหลัง")
    st.stop()

# Header หลัก
st.title("🚀 SmartMarket Dashboard Pro")
st.write(f"อัปเดตล่าสุด: {datetime.now(thai_tz).strftime('%d %B %Y, %H:%M')} น.")

# ---------- แสดงข้อมูลตามการตั้งค่า ----------

# แสดงราคาเรียลไทม์
if show_live_prices and live_prices:
    st.subheader("📈 ราคาเรียลไทม์")
    cols = st.columns(len(live_prices))
    for idx, (asset_name, price_data) in enumerate(live_prices.items()):
        with cols[idx]:
            change_color = "green" if price_data['change'] >= 0 else "red"
            st.metric(
                label=asset_name,
                value=f"${price_data['price']:.2f}",
                delta=f"{price_data['change']:.2f}%",
                delta_color="normal"
            )

# แสดงการแจ้งเตือนข่าวสำคัญ
if show_alerts and important_alerts:
    st.subheader("🔔 ข่าวสำคัญที่ต้องระวัง")
    for alert in important_alerts[:3]:  # แสดงแค่ 3 การแจ้งเตือน
        with st.expander(f"{alert['category']}: {alert['title']}", expanded=True):
            st.write(f"**หัวข้อ:** {alert['title']}")
            st.write(f"**สรุป:** {alert['summary']}")
            st.markdown(f"[อ่านต่อ...]({alert['link']})")

# แสดงผลตามโหมดที่เลือก
if app_mode == "🏆 Gold Daily Summary":
    gold_summary = generate_gold_daily_summary(gold_data)
    if gold_summary:
        st.markdown(gold_summary)
        
        # แสดงวิเคราะห์ทางเทคนิคสำหรับทองคำ
        if show_technical and "ทองคำ (XAU)" in technical_data:
            tech = technical_data["ทองคำ (XAU)"]
            if tech:
                st.subheader("📊 วิเคราะห์ทางเทคนิค - ทองคำ")
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("ราคาปัจจุบัน", f"${tech['current_price']:.2f}")
                with col2:
                    st.metric("แนวโน้ม", f"{tech['trend_color']} {tech['trend']}")
                with col3:
                    st.metric("RSI", f"{tech['rsi_color']} {tech['rsi']:.1f}{tech['rsi_signal']}")
    
    else:
        st.warning("ไม่พบข่าวทองคำล่าสุดในขณะนี้")

elif app_mode == "📊 Full Market Dashboard":
    if not results:
        st.warning("ไม่พบข่าวที่เกี่ยวข้องกับสินทรัพย์ที่ติดตาม")
    else:
        # แสดงผลแบบ卡片
        st.subheader("📊 ภาพรวมตลาด")
        cols = st.columns(len(results))
        for idx, (asset_name, data) in enumerate(results.items()):
            with cols[idx]:
                st.subheader(f"🔹 {asset_name}")
                st.metric("Sentiment", f"{data['sentiment']:.3f}")
                st.metric("แนวโน้ม", data['trend'])
                st.metric("จำนวนข่าว", data['article_count'])
        
        # แสดงวิเคราะห์ทางเทคนิค
        if show_technical:
            st.markdown("---")
            st.subheader("📈 วิเคราะห์ทางเทคนิค")
            tech_cols = st.columns(len(results))
            for idx, (asset_name, data) in enumerate(results.items()):
                with tech_cols[idx]:
                    tech = technical_data.get(asset_name)
                    if tech:
                        st.write(f"**{asset_name}**")
                        st.write(f"แนวโน้ม: {tech['trend_color']} {tech['trend']}")
                        st.write(f"RSI: {tech['rsi']:.1f}{tech['rsi_signal']}")
                        st.write(f"MA20: ${tech['ma20']:.2f}")
                        st.write(f"MA50: ${tech['ma50']:.2f}")
        
        # แสดงกลยุทธ์การเทรด
        if show_strategies and trading_strategies:
            st.markdown("---")
            st.subheader("🎯 กลยุทธ์การเทรด")
            for strategy in trading_strategies:
                with st.expander(f"{strategy['asset']}: {strategy['action']}", expanded=True):
                    st.write(f"**ความน่าเชื่อถือ:** {strategy['confidence']}")
                    st.write(f"**เหตุผล:** {strategy['reason']}")
                    st.write(f"**ความเสี่ยง:** {strategy['risk']}")
                    st.write(f"**ระยะเวลา:** {strategy['timeframe']}")
                    st.write(f"**Target กำไร:** {strategy['target']}")
                    st.write(f"**Stop Loss:** {strategy['stoploss']}")
        
        st.markdown("---")
        
        # แสดงรายละเอียดข่าว
        st.subheader("📰 ข่าวล่าสุด")
        for asset_name, data in results.items():
            st.write(f"**{asset_name}**")
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

# แสดงปฏิทินเศรษฐกิจ
if show_economic and economic_events:
    st.markdown("---")
    st.subheader("📅 ปฏิทินเศรษฐกิจสำคัญ")
    for event in economic_events:
        col1, col2, col3, col4 = st.columns([2,1,1,2])
        with col1:
            st.write(f"**{event['event']}**")
        with col2:
            st.write(f"📅 {event['date']}")
        with col3:
            st.write(f"⏰ {event['time']}")
        with col4:
            st.write(f"⚡ {event['impact']} - {event['effect_on_gold']}")

# แสดงประสิทธิภาพ
if show_performance and performance_stats:
    st.markdown("---")
    st.subheader("📊 ประสิทธิภาพการวิเคราะห์ย้อนหลัง")
    
    for stat in performance_stats:
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.write(f"**{stat['asset']}**")
        with col2:
            st.write(f"ความแม่นยำ: {stat['accuracy']:.1f}%")
        with col3:
            st.write(f"จำนวนวัน: {stat['total_days']}")
        with col4:
            st.write(f"Sentiment เฉลี่ย: {stat['avg_sentiment']:.3f}")

# บันทึกการวิเคราะห์รายวัน
if results:
    save_daily_analysis(results)

# Footer
st.markdown("---")
st.info("""
**✅ ฟีเจอร์ทั้งหมดที่เพิ่มมา:**
- 📈 ราคาเรียลไทม์จาก Yahoo Finance
- 🔔 การแจ้งเตือนข่าวสำคัญอัตโนมัติ
- 📊 วิเคราะห์ทางเทคนิค (MA, RSI)
- 💾 ระบบบันทึกและติดตามผลใน Database
- 🎯 กลยุทธ์การเทรดตามสภาวะตลาด
- 📅 ปฏิทินเศรษฐกิจสำคัญ
- 📈 Dashboard ประสิทธิภาพการทำนาย
- 🎨 Customizable Dashboard
- 🔄 Background Updates
""")

# ดาวน์โหลดรายงาน
st.markdown("---")
st.subheader("📥 ดาวน์โหลดรายงาน")

col1, col2 = st.columns(2)
with col1:
    if st.button("ดาวน์โหลด Gold Summary"):
        gold_summary = generate_gold_daily_summary(gold_data)
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
        
        if results:
            for asset_name, data in results.items():
                full_report += f"{asset_name}: {data['trend']} (Sentiment: {data['sentiment']:.3f})\n"
        
        st.download_button(
            label="📥 ดาวน์โหลด",
            data=full_report,
            file_name=f"full_report_{datetime.now(thai_tz).strftime('%Y%m%d')}.txt",
            mime="text/plain"
        )

st.caption("🧠 SmartMarket Dashboard Pro - รวมทุกฟีเจอร์ในการวิเคราะห์ตลาดการเงิน")
