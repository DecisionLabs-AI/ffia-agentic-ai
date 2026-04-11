# Data Definition

This document defines the core data used by FFIA (Fuel & Food Impact Analyzer).

The purpose of these datasets is to help the system:

* understand restaurant cost structure
* monitor fuel-related business impact
* compare invoice cost with market prices
* personalize analysis based on restaurant profile

---

## 1. oil_price

This table stores the latest oil price used as an external business signal for cost-impact analysis.

| field name      | data type     | description                                  | example             |
| --------------- | ------------- | -------------------------------------------- | ------------------- |
| type            | VARCHAR(50)   | Oil type                                     | Gasohol 95, Diesel  |
| price_per_liter | DECIMAL(10,2) | Latest oil price per liter                   | 35.50               |
| updated_at      | TIMESTAMP     | Date and time when the oil price was updated | 2023-10-27 08:00:00 |

### Business meaning

This dataset helps FFIA estimate how changes in fuel prices may affect restaurant operating costs.

### Example use

If diesel price increases, FFIA can simulate higher logistics or delivery-related cost pressure.

---

## 2. platform_fee

This table stores food delivery platform commission rates.

| field name  | data type    | description                       | example         |
| ----------- | ------------ | --------------------------------- | --------------- |
| platform    | VARCHAR(50)  | Delivery platform name            | Grab, Foodpanda |
| fee_percent | DECIMAL(5,2) | Commission fee percentage         | 30.00           |
| is_default  | BOOLEAN      | Whether this is the default value | true            |

### Business meaning

This dataset helps FFIA estimate margin loss from delivery platform fees.

### Example use

If a restaurant sells mainlyผ่าน Grab with 30% GP, FFIA can include this in pricing and profitability analysis.

---

## 3. ingredient_market_price

This table stores current market prices of ingredients from external sources.

| field name       | data type     | description                  | example                     |
| ---------------- | ------------- | ---------------------------- | --------------------------- |
| id               | VARCHAR(20)   | Ingredient code or SKU       | ING-001                     |
| ingredient       | VARCHAR(100)  | Ingredient name              | Chicken breast, Egg No.2    |
| avg_market_price | DECIMAL(12,2) | Current average market price | 145.00                      |
| unit             | VARCHAR(20)   | Unit of measurement          | kg, tray, piece             |
| source           | VARCHAR(100)  | Source of market data        | Makro, Ministry of Commerce |

### Business meaning

This dataset allows FFIA to compare actual purchase prices with broader market price trends.

### Example use

If invoice price of chicken is much higher than market average, FFIA may flag a sourcing issue.

---

## 4. invoices

This table stores invoice-level purchase records uploaded into the system.

| field name   | data type                       | description                                      | example                         |
| ------------ | ------------------------------- | ------------------------------------------------ | ------------------------------- |
| id           | bigint / text reference in docs | Primary key of the invoice                       | 1                               |
| vendor       | text                            | Supplier or vendor name                          | Central Food Wholesales Limited |
| invoice_no   | text                            | Invoice number                                   | 004048634                       |
| invoice_date | date                            | Invoice date                                     | 2026-04-04                      |
| total_amount | numeric(12,2)                   | Total amount on the invoice                      | 1282.50                         |
| currency     | text                            | Invoice currency                                 | THB                             |
| source_type  | text                            | Source of invoice record                         | ocr_image                       |
| created_at   | timestamptz                     | Timestamp when the invoice was created in system | 2026-04-06 13:17:09.643747+00   |
| user_id      | text                            | Owner / linked user of the invoice               | admin                           |
| source       | text / business note            | OCR upload source                                | OCR                             |

### Business meaning

This is the main purchase history table used to understand what the restaurant bought, from whom, and when.

### Example use

FFIA can show all uploaded invoices for the current month and summarize total spend.

---

## 5. invoice_items

This table stores line-item details under each invoice.

| field name | data type                       | description                              | example                       |
| ---------- | ------------------------------- | ---------------------------------------- | ----------------------------- |
| id         | bigint / text reference in docs | Primary key of invoice item              | 17                            |
| invoice_id | bigint / text reference         | Linked invoice ID                        | 1                             |
| item_name  | text                            | Parsed item name from OCR                |                               |
| qty        | numeric(12,2)                   | Quantity purchased                       | 0.77                          |
| unit_price | numeric(12,2)                   | Price per unit                           | 156.00                        |
| total      | numeric(12,2)                   | Line-item total amount                   | 120.00                        |
| created_at | timestamptz                     | Timestamp when item record was created   | 2026-04-06 13:17:09.643747+00 |
| name       | text                            | Human-readable item name from OCR/source | ปีกกลางไก่ กก.ละ              |
| user_id    | text                            | Owner / linked user of the item          | admin                         |
| source     | text / business note            | OCR upload source                        | OCR                           |

### Business meaning

This is the most important cost-detail table for product analysis, because it stores what ingredients or products were actually purchased.

### Example use

FFIA can use line items to calculate current ingredient cost and estimate margin pressure.

### Data note

If `item_name` is empty or null, the system may use `name` as the display fallback.

---

## 6. restaurant_profiles

This table stores restaurant context so FFIA can remember each restaurant’s business profile and personalize analysis.

| field name         | data type                       | description                       | example                       |
| ------------------ | ------------------------------- | --------------------------------- | ----------------------------- |
| id                 | bigint / text reference in docs | Primary key of restaurant profile | 1                             |
| user_id            | text                            | Owner or linked user/session ID   | demo_admin                    |
| restaurant_name    | text                            | Restaurant name                   | May Kitchen                   |
| business_type      | text                            | Business category                 | restaurant                    |
| food_types         | text / text[]                   | Selected food categories          | ["street_food","high_lpg"]    |
| store_type         | text                            | Store operating type              | hybrid_small                  |
| seat_range         | text                            | Seating range                     | 1_10                          |
| currency           | text                            | Default business currency         | THB                           |
| target_margin_pct  | numeric(5,2)                    | Target margin percentage          | 30.00                         |
| warning_margin_pct | numeric(5,2)                    | Warning threshold percentage      | 25.00                         |
| risk_margin_pct    | numeric(5,2)                    | Risk threshold percentage         | 20.00                         |
| is_active          | boolean                         | Whether the profile is active     | true                          |
| created_at         | timestamptz                     | Profile creation timestamp        | 2026-04-11 06:05:04.243539+00 |
| updated_at         | timestamptz                     | Last update timestamp             | 2026-04-11 06:05:04.243539+00 |

### Business meaning

This table provides the business context layer for FFIA. It tells the system what type of restaurant it is analyzing and what thresholds should be used.

### Example use

If a restaurant is marked as `hybrid_small` with food types `street_food` and `high_lpg`, FFIA can apply more suitable cost and margin logic.

---

## 7. Data Relationships

The system uses these tables together as follows:

* `restaurant_profiles` defines restaurant context and business thresholds
* `invoices` stores uploaded supplier invoices
* `invoice_items` stores item-level cost details under each invoice
* `oil_price` provides external fuel cost signal
* `platform_fee` provides delivery commission context
* `ingredient_market_price` provides external market benchmark for ingredients

### Relationship summary

* One restaurant/user can have multiple invoices
* One invoice can have multiple invoice items
* One restaurant/user can have one active restaurant profile
* External tables (`oil_price`, `platform_fee`, `ingredient_market_price`) enrich analysis but are not direct transaction records

---

## 8. Key Business Questions Supported by This Data

These datasets allow FFIA to answer questions such as:

* What did this restaurant spend this month?
* Which ingredients are driving cost increases?
* Which menu items are at risk if costs rise further?
* How would a fuel price increase affect restaurant margin?
* Are current purchase prices above market benchmark?
* Should this restaurant adjust menu pricing?

---

## 9. Important Assumptions

* Invoice data is primarily captured through OCR uploads
* `invoice_items` is the most granular cost source
* `restaurant_profiles` stores the current business context for personalized analysis
* Fuel price and market price data are external reference signals, not direct purchase records
* Margin thresholds may vary by restaurant type and can be updated later
