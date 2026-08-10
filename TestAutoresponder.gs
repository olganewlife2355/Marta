/*
 * ============================================================
 * ChromaFit — Автореспондент для тестування форми
 * ============================================================
 * Генерує та надсилає 47 тестових відповідей у Google Form:
 *   - 20 пар (40 респондентів, відповіді партнерів корельовані)
 *   - 7 соло-респондентів
 *
 * ВСТАНОВЛЕННЯ:
 * 1. Додайте цей файл (TestAutoresponder.gs) у ТОЙ САМИЙ проект
 *    Apps Script, де лежить Code.gs (script.google.com).
 * 2. Запустіть функцію submitTestResponses(). Скрипт сам знайде
 *    форму «ChromaFit — Кольоровий профіль компетенцій» у вашому
 *    Google Drive за назвою (FORM_NAME із Code.gs).
 *
 * УВАГА щодо ID: посилання виду
 *    https://docs.google.com/forms/d/e/1FAIpQLSc.../viewform
 * — це посилання ДЛЯ РЕСПОНДЕНТІВ, його ID для скрипта НЕ підходить.
 * Якщо хочете вказати форму вручну, відкрийте її в режимі
 * редагування і скопіюйте ID з URL:
 *    https://docs.google.com/forms/d/<ОЦЕ_ОСЬ_ID>/edit
 * та вставте у TEST_FORM_ID нижче. Якщо TEST_FORM_ID порожній —
 * працює автопошук за назвою.
 *
 * ВАЖЛИВО:
 * - Кожен «псевдонім» має префікс TEST_ (TEST_P01_A, TEST_S03…),
 *   щоб тестові рядки було легко відфільтрувати/видалити у Sheets.
 * - Якщо PAUSE_SUBMIT_TRIGGER = true, скрипт перед надсиланням
 *   тимчасово видаляє тригер onFormSubmit, щоб 47 відповідей
 *   НЕ запустили 47 викликів Claude API і 47 листів.
 *   Після тесту запустіть setupTrigger() ще раз, якщо потрібно.
 * - Програмне надсилання не заповнює email респондента, тому
 *   збір email тимчасово вимикається і вмикається назад.
 * ============================================================
 */

// =======================================================
// НАЛАШТУВАННЯ ТЕСТУ
// =======================================================

// Залиште порожнім ('') — форма знайдеться автоматично за назвою.
// Або вставте ID з URL РЕДАГУВАННЯ (docs.google.com/forms/d/<ID>/edit).
const TEST_FORM_ID = '';

const TEST_PAIRS = 20;  // пар (по 2 відповіді) = 40
const TEST_SOLO  = 7;   // соло-відповідей       = 7  → разом 47

// Видалити тригер onFormSubmit перед тестом (рекомендовано),
// щоб не витрачати Claude API на тестові дані.
const PAUSE_SUBMIT_TRIGGER = true;

// Посилання-заглушка для поля «резюме». Можна вставити реальне
// посилання на тестовий Google Doc, якщо хочете перевірити
// і зчитування резюме.
const TEST_RESUME_URL = 'https://drive.google.com/file/d/TEST_FAKE_FILE_ID/view';

// Пауза між надсиланнями, мс (щоб не впертися у квоти)
const SUBMIT_DELAY_MS = 400;


// =======================================================
// ПОШУК ФОРМИ
// =======================================================

/**
 * Повертає форму: за TEST_FORM_ID, якщо вказано, інакше шукає
 * у Drive форму з назвою FORM_NAME (константа з Code.gs).
 */
function getTestForm() {
  if (TEST_FORM_ID) {
    return FormApp.openById(TEST_FORM_ID);
  }

  const files = DriveApp.getFilesByType(MimeType.GOOGLE_FORMS);
  const matches = [];
  while (files.hasNext()) {
    const f = files.next();
    if (f.getName() === FORM_NAME && !f.isTrashed()) {
      matches.push(f);
    }
  }

  if (matches.length === 0) {
    throw new Error('Форму «' + FORM_NAME + '» не знайдено у Drive. ' +
                    'Вставте ID форми (з URL редагування) у TEST_FORM_ID.');
  }
  if (matches.length > 1) {
    Logger.log('УВАГА: знайдено ' + matches.length + ' форм із назвою «' +
               FORM_NAME + '». Використовую найновішу. ID усіх:');
    matches.forEach(f => Logger.log('  ' + f.getId() +
                                    ' (створено ' + f.getDateCreated() + ')'));
    matches.sort((a, b) => b.getDateCreated() - a.getDateCreated());
  }

  const form = FormApp.openById(matches[0].getId());
  Logger.log('Знайдено форму: ' + form.getEditUrl());
  return form;
}

/** Просто вивести ID та URL форми (для довідки). */
function logFormId() {
  const form = getTestForm();
  Logger.log('ID форми: ' + form.getId());
  Logger.log('URL редагування: ' + form.getEditUrl());
  Logger.log('URL для респондентів: ' + form.getPublishedUrl());
}


// =======================================================
// ГОЛОВНА ФУНКЦІЯ
// =======================================================

function submitTestResponses() {
  const form = getTestForm();

  if (PAUSE_SUBMIT_TRIGGER) {
    let removed = 0;
    ScriptApp.getProjectTriggers().forEach(t => {
      if (t.getHandlerFunction() === 'onFormSubmit') {
        ScriptApp.deleteTrigger(t);
        removed++;
      }
    });
    if (removed > 0) {
      Logger.log('Тригер onFormSubmit тимчасово видалено (' + removed +
                 ' шт.). Після тесту запустіть setupTrigger() знову.');
    }
  }

  // Програмний submit не працює зі збором email — тимчасово вимикаємо
  let emailWasCollected = false;
  try {
    emailWasCollected = form.collectsEmail();
    if (emailWasCollected) form.setCollectEmail(false);
  } catch (e) {
    Logger.log('Перевірку збору email пропущено: ' + e.message);
  }

  let submitted = 0;
  try {
    // 20 пар: партнер B = партнер A + невеликий «шум»
    for (let p = 1; p <= TEST_PAIRS; p++) {
      const pairId = 'P' + padNum(p);
      const personaA = makePersona('TEST_' + pairId + '_A', null);
      const personaB = makePersona('TEST_' + pairId + '_B', personaA);

      submitOneResponse(form, personaA);
      submitted++;
      Utilities.sleep(SUBMIT_DELAY_MS);

      submitOneResponse(form, personaB);
      submitted++;
      Utilities.sleep(SUBMIT_DELAY_MS);

      Logger.log('Пара ' + pairId + ' надіслана (' + submitted + '/47)');
    }

    // 7 соло
    for (let s = 1; s <= TEST_SOLO; s++) {
      const persona = makePersona('TEST_S' + padNum(s), null);
      submitOneResponse(form, persona);
      submitted++;
      Logger.log('Соло S' + padNum(s) + ' надіслано (' + submitted + '/47)');
      Utilities.sleep(SUBMIT_DELAY_MS);
    }
  } finally {
    if (emailWasCollected) {
      try { form.setCollectEmail(true); } catch (e) {
        Logger.log('Не вдалося увімкнути збір email назад: ' + e.message);
      }
    }
  }

  Logger.log('=== ГОТОВО: надіслано ' + submitted + ' тестових відповідей ===');
  Logger.log('Усього відповідей у формі: ' + form.getResponses().length);
}


// =======================================================
// ГЕНЕРАЦІЯ ПЕРСОНИ
// =======================================================

/**
 * Створює «персону» з відповідями на всі поля форми.
 * Якщо передано partner — генерує корельовані відповіді
 * (шкали = партнерські ±1, спільна локація, суміжний вік).
 */
function makePersona(name, partner) {
  const genders = ['Жіноча', 'Чоловіча', 'Інша / не вказую'];
  const ages = ['22-25', '26-30', '31-35', '36-40', '41-45', '46-50', '51+'];
  const education = ['Середня / ПТУ', 'Бакалавр', 'Магістр', 'PhD'];
  const fields = [
    'IT / розробка', 'HR / рекрутинг', 'Маркетинг / PR / реклама',
    'Продажі / розвиток бізнесу', 'Фінанси / банківська справа',
    'Креативні індустрії', 'Освіта / наука',
    'Медицина / охорона здоровʼя', 'Виробництво / логістика',
    'Державна служба', 'Інше'
  ];
  const experience = ['< 1', '1-3', '4-7', '8-12', '13-20', '21+'];
  const locations = [
    'Україна (Київ)', 'Україна (інші міста)', 'ЄС (Польща)',
    'ЄС (Німеччина)', 'ЄС (Чехія)', 'ЄС (інші країни)',
    'США / Канада', 'Великобританія', 'Інше'
  ];

  const persona = { name: name };

  if (partner) {
    // Партнери: та сама локація, суміжна вікова група,
    // шкальні відповіді — партнерські з шумом ±1
    persona.gender = pick(genders);
    persona.age = neighbor(ages, partner.age);
    persona.education = pick(education);
    persona.field = pick(fields);
    persona.experience = neighbor(experience, partner.experience);
    persona.location = partner.location;

    persona.domains = partner.domains.map(v => jitter(v, 1, 5));
    persona.sd = partner.sd.map(v => jitter(v, 1, 7));
    persona.bigfive = partner.bigfive.map(v => jitter(v, 1, 5));
    persona.luscher = mutatePermutation(partner.luscher);
  } else {
    persona.gender = pick(genders);
    persona.age = pick(ages);
    persona.education = pick(education);
    persona.field = pick(fields);
    persona.experience = pick(experience);
    persona.location = pick(locations);

    // 10 доменів, шкала 1-5 (з легким зсувом до середини)
    persona.domains = arrayOf(10, () => centeredRandom(1, 5));
    // 30 SD-шкал (10 кольорів × 3 пари), шкала 1-7
    persona.sd = arrayOf(30, () => centeredRandom(1, 7));
    // 20 айтемів Big Five, шкала 1-5
    persona.bigfive = arrayOf(20, () => centeredRandom(1, 5));
    // Люшер: випадкова перестановка позицій 1-8
    persona.luscher = shuffle([1, 2, 3, 4, 5, 6, 7, 8]);
  }

  persona.resumeUrl = TEST_RESUME_URL;
  return persona;
}


// =======================================================
// НАДСИЛАННЯ ОДНІЄЇ ВІДПОВІДІ
// =======================================================

const LUSCHER_COLORS = ['Синій', 'Зелений', 'Червоний', 'Жовтий',
                        'Фіолетовий', 'Коричневий', 'Чорний', 'Сірий'];

function submitOneResponse(form, persona) {
  const formResponse = form.createResponse();

  let domainIdx = 0;   // лічильник шкал Блоку 3 (10 доменів)
  let sdIdx = 0;       // лічильник SD-шкал Блоку 4 (30 шт.)

  form.getItems().forEach(item => {
    const type = item.getType();
    const title = item.getTitle();

    if (type === FormApp.ItemType.TEXT) {
      const textItem = item.asTextItem();
      if (title.includes('псевдонім')) {
        formResponse.withItemResponse(textItem.createResponse(persona.name));
      } else if (title.includes('резюме')) {
        formResponse.withItemResponse(textItem.createResponse(persona.resumeUrl));
      }

    } else if (type === FormApp.ItemType.MULTIPLE_CHOICE) {
      const mcItem = item.asMultipleChoiceItem();
      let answer = null;

      if (title === 'Стать') answer = persona.gender;
      else if (title === 'Ваш вік') answer = persona.age;
      else if (title === 'Рівень освіти') answer = persona.education;
      else if (title === 'Професійна сфера') answer = persona.field;
      else if (title.includes('Досвід')) answer = persona.experience;
      else if (title.includes('локація')) answer = persona.location;
      else if (title.startsWith('Позиція кольору')) {
        const colorIdx = LUSCHER_COLORS.findIndex(c => title.endsWith(c));
        if (colorIdx !== -1) answer = String(persona.luscher[colorIdx]);
      }

      if (answer !== null) {
        formResponse.withItemResponse(mcItem.createResponse(answer));
      }

    } else if (type === FormApp.ItemType.SCALE) {
      const scaleItem = item.asScaleItem();
      let value = null;

      if (title.startsWith('Колір ')) {
        value = persona.sd[sdIdx++];               // Блок 4: SD
      } else if (/^\d+\. /.test(title)) {
        const bfIdx = parseInt(title, 10) - 1;     // Блок 6: Big Five
        value = persona.bigfive[bfIdx];
      } else {
        value = persona.domains[domainIdx++];      // Блок 3: 10 доменів
      }

      if (value !== null && value !== undefined) {
        formResponse.withItemResponse(scaleItem.createResponse(value));
      }

    } else if (type === FormApp.ItemType.CHECKBOX) {
      const cbItem = item.asCheckboxItem();
      if (title.includes('погоджуюся')) {
        formResponse.withItemResponse(cbItem.createResponse(['Так, я погоджуюся']));
      }
    }
    // PAGE_BREAK та інші типи пропускаємо
  });

  formResponse.submit();
}


// =======================================================
// ДОПОМІЖНІ ФУНКЦІЇ
// =======================================================

function pick(arr) {
  return arr[Math.floor(Math.random() * arr.length)];
}

function arrayOf(n, fn) {
  return Array.from({ length: n }, fn);
}

// Випадкове ціле у [min, max] з м'яким зсувом до середини шкали
function centeredRandom(min, max) {
  const a = min + Math.random() * (max - min);
  const b = min + Math.random() * (max - min);
  return Math.round((a + b) / 2);
}

// value ± 0..1 у межах [min, max]
function jitter(value, min, max) {
  const delta = Math.floor(Math.random() * 3) - 1; // -1, 0, +1
  return Math.min(max, Math.max(min, value + delta));
}

// Сусідній елемент масиву (для «суміжного» віку/досвіду партнера)
function neighbor(arr, value) {
  const idx = arr.indexOf(value);
  if (idx === -1) return pick(arr);
  const shift = Math.floor(Math.random() * 3) - 1; // -1, 0, +1
  const next = Math.min(arr.length - 1, Math.max(0, idx + shift));
  return arr[next];
}

function shuffle(arr) {
  const a = arr.slice();
  for (let i = a.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [a[i], a[j]] = [a[j], a[i]];
  }
  return a;
}

// Легка мутація перестановки Люшера: 1-2 випадкові транспозиції
// (партнерські вподобання схожі, але не ідентичні)
function mutatePermutation(perm) {
  const p = perm.slice();
  const swaps = 1 + Math.floor(Math.random() * 2);
  for (let s = 0; s < swaps; s++) {
    const i = Math.floor(Math.random() * p.length);
    const j = Math.floor(Math.random() * p.length);
    [p[i], p[j]] = [p[j], p[i]];
  }
  return p;
}

function padNum(n) {
  return (n < 10 ? '0' : '') + n;
}


// =======================================================
// ОЧИЩЕННЯ (обережно!)
// =======================================================

/**
 * УВАГА: видаляє ВСІ відповіді форми (Google Forms не дозволяє
 * видаляти вибірково через Apps Script). Рядки у звʼязаній
 * таблиці Sheets залишаються — тестові рядки там можна
 * відфільтрувати за префіксом TEST_ у стовпці імені й видалити
 * вручну.
 *
 * Використовуйте ТІЛЬКИ на тестовій формі, поки немає
 * справжніх відповідей.
 */
function deleteAllFormResponses() {
  const form = getTestForm();
  const count = form.getResponses().length;
  form.deleteAllResponses();
  Logger.log('Видалено ' + count + ' відповідей із форми.');
}
