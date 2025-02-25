import os
import re
import time
import requests
import zipfile
import pandas as pd
import streamlit as st
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
                    pdf_folder = "downloaded_pdfs"
                    os.makedirs(pdf_folder, exist_ok=True)
                    zip_filename = f"{stock_symbol.lower()}_transcripts.zip"
                    zip_path = os.path.join(pdf_folder, zip_filename)
                    
                    downloaded_files = []
                    for i, (url, title, date) in enumerate(transcript_data):
                        pdf_filename = os.path.join(pdf_folder, f"transcript_{i+1}.pdf")
                        headers = {"User-Agent": "Mozilla/5.0", "Referer": "https://nseindia.com/"}
                        
                        try:
                            response = requests.get(url, headers=headers, stream=True, timeout=15)
                            if response.status_code == 200:
                                with open(pdf_filename, "wb") as f:
                                    f.write(response.content)
                                downloaded_files.append(pdf_filename)
                            else:
                                st.warning(f"⚠️ Failed to download: {url}")
                        except Exception as e:
                            st.warning(f"⚠️ Error downloading {url}: {str(e)}")
                    
                    if downloaded_files:
                        with zipfile.ZipFile(zip_path, "w") as zipf:
                            for file in downloaded_files:
                                zipf.write(file, os.path.basename(file))
                        
                        with open(zip_path, "rb") as file:
                            st.download_button(label="📦 Download ZIP File", data=file, file_name=zip_filename, mime="application/zip")
                    else:
                        st.error("❌ No PDFs were downloaded.")
        except Exception as e:
            st.error(f"❌ Error: {str(e)}")
