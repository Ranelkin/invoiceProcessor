import os 
from invoice2data import extract_data
from invoice2data.extract.loader import read_templates
from dotenv import load_dotenv

load_dotenv()

filename = os.environ.get("TEST_PATH")
templates = read_templates('./templates')
result = extract_data(filename, templates=templates)