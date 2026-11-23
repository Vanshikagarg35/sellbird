# adds the 2 sample products of TaskNest so the demo is quick
# prospects are loaded from the dashboard with "Load prospects (local data)"
import database as db

db.init_db()

if db.query("SELECT COUNT(*) as c FROM products", one=True)["c"] > 0:
    print("products already exist, skipping")
else:
    db.add_product("TaskNest Software", "BookEasy",
                   "Online appointment booking with WhatsApp/SMS reminders for clinics and salons",
                   "Rs 1,499/month per branch", "data/company_info/tasknest.txt")
    db.add_product("TaskNest Software", "StockSaathi",
                   "GST billing and inventory app for small retail shops and distributors",
                   "Rs 999/month", "data/company_info/tasknest.txt")
    print("added 2 products. open the dashboard and click 'Load prospects' for each product")
