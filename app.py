import os
import re
import time
import requests
import zipfile
import pandas as pd
import streamlit as st
import io
from firecrawl import FirecrawlApp

# Set up Streamlit UI
st.set_page_config(page_title="Stock Transcript Downloader", layout="wide")
st.title("📊 Stock Transcript Downloader")
st.subheader("Download earnings call transcripts for Indian stocks")

# Initialize FireCrawl API
api_key = 'fc-cc6afedddf66452ea64cacd5cc7dcadc'
app = FirecrawlApp(api_key=api_key)

# User input for stock symbol
stock_symbol = st.text_input("Enter stock symbol (e.g., HDFCBANK, INFY, RELIANCE):", "").strip().upper()

if st.button("🔍 Search"):
    if not stock_symbol:
        st.warning("⚠️ Please enter a valid stock symbol.")
    else:
        st.info(f"🔍 Searching for transcript PDFs for {stock_symbol}...")
        
        try:
            scrape_result = app.scrape_url(
                url=f'https://www.screener.in/company/{stock_symbol}/consolidated/#documents',
                params={'formats': ['markdown']}
            )
            markdown_content = scrape_result.get('markdown', "") if isinstance(scrape_result, dict) else ""

            def extract_transcript_links(markdown):
                links, dates, titles = [], [], []
                lines = markdown.split('\n')
                in_concalls_section = False
                
                for line in lines:
                    if '### Concalls' in line:
                        in_concalls_section = True
                        continue
                    elif line.startswith('###') and in_concalls_section:
                        in_concalls_section = False
                        continue
                    
                    if in_concalls_section and 'Transcript' in line:
                        pdf_pattern = r'https?://[^\s)]+\.pdf'
                        matches = re.findall(pdf_pattern, line, re.IGNORECASE)
                        
                        if matches:
                            for match in matches:
                                links.append(match)
                                date_match = re.search(r'\b\d{1,2}[-/]\d{1,2}[-/]\d{2,4}\b|\b[A-Z][a-z]{2,8}\.\s+\d{1,2},?\s+\d{4}\b', line)
                                dates.append(date_match.group(0) if date_match else "Unknown Date")
                                title_match = re.search(r'(?:Transcript|Call).*?(Q\d|Quarter \d)', line)
                                titles.append(title_match.group(0) if title_match else f"Earnings Call {len(links)}")
                
                return list(zip(links, titles, dates))
            
            transcript_data = extract_transcript_links(markdown_content)
            
            if not transcript_data:
                st.warning(f"⚠️ No transcript PDFs found for {stock_symbol}")
            else:
                df = pd.DataFrame(transcript_data, columns=['URL', 'Title', 'Date'])
                st.success(f"✅ Found {len(df)} transcript PDFs for {stock_symbol}")
                st.dataframe(df[['Title', 'Date', 'URL']])
                
                if st.button("📥 Download All PDFs"):
                    zip_buffer = io.BytesIO()
                    
                    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zipf:
                        for i, (url, title, date) in enumerate(transcript_data):
                            headers = {"User-Agent": "Mozilla/5.0", "Referer": "https://nseindia.com/"}
                            
                            try:
                                st.write(f"🛠️ Downloading: {url}")  # Debug output
                                response = requests.get(url, headers=headers, stream=True, timeout=15)
                                st.write(f"ℹ️ Response Code: {response.status_code}")  # Debug response code
                                if response.status_code == 200:
                                    pdf_filename = f"transcript_{i+1}.pdf"
                                    zipf.writestr(pdf_filename, response.content)
                                else:
                                    st.warning(f"⚠️ Failed to download: {url}")
                            except Exception as e:
                                st.warning(f"⚠️ Error downloading {url}: {str(e)}")
                    
                    zip_buffer.seek(0)
                    st.download_button(label="📦 Download ZIP File", data=zip_buffer, file_name=f"{stock_symbol.lower()}_transcripts.zip", mime="application/zip")
        except Exception as e:
            st.error(f"❌ Error: {str(e)}")
