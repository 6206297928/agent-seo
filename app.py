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

st.title("🕵️ AI SEO Audit Agent")
st.markdown("Enter a website URL below to generate a comprehensive SEO Audit Report.")

# --- SIDEBAR CONFIG ---
with st.sidebar:
    st.header("⚙️ Configuration")
    api_key = st.text_input("Enter Gemini API Key", type="password")
    st.info("Get your key from [Google AI Studio](https://aistudio.google.com/).")
    
    max_pages = st.slider("Max Pages to Crawl", 1, 10, 5)

# --- FUNCTIONS (Your Logic) ---
def stealth_crawler(start_url, max_pages):
    st.toast(f"🕷️ Starting crawl on {start_url}...")
    
    user_agents = [
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/91.0.4472.124 Safari/537.36',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) Safari/605.1.15'
    ]
    
    visited = set()
    queue = [start_url]
    raw_data = []
    base_domain = urlparse(start_url).netloc
    
    # Progress bar
    progress_text = "Crawling in progress. Please wait."
    my_bar = st.progress(0, text=progress_text)
    
    pages_scanned = 0

    while queue and len(visited) < max_pages:
        url = queue.pop(0)
        if url in visited: continue
            
        try:
            # Update UI
            my_bar.progress((pages_scanned + 1) / max_pages, text=f"Scanning: {url}")
            
            headers = {'User-Agent': random.choice(user_agents)}
            time.sleep(random.uniform(0.5, 1.5)) # Polite delay

            response = requests.get(url, headers=headers, timeout=10, verify=False)
            visited.add(url)
            
            if response.status_code == 200:
                soup = BeautifulSoup(response.content, 'html.parser')
                
                title = soup.title.string.strip() if soup.title else "MISSING"
                h1 = soup.find('h1').get_text(strip=True) if soup.find('h1') else "MISSING"
                meta = soup.find('meta', attrs={'name': 'description'})
                desc = meta['content'] if meta else "MISSING"
                
                raw_data.append(f"URL: {url} | TITLE: {title} | H1: {h1} | DESC: {desc}")
                pages_scanned += 1
                
                # Find links
                for link in soup.find_all('a', href=True):
                    full_link = urljoin(url, link['href'])
                    if urlparse(full_link).netloc == base_domain and full_link not in visited:
                        queue.append(full_link)
        except Exception as e:
            st.error(f"Error scanning {url}: {e}")

    my_bar.empty()
    return "\n".join(raw_data)

def analyze_and_fix(raw_data, api_key):
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel('models/gemini-1.5-flash')
    
    with st.spinner("🧠 AI is analyzing data and generating fixes..."):
        prompt = f"""
        You are an Expert SEO Auditor. Analyze this raw data.
        
        TASK:
        Create a detailed remediation plan CSV.
        
        RAW DATA:
        {raw_data}
        
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

# --- MAIN APP UI ---
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
                st.success(f"✅ Crawling complete! Found data.")
                with st.expander("View Raw Crawl Data"):
                    st.code(crawled_data)
                
                # 2. ANALYZE
                csv_result = analyze_and_fix(crawled_data, api_key)
                
                # 3. DISPLAY
                try:
                    headers = ['URL', 'Error_Type', 'Current_Value', 'Recommended_Fix', 'Priority']
                    df = pd.read_csv(io.StringIO(csv_result), names=headers, header=None)
                    
                    st.subheader("📋 Audit Report")
                    st.dataframe(df, use_container_width=True)
                    
                    # 4. DOWNLOAD
                    csv_data = df.to_csv(index=False).encode('utf-8')
                    st.download_button(
                        label="💾 Download Report as CSV",
                        data=csv_data,
                        file_name="seo_audit_report.csv",
                        mime="text/csv",
                    )
                except Exception as e:
                    st.error(f"Formatting Error: {e}")
                    st.text(csv_result)
            else:
                st.error("Crawler returned no data. Site might be blocking bots.")
else:
    st.warning("👈 Please enter your Gemini API Key in the sidebar to start.")
