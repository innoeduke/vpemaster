import json
import os
from flask import session, request, has_request_context

# Cache dictionary to store loaded translations in memory
# Structure: { locale: { english_key: translated_value } }
_translation_cache = {}

def get_locale():
    """
    Detect the user's preferred locale.
    Checks:
    1. Session setting
    2. Accept Languages header in HTTP request
    3. Default fallback ('en')
    """
    if has_request_context():
        # 1. Check session
        locale = session.get('locale')
        if locale:
            return locale
        
        # 2. Check Accept Languages header
        best = request.accept_languages.best_match(['en', 'zh_CN'])
        if best:
            return best
            
    return 'en'

_translation_mtimes = {}

def load_translations(locale):
    """
    Load the translations JSON file for the given locale.
    Caches the results in memory and reloads if the file has been modified.
    """
    global _translation_cache, _translation_mtimes
    
    # Define path to translation file: app/translations/{locale}.json
    base_dir = os.path.dirname(os.path.abspath(__file__))
    translation_file = os.path.join(base_dir, f'{locale}.json')
    
    mtime = 0
    if os.path.exists(translation_file):
        try:
            mtime = os.path.getmtime(translation_file)
        except Exception:
            pass
            
    if locale in _translation_cache and _translation_mtimes.get(locale) == mtime:
        return _translation_cache[locale]

    _translation_cache[locale] = {}
    _translation_mtimes[locale] = mtime

    if os.path.exists(translation_file):
        try:
            with open(translation_file, 'r', encoding='utf-8') as f:
                _translation_cache[locale] = json.load(f)
        except Exception as e:
            # Squelch error and fall back to empty translations (English fallback)
            print(f"Error loading translation file for {locale}: {e}")
            
    return _translation_cache[locale]


def translate(text, **kwargs):
    """
    Translate the given text to the current active locale.
    If the translation is missing, returns the original English text.
    Supports key-value formatting if kwargs are provided.
    """
    if not text:
        return ""
        
    locale = get_locale()
    if locale == 'en':
        translated = text
    else:
        translations = load_translations(locale)
        translated = translations.get(text) or text
        
    if kwargs:
        try:
            return translated % kwargs
        except Exception:
            try:
                return translated.format(**kwargs)
            except Exception:
                return translated
                
    return translated

# Alias for standard internationalization syntax
_ = translate
