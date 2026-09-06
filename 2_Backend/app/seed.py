from datetime import date, timedelta
import random
from .database import Base, engine, SessionLocal
from .models import Farmer, Product, Supply, DemandHistory


def seed():
    print("Clearing and rebuilding database schema...")
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)

    db = SessionLocal()

    try:
        print("Seeding agricultural commodities...")
        products_data = [
            {"name": "Tomato", "category": "Vegetable", "unit": "kg", "mandi_benchmark_price": 22.0, "perishability_days": 7},
            {"name": "Potato (Jyoti)", "category": "Tuber", "unit": "kg", "mandi_benchmark_price": 16.5, "perishability_days": 45},
            {"name": "Red Onion", "category": "Allium", "unit": "kg", "mandi_benchmark_price": 28.0, "perishability_days": 25},
            {"name": "Green Chilli", "category": "Spice", "unit": "kg", "mandi_benchmark_price": 54.0, "perishability_days": 10},
            {"name": "Cauliflower", "category": "Vegetable", "unit": "kg", "mandi_benchmark_price": 18.0, "perishability_days": 8},
        ]

        products = {}
        for pdata in products_data:
            p = Product(**pdata)
            db.add(p)
            db.commit()
            db.refresh(p)
            products[p.name] = p

        print("Seeding local farmer network...")
        farmers_data = [
            {"name": "Subhash Mondal", "location": "Singur, Hooghly", "latitude": 22.8124, "longitude": 88.2312, "contact": "+91-9831102931", "rating": 4.9, "farm_size_acres": 6.5},
            {"name": "Ramesh Ghosh", "location": "Bardhaman Rural", "latitude": 23.2324, "longitude": 87.8615, "contact": "+91-9434218902", "rating": 4.8, "farm_size_acres": 12.0},
            {"name": "Animesh Biswas", "location": "Ranaghat, Nadia", "latitude": 23.1804, "longitude": 88.5801, "contact": "+91-9732194821", "rating": 4.7, "farm_size_acres": 4.5},
            {"name": "Prabir Samanta", "location": "Arambagh, Hooghly", "latitude": 22.8821, "longitude": 87.7812, "contact": "+91-9830561234", "rating": 4.9, "farm_size_acres": 8.0},
            {"name": "Debabrata Das", "location": "Uluberia, Howrah", "latitude": 22.4732, "longitude": 88.1102, "contact": "+91-9647891230", "rating": 4.6, "farm_size_acres": 5.0},
            {"name": "Gourab Roy", "location": "Kalna, Purba Bardhaman", "latitude": 23.2201, "longitude": 88.3612, "contact": "+91-9475123984", "rating": 4.8, "farm_size_acres": 7.5},
            {"name": "Uttam Sarkar", "location": "Kalyani, Nadia", "latitude": 22.9751, "longitude": 88.4345, "contact": "+91-9832456712", "rating": 4.7, "farm_size_acres": 5.5},
            {"name": "Bikash Mukherjee", "location": "Memari, Bardhaman", "latitude": 23.1782, "longitude": 88.1124, "contact": "+91-9433112233", "rating": 4.9, "farm_size_acres": 10.0},
            {"name": "Sunil Pal", "location": "Chandannagar, Hooghly", "latitude": 22.8671, "longitude": 88.3674, "contact": "+91-9836789012", "rating": 4.8, "farm_size_acres": 4.0},
            {"name": "Kamal Malakar", "location": "Barasat, North 24P", "latitude": 22.7214, "longitude": 88.4821, "contact": "+91-9831998877", "rating": 4.6, "farm_size_acres": 6.0}
        ]

        farmers = []
        for fdata in farmers_data:
            f = Farmer(**fdata)
            db.add(f)
            db.commit()
            db.refresh(f)
            farmers.append(f)

        print("Seeding active farmer produce supplies...")
        today = date.today()
        supplies_data = [
            # Tomato supplies (Total ~17,000 kg across 6 farmers)
            (farmers[0].id, products["Tomato"].id, 3500, 21.0, "Grade A"),
            (farmers[1].id, products["Tomato"].id, 4000, 23.0, "Grade A"),
            (farmers[2].id, products["Tomato"].id, 2200, 20.5, "Grade B"),
            (farmers[3].id, products["Tomato"].id, 3000, 22.5, "Grade A"),
            (farmers[4].id, products["Tomato"].id, 2500, 21.5, "Grade B"),
            (farmers[8].id, products["Tomato"].id, 1800, 24.0, "Grade A"),

            # Potato supplies (Total ~45,000 kg across 4 farmers)
            (farmers[1].id, products["Potato (Jyoti)"].id, 12000, 15.5, "Grade A"),
            (farmers[3].id, products["Potato (Jyoti)"].id, 15000, 16.0, "Grade A"),
            (farmers[7].id, products["Potato (Jyoti)"].id, 10000, 15.0, "Grade A"),
            (farmers[5].id, products["Potato (Jyoti)"].id, 8000, 16.2, "Grade B"),

            # Red Onion supplies (Total ~15,500 kg across 4 farmers)
            (farmers[0].id, products["Red Onion"].id, 4000, 27.5, "Grade A"),
            (farmers[2].id, products["Red Onion"].id, 3500, 28.5, "Grade A"),
            (farmers[6].id, products["Red Onion"].id, 5000, 26.8, "Grade A"),
            (farmers[9].id, products["Red Onion"].id, 3000, 29.0, "Grade B"),

            # Green Chilli supplies (Total ~4,500 kg across 3 farmers)
            (farmers[0].id, products["Green Chilli"].id, 1200, 53.0, "Grade A"),
            (farmers[6].id, products["Green Chilli"].id, 1800, 56.0, "Grade A"),
            (farmers[9].id, products["Green Chilli"].id, 1500, 52.5, "Grade A"),

            # Cauliflower supplies (Total ~10,800 kg across 3 farmers)
            (farmers[5].id, products["Cauliflower"].id, 4500, 17.5, "Grade A"),
            (farmers[4].id, products["Cauliflower"].id, 3800, 18.5, "Grade B"),
            (farmers[8].id, products["Cauliflower"].id, 2500, 19.0, "Grade A"),
        ]

        for f_id, p_id, qty, price, grade in supplies_data:
            s = Supply(
                farmer_id=f_id,
                product_id=p_id,
                quantity=qty,
                expected_price=price,
                quality_grade=grade,
                available_date=today + timedelta(days=1),
                harvest_date=today - timedelta(days=1)
            )
            db.add(s)

        print("Seeding 60 days of historical demand & mandi price trends...")
        random.seed(42)
        for p_name, prod in products.items():
            base_vol = 7000.0 if "Potato" in p_name else (5500.0 if "Tomato" in p_name else 3500.0)
            base_price = prod.mandi_benchmark_price

            for day_offset in range(60, 0, -1):
                hist_date = today - timedelta(days=day_offset)
                dow = hist_date.weekday()
                # Weekend surge factor
                surge = 1.18 if dow in (4, 5, 6) else 0.94
                # Upward trend over time
                trend_factor = 1.0 + ((60 - day_offset) * 0.003)

                qty = round(base_vol * surge * trend_factor + random.uniform(-300, 300), 1)
                mandi_p = round(base_price + (random.uniform(-1.5, 1.8)), 2)

                dh = DemandHistory(
                    product_id=prod.id,
                    date=hist_date,
                    region="Kolkata Metro Hub",
                    quantity_demanded=qty,
                    average_mandi_price=mandi_p
                )
                db.add(dh)

        db.commit()
        print("Database seeded successfully with products, farmers, supplies, and 60-day demand history!")

    finally:
        db.close()


if __name__ == "__main__":
    seed()