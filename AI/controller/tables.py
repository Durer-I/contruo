import pandas as pd
import json
import pdfplumber
from dotenv import load_dotenv
import os
import xlsxwriter

load_dotenv() 
drawing = os.environ["Drawing"]

with open(f'../data/{drawing}/full_tables.json', 'r') as file:
    data = json.load(file)

pdf_path = f'../data/{drawing}/{drawing}.pdf'

# Create Excel writer
output_path = f'../data/{drawing}/tables.xlsx'
writer = pd.ExcelWriter(output_path, engine='xlsxwriter')

sheet_count = 0

with pdfplumber.open(pdf_path) as pdf:
    for info in data:
        title = info['title']
        page_number = info['page']

        print(title)

        for i, table in enumerate(info['tables']):
            coordinates = table['bbox']

            page = pdf.pages[page_number - 1]  # ✅ fix indexing
            padding = 40

            x0, top, x1, bottom = coordinates["x0"], coordinates["top"], coordinates["x1"], coordinates["bottom"]

            padded_bbox = (
                max(0, x0 - padding),
                max(0, top - padding),
                min(page.width, x1 + padding),
                min(page.height, bottom + padding)
            )

            cropped = page.crop(padded_bbox)
            table_data = cropped.extract_table()

            if not table_data:
                continue

            df = pd.DataFrame(table_data)

            # Clean a bit
            df = df.dropna(how="all").fillna("")

            # Excel sheet name (max 31 chars)
            safe_title = title[:20].replace(" ", "_")
            sheet_name = f"{safe_title}_{i}"

            df.to_excel(writer, sheet_name=sheet_name, index=False)

            sheet_count += 1

# Save file
writer.close()

print(f"Saved {sheet_count} tables to {output_path}")