/*
 * ════════════════════════════════════════════════════════════════
 *  АВТОРЕСПОНДЕНТ для тестування форми
 *  «Психологічне дослідження подружніх стосунків»
 *  (версія 4 — з аномальними/екстремальними респондентами)
 * ════════════════════════════════════════════════════════════════
 *  Генерує та надсилає 47 тестових відповідей:
 *    - 20 пар  (40 відповідей: жінка + чоловік зі СПІЛЬНИМ кодом
 *               TEST-P-001 … TEST-P-020, спільна демографія)
 *    - 7 соло  (TEST-S-001 … TEST-S-007, випадкова стать)
 *
 *  АНОМАЛЬНІ РЕСПОНДЕНТИ (для перевірки чистки даних):
 *    TEST-P-018 — обоє партнерів відповідають ЛИШЕ середніми
 *                 значеннями (класичний «midline responding»)
 *    TEST-P-019 — жінка на все відповідає МАКСИМУМОМ,
 *                 чоловік — МІНІМУМОМ (дискордантна пара)
 *    TEST-P-020 — обоє «зигзаг» (макс/мін по черзі) +
 *                 аномальний вік: жінці 17, чоловікові 85
 *    TEST-S-006 — суцільний максимум («straight-lining»)
 *    TEST-S-007 — суцільна середина + вік 90 при шлюбі
 *                 «Більше 15 років»
 *  Решта (17 пар і 5 соло) — звичайні реалістичні відповіді.
 *
 *  ЯК ЗАПУСТИТИ:
 *  1. Оберіть угорі функцію submitTestResponses → «Виконати».
 *  2. Прогрес видно у «Журнал виконання» (Ctrl+Enter).
 *  3. Ліміт часу (6 хв) обходиться АВТОМАТИЧНО: скрипт зупиниться
 *     завчасно, сам поставить тригер і продовжить через ~1 хвилину
 *     у фоні — нічого перезапускати не треба. Фонові запуски видно
 *     у меню «Виконання» (ліворуч, іконка ▶ зі списком).
 *
 *  ДОДАТКОВІ ФУНКЦІЇ:
 *  - resetTestProgress()      — скинути лічильник прогресу
 *  - deleteAllFormResponses() — видалити ВСІ відповіді форми
 *    і скинути прогрес (лише поки немає справжніх відповідей!)
 * ════════════════════════════════════════════════════════════════
 */

// ── Налаштування ────────────────────────────────────────────────
// ID форми (з URL редагування docs.google.com/forms/d/<ID>/edit).
// Якщо залишити порожнім (''), візьметься FORM_ID зі ScriptProperties.
var TEST_FORM_ID = '1mBDDIAxktfi9slrlcwDqqTs2Vb-bEgIwFW4hzrKzdBw';

var TEST_PAIRS = 20;             // пар (по 2 відповіді)  = 40
var TEST_SOLO = 7;               // соло-відповідей       = 7  → разом 47
var TEST_CODE_PREFIX = 'TEST-';  // префікс кодів тестових відповідей

// Запас до 6-хвилинного ліміту: зупиняємось на 4.5 хв
// і автоматично продовжуємо через тригер
var MAX_RUNTIME_MS = 4.5 * 60 * 1000;

// ── Аномальні респонденти ───────────────────────────────────────
// Стилі відповідей: 'max' — усе максимум; 'min' — усе мінімум;
// 'mid' — усе середнє; 'zigzag' — макс/мін по черзі.
// ageOverride / durationOverride — підміна демографії.
var PAIR_ANOMALIES = {
  18: { wife: { style: 'mid' },
        husband: { style: 'mid' } },
  19: { wife: { style: 'max' },
        husband: { style: 'min' } },
  20: { wife: { style: 'zigzag', ageOverride: '17' },
        husband: { style: 'zigzag', ageOverride: '85' } }
};
var SOLO_ANOMALIES = {
  6: { style: 'max' },
  7: { style: 'mid', ageOverride: '90',
       durationOverride: 'Більше 15 років' }
};


// ════════════════════════════════════════════════════════════════
//  ГОЛОВНА ФУНКЦІЯ — запускайте саме її
//  (при зупинці за часом продовжиться сама, через тригер)
// ════════════════════════════════════════════════════════════════
function submitTestResponses() {
  var startTime = Date.now();
  var props = PropertiesService.getScriptProperties();
  var pairsDone = parseInt(props.getProperty('TEST_PAIRS_DONE') || '0', 10);
  var soloDone = parseInt(props.getProperty('TEST_SOLO_DONE') || '0', 10);

  if (pairsDone >= TEST_PAIRS && soloDone >= TEST_SOLO) {
    clearContinuationTriggers_();
    Logger.log('Усі 47 тестових відповідей уже надіслано раніше.');
    Logger.log('Щоб згенерувати заново: спершу запустіть resetTestProgress().');
    return;
  }

  var form = getTestForm_();
  Logger.log('Форма: ' + form.getTitle());
  if (pairsDone > 0 || soloDone > 0) {
    Logger.log('ПРОДОВЖУЮ з місця зупинки: пар ' + pairsDone + '/' +
               TEST_PAIRS + ', соло ' + soloDone + '/' + TEST_SOLO);
  }

  // Читаємо структуру форми ОДИН раз
  var plan = buildFormPlan_(form);
  Logger.log('Прочитано питань: ' + plan.length + '. Починаю надсилання...');

  // ── Пари ──────────────────────────────────────────────────
  for (var p = pairsDone + 1; p <= TEST_PAIRS; p++) {
    if (Date.now() - startTime > MAX_RUNTIME_MS) {
      logTimeLimit_(p - 1, soloDone);
      return;
    }

    var code = TEST_CODE_PREFIX + 'P-' + pad3_(p);
    var shared = makeSharedPairData_();
    var anomaly = PAIR_ANOMALIES[p] || {};

    submitOneResponse_(form, plan,
      makePersona_(code, 'Жіноча', shared, anomaly.wife));
    submitOneResponse_(form, plan,
      makePersona_(code, 'Чоловіча', shared, anomaly.husband));

    props.setProperty('TEST_PAIRS_DONE', String(p));
    Logger.log('Пара ' + code + (PAIR_ANOMALIES[p] ? ' [АНОМАЛЬНА]' : '') +
               ' надіслана (' + (p * 2) + '/47)');
  }

  // ── Соло ──────────────────────────────────────────────────
  for (var s = soloDone + 1; s <= TEST_SOLO; s++) {
    if (Date.now() - startTime > MAX_RUNTIME_MS) {
      logTimeLimit_(TEST_PAIRS, s - 1);
      return;
    }

    var soloCode = TEST_CODE_PREFIX + 'S-' + pad3_(s);
    var soloGender = Math.random() < 0.5 ? 'Жіноча' : 'Чоловіча';

    submitOneResponse_(form, plan,
      makePersona_(soloCode, soloGender, null, SOLO_ANOMALIES[s]));

    props.setProperty('TEST_SOLO_DONE', String(s));
    Logger.log('Соло ' + soloCode + ' (' + soloGender + ')' +
               (SOLO_ANOMALIES[s] ? ' [АНОМАЛЬНЕ]' : '') +
               ' надіслано (' + (TEST_PAIRS * 2 + s) + '/47)');
  }

  clearContinuationTriggers_();
  Logger.log('════════════════════════════════════');
  Logger.log('ГОТОВО: усі 47 тестових відповідей надіслано.');
  Logger.log('Аномальні: TEST-P-018 (середина), TEST-P-019 (макс/мін), ' +
             'TEST-P-020 (зигзаг, вік 17/85), TEST-S-006 (максимум), ' +
             'TEST-S-007 (середина, вік 90).');
  Logger.log('Усього відповідей у формі зараз: ' + form.getResponses().length);
}


// Зупинка за часом: плануємо автоматичне продовження через ~1 хв
function logTimeLimit_(pairsDone, soloDone) {
  var total = pairsDone * 2 + soloDone;
  scheduleContinuation_();
  Logger.log('════════════════════════════════════');
  Logger.log('Наближається ліміт часу виконання (6 хв).');
  Logger.log('Надіслано поки що: ' + total + '/47 ' +
             '(пар: ' + pairsDone + '/' + TEST_PAIRS +
             ', соло: ' + soloDone + '/' + TEST_SOLO + ').');
  Logger.log('▶ ПРОДОВЖЕННЯ ЗАПЛАНОВАНО АВТОМАТИЧНО через ~1 хвилину — ' +
             'нічого робити не треба. Фоновий запуск буде видно у меню ' +
             '«Виконання». Дублікатів не буде.');
}


// Одноразовий тригер, який сам перезапустить submitTestResponses
function scheduleContinuation_() {
  clearContinuationTriggers_();
  ScriptApp.newTrigger('submitTestResponses')
    .timeBased()
    .after(60 * 1000)
    .create();
}


// Прибираємо тригери продовження (щоб не накопичувались)
function clearContinuationTriggers_() {
  ScriptApp.getProjectTriggers().forEach(function(t) {
    if (t.getHandlerFunction() === 'submitTestResponses') {
      ScriptApp.deleteTrigger(t);
    }
  });
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
//  План форми: читаємо всі питання, тексти варіантів і межі шкал
//  ОДИН раз, щоб не смикати сервер на кожній із 47 відповідей
// ════════════════════════════════════════════════════════════════
function buildFormPlan_(form) {
  var plan = [];
  var branch = 'common'; // до розгалуження / 'Жіноча' / 'Чоловіча'
  var spaneIdx = 0;

  form.getItems().forEach(function(item) {
    var type = item.getType();
    var title = item.getTitle();

    if (type === FormApp.ItemType.PAGE_BREAK) {
      if (title.indexOf('Жіночий') !== -1) branch = 'Жіноча';
      else if (title.indexOf('Чоловічий') !== -1) branch = 'Чоловіча';
      return;
    }

    if (type === FormApp.ItemType.TEXT) {
      var kind = null;
      if (title.indexOf('Код') !== -1) kind = 'code';
      else if (title.indexOf('вік') !== -1) kind = 'age';
      if (kind) plan.push({ kind: kind, branch: branch, item: item.asTextItem() });

    } else if (type === FormApp.ItemType.MULTIPLE_CHOICE) {
      var mcItem = item.asMultipleChoiceItem();
      var kindMc = 'mcRandom';
      if (title === 'Ваша стать') kindMc = 'gender';
      else if (title.indexOf('сімейний стан') !== -1) kindMc = 'status';
      else if (title.indexOf('Тривалість') !== -1) kindMc = 'duration';
      else if (title.indexOf('діти') !== -1) kindMc = 'children';

      var entry = { kind: kindMc, branch: branch, item: mcItem };
      if (kindMc === 'mcRandom') {
        // Конфліктні ситуації та РОД: запам'ятовуємо реальні
        // тексти варіантів цього питання
        entry.choices = mcItem.getChoices().map(function(c) {
          return c.getValue();
        });
      }
      plan.push(entry);

    } else if (type === FormApp.ItemType.SCALE) {
      var scaleItem = item.asScaleItem();
      if (/^\d+\. Я відчував/.test(title)) {
        plan.push({ kind: 'spane', branch: branch, item: scaleItem,
                    spaneIdx: spaneIdx++,
                    min: scaleItem.getLowerBound(),
                    max: scaleItem.getUpperBound() });
      } else {
        plan.push({ kind: 'scaleRandom', branch: branch, item: scaleItem,
                    min: scaleItem.getLowerBound(),
                    max: scaleItem.getUpperBound() });
      }
    }
    // SECTION_HEADER та інше — пропускаємо
  });

  return plan;
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

// anomaly (необов'язково): { style, ageOverride, durationOverride }
function makePersona_(code, gender, shared, anomaly) {
  anomaly = anomaly || {};
  var persona = { code: code, gender: gender,
                  style: anomaly.style || 'normal' };

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

  // Аномальні підміни демографії
  if (anomaly.ageOverride) persona.age = anomaly.ageOverride;
  if (anomaly.durationOverride) persona.duration = anomaly.durationOverride;

  // SPANE: 12 айтемів (1-5). Позитивні та негативні узгоджені:
  // що вище благополуччя — то вищі позитивні й нижчі негативні.
  // (Для аномальних стилів ці значення буде проігноровано.)
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
//  Надсилання однієї відповіді (за готовим планом — швидко)
// ════════════════════════════════════════════════════════════════
function submitOneResponse_(form, plan, persona) {
  var formResponse = form.createResponse();
  var answered = 0; // лічильник відповідей — потрібен для стилю «зигзаг»

  plan.forEach(function(q) {
    // Заповнюємо спільну частину і тільки гілку своєї статі —
    // так само, як зробив би живий респондент
    if (q.branch !== 'common' && q.branch !== persona.gender) return;

    switch (q.kind) {
      case 'code':
        formResponse.withItemResponse(q.item.createResponse(persona.code));
        break;
      case 'age':
        formResponse.withItemResponse(q.item.createResponse(persona.age));
        break;
      case 'gender':
        formResponse.withItemResponse(q.item.createResponse(persona.gender));
        break;
      case 'status':
        formResponse.withItemResponse(q.item.createResponse(persona.status));
        break;
      case 'duration':
        formResponse.withItemResponse(q.item.createResponse(persona.duration));
        break;
      case 'children':
        formResponse.withItemResponse(q.item.createResponse(persona.children));
        break;
      case 'mcRandom':
        var idx = styleChoiceIndex_(persona.style, q.choices.length, answered);
        formResponse.withItemResponse(q.item.createResponse(q.choices[idx]));
        break;
      case 'spane':
        var vs = (persona.style === 'normal') ?
          persona.spane[q.spaneIdx] :
          styleScaleValue_(persona.style, q.min, q.max, answered);
        formResponse.withItemResponse(q.item.createResponse(vs));
        break;
      case 'scaleRandom':
        var vr = (persona.style === 'normal') ?
          randInt_(q.min, q.max) :
          styleScaleValue_(persona.style, q.min, q.max, answered);
        formResponse.withItemResponse(q.item.createResponse(vr));
        break;
    }
    answered++;
  });

  formResponse.submit();
}


// ════════════════════════════════════════════════════════════════
//  Стилі відповідей (для аномальних респондентів)
// ════════════════════════════════════════════════════════════════

// Індекс варіанта у списку з n відповідей
function styleChoiceIndex_(style, n, counter) {
  switch (style) {
    case 'max': return n - 1;                        // завжди останній
    case 'min': return 0;                            // завжди перший
    case 'mid': return Math.floor((n - 1) / 2);      // завжди середній
    case 'zigzag': return (counter % 2 === 0) ? n - 1 : 0;
    default: return centeredIndex_(n);               // 'normal'
  }
}

// Значення шкали від min до max
function styleScaleValue_(style, min, max, counter) {
  switch (style) {
    case 'max': return max;
    case 'min': return min;
    case 'mid': return Math.round((min + max) / 2);
    case 'zigzag': return (counter % 2 === 0) ? max : min;
    default: return randInt_(min, max);
  }
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
//  Скинути прогрес (щоб згенерувати 47 відповідей заново)
// ════════════════════════════════════════════════════════════════
function resetTestProgress() {
  var props = PropertiesService.getScriptProperties();
  props.deleteProperty('TEST_PAIRS_DONE');
  props.deleteProperty('TEST_SOLO_DONE');
  Logger.log('Прогрес тесту скинуто. Наступний запуск ' +
             'submitTestResponses почне з TEST-P-001.');
}


// ════════════════════════════════════════════════════════════════
//  ОЧИЩЕННЯ (обережно!)
//  Видаляє ВСІ відповіді форми — Google Forms не дає видаляти
//  вибірково через скрипт. Також скидає прогрес тесту.
//  Рядки у зв'язаній таблиці Sheets лишаються: тестові там видно
//  за кодом TEST- у стовпці «Код пари», видаліть їх вручну.
// ════════════════════════════════════════════════════════════════
function deleteAllFormResponses() {
  var form = getTestForm_();
  var count = form.getResponses().length;
  form.deleteAllResponses();
  resetTestProgress();
  Logger.log('Видалено ' + count + ' відповідей із форми.');
}
