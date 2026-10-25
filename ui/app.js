/* L2M - free edition UI. */
"use strict";

mergeI18n({
  en: {
    subtitle: "Convert Linktivity recordings to MP4",
    "help.intro": "L2M is free for SVU students and personal, noncommercial use.",
    "help.free": "No account, activation, or payment is required. If L2M saves you time, you can support its development or star the project on GitHub.",
    "help.note": "Institutions can open an issue on GitHub for deployment questions.",
    "help.supportLink": "GitHub project",
    "help.close": "Close",
    "support": "Support",
    "support.title": "Support L2M",
    "support.intro": "L2M is free and stays free. Want to help keep it going? A small donation is optional, and it does not unlock anything.",
    "support.methods": "You can use Sham Cash or Solana. Copy an address below, or open the support page for QR codes.",
    "support.sham": "Sham Cash",
    "support.solana": "Solana",
    "support.copy": "Copy",
    "support.copied": "Address copied",
    "support.open": "Open support page",
    "support.star": "Star on GitHub",
    "support.share": "Share L2M",
    "support.later": "Maybe later",
    "support.note": "No pressure. Starring the repository or sharing L2M with a classmate helps just as much.",
    "support.shareText": "L2M converts Linktivity .lrec lectures to MP4. Free for SVU students and personal use:",
    "support.shareCopied": "Link copied — share it anywhere"
  },
  ar: {
    "subtitle": "تحويل تسجيلات Linktivity إلى MP4",
    "help.intro": "L2M مجاني لطلاب الجامعة الافتراضية السورية والاستخدام الشخصي غير التجاري.",
    "help.free": "لا حاجة إلى حساب أو تفعيل أو دفع. إن وفّر L2M وقتك، يمكنك دعم تطويره أو وضع نجمة للمشروع على GitHub.",
    "help.note": "يمكن للمؤسسات فتح مشكلة على GitHub للاستفسار عن النشر.",
    "help.supportLink": "صفحة المشروع على GitHub",
    "help.close": "إغلاق",
    "support": "دعم",
    "support.title": "ادعم L2M",
    "support.intro": "L2M مجاني وسيبقى مجانيًا. هل ترغب في المساعدة في استمراره؟ المساهمة صغيرة وطوعية، ولا تفتح أي ميزات إضافية.",
    "support.methods": "يمكنك استخدام شام كاش أو سولانا. انسخ العنوان من الأسفل، أو افتح صفحة الدعم لرموز QR.",
    "support.sham": "شام كاش",
    "support.solana": "سولانا",
    "support.copy": "نسخ",
    "support.copied": "تم نسخ العنوان",
    "support.open": "فتح صفحة الدعم",
    "support.star": "نجمة على GitHub",
    "support.share": "شارك L2M",
    "support.later": "لاحقًا",
    "support.note": "لا ضغط. وضع نجمة على المستودع أو مشاركة L2M مع زميل يساعد أيضًا.",
    "support.shareText": "L2M يحوّل محاضرات Linktivity بصيغة .lrec إلى MP4. مجاني لطلاب الجامعة الافتراضية السورية والاستخدام الشخصي:",
    "support.shareCopied": "تم نسخ الرابط — شاركه أينما شئت"
  }
});

EDITION.id = "free";

EDITION.bind = function () {
  var site = $("open-site");
  if (site) site.addEventListener("click", onOpenSite);
};

EDITION.onBoot = function () {};
