import pdfplumber
from openai import OpenAI
from collections import defaultdict, Counter
import json
from dotenv import load_dotenv
import os

load_dotenv() 
drawing = os.environ["Drawing"]

client = OpenAI(api_key=os.environ["takeoff_api"]) 


def has_text_inside(rect, words, tol=0):
    for w in words:
        # quick reject first
        if w["x1"] < rect["x0"] - tol or w["x0"] > rect["x1"] + tol:
            continue

        if (
            w["x0"] >= rect["x0"] - tol and
            w["x1"] <= rect["x1"] + tol and
            w["top"] >= rect["top"] - tol and
            w["bottom"] <= rect["bottom"] + tol
        ):
            return True
    return False


def get_adjacent_text(rect, words, x_tol=10, y_tol=3, max_gap=200):
    matched_words = []

    for w in words:
        if w["bottom"] < rect["top"] - y_tol or w["top"] > rect["bottom"] + y_tol:
            continue

        if rect["x1"] - x_tol <= w["x0"] <= rect["x1"] + max_gap:
            matched_words.append(w)

    return sorted(matched_words, key=lambda w: w["x0"])


def merge_rects(rects):
    return {
        "x0": min(r["x0"] for r in rects),
        "x1": max(r["x1"] for r in rects),
        "top": min(r["top"] for r in rects),
        "bottom": max(r["bottom"] for r in rects),
    }


def find_rectangles_text(pdf_path, page_number, output_dir=f"../data/{drawing}/legends", tolerance=2):
    os.makedirs(output_dir, exist_ok=True)

    with pdfplumber.open(pdf_path) as pdf:
        if not (0 <= page_number < len(pdf.pages)):
            print("Invalid page number")
            return
        
        page = pdf.pages[page_number]
        words = page.extract_words()
        rectangles = page.rects
        min_size = 16

        print(f"--- Page {page_number + 1} ---")

        # 🔹 Precompute rounded values
        for r in rectangles:
            r["rx0"] = round(r["x0"] / tolerance) * tolerance
            r["rx1"] = round(r["x1"] / tolerance) * tolerance
            r["rwidth"] = round(r["width"] / tolerance) * tolerance
            r["rheight"] = round(r["height"] / tolerance) * tolerance

        # 🔹 Group
        groups = defaultdict(list)
        for r in rectangles:
            groups[(r["rx0"], r["rx1"])].append(r)

        label_map = defaultdict(list)

        for rects in groups.values():
            if len(rects) <= 1:
                continue

            size_count = Counter((r["rwidth"], r["rheight"]) for r in rects)
            most_common_size = size_count.most_common(1)[0][0]

            for r in rects:
                if (
                    (r["rwidth"], r["rheight"]) != most_common_size or
                    r["width"] < min_size or
                    r["height"] < min_size or
                    has_text_inside(r, words)
                ):
                    continue

                adjacent_words = get_adjacent_text(r, words)
                if not adjacent_words:
                    continue

                text = " ".join(w["text"] for w in adjacent_words).strip()
                if text:
                    label_map[text].append(r)

        merged_results = {
            text: merge_rects(rects)
            for text, rects in label_map.items()
        }

        im = page.to_image(resolution=150)
        # im.draw_rects(list(merged_results.values()))
        im.draw_rects(list(rects))
        im.save(f"{output_dir}/final.png")

        print(f"\nTotal rectangles: {len(rectangles)}")
        print(f"Final labels detected: {len(merged_results)}")

    return merged_results


#USAGE
pg = 50

rects = find_rectangles_text(f"../data/{drawing}/{drawing}.pdf", page_number=pg)


#Clean using GPT
prompt = """
    You are given a Json array of coordinates and label data for supposedly legends in a PDF Page.
    Your task is to analyze this data, and remove any false positive and keep only the data that is most likely to be a legend.
    For this remember that the false possitive will have labels that may contain gibberish or sentences that coudl nbot be a legend.
    Please return the same json array but remove the fasle positives

"""
# response = client.responses.create(
#     model="gpt-5.4-mini",
#     input=[{
#         "role": "user",
#         "content": prompt + f"\n\n{rects}"
         
#           }],
#     temperature=0
# )
# gpt = response.output_text

# data = json.loads(gpt)

with open(f"../data/{drawing}/legends/{drawing}_legends_{pg}.json", "w") as f:
    json.dump(rects, f,indent=4)

print('Saved!')