# SPECTRA 3.2 — دليل تجربة المستخدم

## الجديد

- **فهم المنطقة:** اختر منطقة من الخريطة أو القائمة العربية لترى اتجاه التغير، المساحة، مؤشر جودة القياس، تواريخ التصوير، السكان المقدّرين والمباني والطرق المتقاطعة، وملفات الأدلة.
- **الأولوية:** تقاطع موجب مع سكان مقدّرين أو أصول يعطي أولوية مراجعة التعرض؛ مؤشر أقل من 0.5 يعطي أولوية فحص الجودة؛ غير ذلك مراجعة عادية. ليست هذه الأولويات إنذارات خطر مؤكدة.
- **التنبيهات:** المساحة ≥ 1000 م² ومؤشر الجودة ≥ 0.5 يولدان تنبيه مراجعة. التقاطع الموجب يولد تنبيه تعرض؛ نقص التغطية أو اختلاف المعالجة يولدان تنبيه جودة. الحدود قواعد تجريبية معلنة وليست حدودًا علمية معتمدة. التنبيهات داخل التطبيق فقط.
- **تمت المراجعة:** يسجل الزر الاطلاع على التنبيه في SQLite ويبقى بعد إعادة التشغيل؛ لا يؤكد الحدث ولا يحذف التنبيه. الطلب مقيّد بمالك التحليل ومتكرر بأمان.
- **المقارنة:** اختر تحليلًا مكتملًا آخر. تعرض المقارنة تواريخ الصور وإعداد الشاشة وفرق المساحة والبكسلات ونسبة تداخل البصمتين. التحليلان لنفس الصور يظهران بوضوح كمقارنة معالجة لا كتطور زمني. يلزم تطابق الحساس والاستقطاب وتقارب نطاق المنطقة بنسبة 99%؛ هذا فحص توافق أولي وليس شهادة محاذاة.
- **التقرير:** زر «تنزيل تقرير للمشاركة» ينتج HTML مستقلًا يحتوي الصور والخريطة التخطيطية والنتائج والتنبيهات والمصدر والبصمات. افتحه في المتصفح واستخدم الطباعة للحفظ PDF. لا توجد خدمات خارجية أو إرسال تلقائي للتقرير.

## الاستخدام

شغّل المشروع بالطريقة المعتادة. اختر `nisar-oct2026-ghsl2025` ثم Run analysis. بعد اكتمال التحليل انزل إلى «ماذا تغيّر، وما الخطوة التالية؟». يمكن قراءة النتائج القديمة التي تتضمن Phase 3 دون إعادة تشغيلها. إنشاء تحليل بالشاشة الأوسع يسمح بمقارنة الإعدادات على نفس الصور؛ إضافة زوج آخر هي ما يضيف رصدًا جديدًا عبر الزمن.

## البيانات المطلوبة لاحقًا

وظائف التفسير والتنبيه والمقارنة والتقرير تعمل على الملفات الحالية. قياس حركة الجليد لم ينفذ لأن ملفات GCOV الحالية لا تحتوي إزاحة GOFF: المطلوب منتج GOFF لنفس منطقة الدراسة مع طبقات الجودة ووحدات القياس وتواريخ الصورة المرجعية والثانوية. سيحتاج هذا إلى مسار استيراد وفلترة وتحويل إزاحة إلى سرعة بعد فحص الملف؛ لا توجد سرعات مختلقة أو عرض وهمي لهذه الوظيفة.

تأكيد أن التغير فيضان وقياس الدقة ومعايرة الاحتمالات يحتاج مرجع تغير مستقلًا موافقًا للحدث. الطبقات الحالية لا تؤكد اكتمال الطرق والمباني. هذه الحالات ظاهرة في النتائج ولا تمنع تشغيل التطبيق.

## Technical contract and validation

The existing `/api/v1/phase2` namespace remains compatible. Added owner-scoped endpoints:

- `GET /jobs/{id}/insights`: deterministic Arabic explanations, priority reasons and alerts derived from hash-verified run artifacts.
- `PUT /jobs/{id}/alerts/{alert_id}/review`: persistent, idempotent review acknowledgement, validated against actual alerts.
- `GET /jobs/{id}/compare/{other_id}`: equal-area footprint comparison; both jobs must belong to the caller and be complete. Same-pair detection compares actual SAR bytes. Footprint IoU compares any change, not signed-class agreement.
- `GET /jobs/{id}/report`: self-contained, HTML-escaped report with embedded images and SVG; verifies required artifacts before generating the response.

Existing jobs/result columns remain unchanged. An additive `alert_reviews` table is created automatically; no destructive migration. Report and insight outputs are generated on demand using the current application code and original pinned artifacts; they are not frozen historical model predictions. Policy version is included in insights.

37 Phase 2/3 tests passed, including ownership, acknowledgement persistence/idempotency, report content, tamper rejection, identical-image comparison and different-AOI rejection. Current browser checks exercised region selection, same-pair comparison, Arabic rendering and successful HTML report download. See `reports/phase3.2-tests.log` and XML. Existing inherited Phase 1/backend failures documented in `reports/PHASE3-VALIDATION.md` were not changed by this feature release. No operational hazard or glacier-velocity validation is claimed.
