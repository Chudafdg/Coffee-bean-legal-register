import anthropic
import json
import os
import time
from datetime import date

client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

SOURCES = [
    {
        "id": "มกษ_5700",
        "name": "มกษ. 5700 กาแฟโรบัสต้า",
        "check_prompt": "ค้นหาว่ามีประกาศกระทรวงเกษตรและสหกรณ์ เรื่อง กำหนดมาตรฐานสินค้าเกษตร มกษ. 5700 กาแฟโรบัสตา ฉบับใหม่หรือการแก้ไขหลังจากปี 2561 หรือไม่ ค้นหาใน ratchakitcha.soc.go.th และ acfs.go.th"
    },
    {
        "id": "สธ_สารพิษ_460",
        "name": "ประกาศ สธ. ฉ.460 สารพิษตกค้าง",
        "check_prompt": "ค้นหาว่ามีประกาศกระทรวงสาธารณสุข เรื่อง อาหารที่มีสารพิษตกค้าง ฉบับใหม่หลังจากฉบับที่ 460 พ.ศ. 2568 หรือมีการแก้ไขที่เกี่ยวข้องกับกาแฟหรือไม่"
    },
    {
        "id": "สธ_สารปนเปื้อน",
        "name": "ประกาศ สธ. สารปนเปื้อน (OTA/Aflatoxin)",
        "check_prompt": "ค้นหาว่ามีประกาศกระทรวงสาธารณสุข เรื่อง อาหารที่มีสารปนเปื้อน ฉบับใหม่หรือมีการแก้ไขค่า Ochratoxin A หรือ Aflatoxin ในกาแฟหรือไม่ ค้นหาใน food.fda.moph.go.th"
    },
    {
        "id": "codex_cxc27",
        "name": "Codex CXC 27-1981 (SB 07/16)",
        "check_prompt": "Search for the latest status of Codex CXC 27-1981 Code of Practice for Coffee (Green Roasted Soluble). Has the Draft Amendment been officially adopted by CCCF or Codex Alimentarius Commission after 2024? Check fao.org/fao-who-codexalimentarius"
    },
    {
        "id": "codex_stan193",
        "name": "Codex Stan 193 Contaminants",
        "check_prompt": "Search for any revision or amendment to Codex Stan 193 General Standard for Contaminants after the 2023 revision, specifically regarding OTA or Aflatoxin limits in coffee beans. Check fao.org/fao-who-codexalimentarius"
    },
    {
        "id": "codex_cxl",
        "name": "Codex MRL Pesticides in Coffee (CXL)",
        "check_prompt": "Search for any updates to Codex Maximum Residue Limits for pesticides in coffee beans (CXL) after the 2024 update. Check fao.org/pesticide-residues-jmpr-database"
    },
]

def check_source(source, max_retries=3):
    """ตรวจสอบแหล่งข้อมูลโดยใช้ Claude + web search พร้อม retry"""
    for attempt in range(max_retries):
        try:
            response = client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=600,
                tools=[{"type": "web_search_20250305", "name": "web_search"}],
                system="""ตอบเป็น JSON เท่านั้น ไม่มีข้อความอื่น ไม่มี markdown backticks
รูปแบบ: {"updated": true หรือ false, "detail": "รายละเอียดภาษาไทย 1-2 ประโยค", "version": "ฉบับหรือปีที่พบ หรือ '' ถ้าไม่มี"}
updated = true เฉพาะเมื่อพบการเปลี่ยนแปลงจริงหลังจากฉบับที่กำหนด""",
                messages=[{
                    "role": "user",
                    "content": source["check_prompt"]
                }]
            )
            # รวม text จาก content blocks
            text = "".join(
                block.text for block in response.content
                if hasattr(block, "text")
            ).strip()

            # หา JSON ใน response
            import re
            match = re.search(r'\{[^{}]+\}', text, re.DOTALL)
            if match:
                result = json.loads(match.group())
                result.setdefault("updated", False)
                result.setdefault("detail", "ตรวจสอบเรียบร้อย")
                result.setdefault("version", "")
                return result
            else:
                print(f"  ⚠ ไม่พบ JSON ใน response: {text[:100]}")
                return {"updated": False, "detail": "ไม่สามารถแปลงผลลัพธ์ได้", "version": ""}

        except anthropic.APIStatusError as e:
            wait = 10 * (attempt + 1)
            print(f"  ⚠ API error (attempt {attempt+1}/{max_retries}): {e.status_code} — พัก {wait}s...")
            if attempt < max_retries - 1:
                time.sleep(wait)
            else:
                return {"updated": False, "detail": f"API ไม่พร้อมใช้งาน: {e.status_code}", "version": "error"}

        except Exception as e:
            print(f"  ⚠ Error (attempt {attempt+1}/{max_retries}): {e}")
            if attempt < max_retries - 1:
                time.sleep(5)
            else:
                return {"updated": False, "detail": f"เกิดข้อผิดพลาด: {str(e)[:80]}", "version": "error"}

def check_regulations():
    print(f"เริ่มตรวจสอบวันที่: {date.today()}")
    results = []
    has_updates = False
    errors = []

    for source in SOURCES:
        print(f"กำลังตรวจสอบ: {source['name']}")
        result = check_source(source)
        result["id"]   = source["id"]
        result["name"] = source["name"]
        result["checked_at"] = str(date.today())
        results.append(result)

        if result.get("version") == "error":
            errors.append(source["name"])
            print(f"  ✗ ไม่สามารถตรวจสอบได้")
        elif result.get("updated"):
            has_updates = True
            print(f"  ✅ พบการเปลี่ยนแปลง: {result.get('detail','')}")
        else:
            print(f"  ✓ ไม่มีการเปลี่ยนแปลง: {result.get('detail','')}")

        time.sleep(2)  # หน่วงเล็กน้อยระหว่างแต่ละแหล่ง

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
    error_names   = [r["name"] for r in results if r.get("version") == "error"]

    if updated_names:
        summary = "พบการเปลี่ยนแปลง: " + ", ".join(updated_names)
    elif error_names:
        summary = f"ตรวจสอบเสร็จ (ไม่สามารถตรวจสอบได้ {len(error_names)} รายการ: {', '.join(error_names)})"
    else:
        summary = "ไม่พบการเปลี่ยนแปลง"

    # บันทึก changelog
    changelog.insert(0, {
        "date": str(date.today()),
        "has_updates": has_updates,
        "summary": summary,
        "errors": error_names
    })
    changelog = changelog[:20]  # เก็บแค่ 20 รายการล่าสุด

    output = {
        "last_checked": str(date.today()),
        "has_updates": has_updates,
        "update_summary": summary,
        "error_count": len(error_names),
        "sources": results,
        "changelog": changelog
    }

    os.makedirs("data", exist_ok=True)
    with open(data_file, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"\n{'='*50}")
    print(f"ตรวจสอบเสร็จ | อัปเดต: {has_updates} | ข้อผิดพลาด: {len(error_names)}/{len(SOURCES)}")
    print(f"สรุป: {summary}")

    # ไม่ raise error แม้จะมี API error บางรายการ
    # (workflow จะยังคง commit และส่งอีเมลได้)

if __name__ == "__main__":
    check_regulations()
