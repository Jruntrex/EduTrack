# pyright: reportGeneralTypeIssues=false
# pyright: reportMissingImports=false
import os
import sys
import django
import random
from datetime import date, timedelta, datetime, time
from zoneinfo import ZoneInfo

KYIV_TZ = ZoneInfo("Europe/Kyiv")

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'edutrack_project.settings')
django.setup()

from main.models import (  # type: ignore[import]
    User, StudyGroup, Subject, TeachingAssignment,
    EvaluationType, ScheduleTemplate, Lesson,
    StudentPerformance, AbsenceReason, Classroom,
    TimeSlot, GradingScale, GradeRule,
)
from django.contrib.auth import get_user_model  # type: ignore[import]

User = get_user_model()

# ─────────────────────────────────────────────────────────────────────────────
# Теми занять по предметах
# ─────────────────────────────────────────────────────────────────────────────
SUBJECT_TOPICS: dict[str, list[str]] = {
    "Вища математика": [
        "Границі та неперервність функцій", "Похідна та правила диференціювання",
        "Невизначений інтеграл", "Визначений інтеграл та його застосування",
        "Ряди та їх збіжність", "Диференціальні рівняння першого порядку",
        "Числові методи інтегрування", "Функції багатьох змінних",
    ],
    "Об'єктно-орієнтоване програмування": [
        "Класи та об'єкти в Python/Java", "Спадкування та поліморфізм",
        "Інтерфейси та абстрактні класи", "Патерни проектування: Singleton, Factory",
        "SOLID принципи", "Generics та колекції", "Обробка виключень",
    ],
    "Бази даних": [
        "Реляційна модель та нормалізація", "SQL: SELECT, WHERE, GROUP BY",
        "JOINs та підзапити", "Транзакції та ACID", "Індекси та оптимізація",
        "Процедури та тригери", "NoSQL: MongoDB огляд",
    ],
    "Веб-технології": [
        "HTML5 та семантична розмітка", "CSS3: Flexbox та Grid",
        "JavaScript ES6+: Promise, async/await", "REST API та HTTP протокол",
        "Django: моделі, представлення, шаблони", "React: компоненти та стан",
        "Автентифікація та авторизація у вебі",
    ],
    "Алгоритми та структури даних": [
        "Аналіз складності O(n)", "Масиви та зв'язані списки",
        "Стеки та черги", "Дерева: BST, AVL", "Графи та обходи BFS/DFS",
        "Алгоритми сортування", "Динамічне програмування",
    ],
    "Комп'ютерні мережі": [
        "Модель OSI / TCP-IP", "Протоколи мережевого рівня: IP, ICMP",
        "Транспортний рівень: TCP vs UDP", "DNS та DHCP", "Маршрутизація та OSPF",
        "Безпека мереж: VPN, firewall", "Бездротові мережі 802.11",
    ],
    "Архітектура комп'ютерів": [
        "Архітектура фон Неймана", "Система числення та АЛП",
        "Організація пам'яті: ROM, RAM, кеш", "Процесор: конвеєр виконання",
        "Введення/виведення та переривання", "Паралельні архітектури",
    ],
    "Дискретна математика": [
        "Теорія множин та відношення", "Математична логіка та предикати",
        "Комбінаторика та перестановки", "Теорія графів",
        "Булева алгебра та схеми", "Рекурентні співвідношення",
    ],
    "Операційні системи": [
        "Процеси та потоки виконання", "Планування процесів CPU",
        "Синхронізація: mutex, semaphore", "Тупики та їх запобігання",
        "Управління пам'яттю: сторінки", "Файлові системи EXT4, NTFS",
        "Системні виклики Linux",
    ],
    "Програмування мовою Python": [
        "Основи синтаксису та типи даних", "Функції, лямбди, декоратори",
        "ООП в Python: dataclass, ABC", "NumPy: масиви та операції",
        "Pandas: DataFrame та аналіз", "Веб-скрейпінг: BeautifulSoup",
        "Асинхронне програмування asyncio",
    ],
    "Штучний інтелект та МН": [
        "Типи МН: supervised, unsupervised", "Лінійна та логістична регресія",
        "Дерева рішень та Random Forest", "SVM та метрики якості",
        "Нейронні мережі: перцептрон", "CNN для обробки зображень",
        "Трансформери та LLM огляд",
    ],
    "Безпека інформаційних систем": [
        "Основи криптографії", "Симетричне шифрування: AES, DES",
        "Асиметричне шифрування: RSA", "Цифровий підпис та сертифікати PKI",
        "OWASP Top 10 вразливостей", "SQL-ін'єкції та XSS", "Пентестинг та CTF",
    ],
    "Мобільна розробка": [
        "Огляд iOS та Android платформ", "React Native: основи",
        "Навігація та стек екранів", "Робота з REST API у мобільних",
        "Збереження даних: AsyncStorage, SQLite", "Push-сповіщення",
        "Публікація у App Store / Google Play",
    ],
    "Теорія ймовірностей та статистика": [
        "Аксіоматика ймовірності Колмогорова", "Теорема Байєса",
        "Випадкові величини та розподіли", "Нормальний розподіл та ЦГТ",
        "Вибірки та точкові оцінки", "Перевірка статистичних гіпотез",
        "Регресійний аналіз",
    ],
    "Системне програмування": [
        "Мова C: покажчики та пам'ять", "Системні виклики POSIX",
        "Управління процесами: fork, exec", "Міжпроцесна взаємодія: pipe, shared memory",
        "Потоки POSIX та синхронізація", "Сокети та мережеве програмування",
        "Профілювання: gprof, Valgrind",
    ],
}

COMMENTS_EXCELLENT = [
    "Відмінне розуміння матеріалу, повне розкриття теми",
    "Якісна відповідь, бездоганне виконання завдання",
    "Глибокий аналіз, чудові знання",
    "Виконано на найвищому рівні, продовжуйте в тому ж дусі",
    "Блискуча робота, усі концепції засвоєні",
]
COMMENTS_GOOD = [
    "Добра робота, є незначні недоліки",
    "Матеріал засвоєно, кілька дрібних помилок",
    "Непоганий результат, варто закріпити теорію",
    "Хороший рівень, але можна глибше",
    "Загалом вірно, зверніть увагу на деталі",
]
COMMENTS_SATISFACTORY = [
    "Задовільний рівень, потрібно більше практики",
    "Матеріал засвоєно частково, варто повторити",
    "Є суттєві прогалини, рекомендую додаткові вправи",
    "Недостатня підготовка, поверніться до теми",
    "Відповідь неповна, зверніть увагу на основні поняття",
]
COMMENTS_POOR = [
    "Слабке розуміння теми, необхідна консультація",
    "Матеріал не засвоєно, обов'язково повторіть",
    "Серйозні помилки, потребує індивідуальної роботи",
    "Рівень знань нижче допустимого мінімуму",
]

HOMEWORK_TEMPLATES = [
    "Повторити конспект лекції, виконати вправи 1–5 зі збірника",
    "Опрацювати §{n} підручника, підготуватись до тесту",
    "Реалізувати задачу з варіанту №{n}",
    "Підготувати реферат (1 стор.) за темою заняття",
    "Пройти онлайн-тест на платформі Moodle до п'ятниці",
    "Переглянути відео-лекцію та записати ключові тези",
    "Виконати лабораторну роботу та здати звіт",
]


def get_comment(points: int | None) -> str:
    if points is None:
        return ""
    if points >= 90:
        pool = COMMENTS_EXCELLENT
    elif points >= 75:
        pool = COMMENTS_GOOD
    elif points >= 55:
        pool = COMMENTS_SATISFACTORY
    else:
        pool = COMMENTS_POOR
    return random.choice(pool) if random.random() < 0.55 else ""


def get_homework() -> str:
    if random.random() < 0.35:
        return random.choice(HOMEWORK_TEMPLATES).replace("{n}", str(random.randint(1, 20)))
    return ""


_used_topics: dict[str, int] = {}


def next_topic(subject_name: str) -> str:
    topics = SUBJECT_TOPICS.get(subject_name, ["Тема заняття"])
    idx = _used_topics.get(subject_name, 0)
    topic = topics[idx % len(topics)]
    _used_topics[subject_name] = idx + 1
    return topic


# ─────────────────────────────────────────────────────────────────────────────
# Основна функція
# ─────────────────────────────────────────────────────────────────────────────
def create_initial_data() -> None:
    print("Очищення бази даних...")
    for model in [
        StudentPerformance, Lesson, ScheduleTemplate, EvaluationType,
        TeachingAssignment, Subject, StudyGroup, AbsenceReason,
        Classroom, TimeSlot, GradeRule, GradingScale,
    ]:
        model.objects.all().delete()
    User.objects.exclude(is_superuser=True).delete()
    print("База очищена.\n")

    # ── 1. Причини пропусків ─────────────────────────────────────────────────
    reasons_data = [
        ("Н",  "Неявка без поважної причини",  False, "#ef4444", 0),
        ("Б",  "Хвороба (лікарняний)",          True,  "#f97316", 1),
        ("ПП", "Поважна причина",                True,  "#3b82f6", 2),
        ("В",  "Відрядження / конференція",      True,  "#8b5cf6", 3),
    ]
    reasons = [
        AbsenceReason.objects.create(code=c, description=d, is_respectful=r, color=col, order=o)
        for c, d, r, col, o in reasons_data
    ]
    print(f"  Причини пропусків: {len(reasons)}")

    # ── 2. Шкала оцінювання (100-бальна ЄКТС) ───────────────────────────────
    scale = GradingScale.objects.create(name="100-бальна шкала ЄКТС", is_default=True)
    for label, mn, mx, color in [
        ("Відмінно (A)",       90, 100, "#22c55e"),
        ("Добре (B)",          82,  89, "#84cc16"),
        ("Добре (C)",          74,  81, "#a3e635"),
        ("Задовільно (D)",     64,  73, "#eab308"),
        ("Задовільно (E)",     55,  63, "#f97316"),
        ("Незадовільно (FX)",   0,  54, "#ef4444"),
    ]:
        GradeRule.objects.create(scale=scale, label=label, min_points=mn, max_points=mx, color=color)
    print("  Шкала оцінювання: 100-бальна ЄКТС")

    # ── 3. Навчальні групи ───────────────────────────────────────────────────
    groups_data = [
        ("КН-41",  2022, 2026, "Комп'ютерні науки",                  4),
        ("КН-42",  2022, 2026, "Комп'ютерні науки",                  4),
        ("ІПЗ-31", 2023, 2027, "Інженерія програмного забезпечення", 3),
        ("ІПЗ-32", 2023, 2027, "Інженерія програмного забезпечення", 3),
        ("ШІ-21",  2024, 2028, "Штучний інтелект та наука про дані", 2),
    ]
    groups = [
        StudyGroup.objects.create(
            name=nm, year_of_entry=ye, graduation_year=gy, specialty=sp, course=co
        )
        for nm, ye, gy, sp, co in groups_data
    ]
    print(f"  Групи: {len(groups)}")

    # ── 4. Аудиторії ─────────────────────────────────────────────────────────
    classrooms_data = [
        ("101", "Корпус А", 1, 60, "lecture"),
        ("102", "Корпус А", 1, 30, "computer"),
        ("103", "Корпус А", 1, 25, "lab"),
        ("201", "Корпус А", 2, 60, "lecture"),
        ("202", "Корпус А", 2, 30, "computer"),
        ("203", "Корпус А", 2, 25, "lab"),
        ("301", "Корпус Б", 1, 80, "lecture"),
        ("302", "Корпус Б", 1, 30, "computer"),
        ("303", "Корпус Б", 1, 30, "lab"),
        ("401", "Корпус Б", 2, 50, "lecture"),
        ("402", "Корпус Б", 2, 30, "computer"),
        ("403", "Корпус Б", 2, 25, "other"),
    ]
    classrooms = [
        Classroom.objects.create(name=nm, building=bl, floor=fl, capacity=cap, type=tp)
        for nm, bl, fl, cap, tp in classrooms_data
    ]
    print(f"  Аудиторії: {len(classrooms)}")

    # ── 5. Часові слоти ──────────────────────────────────────────────────────
    time_data = [
        (1, time(8, 30),  time(9, 50)),
        (2, time(10, 5),  time(11, 25)),
        (3, time(11, 40), time(13, 0)),
        (4, time(13, 30), time(14, 50)),
        (5, time(15, 5),  time(16, 25)),
    ]
    time_slots = [
        TimeSlot.objects.create(lesson_number=n, start_time=s, end_time=e)
        for n, s, e in time_data
    ]
    print(f"  Часові слоти: {len(time_slots)}")

    # ── 6. Предмети (15 шт.) ─────────────────────────────────────────────────
    subjects_data = [
        # назва, код, кредити, год.загал, год.лек, год.практ, семестр
        ("Вища математика",                    "MATH",  4, 120, 60, 30, 2),
        ("Об'єктно-орієнтоване програмування", "OOP",   4, 120, 30, 60, 2),
        ("Бази даних",                         "DB",    4, 120, 30, 60, 2),
        ("Веб-технології",                     "WEB",   3,  90, 30, 45, 2),
        ("Алгоритми та структури даних",       "ASD",   4, 120, 30, 60, 2),
        ("Комп'ютерні мережі",                 "NET",   3,  90, 45, 30, 2),
        ("Архітектура комп'ютерів",            "ARCH",  3,  90, 60, 15, 1),
        ("Дискретна математика",               "DISC",  4, 120, 60, 30, 1),
        ("Операційні системи",                 "OS",    3,  90, 30, 45, 2),
        ("Програмування мовою Python",         "PY",    3,  90, 15, 60, 2),
        ("Штучний інтелект та МН",             "AI",    4, 120, 45, 45, 2),
        ("Безпека інформаційних систем",       "SEC",   3,  90, 45, 30, 2),
        ("Мобільна розробка",                  "MOB",   3,  90, 15, 60, 2),
        ("Теорія ймовірностей та статистика",  "STAT",  3,  90, 60, 15, 1),
        ("Системне програмування",             "SYS",   4, 120, 30, 60, 2),
    ]
    subjects = [
        Subject.objects.create(
            name=nm, code=cd, credits=cr,
            hours_total=ht, hours_lectures=hl, hours_practicals=hp, semester=sm,
        )
        for nm, cd, cr, ht, hl, hp, sm in subjects_data
    ]
    print(f"  Предмети: {len(subjects)}")

    # ── 7. Викладачі (10 осіб) ───────────────────────────────────────────────
    teachers_info = [
        ("Мельник Олег Васильович",     "melnyk"),
        ("Шевченко Наталія Іванівна",   "shevchenko"),
        ("Бойко Сергій Михайлович",     "boyko"),
        ("Ткаченко Людмила Петрівна",   "tkachenko"),
        ("Коваленко Ігор Олексійович",  "kovalenko"),
        ("Бондар Олена Григорівна",     "bondar"),
        ("Олійник Андрій Степанович",   "oliynyk"),
        ("Вовк Тетяна Вікторівна",      "vovk"),
        ("Поліщук Роман Юрійович",      "polishchuk"),
        ("Кравченко Марина Дмитрівна",  "kravchenko"),
    ]
    teachers = [
        User.objects.create_user(
            email=f"t_{login}@edutrack.ua",
            password=f"t_{login}",
            full_name=full_name,
            role="teacher",
        )
        for full_name, login in teachers_info
    ]
    print(f"  Викладачі: {len(teachers)}")

    # ── 8. Студенти (40 осіб: 8 на кожну з 5 груп) ──────────────────────────
    students_info = [
        ("Іваненко",    "Олексій"),  ("Петренко",    "Марія"),
        ("Сидоренко",   "Дмитро"),   ("Кушнір",      "Анна"),
        ("Лисенко",     "Василь"),   ("Руденко",     "Юлія"),
        ("Мороз",       "Максим"),   ("Харченко",    "Вікторія"),
        ("Василенко",   "Артем"),    ("Павленко",    "Оксана"),
        ("Савченко",    "Богдан"),   ("Козак",       "Ірина"),
        ("Жук",         "Олег"),     ("Кот",         "Катерина"),
        ("Сорока",      "Андрій"),   ("Ворона",      "Наталія"),
        ("Гончар",      "Тарас"),    ("Швець",       "Людмила"),
        ("Кравець",     "Михайло"),  ("Ткач",        "Соломія"),
        ("Коваль",      "Назар"),    ("Гармаш",      "Аліна"),
        ("Скляр",       "Роман"),    ("Мельниченко", "Яна"),
        ("Білоус",      "Євген"),    ("Чорний",      "Тетяна"),
        ("Білий",       "Ігор"),     ("Мазур",       "Поліна"),
        ("Дубчак",      "Сергій"),   ("Береза",      "Крістіна"),
        ("Яворський",   "Антон"),    ("Гайдай",      "Валерія"),
        ("Довгань",     "Денис"),    ("Стус",        "Ольга"),
        ("Костенко",    "Владислав"),("Тимченко",    "Дарина"),
        ("Рильський",   "Павло"),    ("Сосюра",      "Зоя"),
        ("Гончаренко",  "Микола"),   ("Бондаренко",  "Христина"),
    ]
    students = []
    for i, (last, first) in enumerate(students_info):
        group = groups[i % len(groups)]
        login = f"s{i:02d}_{last.lower()[:6]}"
        students.append(
            User.objects.create_user(
                email=f"{login}@student.ua",
                password=login,
                full_name=f"{last} {first}",
                role="student",
                group=group,
            )
        )
    print(f"  Студенти: {len(students)}")

    # ── 9. Призначення викладачів (кожна група × 7 предметів) ───────────────
    ACADEMIC_YEAR = "2025/2026"
    SEMESTER = 2
    SEM_START = date(2026, 1, 13)
    SEM_END   = date(2026, 5, 30)

    assignments = []
    teacher_idx = 0
    for group in groups:
        group_subjects = random.sample(subjects, 7)
        for subj in group_subjects:
            teacher = teachers[teacher_idx % len(teachers)]
            teacher_idx += 1
            assign = TeachingAssignment.objects.create(
                subject=subj, teacher=teacher, group=group,
                academic_year=ACADEMIC_YEAR, semester=SEMESTER,
                start_date=SEM_START, end_date=SEM_END,
            )
            assignments.append(assign)
            EvaluationType.objects.create(assignment=assign, name="Лекція",      weight_percent=20, order=1)
            EvaluationType.objects.create(assignment=assign, name="Практична",   weight_percent=50, order=2)
            EvaluationType.objects.create(assignment=assign, name="Лабораторна", weight_percent=30, order=3)
    print(f"  Призначення: {len(assignments)} (по 7 предметів на групу)")

    # ── 10. Шаблони розкладу (пн–пт, 3–4 пари/день/група) ──────────────────
    # Unique constraint: (group, day_of_week, lesson_number)
    templates = []
    week_types = ["numerator", "denominator"]
    for group in groups:
        group_assigns = [a for a in assignments if a.group == group]
        assign_idx = 0
        for day in range(1, 6):  # 1=Пн … 5=Пт
            n_lessons = random.randint(3, 4)
            chosen_slots = sorted(
                random.sample(time_slots, n_lessons),
                key=lambda s: s.lesson_number,
            )
            for slot in chosen_slots:
                assign = group_assigns[assign_idx % len(group_assigns)]
                assign_idx += 1
                tmpl = ScheduleTemplate(
                    teaching_assignment=assign,
                    group=group,
                    subject=assign.subject,
                    teacher=assign.teacher,
                    day_of_week=day,
                    lesson_number=slot.lesson_number,
                    start_time=slot.start_time,
                    duration_minutes=80,
                    classroom=random.choice(classrooms),
                    week_type=week_types[assign_idx % 2],
                )
                tmpl.save()
                templates.append(tmpl)
    print(f"  Шаблони розкладу: {len(templates)}")

    # ── 11. Уроки та оцінки (13 січня — 16 березня 2026) ────────────────────
    START = date(2026, 1, 13)
    END   = date(2026, 3, 16)

    print(f"\nГенерація даних з {START} по {END}...")
    lesson_count   = 0
    perf_count     = 0
    absence_count  = 0
    no_grade_count = 0

    cur = START
    while cur <= END:
        weekday = cur.weekday() + 1  # 0-based → 1-based (1=Пн)
        if weekday > 5:
            cur += timedelta(days=1)
            continue

        for tmpl in templates:
            if tmpl.day_of_week != weekday:
                continue

            # Захист від дублювання (group, date, start_time)
            if Lesson.objects.filter(group=tmpl.group, date=cur, start_time=tmpl.start_time).exists():
                continue

            eval_types = list(tmpl.teaching_assignment.evaluation_types.all())
            if not eval_types:
                continue
            eval_type = random.choice(eval_types)

            end_time = (datetime.combine(cur, tmpl.start_time) + timedelta(minutes=80)).time()

            lesson = Lesson.objects.create(
                group=tmpl.group,
                subject=tmpl.subject,
                teacher=tmpl.teacher,
                date=cur,
                start_time=tmpl.start_time,
                end_time=end_time,
                topic=next_topic(tmpl.subject.name),
                evaluation_type=eval_type,
                max_points=100,
                homework=get_homework(),
                template_source=tmpl,
            )
            lesson_count += 1

            group_students = [s for s in students if s.group_id == tmpl.group_id]
            for student in group_students:
                roll = random.random()

                if roll < 0.07:
                    # 7% — неявка без причини
                    StudentPerformance.objects.create(
                        lesson=lesson, student=student,
                        absence=reasons[0],
                        graded_by=tmpl.teacher,
                        graded_at=datetime.combine(cur, time(12, 0), tzinfo=KYIV_TZ),
                    )
                    absence_count += 1

                elif roll < 0.10:
                    # 3% — хвороба / поважна причина
                    StudentPerformance.objects.create(
                        lesson=lesson, student=student,
                        absence=random.choice(reasons[1:]),
                        graded_by=tmpl.teacher,
                        graded_at=datetime.combine(cur, time(12, 0), tzinfo=KYIV_TZ),
                    )
                    absence_count += 1

                elif roll < 0.88:
                    # 78% — отримав оцінку (нормальний розподіл навколо 73 балів)
                    pts = min(100, max(40, int(random.gauss(73, 15))))
                    StudentPerformance.objects.create(
                        lesson=lesson, student=student,
                        earned_points=pts,
                        comment=get_comment(pts),
                        graded_by=tmpl.teacher,
                        graded_at=datetime.combine(cur, time(12, 0), tzinfo=KYIV_TZ),
                    )

                else:
                    # 12% — присутній, але оцінку не виставлено
                    no_grade_count += 1

                perf_count += 1

        cur += timedelta(days=1)

    # ── Підсумок ─────────────────────────────────────────────────────────────
    print(f"\n{'='*55}")
    print("БАЗА ДАНИХ УСПІШНО НАПОВНЕНА")
    print(f"{'='*55}")
    print(f"  Групи              : {len(groups)}")
    print(f"  Предмети           : {len(subjects)}")
    print(f"  Викладачі          : {len(teachers)}")
    print(f"  Студенти           : {len(students)}")
    print(f"  Призначення        : {len(assignments)}")
    print(f"  Шаблони розкладу   : {len(templates)}")
    print(f"  Уроки              : {lesson_count}")
    print(f"  Записи успішності  : {perf_count}")
    print(f"    з них: пропуски  : {absence_count}")
    print(f"           без оцінки: {no_grade_count}")
    print(f"{'='*55}")
    print("\nПРИКЛАДИ ВХОДУ:")
    print(f"  Викладач : t_melnyk@edutrack.ua      / t_melnyk")
    print(f"  Викладач : t_shevchenko@edutrack.ua  / t_shevchenko")
    print(f"  Студент  : s00_ivanen@student.ua     / s00_ivanen")
    print(f"  Студент  : s01_petren@student.ua     / s01_petren")


if __name__ == "__main__":
    create_initial_data()
