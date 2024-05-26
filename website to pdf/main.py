import requests
from bs4 import BeautifulSoup
from weasyprint import HTML
import os

def fetch_page_content(url):
    response = requests.get(url)
    if response.status_code == 200:
        return response.text
    else:
        print(f'Failed to retrieve {url}')
        return None

def convert_to_pdf(html_content, output_file):
    try:
        HTML(string=html_content).write_pdf(output_file)
        print(f'Successfully saved to {output_file}')
    except Exception as e:
        print(f'Failed to convert to PDF: {e}')

def main():
    url = input("Enter the URL of the webpage to convert to PDF: ")
    output_file = input("Enter the output PDF file name (with .pdf extension): ")

    # Fetch and parse the webpage content
    page_content = fetch_page_content(url)

    if page_content:
        convert_to_pdf(page_content, output_file)

if __name__ == '__main__':
    main()
