import streamlit as st
import time
import random
import requests
import io
import pandas as pd
from urllib.parse import urljoin, urlparse
import google.generativeai as genai
import urllib3

# --- 1. PAGE CONFIG (MUST BE FIRST) ---
st.set_page_config(page_title="AI SEO Auditor", page_icon="✨", layout="wide")

# --- 2. ROBUST IMPORT CHECK ---
try:
    from bs4 import BeautifulSoup
except ImportError:
    st.error("❌ Critical Error: 'beautifulsoup4' is missing.")
    st.info("Please update your requirements.txt on GitHub to include 'beautifulsoup4'.")
    st.stop()

# Disable SSL warnings
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# --- 3. HELPER FUNCTIONS ---
def clean_csv_output(text):
    # Removes markdown and extra text to find the CSV data
    text = text.replace("```csv", "").replace("```", "").strip()
    lines = text.split('\n')
    # Keep only lines that look like CSV rows (have commas)
    clean_lines = [line for line in lines if "," in line]
    return "\n".join(clean_lines)

@st.cache_data(show_spinner=False)
def stealth_crawler(start_url, max_pages_limit):
    user_agents = ['Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/91.0.4472.124 Safari/537.36']
    visited = set()
    queue = [start_url]
    raw_data = []
    base_domain = urlparse(start_url).netloc
    
    progress_bar = st.progress(0, text="🕷️ Waiting to start...")
    
    count = 0
    while queue and count < max_pages_limit:
        url = queue.pop(0)
        if url in visited: continue
            
        try:
            progress_bar.progress((count + 1) / max_pages_limit, text=f"Crawling: {url}")
            headers = {'User-Agent': random.choice(user_agents)}
            time.sleep(random.uniform(0.5, 1.0))
            
            response = requests.get(url, headers=headers, timeout=5, verify=False)
            visited.add(url)
            
            if response.status_code == 200:
                soup = BeautifulSoup(response.content, 'html.parser')
                title = soup.title.string.strip() if soup.title else "MISSING"
                h1 = soup.find('h1').get_text(strip=True) if soup.find('h1') else "MISSING"
                meta = soup.find('meta', attrs={'name': 'description'})
                desc = meta['content'] if meta else "MISSING"
                
                raw_data.append(f"URL: {url} | TITLE: {title} | H1: {h1} | DESC: {desc}")
                count += 1
                
                for link in soup.find_all('a', href=True):
                    full_link = urljoin(url, link['href'])
                    if urlparse(full_link).netloc == base_domain and full_link not in visited:
                        queue.append(full_link)
        except Exception:
            pass 
    
    progress_bar.empty()
    return "\n".join(raw_data)

def call_gemini(prompt, api_key):
    genai.configure(api_key=api_key)
    # Models to try (Your API key supports these)
    models = ['gemini-2.5-flash', 'gemini-flash-latest', 'gemini-2.0-flash-lite-preview-02-05']
    
    for model_name in models:
        try:
            model = genai.GenerativeModel(model_name)
            response = model.generate_content(prompt)
            return response.text
        except Exception:
            time.sleep(2) # Wait a moment if busy
            continue
    return "Error: All models failed."

def generate_report(raw_data, api_key, report_type="summary"):
    # Limit text to avoid quota errors
    safe_data = raw_data[:15000]
    
    if report_type == "summary":
        prompt = f"""
        Act as a Senior SEO Auditor. Analyze this raw data.
        OUTPUT FORMAT:
        1. Headline: "### 📋 Executive Summary"
        2. Brief strategy summary.
        3. Markdown Table: | Critical Error | Severity | Description |
        4. "### ⚠️ Action Required" section.
        RAW DATA: {safe_data}
        """
        return call_gemini(prompt, api_key)
    
    else: # Detailed Fixes
        prompt = f"""
        Act as an SEO Expert. 
        OUTPUT: ONLY valid CSV rows. NO HEADERS. NO TEXT.
        Format: "URL","Error","Current","Fix","Priority"
        RAW DATA: {safe_data}
        """
        raw_res = call_gemini(prompt, api_key)
        return clean_csv_output(raw_res)

# --- 4. MAIN APP UI ---
st.title("✨ AI SEO Audit Agent")
st.markdown("---")

col1, col2 = st.columns([1, 2])

with col1:
    st.info("1. Configuration")
    api_key = st.text_input("🔑 Enter Gemini API Key", type="password")
    max_pages = st.slider("Pages to Scan", 1, 6, 3)

with col2:
    st.info("2. Target Website")
    url_input = st.text_input("🌐 Enter Website URL", placeholder="https://example.com")
    
    start_btn = st.button("🚀 Start Professional Audit", type="primary")

# --- 5. EXECUTION LOGIC ---
if start_btn:
    if not api_key:
        st.error("❌ Please enter your API Key in the left box.")
    elif not url_input:
        st.error("❌ Please enter a Website URL.")
    else:
        # Fix URL formatting
        if not url_input.startswith("http"):
            url_input = "https://" + url_input
            
        st.divider()
        # THIS IS THE FIXED LINE BELOW:
        st.write(f"### 🔄 Auditing: {url_input}")
        
        # 1. Crawl
        crawled_data = stealth_crawler(url_input, max_pages)
        
        if crawled_data:
            st.success(f"✅ Scanned {max_pages} pages successfully.")
            
            # 2. Executive Summary
            with st.spinner("🧠 Generating Strategy Report..."):
                summary = generate_report(crawled_data, api_key, "summary")
                st.markdown(summary)
            
            st.divider()
            
            # 3. Detailed CSV
            with st.spinner("🛠️ Generating Fixes Table..."):
                csv_txt = generate_report(crawled_data, api_key, "detailed")
                
                # Check if we got valid CSV data back
                if "Error" not in csv_txt and len(csv_txt) > 10:
                    try:
                        headers = ['URL', 'Error', 'Current', 'Fix', 'Priority']
                        df = pd.read_csv(io.StringIO(csv_txt), names=headers, header=None, on_bad_lines='skip')
                        
                        st.markdown("### 🛠️ Detailed Action Plan")
                        st.dataframe(df, use_container_width=True)
                        
                        csv_file = df.to_csv(index=False).encode('utf-8')
                        st.download_button("💾 Download CSV Report", csv_file, "seo_audit.csv", "text/csv")
                    except Exception as e:
                        st.error(f"Error building table: {e}")
                        st.code(csv_txt)
                else:
                    st.error("AI failed to generate fixes.")
        else:
            st.error("❌ Crawler failed. The website might be blocking bots.")
