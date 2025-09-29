from bs4 import BeautifulSoup
import re

def clean_html(raw_html):
    """Remove HTML tags, scripts, styles, and extra whitespace."""
    soup = BeautifulSoup(raw_html, "html.parser")
    for script in soup(["script", "style"]):
        script.decompose()
    text = soup.get_text(separator=" ")
    text = re.sub(r'\s+', ' ', text)
    return text.strip()
