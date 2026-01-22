
import zipfile
import re
import os
import sys

def extract_variables(pptx_path):
    variables = set()
    pattern = re.compile(r'\{\{([^}]+)\}\}')
    
    if not os.path.exists(pptx_path):
        print(f"File not found: {pptx_path}")
        return

    try:
        with zipfile.ZipFile(pptx_path, 'r') as z:
            # Slides are usually in ppt/slides/slideN.xml
            # Notes are usually in ppt/notesSlides/notesSlideN.xml
            # Masters, etc. might also have them, but let's start with slides.
            for name in z.namelist():
                if (name.startswith('ppt/slides/slide') or 
                    name.startswith('ppt/notesSlides/notesSlide') or 
                    name.startswith('ppt/slideMasters/slideMaster') or 
                    name.startswith('ppt/slideLayouts/slideLayout')) and name.endswith('.xml'):
                    with z.open(name) as f:
                        content = f.read().decode('utf-8')
                        # Remove all XML tags to join split text
                        text = re.sub(r'<[^>]+>', '', content)
                        matches = pattern.findall(text)
                        for m in matches:
                            variables.add(m.strip())
                            
    except Exception as e:
        print(f"Error processing {pptx_path}: {e}")

    return sorted(list(variables))

if __name__ == "__main__":
    pptx_file = "/Users/wmu/workspace/toastmasters/vpemaster/instance/SHLTMC_Meeting_<nnn>.pptx"
    varsFound = extract_variables(pptx_file)
    print("\n".join(varsFound))
