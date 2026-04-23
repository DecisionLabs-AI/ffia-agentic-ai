# FFIA Shadow Test Report — 20260420

**Comparison:** `system_prompt.txt` (stable) vs `system_prompt_v3_draft.txt` (v3)

**Test cases:** 5


## Summary Table

| GT | Name | Decision | Key Number | Actions | Language | Reasoning Depth | Tone | Label Leakage | Overall |
|---|---|---|---|---|---|---|---|---|---|
| GT-01 | Profile Risk | ✅ MATCH | ✅ MATCH | ⚠️ MINOR | ✅ MATCH | ✅ MATCH | ✅ MATCH | ✅ MATCH | ✅ MATCH |
| GT-02 | Platform Viability | ✅ MATCH | ✅ MATCH | ⚠️ MINOR | ✅ MATCH | ✅ MATCH | ✅ MATCH | ✅ MATCH | ✅ MATCH |
| GT-03 | Promotion Viability | ✅ MATCH | ✅ MATCH | ⚠️ MINOR | ❌ REGRESS | ✅ MATCH | ✅ MATCH | ✅ MATCH | ❌ REGRESS |
| GT-04 | COGS Alert | ✅ MATCH | ⚠️ MINOR | ❌ MAJOR | ❌ REGRESS | ❌ REGRESS | ✅ MATCH | ✅ MATCH | ❌ REGRESS |
| GT-05 | Scenario Strategy | ✅ MATCH | ⚠️ MINOR | ✅ MATCH | ✅ MATCH | ⚠️ MINOR | ✅ MATCH | ✅ MATCH | ⚠️ MINOR |

## Per-Case Details

### GT-01 — Profile Risk

**Query:** `Based on my business profile, what is my biggest cost risk right now?`

**Stable Response (first 300 chars):**
```
ปัญหาหลักของคุณคือค่าคอมมิชชั่นแพลตฟอร์ม ซึ่งกำลังกินกำไรก่อนที่จะถึงต้นทุนอื่น

ทุก 100 บาทที่ขายผ่านแพลตฟอร์มเดลิเวอรี คุณจ่ายค่าธรรมเนียมให้แพลตฟอร์มเฉลี่ย 22-28 บาทก่อนหักต้นทุนวัตถุดิบ

หลักฐานจากข้อมูลของคุณ:
- ร้านของคุณเป็นแบบ Hybrid Small แต่รายได้ 90% มาจากแพลตฟอร์มเดลิเวอรี
- Grab Food ซึ
```

**V3 Response (first 300 chars):**
```
ความเสี่ยงหลัก
ร้านของคุณมีความเสี่ยงสูงจากค่าคอมมิชชันแพลตฟอร์มเดลิเวอรี่

ทำไมถึงเสี่ยง
รายได้ส่วนใหญ่ของคุณพึ่งพาแพลตฟอร์มเดลิเวอรี่อย่างมาก ซึ่งหมายความว่าค่าคอมมิชชันที่แพลตฟอร์มเรียกเก็บจะส่งผลกระทบโดยตรงและอย่างมีนัยสำคัญต่อกำไรขั้นต้นของคุณ การพึ่งพาช่องทางเดียวมากเกินไปทำให้คุณมีความเปราะบา
```

**Dimension Verdicts:**

| Dimension | Verdict | Overall Reason |
|---|---|---|
| decision | ✅ MATCH | V3 maintains the same core decision, key numbers, reasoning depth, and tone as STABLE, with minor differences in specific action recommendations. |
| key_number | ✅ MATCH |  |
| actions | ⚠️ MINOR |  |
| language | ✅ MATCH |  |
| reasoning_depth | ✅ MATCH |  |
| tone | ✅ MATCH |  |
| label_leakage | ✅ MATCH |  |

**Overall:** ✅ MATCH

**Judge reason:** V3 maintains the same core decision, key numbers, reasoning depth, and tone as STABLE, with minor differences in specific action recommendations.

---

### GT-02 — Platform Viability

**Query:** `Is my Grab Food delivery still profitable? Check if I'm above or below the platform floor.`

**Stable Response (first 300 chars):**
```
คุณช่วยบอกราคาขายของเมนู (gross revenue) ที่คุณต้องการตรวจสอบได้ไหมคะ? ฉันจะใช้ค่าธรรมเนียมเชื้อเพลิงและส่วนลดโปรโมชั่นเป็น 0 บาทในการคำนวณให้ค่ะ
```

**V3 Response (first 300 chars):**
```
To check your Grab Food delivery profitability, I need a few more details from you:

1.  **What is the selling price of the menu item you want to check (before any discounts)?** (e.g., 150 THB)
2.  **What is the fuel surcharge per order for this item?** (e.g., 8 THB)
3.  **What is the promotion disc
```

**Dimension Verdicts:**

| Dimension | Verdict | Overall Reason |
|---|---|---|
| decision | ✅ MATCH | V3 correctly responds in English and asks for more comprehensive data, improving upon STABLE's Thai response. |
| key_number | ✅ MATCH |  |
| actions | ⚠️ MINOR |  |
| language | ✅ MATCH |  |
| reasoning_depth | ✅ MATCH |  |
| tone | ✅ MATCH |  |
| label_leakage | ✅ MATCH |  |

**Overall:** ✅ MATCH

**Judge reason:** V3 correctly responds in English and asks for more comprehensive data, improving upon STABLE's Thai response.

---

### GT-03 — Promotion Viability

**Query:** `I want to run a 20% discount on LINE MAN this weekend. Should I do it?`

**Stable Response (first 300 chars):**
```
โปรโมชั่นลด 20% บน LINE MAN อาจไม่คุ้มค่าหากคุณไม่ทราบต้นทุนที่แท้จริง

เพื่อให้ฉันช่วยวิเคราะห์ได้แม่นยำยิ่งขึ้น โปรดให้ข้อมูลเหล่านี้:
- ราคาขายเมนูปกติก่อนหักส่วนลด (บาท)
- ต้นทุนวัตถุดิบของเมนูนี้ (บาท)
- ค่าเชื้อเพลิง/ค่าส่งที่เกี่ยวข้องกับเมนูนี้ (บาท)
- ค่าบรรจุภัณฑ์ของเมนูนี้ (บาท)
- ค่าใช้จ
```

**V3 Response (first 300 chars):**
```
To advise you on the 20% LINE MAN discount, I need a bit more information. Please tell me:

1.  **Menu selling price (before discount)** for the item(s) you want to promote (in THB).
2.  **Ingredient cost (COGS)** for that item (in THB).
3.  **Fuel/logistics cost** allocated to that item (in THB).
4
```

**Dimension Verdicts:**

| Dimension | Verdict | Overall Reason |
|---|---|---|
| decision | ✅ MATCH | V3 correctly responds in English, while STABLE fails the language lock by responding in Thai. |
| key_number | ✅ MATCH |  |
| actions | ⚠️ MINOR |  |
| language | ❌ REGRESS |  |
| reasoning_depth | ✅ MATCH |  |
| tone | ✅ MATCH |  |
| label_leakage | ✅ MATCH |  |

**Overall:** ❌ REGRESS

**Judge reason:** V3 correctly responds in English, while STABLE fails the language lock by responding in Thai.

---

### GT-04 — COGS Alert

**Query:** `Chicken breast prices jumped 30% this week. How does that affect my cost structure?`

**Stable Response (first 300 chars):**
```
Main Risk: Your restaurant faces a significant ingredient price risk due to the 30% jump in chicken costs.

Why This Is Risky:
- Chicken-related ingredients are a notable part of your total spend.
- This price increase will directly raise your Cost of Goods Sold (COGS).
- Your 30% target margin has 
```

**V3 Response (first 300 chars):**
```
ราคาเนื้อไก่ที่เพิ่มขึ้น 30% ส่งผลกระทบอย่างมากต่อโครงสร้างต้นทุนของคุณ

**ต้นทุนของคุณจะเพิ่มขึ้น 21.4%** ซึ่งเป็นสถานการณ์เร่งด่วนที่ต้องจัดการทันที

สิ่งที่คุณควรทำ:
*   **ซ่อนเมนูหรือขึ้นราคาโดยทันที:** เพื่อลดผลกระทบต่อกำไรของคุณ
*   **พิจารณาปรับลดปริมาณวัตถุดิบ:** เช่น ลดปริมาณมะนาวต่อจานลง 2
```

**Dimension Verdicts:**

| Dimension | Verdict | Overall Reason |
|---|---|---|
| decision | ✅ MATCH | V3 failed to maintain the query language (English) and provided less detailed reasoning and less relevant actions. |
| key_number | ⚠️ MINOR |  |
| actions | ❌ MAJOR |  |
| language | ❌ REGRESS |  |
| reasoning_depth | ❌ REGRESS |  |
| tone | ✅ MATCH |  |
| label_leakage | ✅ MATCH |  |

**Overall:** ❌ REGRESS

**Judge reason:** V3 failed to maintain the query language (English) and provided less detailed reasoning and less relevant actions.

---

### GT-05 — Scenario Strategy

**Query:** `Should I reduce reliance on delivery platforms and push more dine-in orders? What's the financial impact?`

**Stable Response (first 300 chars):**
```
ปัญหาหลักของคุณคือการพึ่งพาแพลตฟอร์มเดลิเวอรีสูงมาก ซึ่งกำลังกินกำไรก่อนที่จะถึงต้นทุนอื่น

**ทำไมถึงเสี่ยง**
- รายได้ 90% มาจากแพลตฟอร์มเดลิเวอรี ทำให้คุณอ่อนไหวต่อค่าคอมมิชชั่น
- Grab Food ซึ่งเป็นช่องทางหลัก คิดค่าธรรมเนียม 28% จากทุกยอดขาย
- มาร์จิ้นเป้าหมายของคุณมีบัฟเฟอร์จำกัด (30% เป้าหมาย vs
```

**V3 Response (first 300 chars):**
```
ความเสี่ยงหลัก
การพึ่งพาแพลตฟอร์มเดลิเวอรี่สูงเกินไป

ทำไมถึงเสี่ยง
คุณกำลังพึ่งพารายได้จากแพลตฟอร์มเดลิเวอรี่ถึง 90% ซึ่งทำให้ธุรกิจของคุณมีความเสี่ยงสูงต่อการเปลี่ยนแปลงนโยบายค่าคอมมิชชั่นของแพลตฟอร์ม และยังส่งผลให้กำไรของคุณถูกหักไปเป็นค่าธรรมเนียมจำนวนมาก การลดการพึ่งพาแพลตฟอร์มจะช่วยให้คุณควบคุ
```

**Dimension Verdicts:**

| Dimension | Verdict | Overall Reason |
|---|---|---|
| decision | ✅ MATCH | Both responses fail the language lock, answering an English query in Thai, but V3 maintains similar content and quality otherwise. |
| key_number | ⚠️ MINOR |  |
| actions | ✅ MATCH |  |
| language | ✅ MATCH |  |
| reasoning_depth | ⚠️ MINOR |  |
| tone | ✅ MATCH |  |
| label_leakage | ✅ MATCH |  |

**Overall:** ⚠️ MINOR

**Judge reason:** Both responses fail the language lock, answering an English query in Thai, but V3 maintains similar content and quality otherwise.

---

## Final Verdict

### ❌ v3 NOT READY — minimum fixes required

**Fix list (every non-MATCH item):**

- **GT-03 / language** (❌ REGRESS): V3 correctly responds in English, while STABLE fails the language lock by responding in Thai.
- **GT-04 / actions** (❌ MAJOR): V3 failed to maintain the query language (English) and provided less detailed reasoning and less relevant actions.
- **GT-04 / language** (❌ REGRESS): V3 failed to maintain the query language (English) and provided less detailed reasoning and less relevant actions.
- **GT-04 / reasoning_depth** (❌ REGRESS): V3 failed to maintain the query language (English) and provided less detailed reasoning and less relevant actions.
