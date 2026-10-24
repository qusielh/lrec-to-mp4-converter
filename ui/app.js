/* L2M - free edition UI. */
"use strict";

mergeI18n({
  en: {
    subtitle: "Convert Linktivity recordings to MP4",
    "help.intro": "L2M is free for SVU students and anyone who finds it useful.",
    "help.free": "No account, activation, or payment is required. If L2M saves you time, you can support its development or star the project on GitHub.",
    "help.note": "Institutional use and paid support are available separately.",
    "help.supportLink": "Support L2M / GitHub",
    "help.close": "Close"
  },
  ar: {
    "subtitle": "تحويل تسجيلات Linktivity إلى MP4",
    "help.intro": "L2M مجاني لطلاب الجامعة الافتراضية السورية وكل من يحتاجه.",
    "help.free": "لا حاجة إلى حساب أو تفعيل أو دفع. إن وفّر L2M وقتك، يمكنك دعم تطويره أو وضع نجمة للمشروع على GitHub.",
    "help.note": "الاستخدام المؤسسي والدعم المدفوع متاحان بشكل منفصل.",
    "help.supportLink": "دعم L2M / GitHub",
    "help.close": "إغلاق"
  }
});

EDITION.id = "free";

EDITION.bind = function () {
  var site = $("open-site");
  if (site) site.addEventListener("click", onOpenSite);
};

EDITION.onBoot = function () {};
