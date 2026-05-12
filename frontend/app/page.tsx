import Link from "next/link";
import AppShell from "@/components/AppShell";

const quickQuestions = [
  "ดีเซลขึ้น 5 บาท กระทบฉันแค่ไหน",
  "ช่องทางเดลิเวอรี่ยังทำกำไรไหม",
  "โปรนี้ยังคุ้มไหม",
  "ต้นทุนฉันแพงตรงไหน",
  "กำไรหายไปตรงไหน",
  "วัตถุดิบไหนแพงที่สุด",
];

const steps = [
  {
    title: "ตั้งค่าร้าน",
    text: "ใส่ประเภทร้าน ช่องทางขาย และเป้ากำไรที่ต้องการ",
    href: "/setup?step=1",
    cta: "ไปตั้งค่าร้าน",
  },
  {
    title: "อัปโหลดใบเสร็จ",
    text: "รวมต้นทุนวัตถุดิบจริงให้ FFIA ใช้วิเคราะห์",
    href: "/setup?step=4",
    cta: "อัปโหลดใบเสร็จ",
  },
  {
    title: "ถาม FFIA Advisor",
    text: "ถามเรื่องราคา โปรโมชัน น้ำมัน และมาร์จิ้นแบบตรงจุด",
    href: "/chat",
    cta: "ถาม FFIA Advisor",
  },
];

const capabilities = [
  {
    title: "Margin Risk",
    text: "เมนูไหนกำไรบาง",
  },
  {
    title: "Delivery GP",
    text: "แพลตฟอร์มไหนกินกำไร",
  },
  {
    title: "Cost Spike",
    text: "วัตถุดิบไหนเริ่มแพง",
  },
  {
    title: "Promo Guard",
    text: "โปรไหนยังคุ้ม",
  },
];

export default function Home() {
  return (
    <AppShell>
      <section className="mx-auto max-w-6xl">
        <div className="grid gap-8 lg:grid-cols-[1.1fr_0.9fr] lg:items-center">
          <div>
            <p className="text-sm font-bold uppercase tracking-[0.18em] text-orange-600">
              Bangkok restaurant decision support
            </p>
            <h1 className="mt-4 max-w-3xl text-4xl font-black leading-tight text-slate-950 sm:text-5xl">
              เห็นต้นทุนจริง ก่อนกำไรหายจากน้ำมัน แพลตฟอร์ม และโปรโมชัน
            </h1>
            <p className="mt-5 max-w-2xl text-lg leading-8 text-slate-600">
              FFIA ช่วยเจ้าของร้านอาหารตัดสินใจจากใบเสร็จ ราคาน้ำมัน GP เดลิเวอรี่ และกฎธุรกิจเดิมของระบบ โดยไม่ต้องเดาสุ่มว่าควรขึ้นราคา ลดโปร หรือแก้ต้นทุนตรงไหนก่อน
            </p>
            <div className="mt-7 flex flex-wrap gap-3">
              <Link
                href="/chat"
                className="rounded-xl bg-orange-600 px-5 py-3 text-sm font-bold text-white shadow-sm transition hover:bg-orange-700"
              >
                เริ่มวิเคราะห์กับ FFIA →
              </Link>
              <Link
                href="/dashboard"
                className="rounded-xl border border-orange-200 bg-white px-5 py-3 text-sm font-bold text-orange-700 transition hover:bg-orange-50"
              >
                ดูแดชบอร์ด
              </Link>
            </div>
          </div>

          <div className="rounded-3xl border border-orange-100 bg-white p-5 shadow-sm">
            <div className="rounded-2xl bg-slate-950 p-5 text-white">
              <p className="text-sm font-semibold text-orange-200">คำถามตัวอย่าง</p>
              <div className="mt-4 space-y-3">
                {quickQuestions.slice(0, 4).map((question) => (
                  <Link
                    key={question}
                    href={`/chat?q=${encodeURIComponent(question)}`}
                    className="block rounded-xl bg-white/10 px-4 py-3 text-sm font-medium transition hover:bg-white/15"
                  >
                    {question}
                  </Link>
                ))}
              </div>
            </div>
          </div>
        </div>

        <div className="mt-10 grid gap-4 md:grid-cols-3">
          {steps.map((step, index) => (
            <Link
              key={step.title}
              href={step.href}
              className="group flex flex-col rounded-2xl border border-orange-100 bg-white p-5 shadow-sm transition hover:border-orange-300 hover:shadow-md"
            >
              <div className="grid h-10 w-10 place-items-center rounded-xl bg-orange-100 text-sm font-black text-orange-700">
                {index + 1}
              </div>
              <h2 className="mt-4 text-lg font-black text-slate-950">{step.title}</h2>
              <p className="mt-2 text-sm leading-6 text-slate-600">{step.text}</p>
              <div className="mt-4">
                <span className="inline-block rounded-lg bg-orange-600 px-4 py-2 text-sm font-bold text-white transition group-hover:bg-orange-700">
                  {step.cta}
                </span>
              </div>
            </Link>
          ))}
        </div>

        <div className="mt-8 rounded-3xl border border-orange-100 bg-white p-5 shadow-sm">
          <h2 className="text-xl font-black text-slate-950">FFIA วิเคราะห์อะไรให้คุณได้บ้าง</h2>
          <p className="mt-2 max-w-3xl text-sm leading-6 text-slate-600">
            จากโปรไฟล์ร้าน ใบเสร็จ และช่องทางขาย FFIA ช่วยแปลข้อมูลต้นทุนเป็นคำแนะนำที่ตัดสินใจได้ทันที
          </p>
          <div className="mt-5 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            {capabilities.map((capability) => (
              <div
                key={capability.title}
                className="rounded-2xl border border-orange-100 bg-orange-50/50 p-4 shadow-sm"
              >
                <p className="text-xs font-black uppercase tracking-[0.14em] text-orange-600">
                  {capability.title}
                </p>
                <p className="mt-2 text-sm font-bold text-slate-800">{capability.text}</p>
              </div>
            ))}
          </div>
        </div>
      </section>
    </AppShell>
  );
}
