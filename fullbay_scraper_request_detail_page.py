from playwright.sync_api import sync_playwright
import requests
import time
import json
import os

ZAPIER_WEBHOOK_URL = "https://hooks.zapier.com/hooks/catch/23611802/u2mokt0/"
PROCESSED_IDS_FILE = "processed_srs.json"
USER_DATA_DIR = "./fullbay_user_data"  # folder to persist login session

# Load processed SRs from file
def load_processed_srs():
    if os.path.exists(PROCESSED_IDS_FILE):
        with open(PROCESSED_IDS_FILE, "r") as f:
            return set(json.load(f))
    return set()

# Save processed SRs to file
def save_processed_srs(processed):
    with open(PROCESSED_IDS_FILE, "w") as f:
        json.dump(list(processed), f)

# Helper: Extract all panel-based fields from the SR detail page, including loose text and tables
def extract_detail_sections(page):
    details = {}
    panels = page.query_selector_all(".panel.panel-default")

    for panel in panels:
        try:
            title = panel.query_selector(".panel-title").inner_text().strip()
        except:
            title = "Unnamed Section"

        section = {}

        # Extract .form-group pairs
        groups = panel.query_selector_all(".form-group")
        for group in groups:
            try:
                label = group.query_selector("label")
                value_el = group.query_selector("div.form-control-static") or group.query_selector("div.col-sm-9")
                if label and value_el:
                    key = label.inner_text().strip()
                    val = value_el.inner_text().strip()
                    section[key] = val
            except:
                continue

        # Extract any inline key-value pairs like "Key: Value" in raw text
        texts = panel.inner_text().split("\n")
        for line in texts:
            if ":" in line:
                parts = line.split(":", 1)
                key = parts[0].strip()
                val = parts[1].strip()
                if key and val and key not in section:
                    section[key] = val

        # Extract data from any tables in the panel
        tables = panel.query_selector_all("table")
        for table in tables:
            try:
                headers = [th.inner_text().strip() for th in table.query_selector_all("thead th")]
                rows = table.query_selector_all("tbody tr")
                table_data = []
                for row in rows:
                    cells = [td.inner_text().strip() for td in row.query_selector_all("td")]
                    if cells:
                        row_dict = dict(zip(headers, cells)) if headers and len(headers) == len(cells) else cells
                        table_data.append(row_dict)
                if table_data:
                    section["Table"] = table_data
            except:
                continue

        if section:
            details[title] = section

    return details


def scrape_fullbay():
    processed_srs = load_processed_srs()

    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(user_data_dir=USER_DATA_DIR, headless=False, slow_mo=200)
        page = context.pages[0] if context.pages else context.new_page()

        print("🔐 Browser launched with persistent context.")
        print("🌐 Navigating to FullBay...")
        page.goto("https://app.fullbay.com/office/shop.html")
        page.screenshot(path="initial_page.png", full_page=True)
        print("📸 Screenshot saved as 'initial_page.png'")

        try:
            page.wait_for_selector("#serviceRequestsDataTable", timeout=120000)
            print("✅ Service Requests table detected.")
        except Exception as e:
            print("❌ Table not found:", e)
            context.close()
            return

        rows = page.query_selector_all("#serviceRequestsDataTable tbody tr")
        print(f"📄 Found {len(rows)} service request(s).")

        table_data = []
        for row in rows:
            cols = row.query_selector_all("td")
            if len(cols) < 9:
                continue
            table_data.append([col.inner_text().strip() for col in cols])

        for cols in table_data:
            sr_id = cols[0]
            if sr_id in processed_srs:
                print(f"⏩ Skipping already processed SR {sr_id}")
                continue

            sr_data = {
                "SR": sr_id,
                "Status": cols[1],
                "Unit": cols[2],
                "Customer": cols[3],
                "Created By": cols[4],
                "1st Complaint": cols[5],
                "# SR Notes": cols[6],
                "Created": cols[7],
                "Unit Return": cols[8],
            }

            detail_url = f"https://app.fullbay.com/office/workorder/viewRepairRequest.html?repairRequestId={sr_id}"
            print(f"🔍 Navigating to SR detail page: {detail_url}")
            page.goto(detail_url)

            try:
                page.wait_for_selector(".panel.panel-default", state="attached", timeout=15000)
                detail_data = extract_detail_sections(page)
                sr_data.update(detail_data)
            except Exception as e:
                print(f"⚠️ Timeout waiting for detail panels on SR {sr_id}: {e}")
                page.screenshot(path=f"sr_{sr_id}_error.png", full_page=True)
                print(f"📸 Screenshot saved for SR {sr_id} error")
                continue

            print("📤 Sending to Zapier:", sr_data)
            try:
                response = requests.post(ZAPIER_WEBHOOK_URL, json=sr_data)
                print(f"✅ Sent (HTTP {response.status_code})")
                processed_srs.add(sr_id)
                save_processed_srs(processed_srs)
            except Exception as err:
                print(f"⚠️ Failed to send to Zapier: {err}")

        print("✅ All done. Closing browser.")
        time.sleep(5)
        context.close()


if __name__ == "__main__":
    scrape_fullbay()
