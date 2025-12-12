import streamlit as st
import time
import random
import requests
import pandas as pd
import io
from urllib.parse import urljoin, urlparse
import google.generativeai as genai
import urllib3

# Disable SSL warnings
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# --- PAGE CONFIG ---
st.set_page_config(page_title="SEO Agent DEBUGGER", page_icon="🛠️", layout="wide")
st.title("🛠️ SEO Agent: Debug Mode")
st.markdown("Use this mode to diagnose why connections are failing.")

# --- SIDEBAR ---
with st.sidebar:
    api_key = st.text_input("Enter Gemini API Key", type="password")
    
    # --- 1. KEY TESTER ---
    if st.button("🔑 Test API Key Connectivity"):
        if not api_key:
            st.error("Enter a key first.")
        else:
            try:
                genai.configure(api_key=api_key)
                # Try to list models to check connection
                models = list(genai.list_models())
                model_names = [m.name for m in models]
                st.success(f"✅ CONNECTION SUCCESS! Found {len(model_names)} models.")
                st.json(model_names) # Show the valid models
            except Exception as e:
                st.error(f"❌ CONNECTION FAILED: {str(e)}")
                st.markdown("**Common Causes:**\n1. Copied extra space in key.\n2. Key expired.\n3. API not enabled in Google Cloud Console.")

# --- CRAWLER ---
@st.cache_data(show_spinner=False)
def quick_crawl(url):
    try:
        response = requests.get(url, timeout=5, verify=False, headers={'User-Agent': 'Mozilla/5.0'})
        if response.status_code == 200:
            return response.text[:5000] # Return first 5000 chars
        return None
    except Exception as e:
        return None

# --- ANALYZER WITH DETAILED LOGS ---
def debug_analyze(raw_data, api_key):
    genai.configure(api_key=api_key)
    
    # Models to test
    models_to_test = ['gemini-2.0-flash', 'gemini-1.5-flash', 'gemini-pro']
    
    st.write("--- 🔍 STARTING MODEL DIAGNOSTIC ---")
    
    for model_name in models_to_test:
        st.write(f"👉 Trying model: **{model_name}**...")
        try:
            model = genai.GenerativeModel(model_name)
            # Simple test prompt
            response = model.generate_content(f"Analyze this SEO data: {raw_data[:500]}")
            
            st.success(f"✅ SUCCESS with {model_name}!")
            return response.text
            
        except Exception as e:
            # PRINT THE EXACT ERROR
            st.error(f"❌ FAILED {model_name}. Reason:")
            st.code(str(e)) # Show the raw error message
            
    return None

# --- MAIN UI ---
url = st.text_input("Website URL", "https://example.com")

if st.button("🚀 Run Debug Audit"):
    if not api_key:
        st.warning("Please enter API Key in sidebar.")
    else:
        # 1. Crawl
        with st.status("Crawling website...") as status:
            raw_text = quick_crawl(url)
            if raw_text:
                status.update(label="Crawling done!", state="complete")
                
                # 2. Analyze
                st.subheader("📝 Model Logs")
                result = debug_analyze(raw_text, api_key)
                
                if result:
                    st.success("Analysis Complete!")
                    st.write(result)
                else:
                    st.error("💀 All models failed. Read the red error boxes above.")
            else:
                st.error("Crawler failed. Check URL.")
