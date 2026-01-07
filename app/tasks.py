
import os
import re
import requests
from flask import current_app

def cache_external_assets():
    """
    Downloads external CSS and font files to a local cache directory
    and rewrites the CSS to point to the local fonts.
    """
    print("Starting external assets cache update...")
    
    # Define assets to cache
    # Format: (name, css_url)
    assets_to_cache = [
        ('fonts', 'https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&family=Montserrat:wght@500;600&display=swap'),
        ('indie-flower', 'https://fonts.googleapis.com/css2?family=Indie+Flower&display=swap'),
        ('quicksand', 'https://fonts.googleapis.com/css2?family=Quicksand:wght@400;500;700&display=swap'),
        ('great-vibes', 'https://fonts.googleapis.com/css2?family=Great+Vibes&display=swap')
    ]

    base_cache_dir = os.path.join(current_app.root_path, 'static', 'cache')
    css_cache_dir = os.path.join(base_cache_dir, 'css')
    fonts_cache_dir = os.path.join(base_cache_dir, 'fonts')

    os.makedirs(css_cache_dir, exist_ok=True)
    os.makedirs(fonts_cache_dir, exist_ok=True)

    for name, url in assets_to_cache:
        try:
            print(f"Processing {name} from {url}...")
            # 1. Download CSS
            headers = {
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.114 Safari/537.36'
            }
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            css_content = response.text

            # 2. Find and download fonts
            # Pattern to find url(...)
            # Google fonts usually return url(https://...) format('truetype') or woff2
            # We will capture the URL
            font_urls = re.findall(r'src:\s*url\((https?://[^)]+)\)', css_content)
            
            for font_url in font_urls:
                font_filename = font_url.split('/')[-1]
                # If filename doesn't have extension, try to guess or just keep it unique
                # Google fonts URLs are usually clean, e.g. .../v20/UcCO....ttf or woff2
                
                local_font_path = os.path.join(fonts_cache_dir, font_filename)
                
                # Check if we already have it to avoid redownloading unnecessarily every time?
                # For now, let's overwrite to ensure freshness/integrity or if URL changes.
                # Actually, if URL changes, filename might be different. 
                
                print(f"  Downloading font: {font_filename}")
                font_response = requests.get(font_url, stream=True)
                font_response.raise_for_status()
                
                with open(local_font_path, 'wb') as f:
                    for chunk in font_response.iter_content(chunk_size=8192):
                        f.write(chunk)
                
                # 3. Rewrite CSS to point to local file
                # The CSS will live in static/cache/css/name.css
                # The fonts live in static/cache/fonts/filename
                # So relative path is ../fonts/filename
                
                css_content = css_content.replace(font_url, f"../fonts/{font_filename}")

            # 4. Save modified CSS
            local_css_path = os.path.join(css_cache_dir, f"{name}.css")
            with open(local_css_path, 'w') as f:
                f.write(css_content)
            
            print(f"  Successfully cached {name}")

        except Exception as e:
            print(f"Error caching {name}: {e}")

    print("External assets cache update finished.")
