import pdfplumber
from collections import Counter
from scipy.spatial import KDTree
from collections import Counter
from collections import Counter
import math
import numpy as np
import cv2
import time

start = time.time()


drawing = 'd3'
# pgs = [18,21,25,27,33]  # Second Floor
pgs = [17,20,24,26,32]  # First Floor

for pg in pgs:

    def build_word_points(words):
        pts = []
        for w in words:
            pts.extend([
                (w["x0"], w["top"]),
                (w["x1"], w["top"]),
                (w["x0"], w["bottom"]),
                (w["x1"], w["bottom"]),
            ])
        return pts


    def has_text_inside(rect, word_pts, tol=2):
        x0, x1 = rect["x0"], rect["x1"]
        y0, y1 = rect["top"], rect["bottom"]

        # expand rect once
        x0 -= tol; x1 += tol
        y0 -= tol; y1 += tol

        # quick reject using bounding box
        for wx, wy in word_pts:
            if x0 <= wx <= x1 and y0 <= wy <= y1:
                return True

        return False


    def find_walls(pdf_path, page_number, output_dir="label/groups/filtered_rects12.png"):
        

        with pdfplumber.open(pdf_path) as pdf:
            if not (0 <= page_number < len(pdf.pages)):
                print("Invalid page number")
                return
            
            page = pdf.pages[page_number]

            edges = page.lines + page.rects
            words = page.extract_words()

            # 🔥 precompute once
            word_pts = build_word_points(words)

            doc = []
            for rect in edges:
                if rect.get('height') or rect.get('width'): doc.append(rect.get('height') or rect.get('width'))

            all = sorted(set(doc))
            
            filtered_edges = []
            for rect in edges:
                if (rect.get('height') or rect.get('width')) > all[-5]: continue
                if not has_text_inside(rect, word_pts):
                    filtered_edges.append(rect)

            print(f"Original: {len(edges)}")
            print(f"Filtered (no text inside): {len(filtered_edges)}")

            return filtered_edges, page
        


    rects_original, page = find_walls(f"data/{drawing}.pdf", page_number=pg)
    # pgs = [18,21,25,27,33]
    #This code collects lines from page.lines whose lengths occur 20 times or fewer
    

    def get_length(rect):
        return rect.get('width') or rect.get('height')

    def angle(rect):
        dx = rect["x1"] - rect["x0"]
        dy = rect["y1"] - rect["y0"]
        return (math.degrees(math.atan2(dy, dx)) % 180)

    # --- Step 1: collect lengths ---
    lengths = [
        get_length(rect)
        for rect in page.lines
        if rect.get('orientation') is None
    ]

    # --- Step 2: count + filter ---
    counts = Counter(lengths)
    valid_lengths = {val for val, cnt in counts.items() if cnt <= 20}

    # --- Step 3: filter lines ---
    line_new = []

    for rect in page.lines:
        ang = angle(rect)
        length = get_length(rect)

        if  length in valid_lengths:
            line_new.append(rect.get('pts'))
            # line_new.append(rect)
    # This code collects rectangles from page.rects whose (height, width) pair occurs two times or fewer and stores their corner points (pts) in rect_new.

    

    rlh = [
        (rect.get('height'), rect.get('width'))
        for rect in page.rects
    ]

    countsh = Counter(rlh)

    valid_lengthsh = {val for val, cnt in countsh.items() if cnt <= 2}

    rect_new = []

    for rect in page.rects:
        if (rect.get('height'), rect.get('width')) in valid_lengthsh:
            rect_new.append(rect.get('pts'))
   

    rects = line_new + rect_new
    points = [p for seg in rects for p in seg]

    tree = KDTree(points)

    radius = 5  # keep this consistent with your earlier calculation
    all_distances = []
    pairs = []

    # Compute distances and store point pairs
    for idx, point in enumerate(points):
        indices = tree.query_ball_point(point, r=radius)
        for i in indices:
            if i != idx:
                d = ((point[0]-points[i][0])**2 + (point[1]-points[i][1])**2)**0.5
                # rd = round(d, 2)
                rd = d
                all_distances.append(rd)
                pairs.append((idx, i, rd))  # store the indices along with distance

    # Find the most common distance
    most_common_distance = Counter(all_distances).most_common(3)[1][0]
    print("Most common distance:", most_common_distance)

    # Keep only points that have this distance with any other point
    points_to_keep_indices = set()
    for i, j, d in pairs:
        if  d <= most_common_distance:
            points_to_keep_indices.add(i)
            points_to_keep_indices.add(j)

    # Extract the filtered points
    filtered_points = [points[i] for i in points_to_keep_indices]

    print(f"Number of points with most common distance: {len(filtered_points)}")
    filtered_set = set(filtered_points)

    r = []
    for rect in rects_original:
        pts = rect.get('pts', [])
        if any(p in filtered_set for p in pts):
            r.append(rect)
    #DRAW POINTS
    # r = page.extract_words()+ page.rects
    im = page.to_image(resolution=300)
        
    im.draw_lines(r, stroke=(0,255,0), stroke_width=4)

    im.save(f"label/legend/rooms/filtered_rects_{pg}.png")

    #ROOM COLOR WITHOUT BACKGROUND COLOR

    

    rects = r

    base = cv2.imread(f'label/legend/rooms/filtered_rects_{pg}.png')
    h, w = base.shape[:2]

    img = np.zeros((h, w), dtype=np.uint8)

    scale_x = w / page.width
    scale_y = h / page.height

    # -----------------------------
    # 1. DRAW WALLS
    # -----------------------------
    for rect in rects:
        x0 = int(rect["x0"] * scale_x)
        x1 = int(rect["x1"] * scale_x)
        y0 = int(rect["top"] * scale_y)
        y1 = int(rect["bottom"] * scale_y)

        cv2.rectangle(img, (x0, y0), (x1, y1), 255, -1)

    # -----------------------------
    # 2. INVERT → ROOMS
    # -----------------------------
    rooms_mask = cv2.bitwise_not(img)

    # -----------------------------
    # 3. CONNECTED COMPONENTS
    # -----------------------------
    num_labels, labels, stats, centroids = cv2.connectedComponentsWithStats(rooms_mask)

    # -----------------------------
    # 4. FILTER + COLOR + EXTRACT
    # -----------------------------
    colored = np.zeros((h, w, 3), dtype=np.uint8)
    regions = []

    total_area = h * w

    for i in range(1, num_labels):
        area = stats[i, cv2.CC_STAT_AREA]

        # ❌ remove tiny noise
        if area < 500:
            continue

        # ❌ remove outer background (largest region)
        if area > 0.5 * total_area:
            continue

        # largest_label = np.argmax(stats[1:, cv2.CC_STAT_AREA]) + 1
        # if i == largest_label:
        #     continue

        mask = (labels == i)

        # random color
        color = np.random.randint(50, 255, size=3)
        colored[mask] = color

        # bounding box
        x = stats[i, cv2.CC_STAT_LEFT]
        y = stats[i, cv2.CC_STAT_TOP]
        w_box = stats[i, cv2.CC_STAT_WIDTH]
        h_box = stats[i, cv2.CC_STAT_HEIGHT]

        regions.append({
            "label": i,
            "x0": int(x),
            "y0": int(y),
            "x1": int(x + w_box),
            "y1": int(y + h_box),
            "area": int(area),
            "centroid": tuple(centroids[i])
        })

    # -----------------------------
    # 5. OVERLAY (ONLY COLORED REGIONS)
    # -----------------------------
    overlay = base.copy()

    mask_nonzero = np.any(colored > 0, axis=2)
    overlay[mask_nonzero] = cv2.addWeighted(
        base[mask_nonzero], 0.7,
        colored[mask_nonzero], 0.3,
        0
    )

    # -----------------------------
    # 6. SAVE
    # -----------------------------
    cv2.imwrite(f'label/legend/rooms/{pg}.png', overlay)



end = time.time()

print(f"Time taken: {end - start} seconds")