from openai import OpenAI
import pytesseract
import json
from dotenv import load_dotenv
import os

load_dotenv() 

drawing = os.environ["Drawing"]

pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

client = OpenAI(api_key=os.environ["takeoff_api"]) 


with open(f'../data/{drawing}/table_id.json', 'r') as file:
    data = json.load(file)

results_filtered = []

instruction = (
    "Identify which images contain a full table. "
    "Exclude images that not tables or full drawings. "
    "Respond ONLY in the following JSON format:\n\n"
    "{\n"
    "  \"full_tables\": [\n"
    "    {\n"
    "      \"image_number\": 0,\n"
    "      \"label\": \"Image 0\"\n"
    "    }\n"
    "  ]\n"
    "}\n"
    "Do not include any extra text outside this JSON."
)

for page_entry in data:  # results from your extraction script
    input_objects = []

    # Main instruction
    input_objects = [{"type": "input_text", "text": instruction}]

    # Add each table image with label
    for i, table in enumerate(page_entry["tables"]):
        input_objects.append({"type": "input_text", "text": f"Image {i}"})
        input_objects.append({"type": "input_image", "file_id": table["file_id"]})

    # Call GPT
    response = client.responses.create(
        model="gpt-5.4-mini",
        input=[{"role": "user", "content": input_objects}],
        temperature=0
    )

    # GPT returns e.g. "Image 0, Image 2"
    output_text = response.output_text
    # print(f"Page {page_entry['page']} GPT response:", output_text)

    # Extract image numbers from GPT response
    try:
        gpt_json = json.loads(output_text)
        selected_indices = [t["image_number"] for t in gpt_json.get("full_tables", [])]
    except json.JSONDecodeError:
        print(f"Failed to parse GPT JSON on page {page_entry['page']}")
        selected_indices = []

    # Save filtered file_ids + coordinates
    filtered_tables = [
        page_entry["tables"][i] for i in selected_indices
    ]

    if filtered_tables:  # only save pages with at least one full table
        results_filtered.append({
            "title": page_entry["title"],
            "page": page_entry["page"],
            "tables": filtered_tables
        })


with open(f'../data/{drawing}/full_tables.json', 'w', encoding='utf-8') as f:
    json.dump(results_filtered, f, indent=4)

print("Done. Saved filtered full tables.")