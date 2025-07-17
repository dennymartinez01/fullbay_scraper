from playwright.sync_api import sync_playwright
import requests
import time

ZAPIER_WEBHOOK_URL = "https://hooks.zapier.com/hooks/catch/23611802/u2mokt0/"


def scrape_fullbay():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False, slow_mo=200)
        context = browser.new_context()
        page = context.new_page()

        print("🌐 Navigating to FullBay...")
        page.goto("https://app.fullbay.com/office/shop.html")

        print("🕐 Please log in manually in the browser if prompted...")

        try:
            # Wait for the exact table to appear
            page.wait_for_selector("#serviceRequestsDataTable", timeout=120000)
            print("✅ Service Requests table detected.")
        except Exception as e:
            print("❌ Table not found:", e)
            browser.close()
            return

        # Grab all table rows (excluding header)
        rows = page.query_selector_all("#serviceRequestsDataTable tbody tr")
        print(f"📄 Found {len(rows)} service request(s).")

        for row in rows:
            cols = row.query_selector_all("td")
            if len(cols) < 9:
                continue  # skip incomplete rows

            sr_data = {
                "SR": cols[0].inner_text().strip(),
                "Status": cols[1].inner_text().strip(),
                "Unit": cols[2].inner_text().strip(),
                "Customer": cols[3].inner_text().strip(),
                "Created By": cols[4].inner_text().strip(),
                "1st Complaint": cols[5].inner_text().strip(),
                "# SR Notes": cols[6].inner_text().strip(),
                "Created": cols[7].inner_text().strip(),
                "Unit Return": cols[8].inner_text().strip(),
            }

            print("📤 Sending to Zapier:", sr_data)
            try:
                response = requests.post(ZAPIER_WEBHOOK_URL, json=sr_data)
                print(f"✅ Sent (HTTP {response.status_code})")
            except Exception as err:
                print(f"⚠️ Failed to send to Zapier: {err}")

        print("✅ All done. Closing browser.")
        time.sleep(5)
        browser.close()


if __name__ == "__main__":
    scrape_fullbay()
