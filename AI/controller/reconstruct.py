from openai import OpenAI
from dotenv import load_dotenv
import os

load_dotenv() 

drawing = os.environ["Drawing"]


client = OpenAI(api_key=os.environ["takeoff_api"]) 

content = client.files.content("file-BzwW1eHPn5gWtDLqwyUeip")

with open(f"../data/{drawing}/restored.png", "wb") as f:
    f.write(content.read())