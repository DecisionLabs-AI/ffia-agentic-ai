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
    href: "/setup",
    cta: "ไปตั้งค่าร้าน",
  },
  {
    title: "อัปโหลดใบเสร็จ",
    text: "รวมต้นทุนวัตถุดิบจริงให้ FFIA ใช้วิเคราะห์",
    href: "/setup?step=upload",
    cta: "อัปโหลดใบเสร็จ",
  },
  {
    title: "ถาม FFIA",
    text: "ถามเรื่องราคา โปรโมชัน น้ำมัน และมาร์จิ้นแบบตรงจุด",
    href: "/chat",
    cta: "ถาม FFIA ตอนนี้",
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
                ถาม FFIA ตอนนี้
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
          <h2 className="text-xl font-black text-slate-950">ทางลัดสำหรับเดโม</h2>
          <div className="mt-4 flex flex-wrap gap-3">
            {quickQuestions.map((question) => (
              <Link
                key={question}
                href={`/chat?q=${encodeURIComponent(question)}`}
                className="rounded-full border border-orange-200 bg-orange-50 px-4 py-2 text-sm font-semibold text-orange-800 transition hover:border-orange-300 hover:bg-orange-100"
              >
                {question}
              </Link>
            ))}
          </div>
        </div>
      </section>
    </AppShell>
  );
}
