import google.generativeai as genai
import json
import os
import time
import re
from datetime import date

# ตั้งค่า Google AI
genai.configure(api_key=os.environ["GOOGLE_AI_KEY"])
model = genai.GenerativeModel("gemini-1.5-flash")  # ฟรี tier

SOURCES = [
    {
        "id": "มกษ_5700",
        "name": "มกษ. 5700 กาแฟโรบัสต้า",
        "check_prompt": "ค้นหาข้อมูลจาก ratchakitcha.soc.go.th และ acfs.go.th ว่ามีประกาศกระทรวงเกษตรและสหกรณ์ เรื่อง กำหนดมาตรฐานสินค้าเกษตร มกษ. 5700 กาแฟโรบัสตา ฉบับใหม่หรือแก้ไขหลังจากปี 2561 หรือไม่"
    },
    {
        "id": "สธ_สารพิษ_460",
        "name": "ประกาศ สธ. ฉ.460 สารพิษตกค้าง",
        "check_prompt": "ค้นหาจาก food.fda.moph.go.th ว่ามีประกาศกระทรวงสาธารณสุข เรื่อง อาหารที่มีสารพิษตกค้าง ฉบับใหม่หลังจากฉบับที่ 460 พ.ศ. 2568 ที่เกี่ยวข้องกับกาแฟหรือไม่"
    },
    {
        "id": "สธ_สารปนเปื้อน",
        "name": "ประกาศ สธ. สารปนเปื้อน OTA/Aflatoxin",
        "check_prompt": "ค้นหาจาก food.fda.moph.go.th ว่ามีประกาศกระทรวงสาธารณสุข เรื่อง อาหารที่มีสารปนเปื้อน ฉบับใหม่หรือแก้ไขค่า Ochratoxin A หรือ Aflatoxin ในกาแฟหลังปี 2566 หรือไม่"
    },
    {
        "id": "codex_cxc27",
        "name": "Codex CXC 27-1981 (SB 07/16)",
        "check_prompt": "Search fao.org/fao-who-codexalimentarius for the latest status of Codex CXC 27-1981 Code of Practice for Coffee. Has the Draft Amendment been officially adopted by CCCF after 2024?"
    },
    {
        "id": "codex_stan193",
        "name": "Codex Stan 193 Contaminants",
        "check_prompt": "Search fao.org/fao-who-codexalimentarius for any revision to Codex Stan 193 after the 2023 revision, specifically regarding OTA or Aflatoxin limits in coffee beans."
    },
    {
        "id": "codex_cxl",
        "name": "Codex MRL Pesticides in Coffee (CXL)",
        "check_prompt": "Search fao.org/pesticide-residues-jmpr-database for any updates to Codex Maximum Residue Limits for pesticides in coffee beans after 2024."
    },
]

SYSTEM_PROMPT = """คุณเป็นผู้ช่วยตรวจสอบกฎหมาย ตอบเป็น JSON เท่านั้น ไม่มีข้อความอื่น ไม่มี markdown backticks
รูปแบบที่ต้องการ:
{"updated": true หรือ false, "detail": "รายละเอียด 1-2 ประโยค", "version": "ฉบับ/ปีที่พบ หรือ empty string"}
- updated = true เฉพาะเมื่อพบการเปลี่ยนแปลงจริงหลังจากฉบับปัจจุบัน
- ถ้าค้นหาไม่พบข้อมูล ให้ updated = false และ detail อธิบายสั้นๆ"""

def check_source(source, max_retries=3):
    """ตรวจสอบแหล่งข้อมูลโดยใช้ Gemini พร้อม retry"""
    full_prompt = f"{SYSTEM_PROMPT}\n\nคำถาม: {source['check_prompt']}"

    for attempt in range(max_retries):
        try:
            response = model.generate_content(full_prompt)
            text = response.text.strip()

            # ลบ markdown backticks ถ้ามี
            text = re.sub(r'```(?:json)?', '', text).strip()

            # หา JSON
            match = re.search(r'\{[^{}]+\}', text, re.DOTALL)
            if match:
                result = json.loads(match.group())
                result.setdefault("updated", False)
                result.setdefault("detail", "ตรวจสอบเรียบร้อย")
                result.setdefault("version", "")
                return result
            else:
                print(f"  ⚠ ไม่พบ JSON: {text[:100]}")
                if attempt < max_retries - 1:
                    time.sleep(5)
                    continue
                return {"updated": False, "detail": "ไม่สามารถแปลงผลลัพธ์ได้", "version": ""}

        except Exception as e:
            err_str = str(e)
            wait = 10 * (attempt + 1)
            print(f"  ⚠ Error attempt {attempt+1}/{max_retries}: {err_str[:80]}")

            # Rate limit — รอนานขึ้น
            if "429" in err_str or "quota" in err_str.lower() or "rate" in err_str.lower():
                wait = 30 * (attempt + 1)
                print(f"  Rate limit — พัก {wait}s...")

            if attempt < max_retries - 1:
                time.sleep(wait)
            else:
                return {"updated": False, "detail": f"ไม่สามารถตรวจสอบได้: {err_str[:60]}", "version": "error"}

def check_regulations():
    print(f"เริ่มตรวจสอบวันที่: {date.today()}")
    print(f"{'='*50}")
    results = []
    has_updates = False
    error_names = []

    for i, source in enumerate(SOURCES):
        print(f"\n[{i+1}/{len(SOURCES)}] กำลังตรวจสอบ: {source['name']}")
        result = check_source(source)
        result["id"]         = source["id"]
        result["name"]       = source["name"]
        result["checked_at"] = str(date.today())
        results.append(result)

        if result.get("version") == "error":
            error_names.append(source["name"])
            print(f"  ✗ ข้าม (บันทึก error ไว้แล้ว)")
        elif result.get("updated"):
            has_updates = True
            print(f"  ✅ พบการเปลี่ยนแปลง: {result.get('detail','')}")
        else:
            print(f"  ✓ ไม่มีการเปลี่ยนแปลง: {result.get('detail','')}")

        # หน่วงระหว่างแต่ละแหล่ง เพื่อหลีกเลี่ยง rate limit
        if i < len(SOURCES) - 1:
            time.sleep(3)

    # โหลด changelog เดิม
    data_file = "data/regulations.json"
    try:
        with open(data_file, encoding="utf-8") as f:
            existing = json.load(f)
        changelog = existing.get("changelog", [])
    except Exception:
        changelog = []

    # สรุปผล
    updated_names = [r["name"] for r in results if r.get("updated")]
    if updated_names:
        summary = "พบการเปลี่ยนแปลง: " + ", ".join(updated_names)
    elif error_names:
        summary = f"ตรวจสอบเสร็จ — ไม่สามารถตรวจสอบได้ {len(error_names)} รายการ"
    else:
        summary = "ตรวจสอบครบทุกรายการ ไม่พบการเปลี่ยนแปลง"

    changelog.insert(0, {
        "date":        str(date.today()),
        "has_updates": has_updates,
        "summary":     summary,
        "errors":      error_names
    })
    changelog = changelog[:20]

    output = {
        "last_checked":   str(date.today()),
        "has_updates":    has_updates,
        "update_summary": summary,
        "error_count":    len(error_names),
        "sources":        results,
        "changelog":      changelog
    }

    os.makedirs("data", exist_ok=True)
    with open(data_file, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"\n{'='*50}")
    print(f"เสร็จสิ้น | มีการอัปเดต: {has_updates} | Error: {len(error_names)}/{len(SOURCES)}")
    print(f"สรุป: {summary}")
    # ไม่ raise error — workflow จะ complete เสมอ

if __name__ == "__main__":
    check_regulations()
