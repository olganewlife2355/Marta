/*
 * ============================================================
 * ChromaFit Google Apps Script
 * ============================================================
 * Автор: Карасевич О. О.
 * Магістерська робота, КНУ ім. Тараса Шевченка, 2026
 *
 * ФУНКЦІЇ:
 * 1) createChromaFitForm() — автоматично створює Google Form
 *    з усіма полями + посилання на резюме (Google Drive)
 * 2) onFormSubmit(e) — обробляє відповідь, аналізує резюме
 *    через Claude API, зберігає результати у Sheets,
 *    надсилає профіль на email респондента
 * 3) setupTrigger() — активує автоматичну обробку
 * 4) testClaudeCall() — тестовий запит до Claude
 *
 * ВСТАНОВЛЕННЯ:
 * 1. Відкрийте script.google.com → Новий проект
 * 2. Вставте цей код у Code.gs
 * 3. Замініть CLAUDE_API_KEY на ваш ключ від anthropic.com
 * 4. Запустіть createChromaFitForm() — отримайте URL форми
 * 5. Запустіть setupTrigger() — для автоматизації обробки
 *
 * ПРИМІТКА: цей скрипт розрахований на ЗВИЧАЙНИЙ @gmail.com.
 * Методи setRequireLogin() та addFileUploadItem() вимагають
 * Google Workspace і тут НЕ використовуються. Замість
 * завантаження файлу — поле для посилання на Google Drive.
 * ============================================================
 */

// =======================================================
// КОНФІГУРАЦІЯ
// =======================================================

const CLAUDE_API_KEY = 'sk-ant-...'; // <-- ваш ключ
const CLAUDE_API_URL = 'https://api.anthropic.com/v1/messages';
const CLAUDE_MODEL = 'claude-opus-4-7';

const SPREADSHEET_NAME = 'ChromaFit Responses';
const FORM_NAME = 'ChromaFit — Кольоровий профіль компетенцій';

const DOMAINS = [
  { code: 'LEAD',        name: 'Лідерство',           hex: '#E63946' },
  { code: 'ACHIEVE',     name: 'Досягнення',          hex: '#F77F00' },
  { code: 'COMMUNICATE', name: 'Комунікація',         hex: '#FFD60A' },
  { code: 'COLLAB',      name: 'Співпраця',           hex: '#06A77D' },
  { code: 'TECH',        name: 'Технічна експертиза', hex: '#1D4E89' },
  { code: 'STRATEGY',    name: 'Стратегія',           hex: '#7209B7' },
  { code: 'ANALYSIS',    name: 'Аналітика',           hex: '#00B4D8' },
  { code: 'ORDER',       name: 'Організованість',     hex: '#8B5A2B' },
  { code: 'SELF_AWARE',  name: 'Саморефлексія',       hex: '#F8F9FA' },
  { code: 'MENTOR',      name: 'Наставництво',        hex: '#2B2D42' },
];


// =======================================================
// ГОЛОВНА ФУНКЦІЯ: СТВОРЕННЯ ФОРМИ
// =======================================================

function createChromaFitForm() {
  const form = FormApp.create(FORM_NAME);
  form.setTitle(FORM_NAME);
  form.setDescription(
    'Дякуємо за інтерес до дослідження!\n\n' +
    'Магістерське дослідження Карасевич О. О. (КНУ, 2026). ' +
    'Мета: валідизувати модель кольорового кодування 10 ' +
    'компетентнісних доменів особистості у рекрутингу.\n\n' +
    'Час: 45-60 хв. Ваші дані анонімізуються і використовуються ' +
    'у агрегованому вигляді (GDPR). Після обробки ви отримаєте ' +
    'на email свій кольоровий ChromaFit-профіль.\n\n' +
    'Запитання: karasevych.olga@gmail.com\n' +
    'Науковий керівник: к.психол.н., доц. Рогаль Ніна Іванівна'
  );

  // setCollectEmail може бути недоступним на деяких особистих акаунтах
  try {
    form.setCollectEmail(true);
  } catch (e) {
    Logger.log('setCollectEmail пропущено: ' + e.message);
  }

  // ===== БЛОК 1: ДЕМОГРАФІЯ =====
  form.addPageBreakItem()
    .setTitle('Блок 1 з 6: Про вас');

  form.addTextItem()
    .setTitle('Імʼя (або псевдонім)')
    .setRequired(true);

  form.addMultipleChoiceItem()
    .setTitle('Стать')
    .setChoiceValues(['Жіноча', 'Чоловіча', 'Інша / не вказую'])
    .setRequired(true);

  form.addMultipleChoiceItem()
    .setTitle('Ваш вік')
    .setChoiceValues(['22-25', '26-30', '31-35', '36-40',
                      '41-45', '46-50', '51+'])
    .setRequired(true);

  form.addMultipleChoiceItem()
    .setTitle('Рівень освіти')
    .setChoiceValues(['Середня / ПТУ', 'Бакалавр', 'Магістр', 'PhD'])
    .setRequired(true);

  form.addMultipleChoiceItem()
    .setTitle('Професійна сфера')
    .setChoiceValues([
      'IT / розробка',
      'HR / рекрутинг',
      'Маркетинг / PR / реклама',
      'Продажі / розвиток бізнесу',
      'Фінанси / банківська справа',
      'Креативні індустрії',
      'Освіта / наука',
      'Медицина / охорона здоровʼя',
      'Виробництво / логістика',
      'Державна служба',
      'Інше'
    ])
    .setRequired(true);

  form.addMultipleChoiceItem()
    .setTitle('Досвід роботи (повних років)')
    .setChoiceValues(['< 1', '1-3', '4-7', '8-12', '13-20', '21+'])
    .setRequired(true);

  form.addMultipleChoiceItem()
    .setTitle('Поточна локація')
    .setChoiceValues([
      'Україна (Київ)',
      'Україна (інші міста)',
      'ЄС (Польща)',
      'ЄС (Німеччина)',
      'ЄС (Чехія)',
      'ЄС (інші країни)',
      'США / Канада',
      'Великобританія',
      'Інше'
    ])
    .setRequired(true);

  // ===== БЛОК 2: РЕЗЮМЕ (посилання замість файлу) =====
  form.addPageBreakItem()
    .setTitle('Блок 2 з 6: Ваше резюме')
    .setHelpText('Завантаження файлів доступне лише для Google Workspace. ' +
                 'Будь ласка, вставте посилання на ваше резюме у Google Drive.');

  form.addTextItem()
    .setTitle('Посилання на резюме (Google Drive)')
    .setHelpText(
      'Як створити посилання:\n' +
      '1) Завантажте резюме у свій Google Drive (PDF або DOCX).\n' +
      '2) Клацніть правою кнопкою → «Поділитися» → «Будь-хто з посиланням» (роль: Читач).\n' +
      '3) Скопіюйте посилання та вставте у поле нижче.\n\n' +
      'Текст резюме використовується лише для побудови вашого ChromaFit-профілю.'
    )
    .setRequired(true);

  // ===== БЛОК 3: САМООЦІНКА 10 ДОМЕНІВ =====
  form.addPageBreakItem()
    .setTitle('Блок 3 з 6: Самооцінка 10 доменів');

  DOMAINS.forEach(d => {
    form.addScaleItem()
      .setTitle(d.name + ': наскільки цей домен про вас?')
      .setHelpText(getDomainDescription(d.code))
      .setBounds(1, 5)
      .setLabels('Зовсім не про мене', 'Максимально про мене')
      .setRequired(true);
  });

  // ===== БЛОК 4: SD =====
  form.addPageBreakItem()
    .setTitle('Блок 4 з 6: Сприйняття кольорів');

  const colors = [
    ['Червоний', '#E63946'],
    ['Помаранчевий', '#F77F00'],
    ['Жовтий', '#FFD60A'],
    ['Зелений', '#06A77D'],
    ['Блакитний', '#00B4D8'],
    ['Синій', '#1D4E89'],
    ['Фіолетовий', '#7209B7'],
    ['Коричневий', '#8B5A2B'],
    ['Білий', '#F8F9FA'],
    ['Чорний', '#2B2D42'],
  ];

  colors.forEach(([name, hex]) => {
    form.addScaleItem()
      .setTitle('Колір ' + name + ': приємний ↔ неприємний')
      .setBounds(1, 7)
      .setLabels('Дуже приємний', 'Дуже неприємний')
      .setRequired(true);

    form.addScaleItem()
      .setTitle('Колір ' + name + ': сильний ↔ слабкий')
      .setBounds(1, 7)
      .setLabels('Дуже сильний', 'Дуже слабкий')
      .setRequired(true);

    form.addScaleItem()
      .setTitle('Колір ' + name + ': активний ↔ пасивний')
      .setBounds(1, 7)
      .setLabels('Дуже активний', 'Дуже пасивний')
      .setRequired(true);
  });

  // ===== БЛОК 5: LÜSCHER =====
  form.addPageBreakItem()
    .setTitle('Блок 5 з 6: Уподобання кольорів')
    .setHelpText('Розташуйте 8 кольорів за приємністю: ' +
                 '1 = найбільш приємний, 8 = найменш.');

  const luscher = ['Синій', 'Зелений', 'Червоний', 'Жовтий',
                   'Фіолетовий', 'Коричневий', 'Чорний', 'Сірий'];
  luscher.forEach(color => {
    form.addMultipleChoiceItem()
      .setTitle('Позиція кольору ' + color)
      .setChoiceValues(['1', '2', '3', '4', '5', '6', '7', '8'])
      .setRequired(true);
  });

  // ===== БЛОК 6: BIG FIVE =====
  form.addPageBreakItem()
    .setTitle('Блок 6 з 6: Коротка самооцінка особистості');

  const bigfive_items = [
    'Я — душа компанії.',
    'Я співчуваю почуттям інших.',
    'Я завжди готовий до справи.',
    'Я часто почуваюся засмученим.',
    'Я маю багату уяву.',
    'Я тримаюся в тіні.',
    'Я цікавлюся людьми.',
    'Я залишаю речі у безладі.',
    'Я переважно розслаблений.',
    'Я не цікавлюся абстрактними ідеями.',
    'Я легко вступаю в розмову з незнайомими.',
    'Я ображаю людей.',
    'Я звертаю увагу на деталі.',
    'Я багато хвилююся.',
    'Я маю яскраві уявлення.',
    'Я не привертаю уваги в групі.',
    'Я співчуваю іншим.',
    'Я рідко виконую обіцяне.',
    'Я легко засмучуюся.',
    'Мені важко зрозуміти абстрактні ідеї.',
  ];

  bigfive_items.forEach((item, idx) => {
    form.addScaleItem()
      .setTitle((idx + 1) + '. ' + item)
      .setBounds(1, 5)
      .setLabels('Цілком не відповідає', 'Цілком відповідає')
      .setRequired(true);
  });

  // ===== ЗГОДА =====
  form.addPageBreakItem().setTitle('Інформована згода');

  form.addCheckboxItem()
    .setTitle('Я погоджуюся на участь у дослідженні')
    .setHelpText('Я ознайомлений/а зі згодою. Мої дані ' +
                 'аналізуються у агрегованому вигляді (GDPR). ' +
                 'Я можу припинити участь у будь-який момент.')
    .setChoiceValues(['Так, я погоджуюся'])
    .setRequired(true);

  // Створюємо Spreadsheet
  const spreadsheet = SpreadsheetApp.create(SPREADSHEET_NAME);
  form.setDestination(FormApp.DestinationType.SPREADSHEET,
                      spreadsheet.getId());

  const formUrl = form.getPublishedUrl();
  const editUrl = form.getEditUrl();
  const sheetUrl = spreadsheet.getUrl();

  Logger.log('=== ChromaFit форма створена ===');
  Logger.log('URL для респондентів: ' + formUrl);
  Logger.log('URL для редагування: ' + editUrl);
  Logger.log('Spreadsheet: ' + sheetUrl);
  Logger.log('ID spreadsheet: ' + spreadsheet.getId());

  return {
    formUrl: formUrl,
    editUrl: editUrl,
    sheetUrl: sheetUrl,
    sheetId: spreadsheet.getId(),
  };
}


function getDomainDescription(code) {
  const descriptions = {
    'LEAD': 'Вплив, відповідальність, задавати напрямок',
    'ACHIEVE': 'Результат, драйв, KPI',
    'COMMUNICATE': 'Експресія, презентації, public relations',
    'COLLAB': 'Емпатія, командність, підтримка інших',
    'TECH': 'Глибина експертизи, ремесло, майстерність',
    'STRATEGY': 'Системне мислення, roadmap',
    'ANALYSIS': 'Робота з даними, логіка, дослідження',
    'ORDER': 'Процеси, дедлайни, операційна дисципліна',
    'SELF_AWARE': 'Рефлексія, емоційна зрілість',
    'MENTOR': 'Коучинг, розвиток інших',
  };
  return descriptions[code] || '';
}


// =======================================================
// TRIGGER: обробка форми
// =======================================================

function onFormSubmit(e) {
  try {
    const data = parseFormResponse(e);
    Logger.log('Отримано відповідь від: ' + data.email);

    let resumeText = '';
    if (data.resumeUrl) {
      resumeText = extractTextFromDriveUrl(data.resumeUrl);
    }

    const claudeResponse = analyzeWithClaude(data, resumeText);
    saveResultsToSheet(data, claudeResponse);
    sendProfileEmail(data.email, claudeResponse);

    Logger.log('Успішно оброблено: ' + data.email);
  } catch (err) {
    Logger.log('ПОМИЛКА: ' + err.message);
  }
}


function parseFormResponse(e) {
  const response = e.response;
  const itemResponses = response.getItemResponses();

  const data = {
    timestamp: response.getTimestamp(),
    email: response.getRespondentEmail(),
    name: '',
    gender: '',
    age: '',
    education: '',
    field: '',
    experience: '',
    location: '',
    resumeUrl: '',
    selfAssessment: {},
    bigfive: [],
    consent: false,
  };

  itemResponses.forEach(ir => {
    const title = ir.getItem().getTitle();
    const answer = ir.getResponse();

    if (title.includes('псевдонім')) data.name = answer;
    else if (title === 'Стать') data.gender = answer;
    else if (title === 'Ваш вік') data.age = answer;
    else if (title === 'Рівень освіти') data.education = answer;
    else if (title === 'Професійна сфера') data.field = answer;
    else if (title.includes('Досвід')) data.experience = answer;
    else if (title.includes('локація')) data.location = answer;
    else if (title.includes('резюме')) {
      data.resumeUrl = String(answer || '').trim();
    }

    DOMAINS.forEach(d => {
      if (title.startsWith(d.name)) {
        data.selfAssessment[d.code] = parseInt(answer);
      }
    });

    const bfMatch = title.match(/^(\d+)\. /);
    if (bfMatch) {
      const idx = parseInt(bfMatch[1]) - 1;
      data.bigfive[idx] = parseInt(answer);
    }

    if (title.includes('погоджуюся')) {
      data.consent = Array.isArray(answer) ? answer.length > 0 : !!answer;
    }
  });

  return data;
}


function extractFileIdFromDriveUrl(url) {
  if (!url) return null;
  const patterns = [
    /\/file\/d\/([a-zA-Z0-9_-]+)/,
    /[?&]id=([a-zA-Z0-9_-]+)/,
    /\/document\/d\/([a-zA-Z0-9_-]+)/,
    /\/open\?id=([a-zA-Z0-9_-]+)/,
  ];
  for (const re of patterns) {
    const m = url.match(re);
    if (m) return m[1];
  }
  return null;
}


function extractTextFromDriveUrl(url) {
  try {
    const fileId = extractFileIdFromDriveUrl(url);
    if (!fileId) {
      Logger.log('Не вдалося розпізнати ID файлу у посиланні: ' + url);
      return '';
    }
    return extractTextFromFile(fileId);
  } catch (err) {
    Logger.log('Помилка читання резюме за посиланням: ' + err.message);
    return '';
  }
}


function extractTextFromFile(fileId) {
  try {
    const file = DriveApp.getFileById(fileId);
    const mimeType = file.getMimeType();

    if (mimeType === MimeType.GOOGLE_DOCS) {
      return DocumentApp.openById(fileId).getBody().getText();
    }

    if (mimeType === 'application/pdf' ||
        mimeType.indexOf('officedocument.wordprocessingml') !== -1 ||
        mimeType.indexOf('msword') !== -1) {
      const resource = {
        title: file.getName() + '_temp',
        mimeType: MimeType.GOOGLE_DOCS,
      };
      const docFile = Drive.Files.copy(resource, fileId, { convert: true });
      const doc = DocumentApp.openById(docFile.id);
      const text = doc.getBody().getText();
      DriveApp.getFileById(docFile.id).setTrashed(true);
      return text;
    }

    return file.getBlob().getDataAsString();
  } catch (err) {
    Logger.log('Помилка читання резюме: ' + err.message);
    return '';
  }
}


function analyzeWithClaude(data, resumeText) {
  const systemPrompt =
    'Ти — ChromaFit AI-аналітик. Побудуй персональний кольоровий ' +
    'профіль 10 компетентнісних доменів особистості на основі ' +
    '(1) самооцінки, (2) Big Five, (3) резюме.\n\n' +
    '10 ДОМЕНІВ:\n' +
    DOMAINS.map(d => '- ' + d.code + ' (' + d.hex + '): ' + d.name + ' — ' + getDomainDescription(d.code)).join('\n') + '\n\n' +
    'Вихідний формат: JSON-об\'єкт з полями:\n' +
    '{\n' +
    '  "summary": "2-3 речення про профіль",\n' +
    '  "weights": {"LEAD": число 0-30, ...}, // сума = 100\n' +
    '  "levels": {"LEAD": "latent|emerging|functional|advanced|strategic", ...},\n' +
    '  "top_3_domains": ["CODE1", "CODE2", "CODE3"],\n' +
    '  "growth_areas": ["CODE1", "CODE2"],\n' +
    '  "career_recommendations": "3-4 абзаци рекомендацій",\n' +
    '  "big_five_scores": {"E": float, "A": float, "C": float, "ES": float, "O": float}\n' +
    '}\n\n' +
    'Сума weights = 100. Відповідь тільки JSON, без markdown.';

  const userPrompt =
    'Вік: ' + data.age + '\n' +
    'Освіта: ' + data.education + '\n' +
    'Сфера: ' + data.field + '\n' +
    'Досвід: ' + data.experience + '\n' +
    'Локація: ' + data.location + '\n\n' +
    'Самооцінка 10 доменів (1-5):\n' +
    Object.entries(data.selfAssessment).map(([k, v]) => '- ' + k + ': ' + v).join('\n') + '\n\n' +
    'Big Five (20 айтемів):\n' +
    data.bigfive.map((v, i) => (i+1) + ': ' + v).join(', ') + '\n\n' +
    (resumeText ? 'РЕЗЮМЕ:\n' + resumeText.slice(0, 5000) : '') + '\n\n' +
    'Побудуй ChromaFit-профіль. Відповідь — JSON.';

  const payload = {
    model: CLAUDE_MODEL,
    max_tokens: 2000,
    system: systemPrompt,
    messages: [{ role: 'user', content: userPrompt }],
  };

  const options = {
    method: 'post',
    contentType: 'application/json',
    headers: {
      'x-api-key': CLAUDE_API_KEY,
      'anthropic-version': '2023-06-01',
    },
    payload: JSON.stringify(payload),
    muteHttpExceptions: true,
  };

  const response = UrlFetchApp.fetch(CLAUDE_API_URL, options);
  const code = response.getResponseCode();

  if (code !== 200) {
    throw new Error('Claude API помилка ' + code + ': ' + response.getContentText());
  }

  const result = JSON.parse(response.getContentText());
  const text = result.content[0].text;
  const cleaned = text.replace(/^```json\n?|\n?```$/g, '').trim();
  return JSON.parse(cleaned);
}


function saveResultsToSheet(data, claudeResponse) {
  const spreadsheet = SpreadsheetApp.getActiveSpreadsheet();
  let sheet = spreadsheet.getSheetByName('ChromaFit_Results');

  if (!sheet) {
    sheet = spreadsheet.insertSheet('ChromaFit_Results');
    const headers = [
      'Timestamp', 'Email', 'Name', 'Age', 'Education', 'Field',
      'Experience', 'Location', 'ResumeUrl', 'Summary', 'Top_Domains',
      'Growth_Areas'
    ];
    DOMAINS.forEach(d => headers.push('W_' + d.code));
    DOMAINS.forEach(d => headers.push('L_' + d.code));
    headers.push('BigFive_E', 'BigFive_A', 'BigFive_C',
                 'BigFive_ES', 'BigFive_O', 'Recommendations');
    sheet.appendRow(headers);
  }

  const row = [
    data.timestamp,
    data.email,
    data.name,
    data.age,
    data.education,
    data.field,
    data.experience,
    data.location,
    data.resumeUrl,
    claudeResponse.summary || '',
    (claudeResponse.top_3_domains || []).join(', '),
    (claudeResponse.growth_areas || []).join(', '),
  ];
  DOMAINS.forEach(d => row.push(claudeResponse.weights[d.code] || 0));
  DOMAINS.forEach(d => row.push(claudeResponse.levels[d.code] || ''));
  row.push(
    claudeResponse.big_five_scores.E || 0,
    claudeResponse.big_five_scores.A || 0,
    claudeResponse.big_five_scores.C || 0,
    claudeResponse.big_five_scores.ES || 0,
    claudeResponse.big_five_scores.O || 0,
    claudeResponse.career_recommendations || ''
  );
  sheet.appendRow(row);
}


function sendProfileEmail(email, profile) {
  const subject = 'Ваш ChromaFit-профіль готовий!';

  const topDomains = (profile.top_3_domains || []).map(c => {
    const d = DOMAINS.find(x => x.code === c);
    return '  • ' + (d ? d.name : c) + ': ' + profile.weights[c] + '%';
  }).join('\n');

  const growthAreas = (profile.growth_areas || []).map(c => {
    const d = DOMAINS.find(x => x.code === c);
    return '  • ' + (d ? d.name : c);
  }).join('\n');

  const allDomains = DOMAINS.map(d =>
    '  ' + d.name + ': ' + profile.weights[d.code] + '% (' +
    profile.levels[d.code] + ')'
  ).join('\n');

  const body =
    'Вітаю!\n\n' +
    'Дякуємо за участь у дослідженні ChromaFit. Нижче ваш ' +
    'персональний кольоровий профіль:\n\n' +
    'ПРО ВАШ ПРОФІЛЬ:\n' + profile.summary + '\n\n' +
    'ТОП-3 ПРОВІДНИХ ДОМЕНІВ:\n' + topDomains + '\n\n' +
    'ПОТЕНЦІЙНІ ЗОНИ РОСТУ:\n' + growthAreas + '\n\n' +
    'КАР\'ЄРНІ РЕКОМЕНДАЦІЇ:\n' + profile.career_recommendations + '\n\n' +
    'РОЗПОДІЛ ПО 10 ДОМЕНАХ:\n' + allDomains + '\n\n' +
    '────────────────────────────────────\n' +
    'Дослідження: Карасевич О. О.\n' +
    'Питання: karasevych.olga@gmail.com';

  MailApp.sendEmail({
    to: email,
    subject: subject,
    body: body,
  });
}


function setupTrigger() {
  ScriptApp.getProjectTriggers().forEach(t => {
    if (t.getHandlerFunction() === 'onFormSubmit') {
      ScriptApp.deleteTrigger(t);
    }
  });

  const form = FormApp.getActiveForm();
  ScriptApp.newTrigger('onFormSubmit')
    .forForm(form)
    .onFormSubmit()
    .create();

  Logger.log('Trigger встановлено.');
}


function testClaudeCall() {
  const testData = {
    age: '31-35',
    education: 'Магістр',
    field: 'HR / рекрутинг',
    experience: '13-20',
    location: 'Україна (Київ)',
    selfAssessment: {
      LEAD: 4, ACHIEVE: 4, COMMUNICATE: 5, COLLAB: 5,
      TECH: 2, STRATEGY: 3, ANALYSIS: 3, ORDER: 4,
      SELF_AWARE: 4, MENTOR: 5,
    },
    bigfive: [4,5,4,2,4,2,5,2,4,2,5,1,4,3,4,2,5,2,3,1],
  };

  const result = analyzeWithClaude(testData, '');
  Logger.log('Тестовий результат: ' + JSON.stringify(result, null, 2));
}
