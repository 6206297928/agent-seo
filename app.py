import streamlit as st
import time
import random
import requests
import io
import pandas as pd
from bs4 import BeautifulSoup 
from urllib.parse import urljoin, urlparse
import google.generativeai as genai
import urllib3

# Disable SSL warnings
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# --- PAGE CONFIG ---
st.set_page_config(page_title="AI SEO Auditor", page_icon="🕵️", layout="wide")

st.title("🕵️ AI SEO Audit Agent (Gemini 2.0)")
st.markdown("Enter a website URL below. Using the high-speed **Gemini 2.0 Flash** model.")

# --- SIDEBAR ---
with st.sidebar:
    st.header("⚙️ Configuration")
    api_key = st.text_input("Enter Gemini API Key", type="password")
    max_pages = st.slider("Max Pages to Crawl", 1, 5, 3) 
    st.info("Using 'gemini-2.0-flash'. Max pages limited to 5 to save quota.")

# --- 1. THE CRAWLER (With Caching) ---
@st.cache_data(show_spinner=False)
def stealth_crawler(start_url, max_pages_limit):
    # This function only runs ONCE per URL. Streamlit remembers the result!
    user_agents = [
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/91.0.4472.124 Safari/537.36',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) Safari/605.1.15'
    ]
    
    visited = set()
    queue = [start_url]
    raw_data = []
    base_domain = urlparse(start_url).netloc
    
    progress_bar = st.progress(0, text="Starting spider...")
    
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

# --- 2. THE ANALYZER (Using Gemini 2.0 Flash) ---
def analyze_and_fix(raw_data, api_key):
    genai.configure(api_key=api_key)
    
    # *** MODEL CHANGED TO 2.0 FLASH ***
    model = genai.GenerativeModel('gemini-2.0-flash')
    
    # Limit data size to avoid "Quota Exceeded"
    safe_data = raw_data[:25000] 
    
    with st.spinner("🧠 Gemini 2.0 is analyzing..."):
        prompt = f"""
        You are an Expert SEO Auditor.
        
        TASK:
        Audit this website data and provide a remediation plan.
        
        RAW DATA:
        {safe_data}
        
        OUTPUT FORMAT:
        ONLY valid CSV rows. NO HEADERS.
        Columns: URL, Error_Type, Current_Value, Recommended_Fix, Priority
        Quote every field.
        """
        
        try:
            response = model.generate_content(prompt)
            return response.text.replace("```csv", "").replace("```", "").strip()
        except Exception as e:
            return f"Error: {e}"

# --- MAIN UI ---
if api_key:
    url_input = st.text_input("Website URL", placeholder="https://example.com")
    
    if st.button("🚀 Start Audit"):
        if not url_input:
            st.warning("Please enter a URL.")
        else:
            if not url_input.startswith("http"): url_input = "https://" + url_input
            
            # 1. CRAWL
            crawled_data = stealth_crawler(url_input, max_pages)
            
            if crawled_data:
                st.success(f"✅ Crawling complete! Sending to AI...")
                
                # 2. ANALYZE
                csv_result = analyze_and_fix(crawled_data, api_key)
                
                # 3. REPORT
                try:
                    headers = ['URL', 'Error_Type', 'Current_Value', 'Recommended_Fix', 'Priority']
                    df = pd.read_csv(io.StringIO(csv_result), names=headers, header=None)
                    
                    st.subheader("📋 Audit Results")
                    st.dataframe(df, use_container_width=True)
                    
                    csv_data = df.to_csv(index=False).encode('utf-8')
                    st.download_button(
                        label="💾 Download Report",
                        data=csv_data,
                        file_name="seo_audit_report.csv",
                        mime="text/csv",
                    )
                except Exception as e:
                    st.error("AI Error: Quota exceeded or invalid response.")
                    st.text(csv_result)
            else:
                st.error("Crawler blocked or found no data.")
else:
    st.warning("👈 Please enter your Gemini API Key in the sidebar.")
