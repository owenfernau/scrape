import requests
from bs4 import BeautifulSoup


page = requests.get("https://www.owenfernau.com/")
soup = BeautifulSoup(page.content, 'html.parser')

#page = requests.get("https://www.owenfernau.com/")


print(page.status_code)
print(page.content)
