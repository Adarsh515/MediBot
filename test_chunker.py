from backend.ingestion.chunker import build_chunks
from pathlib import Path

data_root = Path("data")
total = 0

for collection in ["general", "clinical", "nursing", "billing", "equipment"]:
    folder = data_root / collection
    for file in sorted(folder.iterdir()):
        if file.suffix.lower() in (".pdf", ".md"):
            chunks = build_chunks(str(file))
            total += len(chunks)
            print(f"{file.name:45s} → {len(chunks):3d} chunks")

print(f"\nTotal chunks across all documents: {total}")