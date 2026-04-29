import fitz  # PyMuPDF
import pandas as pd
from dotenv import load_dotenv
import os

load_dotenv() 

drawing = os.environ["Drawing"]

def search_and_highlight(file_path, search_text, output_file="output.pdf", highlight=False):
    doc = fitz.open(file_path)
    results = []
    total = 0

    for i, page in enumerate(doc, start=1):
        text = page.get_text()
        count = text.lower().count(search_text.lower())

        if count > 0:
            results.append((i, count))
            total += count

        if highlight == True:
            # Highlight matches
            matches = page.search_for(search_text)
            for rect in matches:
                page.draw_rect(
                    rect,
                    color=(1, 0, 0),   # red border
                    fill=(1, 1, 0),    # yellow fill
                    overlay=True
                )

            doc.save(output_file)
        

        else: pass
    doc.close()

    return results, total

# Example usage
file_path = f"data/{drawing}/{drawing}.pdf"
search_text = "N104E"

pages, total = search_and_highlight(file_path, search_text, output_file="output_high.pdf", highlight=True)

print("Occurrences by page:")
for page, count in pages:
    print(f"Page {page}: {count} matches")

print(f"\nTotal occurrences: {total}")