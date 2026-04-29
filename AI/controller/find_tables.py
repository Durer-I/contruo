from openai import OpenAI
from io import BytesIO
import pdfplumber
import pytesseract
from pprint import pprint
import json
from dotenv import load_dotenv
import os

load_dotenv() 
drawing = os.environ["Drawing"]

client = OpenAI(api_key=os.environ["takeoff_api"]) 

pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

with open(f'../data/{drawing}/schedules.json', 'r') as file:
    data = json.load(file)


pdf_path = f"../data/{drawing}/{drawing}.pdf"
padding = 40 

results = []


with pdfplumber.open(pdf_path) as pdf:

    for item in data:
        page_number = item["page"] - 1
        title = item["title"]

        print(f"Processing page {item['page']} - {title}")

        tables_data = []

        # safety check
        if page_number < 0 or page_number >= len(pdf.pages):
            print(f"Skipping invalid page: {item['page']}")
            continue

        page = pdf.pages[page_number]
        tables = page.find_tables({
            'vertical_strategy': "lines_strict",
            'horizontal_strategy': 'lines_strict',

        })

        page_image = page.to_image(resolution=200)

        for i, table in enumerate(tables):
            x0, top, x1, bottom = table.bbox

            padded_bbox = (
                max(0, x0 - padding),
                max(0, top - padding),
                min(page.width, x1 + padding),
                min(page.height, bottom + padding)
            )

            page_image.draw_rect(padded_bbox, stroke="red", stroke_width=2)

            cropped = page.crop(padded_bbox)
            im = cropped.to_image(resolution=200)

            # ✅ Save to memory instead of disk
            buffer = BytesIO()
            im.original.save(buffer, format="PNG")
            buffer.seek(0)

            # ✅ Upload directly
            upload = client.files.create(
                file=(f"table_{i}.png", buffer, "image/png"),
                purpose="vision"
            )

            tables_data.append({
                "file_id": upload.id,
                "bbox": {
                "x0": x0,
                "top": top,
                "x1": x1,
                "bottom": bottom
            }
            })

        debug_path = f"../images/{drawing}/page_{item['page']}_boxes.png"
        page_image.save(debug_path)

        # ✅ Store results per page
        results.append({
            "title": title,
            "page": item["page"],
            "tables": tables_data
        })

# ✅ Save final JSON
with open(f'../data/{drawing}/table_id.json', 'w', encoding='utf-8') as f:
    json.dump(results, f, indent=4)

print("Done. Saved file IDs.")