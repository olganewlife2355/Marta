/*
 * ════════════════════════════════════════════════════════════════
 *  АВТОРЕСПОНДЕНТ для тестування форми
 *  «Психологічне дослідження подружніх стосунків»
 * ════════════════════════════════════════════════════════════════
 *  Генерує та надсилає 47 тестових відповідей:
 *    - 20 пар  (40 відповідей: жінка + чоловік зі СПІЛЬНИМ кодом
 *               TEST-P-001 … TEST-P-020, спільна демографія)
 *    - 7 соло  (TEST-S-001 … TEST-S-007, випадкова стать)
 *
 *  КУДИ ВСТАВЛЯТИ:
 *  НЕ вставляйте цей код усередину основного скрипта!
 *  1. Відкрийте ваш проект на script.google.com
 *  2. Ліворуч у панелі «Файли» натисніть «+» → «Скрипт»
 *  3. Назвіть файл, наприклад, TestAutoresponder
 *  4. Вставте туди ВЕСЬ цей код і збережіть (Ctrl+S)
 *  (Усі файли проекту працюють як один — окремий файл нічого
 *   не ламає, а видалити його потім можна одним кліком.)
 *
 *  ЯК ЗАПУСТИТИ:
 *  1. Форма вже має бути створена (step1 → step2 → step3 виконані).
 *  2. Угорі оберіть функцію submitTestResponses і натисніть
 *     «Виконати». При першому запуску підтвердіть дозволи.
 *  3. Прогрес видно у «Журнал виконання» (Ctrl+Enter).
 *
 *  ЯК ПРИБРАТИ ТЕСТОВІ ДАНІ:
 *  Усі тестові відповіді мають код із префіксом TEST- —
 *  їх легко знайти у відповідях/таблиці. Функція
 *  deleteAllFormResponses() видаляє ВСІ відповіді форми
 *  (використовуйте лише поки немає справжніх).
 * ════════════════════════════════════════════════════════════════
 */

// ── Налаштування ────────────────────────────────────────────────
// ID форми (з URL редагування docs.google.com/forms/d/<ID>/edit).
// Якщо залишити порожнім (''), візьметься FORM_ID, збережений
// вашим step1_CreateBase у ScriptProperties.
var TEST_FORM_ID = '1mBDDIAxktfi9slrlcwDqqTs2Vb-bEgIwFW4hzrKzdBw';

var TEST_PAIRS = 20;      // пар (по 2 відповіді)  = 40
var TEST_SOLO = 7;        // соло-відповідей       = 7   → разом 47
var TEST_CODE_PREFIX = 'TEST-';  // префікс кодів тестових відповідей
var SUBMIT_DELAY_MS = 300;       // пауза між надсиланнями


// ════════════════════════════════════════════════════════════════
//  ГОЛОВНА ФУНКЦІЯ — запускайте саме її
// ════════════════════════════════════════════════════════════════
function submitTestResponses() {
  var form = getTestForm_();
  Logger.log('Форма: ' + form.getTitle());

  var submitted = 0;

  // 20 пар: жінка + чоловік зі спільним кодом і демографією
  for (var p = 1; p <= TEST_PAIRS; p++) {
    var code = TEST_CODE_PREFIX + 'P-' + pad3_(p);
    var shared = makeSharedPairData_();

    var wife = makePersona_(code, 'Жіноча', shared);
    var husband = makePersona_(code, 'Чоловіча', shared);

    submitOneResponse_(form, wife);
    submitted++;
    Utilities.sleep(SUBMIT_DELAY_MS);

    submitOneResponse_(form, husband);
    submitted++;
    Utilities.sleep(SUBMIT_DELAY_MS);

    Logger.log('Пара ' + code + ' надіслана (' + submitted + '/47)');
  }

  // 7 соло: випадкова стать, індивідуальний код
  for (var s = 1; s <= TEST_SOLO; s++) {
    var soloCode = TEST_CODE_PREFIX + 'S-' + pad3_(s);
    var soloGender = Math.random() < 0.5 ? 'Жіноча' : 'Чоловіча';
    var solo = makePersona_(soloCode, soloGender, null);

    submitOneResponse_(form, solo);
    submitted++;
    Logger.log('Соло ' + soloCode + ' (' + soloGender + ') надіслано (' +
               submitted + '/47)');
    Utilities.sleep(SUBMIT_DELAY_MS);
  }

  Logger.log('════════════════════════════════════');
  Logger.log('ГОТОВО: надіслано ' + submitted + ' тестових відповідей.');
  Logger.log('Усього відповідей у формі зараз: ' + form.getResponses().length);
}


// ════════════════════════════════════════════════════════════════
//  Пошук форми
// ════════════════════════════════════════════════════════════════
function getTestForm_() {
  var id = TEST_FORM_ID;
  if (!id) {
    id = PropertiesService.getScriptProperties().getProperty('FORM_ID');
  }
  if (!id) {
    throw new Error('Не знайдено ID форми. Вставте його у TEST_FORM_ID ' +
                    'або спочатку запустіть step1_CreateBase.');
  }
  return FormApp.openById(id);
}


// ════════════════════════════════════════════════════════════════
//  Генерація персони
// ════════════════════════════════════════════════════════════════

// Спільні дані пари: партнери мають однакові відповіді про сім'ю
function makeSharedPairData_() {
  var status = Math.random() < 0.7 ?
    'Одружений / Заміжня (офіційний шлюб)' :
    'У стосунках (цивільний шлюб)';
  var duration = pick_(['Менше 1 року', '1–3 роки', '4–7 років',
                        '8–15 років', 'Більше 15 років']);
  var children = pick_(['Так', 'Так', 'Ні', 'Очікуємо']); // «Так» частіше
  var baseAge = 22 + Math.floor(Math.random() * 20);      // 22–41

  return { status: status, duration: duration,
           children: children, baseAge: baseAge };
}

function makePersona_(code, gender, shared) {
  var persona = { code: code, gender: gender };

  if (shared) {
    // Учасник пари: спільна демографія, вік близький до партнерського
    persona.status = shared.status;
    persona.duration = shared.duration;
    persona.children = shared.children;
    persona.age = String(shared.baseAge + Math.floor(Math.random() * 5));
  } else {
    // Соло-учасник
    persona.status = pick_([
      'Одружений / Заміжня (офіційний шлюб)',
      'Одружений / Заміжня (офіційний шлюб)',
      'У стосунках (цивільний шлюб)',
      'Розлучений / Розлучена'
    ]);
    persona.duration = pick_(['Менше 1 року', '1–3 роки', '4–7 років',
                              '8–15 років', 'Більше 15 років']);
    persona.children = pick_(['Так', 'Ні', 'Очікуємо']);
    persona.age = String(22 + Math.floor(Math.random() * 25));
  }

  // SPANE: 12 айтемів (1-5). Позитивні та негативні узгоджені:
  // що вище благополуччя — то вищі позитивні й нижчі негативні.
  var wellbeing = 2 + Math.floor(Math.random() * 3); // 2..4
  var positiveIdx = [0, 2, 4, 6, 9, 11]; // Позитивно, Добре, Приємно…
  persona.spane = [];
  for (var i = 0; i < 12; i++) {
    var isPositive = positiveIdx.indexOf(i) !== -1;
    var base = isPositive ? wellbeing : (6 - wellbeing);
    persona.spane.push(clamp_(base + randShift_(), 1, 5));
  }

  return persona;
}


// ════════════════════════════════════════════════════════════════
//  Надсилання однієї відповіді
// ════════════════════════════════════════════════════════════════
function submitOneResponse_(form, persona) {
  var formResponse = form.createResponse();

  // Відстежуємо, на якій «гілці» форми ми зараз:
  // 'common' → до розгалуження; 'Жіноча'/'Чоловіча' → варіанти.
  // Заповнюємо тільки спільну частину і гілку своєї статі —
  // так само, як зробив би живий респондент.
  var branch = 'common';
  var spaneIdx = 0;

  form.getItems().forEach(function(item) {
    var type = item.getType();
    var title = item.getTitle();

    if (type === FormApp.ItemType.PAGE_BREAK) {
      if (title.indexOf('Жіночий') !== -1) branch = 'Жіноча';
      else if (title.indexOf('Чоловічий') !== -1) branch = 'Чоловіча';
      return;
    }

    if (branch !== 'common' && branch !== persona.gender) return;

    if (type === FormApp.ItemType.TEXT) {
      var textItem = item.asTextItem();
      if (title.indexOf('Код') !== -1) {
        formResponse.withItemResponse(textItem.createResponse(persona.code));
      } else if (title.indexOf('вік') !== -1) {
        formResponse.withItemResponse(textItem.createResponse(persona.age));
      }

    } else if (type === FormApp.ItemType.MULTIPLE_CHOICE) {
      var mcItem = item.asMultipleChoiceItem();
      var answer = null;

      if (title === 'Ваша стать') answer = persona.gender;
      else if (title.indexOf('сімейний стан') !== -1) answer = persona.status;
      else if (title.indexOf('Тривалість') !== -1) answer = persona.duration;
      else if (title.indexOf('діти') !== -1) answer = persona.children;
      else {
        // Конфліктні ситуації (5 варіантів) та РОД (4 варіанти):
        // беремо випадковий варіант із РЕАЛЬНОГО списку відповідей
        // цього питання — жодних розбіжностей у текстах.
        var choices = mcItem.getChoices();
        answer = choices[centeredIndex_(choices.length)].getValue();
      }

      if (answer !== null) {
        formResponse.withItemResponse(mcItem.createResponse(answer));
      }

    } else if (type === FormApp.ItemType.SCALE) {
      var scaleItem = item.asScaleItem();
      var value;
      if (/^\d+\. Я відчував/.test(title)) {
        value = persona.spane[spaneIdx++];             // SPANE
      } else {
        value = randInt_(scaleItem.getLowerBound(),    // будь-яка інша шкала
                         scaleItem.getUpperBound());
      }
      formResponse.withItemResponse(scaleItem.createResponse(value));
    }
    // SECTION_HEADER та інше — пропускаємо
  });

  formResponse.submit();
}


// ════════════════════════════════════════════════════════════════
//  Допоміжні
// ════════════════════════════════════════════════════════════════
function pick_(arr) {
  return arr[Math.floor(Math.random() * arr.length)];
}

function randInt_(min, max) {
  return min + Math.floor(Math.random() * (max - min + 1));
}

// -1 / 0 / +1
function randShift_() {
  return Math.floor(Math.random() * 3) - 1;
}

function clamp_(v, min, max) {
  return Math.min(max, Math.max(min, v));
}

// Випадковий індекс 0..n-1 з м'яким зсувом до середини
// (крайні відповіді трапляються рідше — реалістичніше)
function centeredIndex_(n) {
  var a = Math.random() * n;
  var b = Math.random() * n;
  return Math.min(n - 1, Math.floor((a + b) / 2));
}

function pad3_(n) {
  return ('000' + n).slice(-3);
}


// ════════════════════════════════════════════════════════════════
//  ОЧИЩЕННЯ (обережно!)
//  Видаляє ВСІ відповіді форми — Google Forms не дає видаляти
//  вибірково через скрипт. Рядки у зв'язаній таблиці Sheets
//  лишаються: тестові там видно за кодом TEST- у стовпці
//  «Код пари», їх можна видалити вручну.
// ════════════════════════════════════════════════════════════════
function deleteAllFormResponses() {
  var form = getTestForm_();
  var count = form.getResponses().length;
  form.deleteAllResponses();
  Logger.log('Видалено ' + count + ' відповідей із форми.');
}
