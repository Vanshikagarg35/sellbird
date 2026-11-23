# loads prospects from the json file (already downloaded / collected data)
# and optionally fetches website text if online
import json
import sys
import database as db

PROSPECT_FILE = "data/prospects/sample_prospects.json"


def import_prospects_for_product(product_id, file=PROSPECT_FILE):
    p = db.get_product(product_id)
    with open(file, encoding="utf-8") as f:
        data = json.load(f)

    count = 0
    for d in data:
        # file has prospects for both products, only take the ones for this product
        if d.get("product") and d["product"].lower() != p["product_name"].lower():
            continue
        exists = db.query("SELECT id FROM prospects WHERE product_id=? AND company=?", (product_id, d["company"]), one=True)
        if exists:
            continue
        db.execute("""INSERT INTO prospects (product_id, company, website, contact_name, contact_role, email,
                      industry, employees, location, page_text, status, created_at)
                      VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
                   (product_id, d["company"], d.get("website"), d.get("contact_name"), d.get("contact_role"),
                    d.get("email"), d.get("industry"), d.get("employees", 0), d.get("location"),
                    d.get("page_text", ""), "new", db.now()))
        count += 1
    print("imported", count, "prospects")
    return count


def fetch_missing_text():
    """needs internet. fills page_text for prospects that only have a website"""
    from research.scraper import fetch_site
    rows = db.query("SELECT id, website FROM prospects WHERE page_text IS NULL OR page_text=''")
    for r in rows:
        print("fetching", r["website"])
        text = fetch_site(r["website"])
        db.execute("UPDATE prospects SET page_text=? WHERE id=?", (text, r["id"]))


if __name__ == "__main__":
    db.init_db()
    if len(sys.argv) > 1 and sys.argv[1] == "fetch":
        fetch_missing_text()
    else:
        print("usage: python import_data.py fetch")
