import streamlit as st
import time
import random
import requests
import io
import pandas as pd
from urllib.parse import urljoin, urlparse
import google.generativeai as genai
import urllib3

# --- 1. ROBUST IMPORT (Handles missing BS4) ---
try:
    from bs4 import BeautifulSoup
except ImportError:
    st.error("❌ Critical Error: 'beautifulsoup4' is missing from requirements.txt.")
    st.stop()

# Disable SSL warnings
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# --- PAGE CONFIG ---
st.set_page_config(page_title="AI SEO Auditor", page_icon="✨", layout="wide")
st.title("✨ AI SEO Audit Agent (Gemini 2.5 Professional)")

# --- SIDEBAR ---
with st.sidebar:
    st.header("⚙️ Configuration")
    api_key = st.text_input("Enter Gemini API Key", type="password")
    max_pages = st.slider("Max Pages to Scan", 1, 6, 4)
    st.caption("Powered by Gemini 2.5 Flash")

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
    
    progress_bar = st.progress(0, text="🕷️ Spider is crawling...")
    
    count = 0
    while queue and count < max_pages_limit:
        url = queue.pop(0)
        if url in visited: continue
            
        try:
            progress_bar.progress((count + 1) / max_pages_limit, text=f"Scanning: {url}")
            headers = {'User-Agent': random.choice(user_agents)}
            time.sleep(random.uniform(0.5, 1.0)) # Polite delay

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

# --- AI HELPER: ROBUST CALLER (FIXED MODELS) ---
def call_gemini(prompt, api_key):
    genai.configure(api_key=api_key)
    
    # *** CORRECTED MODEL LIST FOR YOUR KEY ***
    models = [
        'gemini-2.5-flash',          # Your best model
        'gemini-flash-latest',       # Your backup
        'gemini-2.0-flash-lite-preview-02-05' # Low quota backup
    ]
    
    last_error = ""
    
    for model_name in models:
        try:
            model = genai.GenerativeModel(model_name)
            # Generate
            response = model.generate_content(prompt)
            return response.text
            
        except Exception as e:
            last_error = str(e)
            if "429" in str(e): # Quota limit
                time.sleep(5) # Wait a bit
                continue # Try next model
            if "404" in str(e): # Model not found
                continue # Try next model
            
            # If it's another error, keep trying next model just in case
            continue
            
    return f"Error: All models failed. Last error: {last_error}"

# --- PHASE 2: THE DIAGNOSTICIAN (Summary) ---
def generate_executive_summary(raw_data, api_key):
    # Limit data input to avoid Token Limit
    safe_data = raw_data[:15000]
    
    prompt = f"""
    Act as a Senior SEO Auditor.
    Analyze the raw crawl data below. Identify the Top 3 Critical Errors.
    
    OUTPUT FORMAT:
    1. A Headline: "### 📋 Executive Summary: Senior SEO Audit Findings"
    2. A brief 1-sentence strategic summary.
    3. A Markdown Table with columns: | # | Critical Error | Severity | Description |
    4. A "### ⚠️ Summary Action Required" paragraph.
    
    RAW DATA:
    {safe_data}
    """
    return call_gemini(prompt, api_key)

# --- PHASE 3: THE SURGEON (Detailed CSV) ---
def generate_detailed_fixes(raw_data, api_key):
    # Limit data input to avoid Token Limit
    safe_data = raw_data[:15000]
    
    prompt = f"""
    Act as an Expert Technical SEO Auditor.
    Analyze the raw data below for specific actionable errors.
    
    LOOK FOR & REPORT:
    - Technical: Fragment URLs (#content), Trailing Slash duplicates.
    - Metadata: Generic Titles ("Home"), Missing Descriptions.
    - Content: Weak H1s.
    
    OUTPUT FORMAT:
    - Provide ONLY valid CSV rows. NO HEADERS.
    - Columns: URL, Error_Type, Current_Value, Recommended_Fix, Priority
    - Quote every field to handle commas.
    
    RAW DATA:
    {safe_data}
    """
    result = call_gemini(prompt, api_key)
    # Clean up any markdown code blocks
    return result.replace("```csv", "").replace("```", "").strip()

# --- MAIN APP LOGIC ---
if api_key:
    url_input = st.text_input("Website URL", placeholder="https://example.com")
    
    if st.button("🚀 Start Professional Audit"):
        if not url_input.startswith("http"):
            st.warning("Please include https://")
        else:
            # 1. CRAWL
            crawled_data = stealth_crawler(url_input, max_pages)
            
            if crawled_data:
                st.success("✅ Site Crawled Successfully!")
                
                # 2. EXECUTIVE SUMMARY
                with st.status("🩺 Diagnosing Site Health (Gemini 2.5)...") as status:
                    summary_report = generate_executive_summary(crawled_data, api_key)
                    
                    if "Error:" in summary_report:
                        status.update(label="AI Failed", state="error")
                        st.error(summary_report)
                        st.stop()
                    else:
                        status.update(label="Diagnosis Complete!", state="complete")
                
                # Show Summary
                st.markdown(summary_report)
                st.divider()
                
                # 3. DETAILED FIXES
                with st.spinner("🔪 Generating Detailed Fixes (The Surgeon)..."):
                    csv_data = generate_detailed_fixes(crawled_data, api_key)
                
                # Show Table & Download
                if "Error:" in csv_data:
                    st.error(csv_data)
                else:
                    try:
                        st.markdown("### 🛠️ Detailed Remediation Plan")
                        headers = ['URL', 'Error_Type', 'Current_Value', 'Recommended_Fix', 'Priority']
                        df = pd.read_csv(io.StringIO(csv_data), names=headers, header=None)
                        st.dataframe(df, use_container_width=True)
                        
                        csv_file = df.to_csv(index=False).encode('utf-8')
                        st.download_button(
                            label="💾 Download Full Report (CSV)",
                            data=csv_file,
                            file_name="seo_audit_report.csv",
                            mime="text/csv"
                        )
                    except Exception:
                        st.error("Could not parse CSV. Here is the raw output:")
                        st.text(csv_data)
            else:
                st.error("Crawler found no data. The site might be blocking bots.")
else:
    st.warning("👈 Please enter your API Key to start.")
