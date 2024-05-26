import requests
from bs4 import BeautifulSoup
import os
import json
from urllib.parse import urljoin, urlparse

def fetch_page(url):
    response = requests.get(url)
    if response.status_code == 200:
        return response.text
    else:
        print(f'Failed to retrieve {url}')
        return None

def parse_links(html_content, base_url, link_selector):
    soup = BeautifulSoup(html_content, 'html.parser')
    links = soup.select(link_selector)
    return [urljoin(base_url, link['href']) for link in links if link['href'].startswith('/')]

def extract_text_and_images_from_html(html_content, content_selector, base_url, image_folder, save_images):
    soup = BeautifulSoup(html_content, 'html.parser')
    main_content = soup.select_one(content_selector)

    if main_content is None:
        return None, None, None, None

    # Extract title
    title = main_content.find('h1').get_text(strip=True) if main_content.find('h1') else 'No Title'

    # Extract sections and combine consecutive paragraphs
    sections = []
    current_section = None
    current_subsection = None
    current_paragraphs = []

    def start_new_section(title, level):
        nonlocal current_section, current_subsection, current_paragraphs
        if current_paragraphs:
            combined_paragraph = '\n\n'.join(current_paragraphs)
            if current_subsection:
                current_subsection['content'].append({'text': combined_paragraph})
            elif current_section:
                current_section['content'].append({'text': combined_paragraph})
            current_paragraphs = []

        new_section = {'title': title, 'content': [], 'subsections': []}

        if level == 'h2':
            if current_section:
                sections.append(current_section)
            current_section = new_section
            current_subsection = None
        elif level == 'h3':
            if current_section:
                if current_subsection:
                    current_section['subsections'].append(current_subsection)
                current_subsection = new_section
        elif level == 'h4' and current_subsection:
            current_subsection['subsections'].append(new_section)

    for element in main_content.find_all(['h2', 'h3', 'h4', 'p', 'div']):
        if element.name in ['h2', 'h3', 'h4']:
            start_new_section(element.get_text(separator='\n', strip=True), element.name)
        elif element.name == 'p':
            if current_section is None:
                start_new_section('', 'h2')
            current_paragraphs.append(element.get_text(separator='\n', strip=True))
        elif element.name == 'div' and 'codeBlockContainer_Ckt0' in element.get('class', []):
            if current_paragraphs:
                combined_paragraph = '\n\n'.join(current_paragraphs)
                if current_subsection:
                    current_subsection['content'].append({'text': combined_paragraph})
                elif current_section:
                    current_section['content'].append({'text': combined_paragraph})
                current_paragraphs = []

            language_class = next((cls for cls in element['class'] if cls.startswith('language-')), None)
            if language_class:
                code_language = language_class.replace('language-', '')
                code_content = element.find('code').get_text(separator='\n', strip=True)
                code_block = {'code': {'language': code_language, 'script': code_content}}
                if current_subsection:
                    current_subsection['content'].append(code_block)
                elif current_section:
                    current_section['content'].append(code_block)

    if current_paragraphs:
        combined_paragraph = '\n\n'.join(current_paragraphs)
        if current_subsection:
            current_subsection['content'].append({'text': combined_paragraph})
        elif current_section:
            current_section['content'].append({'text': combined_paragraph})

    if current_subsection:
        current_section['subsections'].append(current_subsection)
    if current_section:
        sections.append(current_section)

    # Download and save images if enabled
    image_references = []
    if save_images:
        images = main_content.find_all('img')
        for img in images:
            if 'src' in img.attrs:
                image_url = urljoin(base_url, img['src'])
                image_path = save_image(image_url, image_folder)
                if image_path:
                    image_references.append({
                        'original_url': image_url,
                        'local_path': image_path,
                        'alt': img.get('alt', '')
                    })

    return title, sections, image_references

def save_image(url, image_folder):
    try:
        response = requests.get(url, stream=True)
        response.raise_for_status()
        parsed_url = urlparse(url)
        image_path = os.path.join(image_folder, os.path.basename(parsed_url.path))
        os.makedirs(os.path.dirname(image_path), exist_ok=True)
        with open(image_path, 'wb') as out_file:
            out_file.write(response.content)
        print(f'Saved image {url} to {image_path}')
        return image_path
    except requests.exceptions.RequestException as e:
        print(f'Failed to retrieve image {url}: {e}')
        return None

def scrape_website(base_url, start_url, link_selector, content_selector, output_folder, image_folder, save_images=True):
    os.makedirs(output_folder, exist_ok=True)
    if save_images:
        os.makedirs(image_folder, exist_ok=True)
    visited_urls = set()
    urls_to_visit = [start_url]

    all_data = []

    while urls_to_visit:
        current_url = urls_to_visit.pop()
        if current_url in visited_urls:
            continue

        visited_urls.add(current_url)
        page_content = fetch_page(current_url)
        if not page_content:
            continue

        # Extract relevant content, sections, and images from the page
        title, sections, image_references = extract_text_and_images_from_html(page_content, content_selector, base_url, image_folder, save_images)
        if title and sections is not None:
            content = save_content(current_url, title, sections, image_references, output_folder)
            all_data.append(content)
        print(f'Saved {current_url}')

        # Parse new links from the current page
        new_links = parse_links(page_content, base_url, link_selector)
        urls_to_visit.extend(new_links)

    combined_data = {
        'title': 'Combined Documentation',
        'url': base_url,
        'description': 'This JSON file contains the combined documentation extracted from multiple pages of the specified website.',
        'pages': all_data
    }

    with open(os.path.join(output_folder, 'combined_docs.json'), 'w', encoding='utf-8') as combined_file:
        json.dump(combined_data, combined_file, ensure_ascii=False, indent=4)

def save_content(url, title, sections, images, output_folder):
    content = {
        'url': url,
        'title': title,
        'sections': sections,
        'images': images
    }
    filename = url.replace(base_url, '').replace('/', '_') + '.json'
    filepath = os.path.join(output_folder, filename)
    with open(filepath, 'w', encoding='utf-8') as file:
        json.dump(content, file, ensure_ascii=False, indent=4)
    return content

if __name__ == '__main__':
    base_url = 'https://microsoft.github.io/autogen'
    start_url = f'{base_url}/docs/Getting-Started'
    link_selector = 'nav a[href^="/"]'  # Adjust this based on the site's structure
    content_selector = 'main'  # Adjust this based on the site's structure
    output_folder = 'autogen_docs'
    image_folder = 'autogen_images'
    output_json = 'autogen_docs.json'
    save_images = False  # Set to False if you do not want to save images

    scrape_website(base_url, start_url, link_selector, content_selector, output_folder, image_folder, save_images)
