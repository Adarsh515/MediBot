import re
from pypdf import PdfReader

def parse_document(file_path):
    """
    Parse a PDF and return a list of (label, text) tuples.
    label is one of: HEADING, TEXT, TABLE, LIST, NOISE
    """
    from pathlib import Path
    
    results = []
    
    # Handle markdown files differently
    if Path(file_path).suffix.lower() in ('.md', '.markdown'):
        return parse_markdown(file_path)
    
    reader = PdfReader(file_path)
    
    for page_num, page in enumerate(reader.pages):
        raw = page.extract_text() or ""
        lines = raw.splitlines()
        
        for i, line in enumerate(lines):
            stripped = line.strip()
            if not stripped:
                continue
            
            block_type = is_likely_table_block(lines, i)
            
            if is_noise(stripped):
                label = "NOISE"
            elif is_heading(stripped):
                label = "HEADING"
            elif block_type == 'table':
                label = "TABLE"
            elif block_type == 'list':
                label = "LIST"
            else:
                label = "TEXT"
            
            results.append((label, stripped))
    
    return results

def is_noise(line):
    """Skip page headers, footers, and confidentiality notices."""
    noise_patterns = [
        r'^MediAssist Health Network',
        r'^Page \d+ of \d+',
        r'^CONFIDENTIAL',
        r'^Document ref:',
        r'^Access:',
    ]
    for pattern in noise_patterns:
        if re.match(pattern, line.strip()):
            return True
    return False


def is_heading(line):
    line = line.strip()
    
    if not line:
        return False
    
    # Too long to be a heading
    if len(line) > 100:
        return False
    
    # Contains a drug dose — it's a table cell, not a heading
    if re.search(r'\d+\s*(mg|mcg|ml|g|units?|IU)\b', line, re.IGNORECASE):
        return False
    
    # Drug administration routes — table cell
    if re.match(r'^(IV|IM|SC|PO)\s+', line):
        return False

    # NEW: Table column headers — these exact words appear as column labels
    table_column_headers = {
        'drug & dose', 'drug', 'dose', 'caution', 'cautions',
        'notes', 'line', 'setting', 'regimen', 'duration',
        'first-line', 'second-line', 'third-line', 'add-on',
        'outpatient', 'inpatient'
    }
    if line.lower() in table_column_headers:
        return False

    # NEW: Clinical instruction phrases — appear in table cells
    clinical_phrases = [
        r'^Check\s+', r'^Monitor\s+', r'^Consider\s+',
        r'^Avoid\s+', r'^Switch\s+', r'^Calculate\s+'
    ]
    for phrase in clinical_phrases:
        if re.match(phrase, line, re.IGNORECASE):
            return False

    # Numbered sections: "1.", "A.", "SOP 1", "1.1"
    if re.match(r'^(SOP\s+\d|Section\s+\d|\d+\.\s|[A-Z]\.\s)', line):
        return True
    
    # ALL CAPS short line
    if line.isupper() and 3 < len(line) < 60:
        return True
    
    # Title-cased short line
    words = line.split()
    if 2 <= len(words) <= 8:
        if not line.endswith((',', ';', 'or', 'and')):
            capitalized = sum(1 for w in words if w[0].isupper())
            if capitalized / len(words) >= 0.5:
                return True
    
    return False


def is_table_row(line):
    """Detect table rows by multiple spaces between values."""
    # Has 3+ consecutive spaces (column separator in extracted PDF tables)
    if re.search(r'   +', line) and len(line.split()) >= 3:
        return True
    return False

def is_likely_table_block(lines, index):
    """
    Returns 'table' or 'list' or None.
    - 'table': short lines where some look like column headers (Drug, Dose, Line)
    - 'list' : short lines that are sentences ending with punctuation
    """
    window = lines[max(0, index-2) : index+3]
    short_lines = [l.strip() for l in window if 0 < len(l.strip()) < 80]
    
    if len(short_lines) < 3:
        return None

    # If lines end with punctuation (., ,) they're likely a bullet list
    ends_with_punct = sum(1 for l in short_lines if l.endswith(('.', ',', 'or')))
    if ends_with_punct >= 2:
        return 'list'
    
    return 'table'


def parse_markdown(file_path):
    """Parse a .md file and return (label, text) tuples."""
    import re
    results = []
    
    with open(file_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        
        # Markdown headings: # ## ###
        if re.match(r'^#{1,3}\s+', stripped):
            text = re.sub(r'^#+\s+', '', stripped)
            results.append(("HEADING", text))
        # Markdown table rows: | col | col |
        elif stripped.startswith('|'):
            results.append(("TABLE", stripped))
        # Markdown bullet points: - item or * item
        elif re.match(r'^[-*]\s+', stripped):
            text = re.sub(r'^[-*]\s+', '', stripped)
            results.append(("LIST", text))
        else:
            results.append(("TEXT", stripped))
    
    return results

if __name__ == "__main__":
    from pypdf import PdfReader
    
    reader = PdfReader("data/clinical/treatment_protocols.pdf")
    
    for page_num in range(1, 5):
        text = reader.pages[page_num].extract_text()
        lines = text.splitlines()
        
        for i, line in enumerate(lines):
            stripped = line.strip()
            if not stripped:
                continue
            
            block_type = is_likely_table_block(lines, i)

            if is_noise(stripped):
                label = "NOISE  "
            elif is_heading(stripped):
                label = "HEADING"
            elif block_type == 'table':
                label = "TABLE  "
            elif block_type == 'list':
                label = "LIST   "
            else:
                label = "TEXT   "
            
            print(f"[{label}] {stripped[:80]}")