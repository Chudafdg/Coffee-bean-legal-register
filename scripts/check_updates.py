import os
import json
import time
from datetime import date
from google import genai

# นำกุญแจ API มาใช้งาน
client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])

# ตั้งค่าคีย์เวิร์ดดักจับในราชกิจจานุเบกษา และ Codex
SOURCES = [
    {
        "id": "ราชกิจจา_มาตรฐานกาแฟ",
        "name": "มกษ. 5700 กาแฟโรบัสต้า",
        "prompt": "ค้นหาข้อมูลล่าสุดจากเว็บไซต์ราชกิจจานุเบกษา เกี่ยวกับ 'มาตรฐานสินค้าเกษตร กาแฟ' หรือ 'มกษ. 5700' มีประกาศฉบับใหม่ที่อัปเดตกว่าปี 2561 หรือไม่ ตอบผลลัพธ์สั้นๆ"
    },
    {
        "id": "ราชกิจจา_สธ_สารพิษ",
        "name": "ประกาศ สธ. สารพิษตกค้าง/ปนเปื้อนในกาแฟดิบ",
        "prompt": "ค้นหาข้อมูลล่าสุดจากเว็บไซต์ราชกิจจานุเบกษา เกี่ยวกับ 'ประกาศกระทรวงสาธารณสุข สารพิษตกค้าง' ที่เกี่ยวกับเมล็ดกาแฟ มีฉบับใหม่กว่าปี 2568 หรือไม่ ตอบผลลัพธ์สั้นๆ"
    },
    {
        "id": "codex_cxc27",
        "name": "Codex CXC 27-1981 (SB 07/16)",
        "prompt": "ค้นหาข้อมูลล่าสุดเกี่ยวกับมาตรฐาน Codex 'CXC 27-1981' หรือ 'Code of Practice for the Prevention and Reduction of Ochratoxin A Contamination in Coffee' มีการปรับปรุงฉบับใหม่ (Revision) หรือไม่ ตอบผลลัพธ์สั้นๆ"
    }
]

def check_regulations():
    print(f"เริ่มการตรวจสอบวันที่: {date.today()}")
    results = []
    has_updates = False
    update_summary = []
    error_summary = [] 

    for source in SOURCES:
        print(f"กำลังตรวจสอบ: {source['name']}")
        try:
            # เปลี่ยนมาใช้รุ่น 2.5-flash ซึ่งเป็นรุ่นฟรีตัวล่าสุดและมีความเสถียรที่สุด
            response = client.models.generate_content(
                model='gemini-2.5-flash', 
                contents=f"คุณคือผู้เชี่ยวชาญด้านกฎหมายอาหาร หน้าที่ของคุณคือ: {source['prompt']} \nตอบเฉพาะรูปแบบ JSON เท่านั้น ดังนี้: {{\"updated\": true/false, \"detail\": \"รายละเอียดที่พบ\"}}"
            )
            
            text = response.text.replace("```json", "").replace("```", "").strip()
            data = json.loads(text)
            
            result_entry = {
                "id": source["id"],
                "name": source["name"],
                "status": "success",
                "updated": data.get("updated", False),
                "detail": data.get("detail", "ไม่พบข้อมูลใหม่"),
                "checked_at": str(date.today())
            }
            results.append(result_entry)
            
            if data.get("updated"):
                has_updates = True
                update_summary.append(source["name"])
                
        except Exception as e:
            print(f"พบข้อผิดพลาดกับ {source['name']}: {e}")
            error_summary.append(source["name"])
            
            result_entry = {
                "id": source["id"],
                "name": source["name"],
                "status": "failed",
                "updated": False,
                "detail": f"การตรวจสอบล้มเหลว: จำเป็นต้องตรวจสอบด้วยมนุษย์",
                "checked_at": str(date.today())
            }
            results.append(result_entry)

        # พัก 5 วินาที เพื่อไม่ให้ความเร็วเกินโควต้าที่ระบบตั้งไว้
        print("พัก 5 วินาทีเพื่อป้องกัน Rate Limit...")
        time.sleep(5)

    final_summary = ""
    if has_updates:
        final_summary += "มีการอัปเดต: " + ", ".join(update_summary) + " | "
    if error_summary:
        final_summary += "ตรวจสอบล้มเหลว: " + ", ".join(error_summary)
    if not has_updates and not error_summary:
        final_summary = "ไม่พบการเปลี่ยนแปลง (ระบบทำงานปกติ)"

    output = {
        "last_checked": str(date.today()),
        "has_updates": has_updates,
        "has_errors": len(error_summary) > 0,
        "update_summary": final_summary.strip(" | "),
        "sources": results
    }

    if not os.path.exists('data'):
        os.makedirs('data')

    with open("data/regulations.json", "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
        
    print("ตรวจสอบและบันทึกผลเสร็จสิ้น")

    if error_summary:
        raise RuntimeError(f"แจ้งเตือน: พบข้อผิดพลาดในการตรวจสอบ {len(error_summary)} รายการ")

if __name__ == "__main__":
    check_regulations()
