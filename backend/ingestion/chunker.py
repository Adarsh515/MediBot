from backend.ingestion.pdf_parser import parse_document

MAX_WORDS = 300  # max words per chunk before we split

def build_chunks(file_path):
    """
    Takes a file path, parses it, and returns a list of chunk dicts.
    Each chunk has:
      - text:          the full chunk string (prefix + content)
      - section_title: the heading this chunk belongs to
      - chunk_type:    'text', 'table', or 'list'
      - source_file:   filename
    """
    lines = parse_document(file_path)  # returns list of (label, text) tuples
    
    chunks = []
    
    main_heading = ""
    sub_heading = ""
    
    current_type = None   # 'text', 'table', 'list'
    current_lines = []    # lines being collected for current chunk
    
    def save_chunk():
        if not current_lines:
            return
        
        if sub_heading and sub_heading != main_heading:
            section = f"{main_heading} > {sub_heading}"
        else:
            section = main_heading
        
        prefix = f"[Section: {section}]\n"
        content = "\n".join(line for line in current_lines if line.strip())
        
        if not content.strip():
            return
        
        # NEW: Skip chunks that are too short to be useful
        # Count words in content only (not the prefix)
        content_words = len(content.split())
        if content_words < 5:
            return
        
        chunks.append({
            "text": prefix + content,
            "section_title": section,
            "chunk_type": current_type or "text",
            "source_file": file_path,
        })
    
    for label, line_text in lines:
        line_text = line_text.strip()
        
        # Always skip noise
        if label == "NOISE":
            continue
        
        if label == "HEADING":
            import re
            is_main = bool(re.match(
                r'^([A-Z]\.\s|SOP\s+\d|Section\s+\d|\d+\.\s)', line_text
            ))
            
            if is_main:
                save_chunk()
                current_lines = []
                current_type = None
                main_heading = line_text
                sub_heading = ""
            else:
                # NEW: Only treat as sub-heading if we already have a main heading
                # This skips cover page items like "Clinical Governance Committee"
                if main_heading:
                    save_chunk()
                    current_lines = []
                    current_type = None
                    sub_heading = line_text
                # If no main heading yet, just skip it entirely
            
            continue
        
        # For TEXT, TABLE, LIST lines:
        # If the type changes, save current chunk and start fresh
        if label != current_type and current_lines:
            save_chunk()
            current_lines = []
        
        current_type = label
        
        # Check if current chunk is getting too long — split if needed
        current_words = sum(len(l.split()) for l in current_lines)
        new_words = len(line_text.split())
        
        if current_words + new_words > MAX_WORDS and current_lines:
            save_chunk()
            current_lines = []
            # Keep current_type the same — we're continuing same type
        
        current_lines.append(line_text)
    
    # Don't forget the last chunk
    save_chunk()
    
    return chunks