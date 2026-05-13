/**
 * ════════════════════════════════════════════════════════════════
 *  ПСИХОЛОГІЧНЕ ДОСЛІДЖЕННЯ ПОДРУЖНІХ СТОСУНКІВ
 *  Автоматична генерація кодів пар + сольний режим
 * ════════════════════════════════════════════════════════════════
 *
 *  ПОРЯДОК НАЛАШТУВАННЯ:
 *    1. Замініть увесь код у редакторі на цей файл
 *    2. Запустіть step1_CreateBase
 *    3. Запустіть step2_AddFemale, потім step3_AddMale
 *    4. Запустіть step4_LinkSpreadsheet  ← створює таблицю відповідей
 *    5. Запустіть logEntryIds — для перевірки entry IDs
 *    6. Опублікуйте Web App: Розгорнути → Новий розгортання →
 *       Тип: Web App → Виконувати як: Я → Доступ: Усі
 *
 *  ДЕ БАЧИТИ ВІДПОВІДІ:
 *    • showCounters()       — статистика у Logs
 *    • openResponsesSheet() — URL Google Sheets з відповідями
 *    • Або відкрийте форму → вкладка «Відповіді»
 * ════════════════════════════════════════════════════════════════
 */


// ════════════════════════════════════════════════════════════════
//  КОНСТАНТИ — заповнюються після запуску logEntryIds()
// ════════════════════════════════════════════════════════════════
var FORM_URL_BASE  = '';
var ENTRY_PAIR_CODE = '';
var ENTRY_GENDER    = '';


// ════════════════════════════════════════════════════════════════
//  КРОК 1: Демографія + SPANE
// ════════════════════════════════════════════════════════════════
function step1_CreateBase() {
  Logger.log('⏳ КРОК 1: Створюємо форму...');

  var form = FormApp.create('Психологічне дослідження подружніх стосунків');

  form.setDescription(
    '⚠️ ЦЕ ОПИТУВАННЯ ПРИЗНАЧЕНЕ ДЛЯ ПОДРУЖНІХ ПАР (можна й одному).\n' +
    'Якщо є можливість — кожен із партнерів заповнює форму ОКРЕМО.\n\n' +
    '🔑 КОД:\n' +
    'Перед початком ви отримаєте унікальний код і посилання. ' +
    'Код буде заповнений автоматично. Опитування є анонімним.\n\n' +
    '📋 СКЛАД ДОСЛІДЖЕННЯ:\n' +
    '1. SPANE — оцінка емоційного благополуччя\n' +
    '2. Характер взаємодії подружжя в конфліктних ситуаціях\n' +
    '3. РОД — рольові очікування і домагання у шлюбі\n\n' +
    'Заповнення займе орієнтовно 20–30 хвилин.'
  );
  form.setCollectEmail(false);
  form.setShowLinkToRespondAgain(false);
  form.setConfirmationMessage(
    'Дякуємо за участь у дослідженні!\n' +
    'Якщо ваш партнер теж бере участь — нагадайте йому заповнити форму за своїм посиланням.'
  );

  form.addSectionHeaderItem()
    .setTitle('Розділ 1. Загальні відомості');

  var pairCodeItem = form.addTextItem()
    .setTitle('🔑 Код пари')
    .setHelpText(
      'Цей код згенеровано автоматично. Не змінюйте його. ' +
      'Для парної участі код починається з "P-", для індивідуальної — з "S-".'
    )
    .setRequired(true);

  form.addTextItem()
    .setTitle('Ваш вік (повних років)')
    .setRequired(true);

  form.addMultipleChoiceItem()
    .setTitle('Ваш сімейний стан')
    .setChoiceValues([
      'Одружений / Заміжня (офіційний шлюб)',
      'У стосунках (цивільний шлюб)',
      'Розлучений / Розлучена',
      'Вдівець / Вдова',
      'Не одружений / Не заміжня'
    ])
    .setRequired(true);

  form.addMultipleChoiceItem()
    .setTitle('Тривалість шлюбу або стосунків')
    .setChoiceValues([
      'Менше 1 року', '1–3 роки', '4–7 років', '8–15 років', 'Більше 15 років'
    ])
    .setRequired(true);

  form.addMultipleChoiceItem()
    .setTitle('Чи є у вас діти?')
    .setChoiceValues(['Так', 'Ні', 'Очікуємо'])
    .setRequired(true);

  form.addSectionHeaderItem()
    .setTitle('Розділ 2. Шкала переживань (SPANE)')
    .setHelpText(
      'Автори: Diener E. et al. (2010). ' +
      'Укр. адаптація: Олефір В. О., Боснюк В. Ф., Малофейкіна К. О. (2021).\n\n' +
      'Вкажіть, якою мірою ви відчували себе так ПРОТЯГОМ ОСТАННІХ 4 ТИЖНІВ.\n' +
      '1 = Дуже рідко або ніколи   →   5 = Дуже часто або завжди'
    );

  var spaneItems = [
    'Позитивно', 'Негативно', 'Добре', 'Погано',
    'Приємно', 'Неприємно',
    'Щасливим (щасливою)', 'Засмученим (засмученою)',
    'Наляканим (наляканою)', 'Радісним (радісною)',
    'Роздратованим (роздратованою)', 'Задоволеним (задоволеною)'
  ];

  for (var i = 0; i < spaneItems.length; i++) {
    form.addScaleItem()
      .setTitle((i + 1) + '. Я відчував(ла) себе: ' + spaneItems[i])
      .setBounds(1, 5)
      .setLabels('Дуже рідко або ніколи', 'Дуже часто або завжди')
      .setRequired(true);
  }

  form.addSectionHeaderItem()
    .setTitle('Визначення варіанту опитувальника')
    .setHelpText('Оберіть вашу стать — форма автоматично відкриє відповідний варіант.');

  var genderItem = form.addMultipleChoiceItem()
    .setTitle('Ваша стать')
    .setChoiceValues(['Жіноча', 'Чоловіча'])
    .setRequired(true);

  var props = PropertiesService.getScriptProperties();
  props.setProperty('FORM_ID', form.getId());
  props.setProperty('GENDER_Q_ID', String(genderItem.getId()));
  props.setProperty('PAIR_CODE_ITEM_ID', String(pairCodeItem.getId()));
  props.setProperty('FORM_URL', form.getPublishedUrl());
  props.setProperty('PAIR_COUNTER', '0');
  props.setProperty('SOLO_COUNTER', '0');

  Logger.log('✅ КРОК 1 ГОТОВО.');
  Logger.log('Форма ID: ' + form.getId());
  Logger.log('➡️  Запустіть step2_AddFemale, потім step3_AddMale,');
  Logger.log('    потім step4_LinkSpreadsheet, потім logEntryIds()');
}


// ════════════════════════════════════════════════════════════════
//  КРОК 4: Прив'язка Google Sheets для збору відповідей
// ════════════════════════════════════════════════════════════════
function step4_LinkSpreadsheet() {
  Logger.log('⏳ КРОК 4: Прив\'язуємо Google Sheets для відповідей...');

  var props = PropertiesService.getScriptProperties();
  var formId = props.getProperty('FORM_ID');
  if (!formId) {
    Logger.log('❌ ПОМИЛКА: Спочатку запустіть step1_CreateBase!');
    return;
  }

  var form = FormApp.openById(formId);

  var existingDestId = null;
  try { existingDestId = form.getDestinationId(); } catch (e) {}

  if (existingDestId) {
    var existing = SpreadsheetApp.openById(existingDestId);
    props.setProperty('RESPONSES_SHEET_ID', existing.getId());
    props.setProperty('RESPONSES_SHEET_URL', existing.getUrl());
    Logger.log('ℹ️ Форма вже прив\'язана до таблиці:');
    Logger.log('🔗 ' + existing.getUrl());
    return existing.getUrl();
  }

  var ss = SpreadsheetApp.create('Відповіді — Подружні стосунки');
  form.setDestination(FormApp.DestinationType.SPREADSHEET, ss.getId());

  props.setProperty('RESPONSES_SHEET_ID', ss.getId());
  props.setProperty('RESPONSES_SHEET_URL', ss.getUrl());

  Logger.log('✅ КРОК 4 ГОТОВО!');
  Logger.log('🔗 Таблиця відповідей: ' + ss.getUrl());
  Logger.log('Тепер кожна нова відповідь автоматично потрапляє у цю таблицю.');
  Logger.log('Знайти її також можна на drive.google.com за назвою');
  Logger.log('«Відповіді — Подружні стосунки».');

  return ss.getUrl();
}


// ════════════════════════════════════════════════════════════════
//  ДОПОМІЖНІ: Статистика і швидкий доступ до відповідей
// ════════════════════════════════════════════════════════════════
function showCounters() {
  var p = PropertiesService.getScriptProperties();
  Logger.log('═══ Статистика ChromaFit ═══');
  Logger.log('Видано кодів пар (P-XXX): ' + (p.getProperty('PAIR_COUNTER') || '0'));
  Logger.log('Видано соло-кодів (S-XXX): ' + (p.getProperty('SOLO_COUNTER') || '0'));

  var sheetId = p.getProperty('RESPONSES_SHEET_ID');
  if (sheetId) {
    try {
      var ss = SpreadsheetApp.openById(sheetId);
      var sheet = ss.getSheets()[0];
      var rowCount = Math.max(0, sheet.getLastRow() - 1);
      Logger.log('Заповнено форм усього: ' + rowCount);
      Logger.log('🔗 Відповіді: ' + ss.getUrl());
    } catch (e) {
      Logger.log('⚠️ Не вдалося прочитати таблицю: ' + e.message);
    }
  } else {
    Logger.log('⚠️ Таблицю відповідей ще не створено.');
    Logger.log('   Запустіть step4_LinkSpreadsheet()');
  }
}

function openResponsesSheet() {
  var p = PropertiesService.getScriptProperties();
  var url = p.getProperty('RESPONSES_SHEET_URL');
  if (url) {
    Logger.log('🔗 Відповіді (Google Sheets):');
    Logger.log(url);
  } else {
    Logger.log('⚠️ Таблицю ще не створено. Запустіть step4_LinkSpreadsheet()');
  }
}


// ════════════════════════════════════════════════════════════════
//  ДОПОМІЖНА: Entry IDs для pre-fill URL
// ════════════════════════════════════════════════════════════════
function logEntryIds() {
  var props = PropertiesService.getScriptProperties();
  var formId = props.getProperty('FORM_ID');
  var form = FormApp.openById(formId);
  var items = form.getItems();

  Logger.log('=== Entry IDs для pre-fill URL ===');
  Logger.log('Форма URL: ' + form.getPublishedUrl());
  Logger.log('');

  for (var i = 0; i < items.length; i++) {
    var item = items[i];
    var title = item.getTitle();
    if (title.indexOf('Код пари') !== -1 ||
        title.indexOf('стать') !== -1 ||
        title.indexOf('Стать') !== -1) {
      Logger.log('Поле: "' + title + '"');
      Logger.log('  entry ID: entry.' + item.getId());
      Logger.log('');
    }
  }

  for (var j = 0; j < items.length; j++) {
    var it = items[j];
    if (it.getTitle().indexOf('Код пари') !== -1) {
      props.setProperty('ENTRY_PAIR_CODE', String(it.getId()));
      Logger.log('ENTRY_PAIR_CODE saved: ' + it.getId());
    }
    if (it.getTitle().indexOf('стать') !== -1 || it.getTitle().indexOf('Стать') !== -1) {
      props.setProperty('ENTRY_GENDER', String(it.getId()));
      Logger.log('ENTRY_GENDER saved: ' + it.getId());
    }
  }

  Logger.log('✅ Entry IDs збережено. Тепер можна публікувати Web App.');
}


// ════════════════════════════════════════════════════════════════
//  WEB APP — точка входу для респондентів
// ════════════════════════════════════════════════════════════════
function generatePairCode() {
  var props = PropertiesService.getScriptProperties();
  var lock = LockService.getScriptLock();
  lock.waitLock(10000);

  try {
    var counter = parseInt(props.getProperty('PAIR_COUNTER') || '0') + 1;
    props.setProperty('PAIR_COUNTER', String(counter));
    return 'P-' + ('000' + counter).slice(-3);
  } finally {
    lock.releaseLock();
  }
}

function generateSoloCode() {
  var props = PropertiesService.getScriptProperties();
  var lock = LockService.getScriptLock();
  lock.waitLock(10000);

  try {
    var counter = parseInt(props.getProperty('SOLO_COUNTER') || '0') + 1;
    props.setProperty('SOLO_COUNTER', String(counter));
    return 'S-' + ('000' + counter).slice(-3);
  } finally {
    lock.releaseLock();
  }
}

function buildFormUrl(pairCode, gender) {
  var props = PropertiesService.getScriptProperties();
  var baseUrl = props.getProperty('FORM_URL');
  var entryCode = props.getProperty('ENTRY_PAIR_CODE');
  var entryGender = props.getProperty('ENTRY_GENDER');

  if (!baseUrl || !entryCode || !entryGender) {
    return null;
  }

  return baseUrl +
    '?usp=pp_url' +
    '&entry.' + entryCode + '=' + encodeURIComponent(pairCode) +
    '&entry.' + entryGender + '=' + encodeURIComponent(gender);
}

function doGet(e) {
  var props = PropertiesService.getScriptProperties();

  if (!props.getProperty('FORM_URL') || !props.getProperty('ENTRY_PAIR_CODE')) {
    return HtmlService.createHtmlOutput(
      '<h2>⚙️ Форму ще налаштовують</h2>' +
      '<p>Будь ласка, зверніться до дослідника.</p>'
    );
  }

  var action = e.parameter.action;

  if (action === 'start') {
    var gender = e.parameter.gender;
    var pairCode = generatePairCode();

    var myGender    = (gender === 'female') ? 'Жіноча'   : 'Чоловіча';
    var partGender  = (gender === 'female') ? 'Чоловіча' : 'Жіноча';
    var myLabel     = (gender === 'female') ? '👩 Жіночий варіант'   : '👨 Чоловічий варіант';
    var partLabel   = (gender === 'female') ? '👨 Чоловічий варіант' : '👩 Жіночий варіант';

    var myUrl   = buildFormUrl(pairCode, myGender);
    var partUrl = buildFormUrl(pairCode, partGender);

    return HtmlService.createHtmlOutput(buildSuccessPage(pairCode, myLabel, partLabel, myUrl, partUrl))
      .setTitle('Ваші посилання на опитування')
      .setXFrameOptionsMode(HtmlService.XFrameOptionsMode.ALLOWALL);
  }

  if (action === 'solo') {
    var gSolo = e.parameter.gender;
    var soloCode = generateSoloCode();

    var soloGender = (gSolo === 'female') ? 'Жіноча' : 'Чоловіча';
    var soloLabel  = (gSolo === 'female') ? '👩 Жіночий варіант' : '👨 Чоловічий варіант';
    var soloUrl    = buildFormUrl(soloCode, soloGender);

    return HtmlService.createHtmlOutput(buildSoloSuccessPage(soloCode, soloLabel, soloUrl))
      .setTitle('Ваше посилання на опитування')
      .setXFrameOptionsMode(HtmlService.XFrameOptionsMode.ALLOWALL);
  }

  return HtmlService.createHtmlOutput(buildLandingPage())
    .setTitle('Психологічне дослідження — Початок')
    .setXFrameOptionsMode(HtmlService.XFrameOptionsMode.ALLOWALL);
}

function buildLandingPage() {
  var scriptUrl = ScriptApp.getService().getUrl();
  return '<!DOCTYPE html><html lang="uk"><head>' +
  '<meta charset="UTF-8">' +
  '<meta name="viewport" content="width=device-width, initial-scale=1">' +
  '<title>Психологічне дослідження подружніх стосунків</title>' +
  '<style>' +
    'body{font-family:Georgia,serif;background:#f5f0eb;margin:0;padding:20px;' +
         'display:flex;justify-content:center;align-items:center;min-height:100vh;box-sizing:border-box}' +
    '.card{background:#fff;border-radius:16px;padding:40px 36px;max-width:560px;width:100%;' +
          'box-shadow:0 4px 24px rgba(0,0,0,.10);text-align:center}' +
    'h1{color:#2c3e50;font-size:1.5em;margin-bottom:8px}' +
    '.subtitle{color:#7f8c8d;font-size:.95em;margin-bottom:28px;line-height:1.6}' +
    '.info-box{background:#eaf4fb;border-left:4px solid #3498db;border-radius:8px;' +
              'padding:16px 18px;text-align:left;margin-bottom:28px;font-size:.9em;line-height:1.7;color:#2c3e50}' +
    '.info-box strong{color:#2980b9}' +
    'p.question{font-size:1.05em;font-weight:bold;color:#2c3e50;margin:24px 0 14px}' +
    '.btn-row{display:flex;gap:16px;justify-content:center;flex-wrap:wrap}' +
    '.btn{display:inline-block;padding:14px 28px;border-radius:50px;font-size:1em;' +
         'font-weight:bold;text-decoration:none;cursor:pointer;border:none;transition:.2s}' +
    '.btn-female{background:#e8748a;color:#fff}' +
    '.btn-female:hover{background:#d45f75;transform:translateY(-2px)}' +
    '.btn-male{background:#5b8dee;color:#fff}' +
    '.btn-male:hover{background:#4070d4;transform:translateY(-2px)}' +
    '.btn-solo-female{background:transparent;color:#d45f75;border:2px solid #e8748a}' +
    '.btn-solo-female:hover{background:#fde8ec}' +
    '.btn-solo-male{background:transparent;color:#4070d4;border:2px solid #5b8dee}' +
    '.btn-solo-male:hover{background:#e8f0fd}' +
    '.divider{display:flex;align-items:center;margin:28px 0 8px;color:#bbb;font-size:.8em;' +
             'text-transform:uppercase;letter-spacing:1px}' +
    '.divider::before,.divider::after{content:"";flex:1;height:1px;background:#e0e0e0}' +
    '.divider span{padding:0 12px}' +
    '.solo-note{font-size:.85em;color:#7f8c8d;margin-bottom:14px;line-height:1.5}' +
    '.note{margin-top:24px;font-size:.82em;color:#aaa;line-height:1.5}' +
  '</style></head><body>' +
  '<div class="card">' +
    '<h1>🔬 Психологічне дослідження<br>подружніх стосунків</h1>' +
    '<p class="subtitle">Участь анонімна. Заповнення займе ~20–30 хвилин.</p>' +
    '<div class="info-box">' +
      '<strong>📋 Як це працює:</strong><br>' +
      '1. Оберіть свою стать нижче<br>' +
      '2. Отримаєте <strong>посилання з pre-filled кодом</strong><br>' +
      '3. Парно — по одному посиланню кожному партнеру; самостійно — одне посилання тільки вам<br>' +
      '4. Код генерується <strong>автоматично</strong> — нічого вигадувати не треба' +
    '</div>' +
    '<p class="question">Разом з партнером</p>' +
    '<div class="btn-row">' +
      '<a class="btn btn-female" href="' + scriptUrl + '?action=start&gender=female">👩 Жінка</a>' +
      '<a class="btn btn-male"   href="' + scriptUrl + '?action=start&gender=male">👨 Чоловік</a>' +
    '</div>' +
    '<div class="divider"><span>або</span></div>' +
    '<p class="question">Самостійно, без партнера</p>' +
    '<p class="solo-note">Ви зможете надіслати свої відповіді, не чекаючи, поки партнер заповнить форму.</p>' +
    '<div class="btn-row">' +
      '<a class="btn btn-solo-female" href="' + scriptUrl + '?action=solo&gender=female">👩 Тільки я (жінка)</a>' +
      '<a class="btn btn-solo-male"   href="' + scriptUrl + '?action=solo&gender=male">👨 Тільки я (чоловік)</a>' +
    '</div>' +
    '<p class="note">Це опитування призначено для людей у шлюбі або тривалих стосунках.<br>' +
    'Ваші дані не будуть передані третім особам.</p>' +
  '</div>' +
  '</body></html>';
}

function buildSuccessPage(pairCode, myLabel, partLabel, myUrl, partUrl) {
  return '<!DOCTYPE html><html lang="uk"><head>' +
  '<meta charset="UTF-8">' +
  '<meta name="viewport" content="width=device-width, initial-scale=1">' +
  '<title>Ваші посилання</title>' +
  '<style>' +
    'body{font-family:Georgia,serif;background:#f5f0eb;margin:0;padding:20px;' +
         'display:flex;justify-content:center;min-height:100vh;box-sizing:border-box}' +
    '.card{background:#fff;border-radius:16px;padding:36px;max-width:560px;width:100%;' +
          'box-shadow:0 4px 24px rgba(0,0,0,.10);margin:auto}' +
    'h1{color:#27ae60;font-size:1.3em;text-align:center;margin-bottom:6px}' +
    '.code-box{background:#f0faf4;border:2px solid #27ae60;border-radius:12px;' +
              'text-align:center;padding:16px;margin:20px 0}' +
    '.code-box .label{font-size:.85em;color:#7f8c8d;margin-bottom:4px}' +
    '.code-box .code{font-size:2em;font-weight:bold;color:#27ae60;letter-spacing:4px}' +
    '.link-block{border-radius:12px;padding:20px;margin:16px 0}' +
    '.link-block.mine{background:#e8f4fd;border:1px solid #3498db}' +
    '.link-block.partner{background:#fef9e7;border:1px solid #f39c12}' +
    '.link-block h3{margin:0 0 10px;font-size:1em}' +
    '.link-block.mine h3{color:#2980b9}' +
    '.link-block.partner h3{color:#e67e22}' +
    '.link-url{word-break:break-all;font-size:.78em;color:#555;background:#fff;' +
              'padding:8px 10px;border-radius:6px;margin-bottom:10px;display:block}' +
    '.btn{display:block;width:100%;padding:12px;border-radius:50px;font-size:.95em;' +
         'font-weight:bold;text-decoration:none;text-align:center;border:none;cursor:pointer;' +
         'box-sizing:border-box;transition:.2s}' +
    '.btn-blue{background:#3498db;color:#fff}' +
    '.btn-blue:hover{background:#2980b9}' +
    '.btn-orange{background:#f39c12;color:#fff;margin-top:8px}' +
    '.btn-orange:hover{background:#e67e22}' +
    '.btn-copy{background:#ecf0f1;color:#555;font-size:.85em;padding:9px;margin-top:8px}' +
    '.btn-copy:hover{background:#d5dbdb}' +
    '.note{font-size:.82em;color:#aaa;text-align:center;margin-top:20px;line-height:1.5}' +
    '.success-msg{display:none;color:#27ae60;font-size:.85em;text-align:center;margin-top:6px}' +
  '</style></head><body>' +
  '<div class="card">' +
    '<h1>✅ Ваші посилання готові!</h1>' +
    '<div class="code-box">' +
      '<div class="label">Код вашої пари (вже вбудований у посилання)</div>' +
      '<div class="code">' + pairCode + '</div>' +
    '</div>' +
    '<div class="link-block mine">' +
      '<h3>🔗 Ваше посилання — ' + myLabel + '</h3>' +
      '<span class="link-url" id="myUrl">' + myUrl + '</span>' +
      '<a class="btn btn-blue" href="' + myUrl + '" target="_blank">▶ Розпочати моє опитування</a>' +
    '</div>' +
    '<div class="link-block partner">' +
      '<h3>📤 Посилання для партнера — ' + partLabel + '</h3>' +
      '<span class="link-url" id="partUrl">' + partUrl + '</span>' +
      '<button class="btn btn-copy" onclick="copyPartner()">📋 Скопіювати посилання партнера</button>' +
      '<div class="success-msg" id="copyMsg">✅ Скопійовано! Надішліть партнеру у месенджер.</div>' +
      '<a class="btn btn-orange" href="whatsapp://send?text=' + encodeURIComponent(
        'Привіт! Будь ласка, заповни цю форму для нашого дослідження:\n' + partUrl +
        '\nКод нашої пари: ' + pairCode + ' (вже заповнений автоматично)'
      ) + '">💬 Надіслати партнеру у WhatsApp</a>' +
    '</div>' +
    '<p class="note">⚠️ Збережіть або одразу надішліть посилання партнеру.<br>' +
    'Після закриття цієї сторінки воно не відновлюється.</p>' +
  '</div>' +
  '<script>' +
  'function copyPartner(){' +
    'var url=document.getElementById("partUrl").innerText;' +
    'navigator.clipboard.writeText(url).then(function(){' +
      'document.getElementById("copyMsg").style.display="block";' +
    '});' +
  '}' +
  '</script>' +
  '</body></html>';
}

function buildSoloSuccessPage(soloCode, myLabel, myUrl) {
  return '<!DOCTYPE html><html lang="uk"><head>' +
  '<meta charset="UTF-8">' +
  '<meta name="viewport" content="width=device-width, initial-scale=1">' +
  '<title>Ваше посилання</title>' +
  '<style>' +
    'body{font-family:Georgia,serif;background:#f5f0eb;margin:0;padding:20px;' +
         'display:flex;justify-content:center;min-height:100vh;box-sizing:border-box}' +
    '.card{background:#fff;border-radius:16px;padding:36px;max-width:560px;width:100%;' +
          'box-shadow:0 4px 24px rgba(0,0,0,.10);margin:auto}' +
    'h1{color:#27ae60;font-size:1.3em;text-align:center;margin-bottom:6px}' +
    '.code-box{background:#f0faf4;border:2px solid #27ae60;border-radius:12px;' +
              'text-align:center;padding:16px;margin:20px 0}' +
    '.code-box .label{font-size:.85em;color:#7f8c8d;margin-bottom:4px}' +
    '.code-box .code{font-size:2em;font-weight:bold;color:#27ae60;letter-spacing:4px}' +
    '.link-block{border-radius:12px;padding:20px;margin:16px 0;background:#e8f4fd;border:1px solid #3498db}' +
    '.link-block h3{margin:0 0 10px;font-size:1em;color:#2980b9}' +
    '.link-url{word-break:break-all;font-size:.78em;color:#555;background:#fff;' +
              'padding:8px 10px;border-radius:6px;margin-bottom:10px;display:block}' +
    '.btn{display:block;width:100%;padding:12px;border-radius:50px;font-size:.95em;' +
         'font-weight:bold;text-decoration:none;text-align:center;border:none;cursor:pointer;' +
         'box-sizing:border-box;transition:.2s}' +
    '.btn-blue{background:#3498db;color:#fff}' +
    '.btn-blue:hover{background:#2980b9}' +
    '.info{background:#fff8e1;border-left:4px solid #f39c12;border-radius:8px;' +
          'padding:14px 16px;font-size:.88em;line-height:1.6;color:#6b4e00;margin:16px 0}' +
    '.note{font-size:.82em;color:#aaa;text-align:center;margin-top:20px;line-height:1.5}' +
  '</style></head><body>' +
  '<div class="card">' +
    '<h1>✅ Ваше посилання готове!</h1>' +
    '<div class="code-box">' +
      '<div class="label">Ваш індивідуальний код</div>' +
      '<div class="code">' + soloCode + '</div>' +
    '</div>' +
    '<div class="info">' +
      'Ви проходите дослідження <strong>самостійно</strong>. ' +
      'Ваші відповіді будуть надіслані без очікування партнера.' +
    '</div>' +
    '<div class="link-block">' +
      '<h3>🔗 Ваше посилання — ' + myLabel + '</h3>' +
      '<span class="link-url">' + myUrl + '</span>' +
      '<a class="btn btn-blue" href="' + myUrl + '" target="_blank">▶ Розпочати опитування</a>' +
    '</div>' +
    '<p class="note">⚠️ Збережіть посилання, якщо хочете повернутися пізніше.<br>' +
    'Дякуємо за участь у дослідженні.</p>' +
  '</div>' +
  '</body></html>';
}


// ════════════════════════════════════════════════════════════════
//  КРОК 2: Жіночий варіант опитувальника
// ════════════════════════════════════════════════════════════════
function step2_AddFemale() {
  Logger.log('⏳ КРОК 2: Додаємо жіночий варіант...');

  var props = PropertiesService.getScriptProperties();
  var formId = props.getProperty('FORM_ID');
  if (!formId) {
    Logger.log('❌ ПОМИЛКА: Спочатку запустіть step1_CreateBase!');
    return;
  }
  var form = FormApp.openById(formId);

  var pageFemale = form.addPageBreakItem()
    .setTitle('Розділи 3–4. Жіночий варіант');

  props.setProperty('PAGE_FEMALE_ID', String(pageFemale.getId()));

  var conflictChoices = [
    '−2 — Категорично не погоджуюсь, активно заперечую і наполягаю на своєму',
    '−1 — Не погоджуюсь, демонструю невдоволення, але уникаю відкритого обговорення',
    ' 0 — Нічого не вживаю, не висловлюю свого ставлення, чекаю розвитку подій',
    '+1 — В цілому погоджуюсь, але не вважаю за необхідне відкрито висловлюватись',
    '+2 — Повністю погоджуюсь, активно підтримую і схвалюю'
  ];

  form.addSectionHeaderItem()
    .setTitle('Розділ 3. Характер взаємодії подружжя в конфліктних ситуаціях')
    .setHelpText(
      'Авторство: Ю. Є. Альошина, Л. Я. Гозман, Є. М. Дубовська (1987).\n\n' +
      'Нижче наведено типові ситуації у сім\'ях. ' +
      'Оберіть варіант, що найбільше відповідає вашій поведінці.\n\n' +
      'Шкала: −2 = Категорично не погоджуюсь  |  0 = Нейтральна позиція  |  +2 = Повністю погоджуюсь'
    );

  var situationsFemale = [
    'Ви запросили своїх родичів у гості. Чоловік, знаючи про це, несподівано пізно повернувся додому. Вас це засмутило, і після відходу гостей ви демонструєте чоловікові своє засмучення, а він не може зрозуміти причини невдоволення. Ви...',
    'Чоловік вже багато разів обіцяв зробити дещо по дому, але досі нічого не зроблено. Ви...',
    'Ви довго стояли в черзі в магазині. Продавщиця грубила покупцям. Коли підійшла ваша черга, чоловік, на вашу думку, занадто різко почав розмовляти з нею. Ви неприємно здивовані його тоном. Ви...',
    'Вже пізно, дитині час лягати спати, але їй не хочеться, а чоловік намагається відправити її в ліжко. Ви втручаєтесь і дозволяєте дитині ще трохи погратися. Чоловік наполягає. Ви...',
    'Ви домовились вихідний провести вдома. Але несподівано вам зателефонували батьки й покликали до себе. Ви одразу почали збиратися. Чоловік невдоволений тим, що порушилися ваші спільні плани. Ви...',
    'У чоловіка поганий настрій. Ви здогадуєтесь, що в нього неприємності на роботі. Ви намагаєтеся викликати його на розмову, але він уникає бесіди. Ви...',
    'Ви з чоловіком запрошені на день народження друга, грошей на подарунок недостатньо. Вам здається, що саме чоловік цього місяця витратив занадто багато. Ви...',
    'Ваша подруга ділиться з вами та вашим чоловіком своїми проблемами. Одне із зауважень чоловіка, на вашу думку, образливе для співрозмовниці. Ви...',
    'Вам обом потрібно затриматися на роботі, і нікому побути з дитиною. Ви вважаєте, що ваші справи важливіші й це повинен зробити чоловік, але він не погоджується. Ви...',
    'Ви почали ремонт квартири. Несподівано виявилось, що це обійдеться дорожче. Чоловік від початку скептично ставився до ваших планів, а тепер ще й сердиться на вас. Ви...',
    'У вас є улюблене заняття. Чоловік радить залучити до цього дитину. Ви вважаєте, що дитина вам заважатиме, а чоловік продовжує наполягати. Ви...',
    'Ви збираєтесь вийти з дому по справах, а чоловік хоче з вами поговорити й невдоволений, що ви відмовляєтесь затриматися на кілька хвилин. Ви...',
    'З юності у вас залишилось багато друзів-чоловіків. Вони заходять до вас у гості. У чоловіка всі ці візити викликають невдоволення. Ви...',
    'Ви зайшли до чоловіка на роботу. Поки ви чекали, вам вдалося завоювати симпатії його колег-чоловіків. Вас здивувала негативна реакція чоловіка. Ви...',
    'Вам здається, що чоловік не на те витрачає гроші. Ось він знову купив непотрібну, на вашу думку, річ. Ви...',
    'Ви просите чоловіка допомогти дитині підготувати уроки, бо самі гірше знайомі з цим предметом. Чоловік продовжує займатися своїми справами. Ви...',
    'Останнім часом на роботі ви багато спілкуєтесь з одним із ваших колег. Ви часто телефонуєте одне одному. Чоловікові це не подобається. Ви...',
    'Ви випадково зустріли стару подругу й провели з нею весь вечір, пізно повернувшись додому. Чоловік хвилювався і висловив своє невдоволення. Ви...',
    'За кілька днів до зарплати знову виникла розмова про брак коштів. Чоловік вважає, що ви недостатньо робите для забезпечення сім\'ї. Ви...',
    'Ви провели вечір із новими друзями чоловіка. По дорозі додому чоловік висловив невдоволення тим, як ви поводилися з його друзями. Ви...',
    'Ваш чоловік збирається до своїх старих друзів у гості. Вам хотілося б піти з ним, але він не пропонує. Ви...',
    'У вас є улюблене захоплення, якому ви приділяєте вільний час. Чоловік виражає відкрите невдоволення. Ви...',
    'Чоловік покарав дитину, але вам здається, що вчинок не такий серйозний, і ви починаєте гратися з дитиною. Чоловік невдоволений. Ви...',
    'В гостях у друзів вас познайомили з привабливою жінкою. Ваш чоловік увесь вечір сидів поруч із нею. Вас це зачепило. Ви...',
    'Ви збиралися провести неділю вдома, але виявилось, що чоловік обіцяв друзям навідати їх. Вам дуже не хочеться йти. Ви...',
    'Ви розповіли подрузі про свої сімейні проблеми. Чоловік дізнався про це й був дуже невдоволений. Ви...',
    'Чоловік давно просив зашити йому штани. Сьогодні він хотів би їх одягнути, але вони залишились незашитими. Він висловлює своє невдоволення. Ви...',
    'Знайомий вашої сім\'ї вже не вперше підвів вас. Ви вважаєте, що треба висловити невдоволення. Чоловік каже, що не варто. Ви...',
    'У вас поганий настрій, і вам хочеться поділитися з чоловіком своїми переживаннями. Ви намагаєтесь заговорити з ним, але він відповідає, що поговорити можна пізніше. Ви...',
    'Приятель чоловіка зателефонував і попросив вас передати повідомлення. Ви згадали про це лише пізно ввечері. Чоловік різко сказав, що ваша необов\'язковість ставить його в незручне становище. Ви...',
    'Увечері ви збираєтесь разом із чоловіком дивитися телевізор, однак хочете дивитися різні канали. Кожен із вас наполягає на своєму. Ви...',
    'Ви обговорюєте з друзями плани спільного відпочинку. Чоловік несподівано починає різко виступати проти вашої пропозиції. Ви...'
  ];

  for (var i = 0; i < situationsFemale.length; i++) {
    form.addMultipleChoiceItem()
      .setTitle('Ситуація ' + (i + 1) + '.\n' + situationsFemale[i])
      .setChoiceValues(conflictChoices)
      .setRequired(true);
  }

  var rodChoices = [
    '3 — Повністю погоджуюсь',
    '2 — В цілому це вірно',
    '1 — Це не зовсім так',
    '0 — Це невірно'
  ];

  form.addSectionHeaderItem()
    .setTitle('Розділ 4. РОД — Рольові очікування і домагання у шлюбі')
    .setHelpText(
      'Автор: А. М. Волкова (1985).\n\n' +
      '3 = Повністю погоджуюсь  |  2 = В цілому вірно  |  1 = Не зовсім так  |  0 = Невірно'
    );

  form.addSectionHeaderItem()
    .setTitle('Частина А. Рольові очікування (що ви очікуєте від чоловіка)');

  var rodFemaleExpect = [
    '1. Настрій і самопочуття людини залежать від задоволення її сексуальних потреб.',
    '2. Щастя в шлюбі залежить від сексуальної гармонії чоловіка й жінки.',
    '3. Сексуальні стосунки — головне у відносинах чоловіка і дружини.',
    '4. Головне в шлюбі — щоб у чоловіка й дружини було багато спільних інтересів.',
    '5. Чоловік — це друг, що поділяє мої інтереси, думки, захоплення.',
    '6. Чоловік — це насамперед друг, з яким можна поговорити про свої справи.',
    '7. Найбільша турбота чоловіка — забезпечити матеріальний статок і побутовий комфорт родини.',
    '8. Чоловік повинен займатися домашнім господарством нарівні із дружиною.',
    '9. Чоловік повинен уміти обслужити себе, а не чекати, що дружина візьме на себе всі турботи.',
    '10. Чоловік повинен займатися дітьми не менше, ніж дружина.',
    '11. Я хотіла б, щоб мій чоловік любив дітей і приділяв їм багато часу.',
    '12. Чоловіка я оцінюю перш за все по тому, чи гарний він батько своїм дітям.',
    '13. Мені подобаються енергійні, ділові чоловіки.',
    '14. Я дуже ціную чоловіків, серйозно захоплених своєю справою.',
    '15. Для мене дуже важливо, як оцінюють на роботі ділові й професійні якості мого чоловіка.',
    '16. Чоловік повинен уміти створювати в родині теплу, довірливу атмосферу.',
    '17. Для мене головне — щоб мій чоловік добре розумів мене й приймав такою, яка я є.',
    '18. Чоловік — це насамперед друг, що уважний і турботливий до моїх переживань і настрою.',
    '19. Мені подобається, коли мій чоловік красиво й модно одягається.',
    '20. Мені подобаються гарні, доглянуті чоловіки.',
    '21. Чоловік повинен виглядати так, щоб на нього було приємно дивитися.'
  ];

  for (var i = 0; i < rodFemaleExpect.length; i++) {
    form.addMultipleChoiceItem()
      .setTitle(rodFemaleExpect[i])
      .setChoiceValues(rodChoices)
      .setRequired(true);
  }

  form.addSectionHeaderItem()
    .setTitle('Частина Б. Рольові домагання (ваша власна готовність)');

  var rodFemaleClaims = [
    '22. Найбільша турбота жінки — щоб усі члени сім\'ї були доглянуті й нагодовані.',
    '23. Я завжди знаю, що потрібно купити для моєї родини.',
    '24. Я збираю корисні поради господарці: як готувати смачні страви, консервувати овочі.',
    '25. Головну роль у вихованні дитини завжди грає мати.',
    '26. Я не боюся труднощів, пов\'язаних із народженням і вихованням дитини.',
    '27. Я люблю дітей і із задоволенням займаюся з ними.',
    '28. Я прагну знайти своє місце в житті.',
    '29. Я хочу стати висококваліфікованим фахівцем своєї справи.',
    '30. Я пишаюся, коли мені доручають важку й відповідальну роботу.',
    '31. Близькі й друзі часто звертаються до мене за порадою, допомогою й підтримкою.',
    '32. Оточуючі часто довіряють мені свої переживання та труднощі.',
    '33. Я завжди щиро співчуваю, втішаю й опікую людей, які цього потребують.',
    '34. Мій настрій великою мірою залежить від того, як я виглядаю.',
    '35. Я люблю гарний одяг, ношу прикраси, користуюся косметикою.',
    '36. Я надаю великого значення своєму зовнішньому вигляду.'
  ];

  for (var i = 0; i < rodFemaleClaims.length; i++) {
    form.addMultipleChoiceItem()
      .setTitle(rodFemaleClaims[i])
      .setChoiceValues(rodChoices)
      .setRequired(true);
  }

  pageFemale.setGoToPage(FormApp.PageNavigationType.SUBMIT);

  Logger.log('✅ КРОК 2 ГОТОВО — жіночий варіант додано.');
  Logger.log('➡️  Тепер запустіть step3_AddMale');
}


// ════════════════════════════════════════════════════════════════
//  КРОК 3: Чоловічий варіант + налаштування розгалуження
// ════════════════════════════════════════════════════════════════
function step3_AddMale() {
  Logger.log('⏳ КРОК 3: Додаємо чоловічий варіант і налаштовуємо розгалуження...');

  var props = PropertiesService.getScriptProperties();
  var formId = props.getProperty('FORM_ID');
  var genderQId = parseInt(props.getProperty('GENDER_Q_ID'));
  var pageFemaleId = parseInt(props.getProperty('PAGE_FEMALE_ID'));

  if (!formId) {
    Logger.log('❌ ПОМИЛКА: Спочатку запустіть step1 і step2!');
    return;
  }

  var form = FormApp.openById(formId);

  var pageMale = form.addPageBreakItem()
    .setTitle('Розділи 3–4. Чоловічий варіант');

  var conflictChoices = [
    '−2 — Категорично не погоджуюсь, активно заперечую і наполягаю на своєму',
    '−1 — Не погоджуюсь, демонструю невдоволення, але уникаю відкритого обговорення',
    ' 0 — Нічого не вживаю, не висловлюю свого ставлення, чекаю розвитку подій',
    '+1 — В цілому погоджуюсь, але не вважаю за необхідне відкрито висловлюватись',
    '+2 — Повністю погоджуюсь, активно підтримую і схвалюю'
  ];

  form.addSectionHeaderItem()
    .setTitle('Розділ 3. Характер взаємодії подружжя в конфліктних ситуаціях')
    .setHelpText(
      'Авторство: Ю. Є. Альошина, Л. Я. Гозман, Є. М. Дубовська (1987).\n\n' +
      'Нижче наведено типові ситуації у сім\'ях. ' +
      'Оберіть варіант, що найбільше відповідає вашій поведінці.\n\n' +
      'Шкала: −2 = Категорично не погоджуюсь  |  0 = Нейтральна позиція  |  +2 = Повністю погоджуюсь'
    );

  var situationsMale = [
    'Ви запросили своїх родичів у гості. Дружина, знаючи про це, несподівано пізно повернулася додому. Після відходу гостей ви демонструєте їй своє засмучення, а вона не може зрозуміти причини вашого невдоволення. Ви...',
    'Дружина вже багато разів обіцяла зробити дещо по дому, але досі нічого не зроблено. Ви...',
    'Ви довго стояли в черзі в магазині. Продавщиця грубила покупцям. Коли підійшла ваша черга, дружина, на вашу думку, занадто різко почала розмовляти з нею. Ви неприємно здивовані її тоном. Ви...',
    'Вже пізно, дитині час лягати спати, але їй не хочеться, а дружина намагається відправити її в ліжко. Ви втручаєтесь і дозволяєте дитині ще трохи погратися. Дружина наполягає. Ви...',
    'Ви домовились вихідний провести вдома. Але несподівано зателефонували батьки дружини й покликали до себе. Дружина одразу почала збиратися. Ви невдоволені тим, що порушилися ваші спільні плани. Ви...',
    'У дружини поганий настрій. Ви здогадуєтесь, що в неї неприємності на роботі. Ви намагаєтеся викликати її на розмову, але вона уникає бесіди. Ви...',
    'Ви з дружиною запрошені на день народження, грошей на подарунок недостатньо. Вам здається, що саме дружина цього місяця витратила занадто багато. Ви...',
    'Ваш друг ділиться з вами та вашою дружиною своїми проблемами. Одне із зауважень дружини, на вашу думку, образливе для нього. Ви...',
    'Вам обом потрібно затриматися на роботі, і нікому побути з дитиною. Ви вважаєте, що справи дружини важливіші й це повинна зробити вона, але вона не погоджується. Ви...',
    'Ви почали ремонт квартири. Несподівано виявилось, що це обійдеться дорожче. Дружина від початку скептично ставилася до ваших планів, а тепер ще й сердиться на вас. Ви...',
    'У вас є улюблене заняття. Дружина радить залучити до цього дитину. Ви вважаєте, що дитина вам заважатиме, а дружина продовжує наполягати. Ви...',
    'Ви збираєтесь вийти з дому по справах, а дружина хоче з вами поговорити й невдоволена, що ви відмовляєтесь затриматися на кілька хвилин. Ви...',
    'З юності у вас залишилось багато подруг-жінок. Вони заходять до вас у гості. У дружини всі ці візити викликають невдоволення. Ви...',
    'Ви зайшли до дружини на роботу. Поки ви чекали, вам вдалося завоювати симпатії її колег-чоловіків. Вас здивувала негативна реакція дружини. Ви...',
    'Вам здається, що дружина не на те витрачає гроші. Ось вона знову купила непотрібну, на вашу думку, річ. Ви...',
    'Ви просите дружину допомогти дитині підготувати уроки, але вона продовжує займатися своїми справами й відсилає дитину до вас. Ви...',
    'Останнім часом на роботі дружина багато спілкується з одним із колег. Вони часто телефонують одне одному. Вам це не подобається. Ви...',
    'Дружина випадково зустріла старого друга й провела з ним весь вечір, пізно повернувшись додому. Ви хвилювалися і висловили своє невдоволення. Ви...',
    'За кілька днів до зарплати знову виникла розмова про брак коштів. Дружина вважає, що ви недостатньо робите для забезпечення сім\'ї. Ви...',
    'Ви провели вечір із новими друзями дружини. По дорозі додому дружина висловила невдоволення тим, як ви поводились із її друзями. Ви...',
    'Ваша дружина збирається до своїх старих подруг у гості. Вам хотілося б піти з нею, але вона не пропонує. Ви...',
    'У вас є улюблене захоплення, якому ви приділяєте вільний час. Дружина виражає відкрите невдоволення. Ви...',
    'Дружина покарала дитину, але вам здається, що вчинок не такий серйозний, і ви починаєте гратися з дитиною. Дружина невдоволена. Ви...',
    'В гостях у друзів вас познайомили з привабливим чоловіком. Ваша дружина увесь вечір сиділа поруч із ним. Вас це зачепило. Ви...',
    'Ви збиралися провести неділю вдома, але виявилось, що дружина обіцяла подругам навідати їх. Вам дуже не хочеться йти. Ви...',
    'Ви розповіли другові про свої сімейні проблеми. Дружина дізналася про це й була дуже невдоволена. Ви...',
    'Дружина давно просила вас зробити щось по дому. Сьогодні це знадобилося, але так і залишилось незробленим. Дружина висловлює своє невдоволення. Ви...',
    'Знайомий вашої сім\'ї вже не вперше підвів вас. Ви вважаєте, що треба висловити невдоволення. Дружина каже, що не варто. Ви...',
    'У вас поганий настрій, і вам хочеться поділитися з дружиною своїми переживаннями. Ви намагаєтесь заговорити з нею, але вона відповідає, що поговорити можна пізніше. Ви...',
    'Подруга дружини зателефонувала і попросила вас передати їй повідомлення. Ви згадали про це лише пізно ввечері. Дружина різко сказала, що ваша необов\'язковість ставить її в незручне становище. Ви...',
    'Увечері ви збираєтесь разом із дружиною дивитися телевізор, однак хочете дивитися різні канали. Кожен із вас наполягає на своєму. Ви...',
    'Ви обговорюєте з друзями плани спільного відпочинку. Дружина несподівано починає різко виступати проти вашої пропозиції. Ви...'
  ];

  for (var i = 0; i < situationsMale.length; i++) {
    form.addMultipleChoiceItem()
      .setTitle('Ситуація ' + (i + 1) + '.\n' + situationsMale[i])
      .setChoiceValues(conflictChoices)
      .setRequired(true);
  }

  var rodChoices = [
    '3 — Повністю погоджуюсь',
    '2 — В цілому це вірно',
    '1 — Це не зовсім так',
    '0 — Це невірно'
  ];

  form.addSectionHeaderItem()
    .setTitle('Розділ 4. РОД — Рольові очікування і домагання у шлюбі')
    .setHelpText(
      'Автор: А. М. Волкова (1985).\n\n' +
      '3 = Повністю погоджуюсь  |  2 = В цілому вірно  |  1 = Не зовсім так  |  0 = Невірно'
    );

  form.addSectionHeaderItem()
    .setTitle('Частина А. Рольові очікування (що ви очікуєте від дружини)');

  var rodMaleExpect = [
    '1. Настрій і самопочуття людини залежать від задоволення її сексуальних потреб.',
    '2. Щастя в шлюбі залежить від сексуальної гармонії подружжя.',
    '3. Сексуальні відносини — головне у відносинах чоловіка й дружини.',
    '4. Головне у шлюбі — щоб чоловік і дружина мали багато спільних інтересів.',
    '5. Дружина — це друг, що поділяє мої інтереси, думки, захоплення.',
    '6. Дружина — це насамперед друг, з яким можна поговорити про свої справи.',
    '7. Найголовніша турбота дружини — годувати і доглядати всіх у сім\'ї.',
    '8. Жінка багато чого втрачає в моїх очах, якщо вона погана господиня.',
    '9. Жінка може пишатися собою, якщо вона хороша господиня.',
    '10. Я хотів би, щоб моя дружина любила дітей і була гарною матір\'ю.',
    '11. Жінка, яка вважає за обтяжливе бути матір\'ю, є неповноцінною.',
    '12. Для мене головне в жінці — щоб вона була доброю матір\'ю моїм дітям.',
    '13. Мені подобаються ділові й енергійні жінки.',
    '14. Я дуже ціную жінок, які захоплені своєю справою й знають її досконало.',
    '15. Для мене дуже важливо, як оцінюють на роботі ділові й професійні якості моєї дружини.',
    '16. Дружина повинна насамперед створювати і підтримувати теплу, довірчу атмосферу в сім\'ї.',
    '17. Для мене головне, щоб моя дружина добре розуміла мене і сприймала таким, який я є.',
    '18. Дружина — це насамперед друг, який уважно і турботливо ставиться до моїх переживань і настрою.',
    '19. Мені дуже подобається, коли моя дружина красиво і модно вдягнена.',
    '20. Я дуже ціную жінок, що вміють красиво вдягатися і стежать за своїм виглядом.',
    '21. Жінка має виглядати так, щоб на неї звертали увагу.'
  ];

  for (var i = 0; i < rodMaleExpect.length; i++) {
    form.addMultipleChoiceItem()
      .setTitle(rodMaleExpect[i])
      .setChoiceValues(rodChoices)
      .setRequired(true);
  }

  form.addSectionHeaderItem()
    .setTitle('Частина Б. Рольові домагання (ваша власна готовність)');

  var rodMaleClaims = [
    '22. Я завжди знаю, що потрібно купити для моєї сім\'ї.',
    '23. Я люблю господарювати і вмію вести домашнє господарство.',
    '24. Я можу робити ремонт квартири, лагодити побутову техніку.',
    '25. Діти люблять грати зі мною, охоче спілкуються.',
    '26. Я дуже люблю дітей і вмію з ними займатися.',
    '27. Я брав би активну участь у вихованні своєї дитини, навіть якби ми з дружиною вирішили розлучитися.',
    '28. Я прагну посісти гідне місце в житті.',
    '29. Я хочу стати висококваліфікованим фахівцем своєї справи.',
    '30. Я пишаюся, коли мені доручають важку і відповідальну роботу.',
    '31. Близькі і друзі часто звертаються до мене за порадою, допомогою й підтримкою.',
    '32. Оточуючі часто звертаються до мене зі своїми труднощами й переживаннями.',
    '33. Я завжди щиро та із співчуттям втішаю й опікую людей, які цього потребують.',
    '34. Мій настрій багато в чому залежить від того, як я виглядаю.',
    '35. Я намагаюся вдягати те, що мені личить і добре на мені виглядає.',
    '36. Я прискіпливо ставлюся до свого зовнішнього вигляду та одягу.'
  ];

  for (var i = 0; i < rodMaleClaims.length; i++) {
    form.addMultipleChoiceItem()
      .setTitle(rodMaleClaims[i])
      .setChoiceValues(rodChoices)
      .setRequired(true);
  }

  var genderQ = form.getItemById(genderQId).asMultipleChoiceItem();
  var pageFemaleItem = form.getItemById(pageFemaleId).asPageBreakItem();

  genderQ.setChoices([
    genderQ.createChoice('Жіноча', pageFemaleItem),
    genderQ.createChoice('Чоловіча', pageMale)
  ]);

  Logger.log('✅ КРОК 3 ГОТОВО — форма повністю побудована!');
  Logger.log('🔗 Посилання на форму: ' + form.getPublishedUrl());
  Logger.log('📊 Редагувати форму: ' + form.getEditUrl());
  Logger.log('➡️  Тепер запустіть step4_LinkSpreadsheet — щоб бачити всі відповіді в Sheets');
}
