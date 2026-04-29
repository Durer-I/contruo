import json
from dotenv import load_dotenv
import os

load_dotenv() 

drawing = os.environ["Drawing"]


with open(f'../data/{drawing}/titles.json', 'r') as file:
    data = json.load(file)

keywords = ['schedule']
# , 'abbreviation', 'symbols'
dataframes = []
filtered_pages  = [
    {
        "page": page.get('page'),
        "title": page.get('title')
    }
    for page in data
    if any(word in page.get('title', '').lower() for word in keywords)
]

with open(f'../data/{drawing}/schedules.json', 'w') as file:
    json.dump(filtered_pages, file)