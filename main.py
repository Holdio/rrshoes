from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from google.oauth2.service_account import Credentials
from gspread_dataframe import set_with_dataframe
from selenium.webdriver.common.by import By
import undetected_chromedriver as uc
from collections import Counter
from datetime import datetime
import pandas as pd
import requests
import gspread
import random
import time
import math
import json
import re

def apply_coupon(price, coupon):
    if coupon["type"] == "threshold_discount":
        if (price * 2) >= coupon["threshold"]:
            return price - (coupon["discount"]/2)
        return price

    elif coupon["type"] == "bogo_percent":
        sale_price = price * (1-float((coupon["discount_percent"]/2) /100))
        return sale_price

    return price

def parse_coupon(text):
    text = text.upper()

    # $X off $Y
    match = re.search(r"\$(\d+)\s+OFF.*\$(\d+)", text)
    if match:
        return {
            "type": "threshold_discount",
            "discount": float(match.group(1)),
            "threshold": float(match.group(2))
        }

    # BOGO 50%
    match = re.search(r"BOGO\s+(\d+)%", text)
    if match:
        return {
            "type": "bogo_percent",
            "discount_percent": float(match.group(1))
        }

    return {"type": "unknown", "raw": text}

def decode_custom_entities(s: str) -> str:
    return (
        s.replace("&q;", '"')
         .replace("&l;", "<")
         .replace("&g;", ">")
         .replace("&a;", "&")
    )

def find_key(data, target_key, path=""):
    if isinstance(data, dict):
        for key, value in data.items():
            new_path = f"{path}.{key}" if path else key

            if key == target_key:
                print("Found:", new_path)
                print("Value:", value)
                print()

            find_key(value, target_key, new_path)

    elif isinstance(data, list):
        for i, item in enumerate(data):
            find_key(item, target_key, f"{path}[{i}]")

options = uc.ChromeOptions()
options.add_argument("--window-size=1280,800")
prefs = {"profile.managed_default_content_settings.images": 2}
options.add_experimental_option("prefs", prefs)

driver = uc.Chrome(version_main=147, options=options)

accepted_brands = ["BROOKS", "NEW BALANCE", "ASICS", "JORDAN", "NIKE", "ADIDAS", "SKECHERS", "COLUMBIA", "MERRELL",
                   "KEEN", "HOKA", "ON", "UNDER ARMOR", "REEBOK", "PUMA", "SOREL", "LIFESTRIDE", "TIMBERLAND"]

shoe_data = []

length = 30

i = 0

start_time = time.time()

seen_texts = set()

finish_time = time.time() + 20

while length == 30:
# while i == 0:

    # Wait for products to appear
    real_url = "https://www.rackroomshoes.com/search/?icid=20260211_RRS2026Events_Core&source=TLN_SalePage_Header&facetFilters=%255B%255B%2522categoryPageId%253Aonsale%2522%255D%255D&currentPage=" + str(i)

    driver.get(real_url)

    print(real_url)

    wait = WebDriverWait(driver, 10)
    wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "div.mx-2")))

    if i == 0:
        try:
            driver.implicitly_wait(8)

            iframe = driver.find_element(By.ID, "lightbox-iframe-9e50d19b-40c1-4c94-9ca4-752b728e5569")

            # Switch to the iframe
            driver.switch_to.frame(iframe)

            # Now you can interact with the modal close button
            close_button = WebDriverWait(driver, 2).until(
                EC.element_to_be_clickable((By.XPATH, "//*[@aria-label='Close Modal']"))
            )
            close_button.click()

            # After interacting with the iframe, you may want to switch back to the main document
            driver.switch_to.default_content()
        except:
            print("Error")

        while time.time() < finish_time:
            try:
                el = driver.find_element(By.ID, "changeText")
                text = el.text.strip()

                if text and text not in seen_texts:
                    seen_texts.add(text)
                    print("Found:", text)

            except Exception:
                pass

            time.sleep(1)

        coupons = {c: parse_coupon(c) for c in seen_texts}

    # ------------------- Scroll to Load All Shoes -------------------
    last_height = driver.execute_script("return document.body.scrollHeight")


    while True:
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(random.uniform(1.5, 3.0))  # random delay

        new_height = driver.execute_script("return document.body.scrollHeight")
        if new_height == last_height:
            break
        last_height = new_height

    # ------------------- Scrape Products -------------------
    wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "div.mx-2")))

    products = driver.find_elements(By.CSS_SELECTOR, "div.mx-2")

    length = len(products)
    i+=1

    print(f"Found {len(products)} products.")

    Threshold_coupon = None

    for key, coupon in coupons.items():
        if "BOGO" in key:
            BOGO_Name = key
            BOGO_Coupon = coupon
    match = re.match(r".*?\*", BOGO_Name)
    result = match.group(0) if match else BOGO_Name

    for coupon in coupons.values():
        if coupon['type'] == 'threshold_discount':
            Threshold_coupon = coupon

    for product in products:
        try:
            brand = product.find_element(By.CSS_SELECTOR, "h2.fs-5.fw-semibold.mb-0").text
        except:
            brand = "N/A"

        if brand not in accepted_brands:
            continue

        coupon_list = []

        text = product.text

        if result in text:
            coupon_list.append(BOGO_Coupon)

        if "Coupon eligible*" in text and Threshold_coupon:
            coupon_list.append(Threshold_coupon)

        if len(coupon_list) == 0:
            continue

        try:
            name = product.find_element(By.CSS_SELECTOR, "h3.fs-6.text-truncate.fw-normal.mb-2").text
        except:
            name = "N/A"

        try:
            link = product.find_element(By.CSS_SELECTOR, 'a[data-test-a="productCardLink"]').get_attribute('href')
        except:
            link = "N/A"

        shoe_data.append({
            "brand": brand,
            "name": name,
            "link": link,
            "coupons": coupon_list
        })

    print(len(shoe_data))

print(shoe_data)
end_time = time.time()

# Calculate elapsed time
elapsed_time = end_time - start_time
print(f"Crawling process took {elapsed_time} seconds")
brand_counts = Counter(shoe["brand"] for shoe in shoe_data)
for brand in sorted(brand_counts):
    print(brand, brand_counts[brand])

final_shoe = []

start_time = time.time()

for shoe in shoe_data:

    url = shoe["link"]

    match = re.search(r'/(\d+)$', url)

    if match:
        final_number = match.group(1)
    else:
        print("No number found")

    session = requests.Session()

    # copy cookies from selenium
    for cookie in driver.get_cookies():
        session.cookies.set(cookie['name'], cookie['value'])

    headers = {
        "User-Agent": driver.execute_script("return navigator.userAgent;"),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": "https://www.champssports.com/",
    }

    # try:
    time.sleep(random.uniform(0.2, 0.6))
    response = session.get(url, headers=headers)

    if response.status_code == 200:
        html = response.text
    else:
        print(f"Request failed: {response.status_code} | {shoe['link']}")
        continue

    match = re.search(r'<script id="serverApp-state" type="application/json">(.*?)</script>', html, re.DOTALL)

    if match:
        # The JSON is in the matched group
        encoded_json = match.group(1)

        # Fix custom entities (if any custom decoding is needed)
        decoded_json = decode_custom_entities(encoded_json)

        # Parse the JSON data
        data = json.loads(decoded_json)

        sizes = data["cx-state"]["product"]["details"]["entities"][final_number]["variants"]["value"]\
            ["variantOptions"]

        active_sizes = [
            {
                "size": s["size"],
                "upc": s["vendorUPC"],
                "og_price": s["priceData"]["value"]
            }
            for s in sizes
            if s["pdpAvailability"].get("hasShippingAvailability") and s.get("vendorUPC")
        ]

        sale_price = active_sizes[0]['og_price'] if active_sizes else None
        if not sale_price == None:
            for coupon in shoe['coupons']:
                sale_price = apply_coupon(sale_price, coupon)
            sale_price = round(sale_price, 2)

        for final in active_sizes:
            final_shoe.append({
                "UPC": final["upc"],
                "name": shoe['name'],
                "bogo_price": sale_price,
                "link": shoe['link'],
                "size": final["size"],
                "og_price": final['og_price'],
                "brand": shoe["brand"],
                "coupons": shoe["coupons"]
            })

end_time = time.time()

# Calculate elapsed time
elapsed_time = end_time - start_time
print(f"Speed process took {elapsed_time} seconds")

current_datetime = datetime.now()

# Convert it to a string (default format)
datetime_string = current_datetime.strftime("%m-%d-%Y %H:%M")

df = pd.DataFrame(final_shoe)

rr_name = "RackRoom "+datetime_string

# Save to CSV
df.to_csv(rr_name+".csv", index=False)

scopes = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]
creds = Credentials.from_service_account_file("credentials.json", scopes=scopes)
client = gspread.authorize(creds)

# Open spreadsheet
spreadsheet = client.open("Francis - Web Scraping")

def create_and_fill_sheet(spreadsheet, title, df):
    rows, cols = df.shape

    # +1 for header row, + a little buffer
    worksheet = spreadsheet.add_worksheet(
        title=title,
        rows=str(rows + 1),
        cols=str(cols)
    )

    set_with_dataframe(worksheet, df)
    return worksheet

rr_sheet = create_and_fill_sheet(spreadsheet, rr_name, df)

driver.quit()


print("CSV saved!")
