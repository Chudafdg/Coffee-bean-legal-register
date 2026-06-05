import json
import os
import time
import re
import urllib.request
import urllib.error
from datetime import date

# ใช้ Google Generative AI REST API โดยตรง (รองรับทุกเวอร์ชัน library)
GEMINI_API_KEY = os.environ["GOOGLE_AI_KEY"]
GEMINI_MODEL = "gemini-2.0-flash"
GEMINI_URL = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent?key={GEMINI_API_KEY}"

SOURCES = [
    {
        "id": "มกษ_5700",
        "name": "มกษ. 5700 กาแฟโรบัสต้า",
        "check_prompt": "ค้นหาข้อมูลจาก ratchakitcha.soc.go.th และ acfs.go.th ว่ามีประกาศกระทรวงเกษตรและสหกรณ์ เรื่อง กำหนดมาตรฐานสินค้าเกษตร มกษ. 5700 กาแฟโรบัสตา ฉบับใหม่หรือแก้ไขหลังจากปี 2561 หรือไม่"
    },
    {
        "id": "สธ_สารพิษ",
        "name": "ประกาศ สธ. สารพิษตกค้าง",
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


def call_gemini(prompt, max_retries=3):
    """เรียก Gemini REST API โดยตรง — รองรับทุกเวอร์ชัน library"""
    payload = json.dumps({
        "contents": [{
            "parts": [{"text": prompt}]
        }],
        "generationConfig": {
            "temperature": 0.1,
            "maxOutputTokens": 512
        }
    }).encode("utf-8")

    for attempt in range(max_retries):
        try:
            req = urllib.request.Request(
                GEMINI_URL,
                data=payload,
                headers={"Content-Type": "application/json"},
                method="POST"
            )
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                # ดึง text จาก response
                text = data["candidates"][0]["content"]["parts"][0]["text"].strip()
                return text

        except urllib.error.HTTPError as e:
            err_body = e.read().decode("utf-8", errors="ignore")
            wait = 15 * (attempt + 1)
            print(f"  ⚠ HTTP {e.code} attempt {attempt+1}/{max_retries}: {err_body[:120]}")
            if e.code == 429:
                wait = 30 * (attempt + 1)
                print(f"  Rate limit — พัก {wait}s...")
            if attempt < max_retries - 1:
                time.sleep(wait)
            else:
                raise

        except Exception as e:
            wait = 10 * (attempt + 1)
            print(f"  ⚠ Error attempt {attempt+1}/{max_retries}: {str(e)[:100]}")
            if attempt < max_retries - 1:
                time.sleep(wait)
            else:
                raise


def check_source(source):
    """ตรวจสอบแหล่งข้อมูลหนึ่งรายการ"""
    full_prompt = f"{SYSTEM_PROMPT}\n\nคำถาม: {source['check_prompt']}"
    try:
        text = call_gemini(full_prompt)

        # ลบ markdown backticks ถ้ามี
        text = re.sub(r"```(?:json)?", "", text).strip()

        # หา JSON
        match = re.search(r"\{[^{}]+\}", text, re.DOTALL)
        if match:
            result = json.loads(match.group())
            result.setdefault("updated", False)
            result.setdefault("detail", "ตรวจสอบเรียบร้อย")
            result.setdefault("version", "")
            return result
        else:
            print(f"  ⚠ ไม่พบ JSON ใน response: {text[:120]}")
            return {"updated": False, "detail": f"ตอบไม่เป็น JSON: {text[:80]}", "version": ""}

    except Exception as e:
        return {
            "updated": False,
            "detail": f"ไม่สามารถตรวจสอบได้: {str(e)[:80]}",
            "version": "error"
        }


def check_regulations():
    print(f"เริ่มตรวจสอบวันที่: {date.today()}")
    print(f"Model: {GEMINI_MODEL}")
    print("=" * 50)

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
            print(f"  ✗ error: {result.get('detail','')}")
        elif result.get("updated"):
            has_updates = True
            print(f"  ✅ พบการเปลี่ยนแปลง: {result.get('detail','')}")
        else:
            print(f"  ✓ ไม่มีการเปลี่ยนแปลง: {result.get('detail','')}")

        # หน่วงเล็กน้อยระหว่างแต่ละรายการ
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

    # สร้าง summary
    updated_names = [r["name"] for r in results if r.get("updated")]
    if updated_names:
        summary = "พบการเปลี่ยนแปลง: " + ", ".join(updated_names)
    elif error_names:
        summary = f"ตรวจสอบเสร็จ — error {len(error_names)}/{len(SOURCES)} รายการ"
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


if error_summary:
        raise RuntimeError(f"แจ้งเตือน: พบข้อผิดพลาดในการตรวจสอบ {len(error_summary)} รายการ")

if __name__ == "__main__":
    check_regulations()
