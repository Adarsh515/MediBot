from pypdf import PdfReader

reader = PdfReader("data/clinical/treatment_protocols.pdf")

for page_num in range(1, 4):  # pages 2, 3, 4
    print(f"\n{'='*50}")
    print(f"PAGE {page_num + 1}")
    print('='*50)
    
    text = reader.pages[page_num].extract_text()
    lines = text.splitlines()
    
    for i, line in enumerate(lines):
        print(f"  {i:3d} | {repr(line)}")