import streamlit as st
import time
import random
import requests
import io
import pandas as pd
from urllib.parse import urljoin, urlparse
import google.generativeai as genai
import urllib3

# --- 1. ROBUST IMPORT (Handles missing BS4 gracefully) ---
try:
    from bs4 import BeautifulSoup
except ImportError:
    st.error("❌ Critical Error: 'beautifulsoup4' is missing.")
    st.info("Please add 'beautifulsoup4' to your requirements.txt file on GitHub.")
    st.stop()

# Disable SSL warnings
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# --- PAGE CONFIG ---
st.set_page_config(page_title="AI SEO Auditor", page_icon="🕵️", layout="wide")
st.title("🕵️ AI SEO Audit Agent (Auto-Fixing)")

# --- SIDEBAR ---
with st.sidebar:
    st.header("⚙️ Configuration")
    api_key = st.text_input("Enter Gemini API Key", type="password")
    max_pages = st.slider("Max Pages", 1, 5, 3)
    
    # Model Selector with Fallback Info
    st.info("💡 This agent will automatically try different Gemini models if one fails.")

# --- CRAWLER FUNCTION ---
@st.cache_data(show_spinner=False)
def stealth_crawler(start_url, max_pages_limit):
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
            time.sleep(random.uniform(0.5, 1.0)) # Wait between pages

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

# --- ANALYZER (With Model Fallback) ---
def analyze_with_fallback(raw_data, api_key):
    genai.configure(api_key=api_key)
    
    # LIST OF MODELS TO TRY (In order of preference)
    # 1. Gemini 2.0 Flash (Fastest)
    # 2. Gemini 1.5 Flash (Standard)
    # 3. Gemini Pro (Legacy/Stable)
    candidate_models = ['gemini-2.0-flash', 'gemini-1.5-flash', 'gemini-pro']
    
    safe_data = raw_data[:20000] # Limit text to prevent Quota issues
    
    prompt = f"""
    Act as an SEO Expert. Create a remediation plan table (CSV).
    Columns: URL, Error, Fix, Priority.
    Data: {safe_data}
    Output: Only CSV data. No markdown.
    """

    for model_name in candidate_models:
        try:
            print(f"Testing model: {model_name}...")
            model = genai.GenerativeModel(model_name)
            response = model.generate_content(prompt)
            
            # If successful, return result immediately
            return response.text.replace("```csv", "").replace("```", "").strip(), model_name
            
        except Exception as e:
            error_msg = str(e)
            # If Quota limit, wait and retry SAME model
            if "429" in error_msg or "Quota" in error_msg:
                st.warning(f"⚠️ Quota hit on {model_name}. Waiting 20s...")
                time.sleep(20)
                try:
                    response = model.generate_content(prompt)
                    return response.text.replace("```csv", "").replace("```", "").strip(), model_name
                except:
                    pass # Move to next model if retry fails
            
            # If 404 (Not Found), just continue to next model
            continue

    return None, "All models failed"

# --- MAIN UI ---
if api_key:
    url_input = st.text_input("Website URL", placeholder="https://example.com")
    
    if st.button("🚀 Start Audit"):
        if not url_input.startswith("http"):
            st.warning("Please include https://")
        else:
            # 1. CRAWL
            crawled_data = stealth_crawler(url_input, max_pages)
            
            if crawled_data:
                st.success(f"✅ Crawling complete! Running AI analysis...")
                
                # 2. ANALYZE (With Auto-Switching)
                csv_result, used_model = analyze_with_fallback(crawled_data, api_key)
                
                if csv_result:
                    st.toast(f"Success! Used model: {used_model}")
                    
                    try:
                        headers = ['URL', 'Error', 'Fix', 'Priority']
                        df = pd.read_csv(io.StringIO(csv_result), names=headers, header=None)
                        st.dataframe(df, use_container_width=True)
                        
                        csv_data = df.to_csv(index=False).encode('utf-8')
                        st.download_button("💾 Download CSV", csv_data, "seo_report.csv", "text/csv")
                    except:
                        st.text(csv_result) # Fallback view
                else:
                    st.error("❌ All AI models failed. Please check your API key or try again in 1 minute.")
            else:
                st.error("Could not crawl site.")
else:
    st.warning("👈 Please enter your API Key.")
