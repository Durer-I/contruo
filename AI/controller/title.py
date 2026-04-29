import fitz
import matplotlib.pyplot as plt
from matplotlib.widgets import RectangleSelector
import json
import pytesseract
import cv2
import numpy as np
import pytesseract
from dotenv import load_dotenv
import os

load_dotenv() 

drawing = os.environ["Drawing"]

pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"


def select_region_on_page(page):
    pix = page.get_pixmap()
    img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, -1)

    fig, ax = plt.subplots()
    ax.imshow(img)
    ax.set_title("Drag to select region, then press ENTER to confirm")

    selected = {"rect": None}

    def onselect(eclick, erelease):
        x0, y0 = int(eclick.xdata), int(eclick.ydata)
        x1, y1 = int(erelease.xdata), int(erelease.ydata)
        selected["rect"] = fitz.Rect(x0, y0, x1, y1)
        print(f"Selected: {selected['rect']}")

    def on_key(event):
        if event.key == "enter":
            plt.close(fig)

    rect_selector = RectangleSelector(
        ax,
        onselect,
        useblit=True,
        button=[1],  # left mouse
        interactive=True
    )

    fig.canvas.mpl_connect("key_press_event", on_key)

    plt.show()

    return selected["rect"]

# ---------------------------
# 🧠 Extract text inside rect (word-based)
# ---------------------------

def extract_text_from_rect(page, rect):
    # 1. Try normal PDF text extraction
    text = page.get_text("text", clip=rect)

    if text and text.strip():
        return text.strip()

    # 2. OCR fallback
    # print("⚠️ Using OCR fallback for this region:", rect)

    # Render page as image (high DPI = better OCR)
    mat = fitz.Matrix(2, 2)  # scale = 2x
    pix = page.get_pixmap(matrix=mat)

    img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, -1)

    # 🔥 IMPORTANT: scale rect to match image
    scale_x = pix.width / page.rect.width
    scale_y = pix.height / page.rect.height

    x0 = int(rect.x0 * scale_x)
    y0 = int(rect.y0 * scale_y)
    x1 = int(rect.x1 * scale_x)
    y1 = int(rect.y1 * scale_y)

    cropped = img[y0:y1, x0:x1]

    # Preprocess for OCR
    gray = cv2.cvtColor(cropped, cv2.COLOR_BGR2GRAY)
    _, thresh = cv2.threshold(gray, 150, 255, cv2.THRESH_BINARY)

    # OCR
    custom_config = r'--oem 3 --psm 6'
    ocr_text = pytesseract.image_to_string(thresh, config=custom_config)

    return ocr_text.strip()

# ---------------------------
# 🧹 Clean title
# ---------------------------
def clean_title(text):
    lines = [l.strip() for l in text.split("\n") if l.strip()]
    return " ".join(lines)


# ---------------------------
# 📄 Main function
# ---------------------------
def extract_titles_from_pdf(file_path, output_json="data/titles.json"):
    doc = fitz.open(file_path)

    # Step 1: select region (you control accuracy here)
    rect = select_region_on_page(doc[14])

    if rect is None:
        raise ValueError("You must select a region and press ENTER")

    results = []

    # Step 2: apply to all pages
    for i, page in enumerate(doc):
        raw_text = extract_text_from_rect(page, rect)

        title = clean_title(raw_text) if raw_text else f"Page_{i+1}"

        results.append({
            "page": i + 1,
            "title": title
        })

    doc.close()

    # Step 3: save JSON
    with open(output_json, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=4, ensure_ascii=False)

    return results


# ---------------------------
# 🚀 Run
# ---------------------------
file_path = f"../data/{drawing}/{drawing}.pdf"
output_json=f"../data/{drawing}/titles.json"

titles = extract_titles_from_pdf(file_path,output_json)
