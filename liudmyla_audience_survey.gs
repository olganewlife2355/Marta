/*
 * ============================================================
 * ОПИТУВАННЯ АУДИТОРІЇ — «ОГРАНКА» та «ДІАНА»
 * Google Apps Script: форма + автоматичні листи + аналітика
 * ============================================================
 *
 * ЩО РОБИТЬ СКРИПТ:
 * 1) setupSurveyForm() — створює Google Форму (22 запитання),
 *    таблицю для відповідей і тригер автоматичної обробки.
 * 2) onFormSubmit(e) — після кожної відповіді:
 *    - записує структуровані дані в аркуш «Аналітика»;
 *    - надсилає персоналізований лист залежно від обраної програми.
 *
 * ЯК ЗАПУСТИТИ:
 * 1. Відкрийте script.google.com → «Новий проєкт».
 * 2. Вставте цей код у Code.gs.
 * 3. У CONFIG нижче замініть плейсхолдери [У КВАДРАТНИХ ДУЖКАХ]
 *    на реальні посилання, дати й підпис.
 * 4. Запустіть setupSurveyForm() (Run) і надайте дозволи
 *    (Forms, Sheets, Gmail).
 * 5. У журналі (Logs) буде посилання на форму — його й публікуємо.
 *
 * ПРИМІТКА: скрипт розрахований на звичайний акаунт @gmail.com,
 * тому email збираємо окремим обов'язковим полем із перевіркою.
 * ============================================================
 */

// =======================================================
// КОНФІГУРАЦІЯ — заповнити перед запуском
// =======================================================

const CONFIG = {
  FORM_TITLE: 'Анкета учасниці | ОГРАНКА та ДІАНА',
  SHEET_TITLE: 'ОГРАНКА_ДІАНА_Відповіді',
  ANALYTICS_SHEET: 'Аналітика',

  // Жодних посилань у листах не публікуємо: і оплату, і домовленість
  // про розмову надсилаємо кожній учасниці особистим повідомленням.

  DATES: {
    ogrankaStart: 'понеділок, 3 серпня 2026',
  },

  PRICES: {
    ogranka: '1500 грн',
    pidpyska: '1500 грн/місяць',
    diana: '15 000 грн за 3 місяці (можлива оплата частинами)',
  },

  SIGNATURE:
    '\n\n—\nЛюдмила Бойко\n' +
    'Instagram: https://www.instagram.com/liudmula_boiko/\n' +
    'Telegram: t.me/liudmula_boiko',
};

// Варіанти відповіді на головне запитання (використовуються
// і у формі, і в обробці — не змінювати лише в одному місці!)
const CHOICE = {
  OGRANKA: '💎 ОГРАНКА — онлайн-марафон, ' + CONFIG.PRICES.ogranka,
  PIDPYSKA: '📱 Підписка — закритий Telegram-канал Людмили Бойко, ' + CONFIG.PRICES.pidpyska,
  FULL: '👑 ДІАНА — програма на 3 місяці, ' + CONFIG.PRICES.diana,
  UNSURE: '🤔 Поки вагаюся — хочу спершу поспілкуватися',
};

// Точні назви запитань (для надійного розбору відповідей)
const Q = {
  name: 'Як тебе звати?',
  email: 'Твій email',
  instagram: 'Твій нік в Instagram',
  telegram: 'Твій нік у Telegram',
  age: 'Скільки тобі років?',
  city: 'З якого ти міста?',

  occupation: 'Чим ти зараз займаєшся?',
  profession: 'Ким працюєш або в якій сфері реалізуєшся?',
  pain: 'У якій сфері життя тобі зараз найбільше «болить»?',
  tried: 'Що ти вже пробувала, щоб змінити ситуацію?',
  missing: 'Чого, на твою думку, тобі не вистачає, щоб дійти до мети?',

  dream: 'Твоя мрія або головна ціль на 2026 рік',
  result3m: 'Що буде для тебе гарним результатом уже через 3 місяці?',

  program: 'Яка програма відгукується тобі найбільше?',
  readiness: 'Коли ти готова почати?',
  budget: 'Який бюджет на власний розвиток для тебе зараз комфортний?',
  obstacles: 'Що може завадити тобі почати?',

  source: 'Звідки ти дізналася про мене?',
  channel: 'Де тобі зручніше спілкуватися?',
  newsletter: 'Хочеш отримувати від мене листи з корисними матеріалами та анонсами?',
  comment: 'Твоє запитання або побажання',

  consent: 'Згода на обробку персональних даних',
};


// =======================================================
// КРОК 1: СТВОРЕННЯ ФОРМИ
// =======================================================

function setupSurveyForm() {
  const form = FormApp.create(CONFIG.FORM_TITLE);
  form.setTitle(CONFIG.FORM_TITLE);
  form.setDescription(
    'Привіт! Я готую нові програми і хочу створити саме те, ' +
    'що потрібно тобі.\n\n' +
    'Ця анкета займе 5–7 хвилин. У відповідь ти отримаєш листа ' +
    'з персональною рекомендацією — яка програма підійде тобі ' +
    'найкраще і з чого почати.'
  );

  // ===== БЛОК 1: ЗНАЙОМСТВО =====
  form.addPageBreakItem()
    .setTitle('Блок 1 із 5: Знайомство');

  form.addTextItem()
    .setTitle(Q.name)
    .setRequired(true);

  const emailItem = form.addTextItem()
    .setTitle(Q.email)
    .setHelpText('Сюди надійде лист із персональною рекомендацією.')
    .setRequired(true);
  emailItem.setValidation(
    FormApp.createTextValidation()
      .setHelpText('Будь ласка, введи коректну email-адресу.')
      .requireTextIsEmail()
      .build()
  );

  form.addTextItem()
    .setTitle(Q.instagram)
    .setHelpText('Наприклад: @tvii_nik — щоб я могла відповісти в дірект.');

  form.addTextItem()
    .setTitle(Q.telegram)
    .setHelpText('Наприклад: @tvii_nik');

  form.addMultipleChoiceItem()
    .setTitle(Q.age)
    .setChoiceValues(['до 25', '26–35', '36–45', '46 і більше'])
    .setRequired(true);

  form.addTextItem()
    .setTitle(Q.city);

  // ===== БЛОК 2: ПРО ТЕБЕ ЗАРАЗ =====
  form.addPageBreakItem()
    .setTitle('Блок 2 із 5: Про тебе зараз')
    .setHelpText('Кілька запитань, щоб я краще зрозуміла твою ситуацію.');

  form.addMultipleChoiceItem()
    .setTitle(Q.occupation)
    .setChoiceValues([
      'Працюю за наймом',
      'Маю власну справу / ФОП',
      'Фриланс',
      'У декреті',
      'У пошуку роботи або себе',
      'Навчаюся',
    ])
    .showOtherOption(true)
    .setRequired(true);

  form.addTextItem()
    .setTitle(Q.profession)
    .setHelpText('Кількома словами: професія, сфера, проєкт.');

  form.addMultipleChoiceItem()
    .setTitle(Q.pain)
    .setChoiceValues([
      'Кар\'єра та самореалізація',
      'Фінанси',
      'Стосунки',
      'Впевненість у собі та самооцінка',
      'Енергія та здоров\'я',
      'Баланс і час для себе',
    ])
    .showOtherOption(true)
    .setRequired(true);

  form.addCheckboxItem()
    .setTitle(Q.tried)
    .setChoiceValues([
      'Читала книжки, слухала подкасти',
      'Проходила курси або марафони',
      'Працювала з психологом / психотерапевтом',
      'Працювала з коучем',
      'Пробувала змінювати все самостійно',
      'Поки нічого не пробувала',
    ])
    .showOtherOption(true)
    .setRequired(true);

  form.addCheckboxItem()
    .setTitle(Q.missing)
    .setChoiceValues([
      'Чіткого плану дій',
      'Знань та інструментів',
      'Підтримки та оточення',
      'Дисципліни й регулярності',
      'Енергії та ресурсу',
      'Віри в себе',
    ])
    .showOtherOption(true)
    .setRequired(true);

  // ===== БЛОК 3: МРІЇ ТА ЦІЛІ =====
  form.addPageBreakItem()
    .setTitle('Блок 3 із 5: Мрії та цілі');

  form.addParagraphTextItem()
    .setTitle(Q.dream)
    .setHelpText('Напиши так, як відчуваєш, — без «правильних» формулювань.')
    .setRequired(true);

  form.addParagraphTextItem()
    .setTitle(Q.result3m)
    .setHelpText('Наприклад: «знайду нову роботу», «почну свою справу», ' +
                 '«перестану відкладати життя на потім».');

  // ===== БЛОК 4: ВИБІР ПРОГРАМИ =====
  form.addPageBreakItem()
    .setTitle('Блок 4 із 5: Вибір програми')
    .setHelpText(
      '💎 ОГРАНКА — груповий онлайн-марафон. Старт, енергія групи, ' +
      'перші відчутні результати. Вартість: ' + CONFIG.PRICES.ogranka + '.\n\n' +
      '📱 Підписка — закритий Telegram-канал Людмили Бойко: практики, ' +
      'ефіри, підтримка щодня. Гнучко і без довгих зобов\'язань. ' +
      'Вартість: ' + CONFIG.PRICES.pidpyska + '.\n\n' +
      '👑 ДІАНА — глибока програма на 3 місяці, персональна робота ' +
      'до результату. Повна вартість: ' + CONFIG.PRICES.diana + '.'
    );

  form.addMultipleChoiceItem()
    .setTitle(Q.program)
    .setChoiceValues([
      CHOICE.OGRANKA,
      CHOICE.PIDPYSKA,
      CHOICE.FULL,
      CHOICE.UNSURE,
    ])
    .setRequired(true);

  form.addMultipleChoiceItem()
    .setTitle(Q.readiness)
    .setChoiceValues([
      'Готова вже зараз',
      'Протягом місяця',
      'За кілька місяців',
      'Поки просто придивляюся',
    ])
    .setRequired(true);

  form.addMultipleChoiceItem()
    .setTitle(Q.budget)
    .setChoiceValues([
      'До 1500 грн',
      '1500–5000 грн',
      '5000–15 000 грн',
      'Понад 15 000 грн',
      'Поки не готова інвестувати',
    ])
    .setRequired(true);

  form.addCheckboxItem()
    .setTitle(Q.obstacles)
    .setChoiceValues([
      'Брак часу',
      'Фінанси',
      'Сумніви або страх',
      'Сімейні обставини',
      'Ніщо — я готова',
    ])
    .showOtherOption(true);

  // ===== БЛОК 5: ЗВ'ЯЗОК =====
  form.addPageBreakItem()
    .setTitle('Блок 5 із 5: Зв\'язок');

  form.addMultipleChoiceItem()
    .setTitle(Q.source)
    .setChoiceValues([
      'Instagram',
      'Telegram',
      'Порекомендувала подруга',
      'YouTube',
      'Побачила рекламу',
    ])
    .showOtherOption(true)
    .setRequired(true);

  form.addMultipleChoiceItem()
    .setTitle(Q.channel)
    .setChoiceValues([
      'Email',
      'Telegram',
      'Instagram (дірект)',
      'Телефоном',
    ])
    .setRequired(true);

  form.addMultipleChoiceItem()
    .setTitle(Q.newsletter)
    .setChoiceValues([
      'Так, хочу',
      'Ні, лише відповідь на цю анкету',
    ])
    .setRequired(true);

  form.addParagraphTextItem()
    .setTitle(Q.comment);

  // ===== ЗГОДА НА ОБРОБКУ ПЕРСОНАЛЬНИХ ДАНИХ =====
  form.addCheckboxItem()
    .setTitle(Q.consent)
    .setHelpText(
      'Твої дані використовуються лише для зв\'язку з тобою щодо ' +
      'програм і не передаються третім особам.'
    )
    .setChoiceValues([
      'Я даю згоду на обробку моїх персональних даних відповідно до ' +
      'Закону України «Про захист персональних даних»',
    ])
    .setRequired(true);

  // ===== ТАБЛИЦЯ ДЛЯ ВІДПОВІДЕЙ =====
  const spreadsheet = SpreadsheetApp.create(CONFIG.SHEET_TITLE);
  form.setDestination(FormApp.DestinationType.SPREADSHEET, spreadsheet.getId());

  // Запам'ятовуємо ID таблиці для onFormSubmit
  PropertiesService.getScriptProperties()
    .setProperty('SPREADSHEET_ID', spreadsheet.getId());

  // ===== ТРИГЕР АВТОМАТИЧНОЇ ОБРОБКИ =====
  ScriptApp.getProjectTriggers().forEach(t => {
    if (t.getHandlerFunction() === 'onFormSubmit') {
      ScriptApp.deleteTrigger(t);
    }
  });
  ScriptApp.newTrigger('onFormSubmit')
    .forForm(form)
    .onFormSubmit()
    .create();

  Logger.log('=== Форму створено ===');
  Logger.log('Посилання для учасниць: ' + form.getPublishedUrl());
  Logger.log('Редагування форми: ' + form.getEditUrl());
  Logger.log('Таблиця з відповідями: ' + spreadsheet.getUrl());

  return {
    formUrl: form.getPublishedUrl(),
    editUrl: form.getEditUrl(),
    sheetUrl: spreadsheet.getUrl(),
  };
}


// =======================================================
// КРОК 2: ОБРОБКА КОЖНОЇ ВІДПОВІДІ
// =======================================================

function onFormSubmit(e) {
  try {
    const data = parseResponse(e);
    Logger.log('Нова відповідь: ' + data.email);

    saveToAnalyticsSheet(data);

    if (data.email) {
      sendPersonalizedEmail(data);
    }

    Logger.log('Оброблено успішно: ' + data.email);
  } catch (err) {
    Logger.log('ПОМИЛКА обробки відповіді: ' + err.message);
  }
}


function parseResponse(e) {
  const itemResponses = e.response.getItemResponses();

  const data = {
    timestamp: e.response.getTimestamp(),
    name: '', email: '', instagram: '', telegram: '',
    age: '', city: '',
    occupation: '', profession: '', pain: '',
    tried: '', missing: '',
    dream: '', result3m: '',
    program: '', readiness: '', budget: '', obstacles: '',
    source: '', channel: '', newsletter: '', comment: '',
    consent: false,
  };

  const asText = a => Array.isArray(a) ? a.join('; ') : String(a || '');

  itemResponses.forEach(ir => {
    const title = ir.getItem().getTitle();
    const answer = ir.getResponse();

    switch (title) {
      case Q.name:       data.name = asText(answer); break;
      case Q.email:      data.email = asText(answer).trim(); break;
      case Q.instagram:  data.instagram = asText(answer); break;
      case Q.telegram:   data.telegram = asText(answer); break;
      case Q.age:        data.age = asText(answer); break;
      case Q.city:       data.city = asText(answer); break;
      case Q.occupation: data.occupation = asText(answer); break;
      case Q.profession: data.profession = asText(answer); break;
      case Q.pain:       data.pain = asText(answer); break;
      case Q.tried:      data.tried = asText(answer); break;
      case Q.missing:    data.missing = asText(answer); break;
      case Q.dream:      data.dream = asText(answer); break;
      case Q.result3m:   data.result3m = asText(answer); break;
      case Q.program:    data.program = asText(answer); break;
      case Q.readiness:  data.readiness = asText(answer); break;
      case Q.budget:     data.budget = asText(answer); break;
      case Q.obstacles:  data.obstacles = asText(answer); break;
      case Q.source:     data.source = asText(answer); break;
      case Q.channel:    data.channel = asText(answer); break;
      case Q.newsletter: data.newsletter = asText(answer); break;
      case Q.comment:    data.comment = asText(answer); break;
      case Q.consent:
        data.consent = Array.isArray(answer) ? answer.length > 0 : !!answer;
        break;
    }
  });

  return data;
}


// =======================================================
// ЗАПИС В АРКУШ «АНАЛІТИКА»
// =======================================================

function saveToAnalyticsSheet(data) {
  const sheetId = PropertiesService.getScriptProperties()
    .getProperty('SPREADSHEET_ID');
  if (!sheetId) {
    Logger.log('SPREADSHEET_ID не знайдено — запустіть setupSurveyForm().');
    return;
  }

  const spreadsheet = SpreadsheetApp.openById(sheetId);
  let sheet = spreadsheet.getSheetByName(CONFIG.ANALYTICS_SHEET);

  if (!sheet) {
    sheet = spreadsheet.insertSheet(CONFIG.ANALYTICS_SHEET);
    sheet.appendRow([
      'Дата', 'Ім\'я', 'Email', 'Instagram', 'Telegram', 'Вік', 'Місто',
      'Зайнятість', 'Професія', 'Де болить', 'Що вже пробувала',
      'Чого бракує', 'Мрія на 2026', 'Результат за 3 місяці',
      'ОБРАНА ПРОГРАМА', 'Готовність', 'Бюджет', 'Перешкоди',
      'Звідки дізналася', 'Канал зв\'язку', 'Розсилка', 'Коментар', 'Згода',
    ]);
    sheet.setFrozenRows(1);
  }

  sheet.appendRow([
    data.timestamp, data.name, data.email, data.instagram, data.telegram,
    data.age, data.city,
    data.occupation, data.profession, data.pain, data.tried,
    data.missing, data.dream, data.result3m,
    data.program, data.readiness, data.budget, data.obstacles,
    data.source, data.channel, data.newsletter, data.comment,
    data.consent ? 'Так' : 'Ні',
  ]);
}


// =======================================================
// ПЕРСОНАЛІЗОВАНІ ЛИСТИ
// =======================================================

function sendPersonalizedEmail(data) {
  const firstName = data.name.split(' ')[0] || 'Привіт';
  let subject = '';
  let body = '';

  if (data.program === CHOICE.OGRANKA) {
    subject = '💎 ОГРАНКА: твоє місце в марафоні';
    body =
      firstName + ', привіт!\n\n' +
      'Дякую за твої відповіді — я їх уважно прочитала.\n\n' +
      'Ти обрала ОГРАНКУ, і це чудовий старт: формат марафону дає ' +
      'енергію групи, чіткий план і перші відчутні результати вже ' +
      'за кілька тижнів.\n\n' +
      'Що на тебе чекає:\n' +
      '• щоденні практики та завдання;\n' +
      '• підтримка групи однодумиць;\n' +
      '• мої розбори та зворотний зв\'язок;\n' +
      '• чіткий результат наприкінці марафону.\n\n' +
      'Вартість: ' + CONFIG.PRICES.ogranka + '\n' +
      'Старт: ' + CONFIG.DATES.ogrankaStart + '\n\n' +
      'Посилання на оплату надішлемо тобі в особистому повідомленні — ' +
      'у Telegram, Instagram або у відповідь на цей лист.\n\n' +
      'Якщо є запитання — просто відпиши на цей лист.';

  } else if (data.program === CHOICE.PIDPYSKA) {
    subject = '📱 Підписка на закритий канал — твій формат';
    body =
      firstName + ', привіт!\n\n' +
      'Дякую за твої відповіді!\n\n' +
      'Ти обрала підписку на мій закритий Telegram-канал — гнучкий ' +
      'формат, який легко вписати навіть у щільний графік.\n\n' +
      'Що всередині каналу:\n' +
      '• регулярні практики та завдання;\n' +
      '• живі ефіри та відповіді на запитання;\n' +
      '• спільнота підтримки;\n' +
      '• усі матеріали під рукою — у зручний для тебе час.\n\n' +
      'Вартість: ' + CONFIG.PRICES.pidpyska + '\n' +
      'Приєднатися можна вже сьогодні: посилання на оформлення підписки ' +
      'надішлемо тобі в особистому повідомленні.\n\n' +
      'Якщо є запитання — просто відпиши на цей лист.';

  } else if (data.program === CHOICE.FULL) {
    subject = '👑 ДІАНА — твої 3 місяці трансформації';
    body =
      firstName + ', привіт!\n\n' +
      'Дякую за відвертість у відповідях — це важливо.\n\n' +
      (data.dream
        ? 'Ти написала про свою мрію на 2026 рік:\n«' + data.dream + '»\n\n' +
          'Програма ДІАНА — саме про те, щоб пройти цей шлях не самій, ' +
          'а з персональним супроводом до результату.\n\n'
        : 'Програма ДІАНА — це глибока персональна робота зі мною ' +
          'до результату.\n\n') +
      'Що на тебе чекає за 3 місяці:\n' +
      '• індивідуальна стратегія під твою ціль;\n' +
      '• регулярні особисті сесії;\n' +
      '• підтримка між сесіями;\n' +
      '• робота до результату, а не «до кінця курсу».\n\n' +
      'Повна вартість: ' + CONFIG.PRICES.diana + '.\n' +
      'Деталі оплати частинами обговоримо особисто.\n\n' +
      'Наступний крок — безплатна консультація, де ми познайомимося ' +
      'і я розповім, як може виглядати твоя програма. Я напишу тобі ' +
      'в особисті повідомлення, і ми домовимося про зручний час.\n\n' +
      'До зустрічі!';

  } else {
    subject = '💬 Допоможу обрати твій формат';
    body =
      firstName + ', привіт!\n\n' +
      'Дякую за твої відповіді!\n\n' +
      'Ти написала, що поки вагаєшся, — і це абсолютно нормально. ' +
      'Обрати формат простіше після короткої розмови.\n\n' +
      'Пропоную безплатну 15-хвилинну розмову: розкажеш про свою ' +
      'ситуацію, а я підкажу, з чого краще почати саме тобі.\n\n' +
      'Я напишу тобі в особисті повідомлення, щоб домовитися про ' +
      'зручний час. Або просто відпиши на цей лист — відповім особисто.';
  }

  body += CONFIG.SIGNATURE;

  MailApp.sendEmail({
    to: data.email,
    subject: subject,
    body: body,
  });
}


// =======================================================
// ТЕСТ ЛИСТА (надсилає приклад на вашу адресу)
// =======================================================

function testEmail() {
  sendPersonalizedEmail({
    name: 'Тест',
    email: Session.getActiveUser().getEmail(),
    program: CHOICE.OGRANKA,
    dream: 'Відкрити власну студію',
  });
  Logger.log('Тестовий лист надіслано на ' + Session.getActiveUser().getEmail());
}
