import streamlit as st
import time
import random
import requests
import io
import pandas as pd
from urllib.parse import urljoin, urlparse
import google.generativeai as genai
import urllib3

# --- ROBUST IMPORT FOR BS4 ---
try:
    from bs4 import BeautifulSoup
except ImportError:
    st.error("❌ Critical Error: 'beautifulsoup4' is missing from requirements.txt.")
    st.stop()

# Disable SSL warnings
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# --- PAGE CONFIG ---
st.set_page_config(page_title="AI SEO Auditor", page_icon="✨", layout="wide")
st.title("✨ AI SEO Audit Agent (Gemini 2.5)")

# --- SIDEBAR ---
with st.sidebar:
    st.header("⚙️ Configuration")
    api_key = st.text_input("Enter Gemini API Key", type="password")
    max_pages = st.slider("Max Pages", 1, 5, 3)
    st.caption("Using Gemini 2.5 Flash (Your best available model)")

# --- CRAWLER ---
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
            time.sleep(random.uniform(0.5, 1.0)) # Politeness delay

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

# --- ANALYZER (Using YOUR Valid Models) ---
def analyze_with_valid_models(raw_data, api_key):
    genai.configure(api_key=api_key)
    
    # *** THIS IS THE FIX ***
    # These are the exact models from your list that will work.
    valid_models = [
        'gemini-2.5-flash',          # First choice: Newest & Fastest
        'gemini-flash-latest',       # Second choice: Stable alias
        'gemini-2.0-flash-lite-preview-02-05' # Third choice: Low quota
    ]
    
    # Truncate to prevent Token Limit errors
    safe_data = raw_data[:15000] 
    
    prompt = f"""
    Act as an SEO Expert. Create a remediation plan table (CSV).
    Columns: URL, Error, Fix, Priority.
    Data: {safe_data}
    Output: Only CSV data. No markdown.
    """

    for model_name in valid_models:
        try:
            model = genai.GenerativeModel(model_name)
            response = model.generate_content(prompt)
            
            # If we get here, it worked!
            return response.text.replace("```csv", "").replace("```", "").strip(), model_name
            
        except Exception as e:
            error_msg = str(e)
            # If Quota limit (429), wait and retry ONCE
            if "429" in error_msg or "Quota" in error_msg:
                time.sleep(10)
                try:
                    response = model.generate_content(prompt)
                    return response.text.replace("```csv", "").replace("```", "").strip(), model_name
                except:
                    pass # Move to next model
            
            # If 404, just move to the next model in the list
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
                
                # 2. ANALYZE
                csv_result, used_model = analyze_with_valid_models(crawled_data, api_key)
                
                if csv_result:
                    st.toast(f"Success! Powered by: {used_model}")
                    
                    try:
                        headers = ['URL', 'Error', 'Fix', 'Priority']
                        df = pd.read_csv(io.StringIO(csv_result), names=headers, header=None)
                        st.dataframe(df, use_container_width=True)
                        
                        csv_data = df.to_csv(index=False).encode('utf-8')
                        st.download_button("💾 Download CSV Report", csv_data, "seo_report.csv", "text/csv")
                    except:
                        st.text("Raw Output (CSV parsing failed):")
                        st.text(csv_result)
                else:
                    st.error("❌ Analysis failed. Your API key might be rate-limited. Try again in 60 seconds.")
            else:
                st.error("Could not crawl site. The website might be blocking bots.")
else:
    st.warning("👈 Please enter your Gemini API Key.")
