import csv
import json
from collections import defaultdict
from datetime import date, datetime, time, timedelta
from typing import List, Dict, Any, Optional, Union, Callable, Tuple

from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ObjectDoesNotExist
from django.db import IntegrityError, transaction
from django.db.models import Avg, Count, F, Max, Min, Prefetch, Q, Sum
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST, require_http_methods

from .forms import ClassroomForm, StudyGroupForm, SubjectForm, UserAdminForm, ProfileForm
from .models import (
    AbsenceReason,
    EvaluationType,
    Lesson,
    StudentPerformance,
    StudyGroup,
    Subject,
    TeachingAssignment,
    User,
    ScheduleTemplate,
    TimeSlot,
    Classroom,
    GradingScale,
    GradeRule,
)

# =========================
# UTILITY & DECORATORS
# =========================

def role_required(allowed_roles: Union[str, List[str]]) -> Callable:
    """
    Декоратор для перевірки ролі через стандартний request.user.
    allowed_roles може бути строкою ('admin') або списком (['admin', 'teacher']).
    """
    if isinstance(allowed_roles, str):
        allowed_roles = [allowed_roles]

    def decorator(view_func: Callable) -> Callable:
        def wrapper(request: HttpRequest, *args: Any, **kwargs: Any) -> Union[HttpResponse, JsonResponse]:
            # 1. Перевірка авторизації Django
            if not request.user.is_authenticated:
                return redirect('login')

            # 2. Перевірка ролі
            if request.user.role not in allowed_roles:
                messages.error(request, "У вас немає прав для доступу до цієї сторінки.")
                # Редірект на "свою" сторінку, щоб уникнути циклів
                if request.user.role == 'student':
                    return redirect('student_dashboard')
                elif request.user.role == 'teacher':
                    return redirect('teacher_dashboard')
                else:
                    return redirect('login')

            # Виконуємо в'юху
            response = view_func(request, *args, **kwargs)

            # Заголовки проти кешування (безпека після логауту)
            response['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
            response['Pragma'] = 'no-cache'
            response['Expires'] = '0'
            
            return response

        return wrapper

    return decorator


def generate_csv_response(filename, header, rows):
    """Утиліта для генерації CSV."""
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="{filename}.csv"'
    response.write(u'\ufeff'.encode('utf8'))  # BOM для Excel

    writer = csv.writer(response)
    writer.writerow(header)
    for row in rows:
        writer.writerow(row)
    return response

# =========================
# 1. АУТЕНТИФІКАЦІЯ
# =========================

def login_view(request: HttpRequest) -> HttpResponse:
    """Сторінка входу."""
    if request.user.is_authenticated:
        role = request.user.role
        if role == 'admin':
            return redirect('admin_panel')
        if role == 'teacher':
            return redirect('teacher_dashboard')
        if role == 'student':
            return redirect('student_dashboard')

    return render(request, 'index.html')


@require_POST
def login_process(request):
    """Обробка входу через стандартний authenticate."""
    email = request.POST.get('username')
    password = request.POST.get('password')

    # Django authenticate хешує пароль і звіряє з БД
    # Важливо: переконайтесь, що в моделі User поле USERNAME_FIELD = 'email'
    user = authenticate(request, email=email, password=password)

    if user is not None:
        login(request, user)  # Створює сесію Django
        
        if user.role == 'admin':
            return redirect('admin_panel')
        elif user.role == 'teacher':
            return redirect('teacher_dashboard')
        elif user.role == 'student':
            return redirect('student_dashboard')
        else:
            return redirect('login')
    else:
        messages.error(request, "Невірний email або пароль")
        return redirect('login')


def logout_view(request: HttpRequest) -> HttpResponse:
    """Вихід із системи."""
    logout(request)
    return redirect('login')


def csrf_debug_view(request: HttpRequest) -> JsonResponse:
    """Debug endpoint: returns the current CSRF token and request cookies.

    Use this temporarily to verify that the CSRF token is generated and that
    the browser is sending cookies correctly.
    """
    try:
        from django.middleware.csrf import get_token
    except Exception:
        return JsonResponse({'error': 'csrf module not available'}, status=500)

    token = get_token(request)
    return JsonResponse({
        'csrf_token': token,
        'cookies': request.COOKIES,
        'method': request.method,
    })

# =========================
# 2. АДМІНІСТРАТОР
# =========================

@role_required('admin')
def admin_panel_view(request: HttpRequest) -> HttpResponse:
    context = {
        'total_users': User.objects.count(),
        'student_count': User.objects.filter(role='student').count(),
        'group_count': StudyGroup.objects.count(),
        'subject_count': Subject.objects.count(),
        'classroom_count': Classroom.objects.count(),
        'active_page': 'admin',
    }
    return render(request, 'admin.html', context)

# --- USERS ---
@role_required('admin')
def users_list_view(request: HttpRequest) -> HttpResponse:
    if request.method == 'POST':
        form = UserAdminForm(request.POST)
        if form.is_valid():
            # Важливо: UserAdminForm повинен вміти хешувати пароль при збереженні,
            # або використовуйте create_user у формі.
            form.save()
            messages.success(request, "Користувача успішно додано")
            return redirect('users_list')
        else:
            messages.error(request, "Помилка при додаванні: " + str(form.errors))
    else:
        form = UserAdminForm()

    # 1. Параметри фільтрації
    role_filter = request.GET.get('role', '')
    group_filter = request.GET.get('group', '')
    subject_filter = request.GET.get('subject', '')
    search_query = request.GET.get('search', '')
    date_from = request.GET.get('date_from', '')
    date_to = request.GET.get('date_to', '')

    # 2. Базовий запит
    users = User.objects.select_related('group').prefetch_related(
        'teachingassignment_set__subject'
    ).order_by('-id')

    # 3. Фільтри
    if role_filter:
        users = users.filter(role=role_filter)
    
    if group_filter:
        users = users.filter(group_id=group_filter)
        
    if subject_filter:
        users = users.filter(teachingassignment__subject_id=subject_filter).distinct()

    if search_query:
        users = users.filter(
            Q(full_name__icontains=search_query) | 
            Q(email__icontains=search_query)
        )

    if date_from:
        users = users.filter(created_at__date__gte=date_from)
    if date_to:
        users = users.filter(created_at__date__lte=date_to)

    groups = StudyGroup.objects.all()
    all_subjects = Subject.objects.all()

    return render(
        request,
        'users.html',
        {
            'users': users,
            'form': form,
            'groups': groups,
            'all_subjects': all_subjects,
            'active_page': 'users',
        },
    )

@role_required('admin')
def user_edit_view(request: HttpRequest, pk: int) -> HttpResponse:
    user = get_object_or_404(User, pk=pk)
    if request.method == 'POST':
        form = UserAdminForm(request.POST, instance=user)
        if form.is_valid():
            form.save()
            messages.success(request, "Дані оновлено")
            return redirect('users_list')
    else:
        form = UserAdminForm(instance=user)

    groups = StudyGroup.objects.all()

    # Отримуємо предмети для цього користувача (якщо це викладач)
    user_subjects = []
    if user.role == 'teacher':
        subjects = Subject.objects.filter(
            teachingassignment__teacher=user
        ).distinct()
        user_subjects = list(subjects)

    return render(
        request,
        'user_edit.html',
        {
            'form': form,
            'user': user,
            'groups': groups,
            'user_subjects': user_subjects,
        },
    )


@role_required('admin')
@require_POST
def user_delete_view(request, pk):
    user = get_object_or_404(User, pk=pk)
    # Перевірка через request.user
    if user.id == request.user.id:
        messages.error(request, "Не можна видалити самого себе!")
    else:
        user.delete()
        messages.success(request, "Користувача видалено")
    return redirect('users_list')


# --- GROUPS ---
@role_required('admin')
def groups_list_view(request):
    if request.method == 'POST':
        form = StudyGroupForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Групу додано")
            return redirect('groups_list')
        else:
            messages.error(request, "Помилка: така група вже існує")
    else:
        form = StudyGroupForm()

    search_query = request.GET.get('search', '')
    groups = StudyGroup.objects.annotate(
        student_count=Count('students')
    ).order_by('name')
    
    if search_query:
        groups = groups.filter(name__icontains=search_query)

    return render(request, 'groups.html', {'groups': groups, 'form': form, 'active_page': 'groups'})


@role_required('admin')
@require_POST
def group_add_view(request):
    form = StudyGroupForm(request.POST)
    if form.is_valid():
        form.save()
        messages.success(request, "Групу додано")
    else:
        messages.error(request, "Помилка: така група вже існує")
    return redirect('groups_list')


@role_required('admin')
@require_POST
def group_delete_view(request, pk):
    group = get_object_or_404(StudyGroup, pk=pk)
    group.delete()
    messages.success(request, "Групу видалено")
    return redirect('groups_list')


@role_required('admin')
def subjects_list_view(request):
    search_query = request.GET.get('search', '')
    subjects = Subject.objects.annotate(
        teachers_count=Count('teachingassignment')
    ).order_by('name')
    
    if search_query:
        subjects = subjects.filter(
            Q(name__icontains=search_query) | 
            Q(description__icontains=search_query)
        )
        
    form = SubjectForm()
    return render(request, 'subjects.html', {'subjects': subjects, 'form': form, 'active_page': 'subjects'})


@role_required('admin')
def subject_add_view(request):
    if request.method == 'POST':
        form = SubjectForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Предмет додано")
            return redirect('subjects_list')
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f"{field}: {error}")
            return redirect('subjects_list')
    else:
        subjects = Subject.objects.annotate(
            teachers_count=Count('teachingassignment')
        ).order_by('name')
        form = SubjectForm()
        return render(request, 'subjects.html', {'subjects': subjects, 'form': form})


@role_required('admin')
@require_POST
def subject_delete_view(request, pk):
    subject = get_object_or_404(Subject, pk=pk)
    try:
        subject.delete()
        messages.success(request, "Предмет видалено")
    except Exception as e:
        messages.error(
            request,
            "Неможливо видалити предмет, він використовується в системі.",
        )
    return redirect('subjects_list')


# --- CLASSROOMS ---
@role_required('admin')
def classrooms_list_view(request):
    search_query = request.GET.get('search', '')
    classrooms = Classroom.objects.all().order_by('name')
    
    if search_query:
        classrooms = classrooms.filter(
            Q(name__icontains=search_query) | 
            Q(building__icontains=search_query)
        )
        
    form = ClassroomForm()
    return render(request, 'classrooms.html', {'classrooms': classrooms, 'form': form, 'active_page': 'classrooms'})


@role_required('admin')
@require_POST
def classroom_add_view(request):
    form = ClassroomForm(request.POST)
    if form.is_valid():
        form.save()
        messages.success(request, "Аудиторію додано")
    else:
        for field, errors in form.errors.items():
            for error in errors:
                messages.error(request, f"{field}: {error}")
    return redirect('classrooms_list')


@role_required('admin')
@require_POST
def classroom_delete_view(request, pk):
    classroom = get_object_or_404(Classroom, pk=pk)
    try:
        classroom.delete()
        messages.success(request, "Аудиторію видалено")
    except Exception as e:
        messages.error(
            request,
            "Неможливо видалити аудиторію, вона використовується в системі.",
        )
    return redirect('classrooms_list')


# --- SCHEDULE ---
@role_required('admin')
def set_weekly_schedule_view(request):
    """Сторінка налаштування розкладу."""
    if request.method == 'POST':
        return save_schedule_changes(request)
    
    groups = StudyGroup.objects.all().order_by('name')
    
    assignments = TeachingAssignment.objects.select_related(
        'subject', 'teacher', 'group'
    ).order_by('group__name', 'subject__name')
    
    subject_teachers = defaultdict(list)
    for assignment in assignments:
        subj_id = assignment.subject.id
        teacher_tuple = (assignment.teacher.id, assignment.teacher.full_name)
        if teacher_tuple not in subject_teachers[subj_id]:
            subject_teachers[subj_id].append(teacher_tuple)
    
    current_schedule = ScheduleTemplate.objects.all().select_related(
        'subject',
        'teacher',
        'group'
    )
    
    schedule_map_temp = defaultdict(lambda: defaultdict(dict))
    for item in current_schedule:
        grp_id = str(item.group.id)
        day = str(item.day_of_week)
        
        # Зберегти всі уроки, незалежно від часу
        # Використовувати lesson_number з бази даних (він повинен бути встановлений коректно)
        lesson_num = item.lesson_number
        if lesson_num:
            schedule_map_temp[grp_id][day][str(lesson_num)] = {
                'subject_id': item.subject.id,
                'subject_name': item.subject.name,
                'teacher_id': item.teacher.id,
                'teacher_name': item.teacher.full_name,
                'start_time': item.start_time.strftime("%H:%M"),
                'duration': item.duration_minutes, # Важливо
                'classroom': item.classroom.name if item.classroom else ""
            }
    
    schedule_map = {}
    for grp_id, days in schedule_map_temp.items():
        schedule_map[grp_id] = {}
        for day, lessons in days.items():
            schedule_map[grp_id][day] = dict(lessons)

    subjects = Subject.objects.all().order_by('name')
    subject_data = []
    subject_teachers_map = {}
    
    for subject in subjects:
        teachers = TeachingAssignment.objects.filter(
            subject=subject
        ).select_related('teacher').values_list('teacher_id', 'teacher__full_name').distinct()
        teachers_list = list(teachers)
        
        if subject.id not in subject_teachers_map:
            subject_teachers_map[subject.id] = teachers_list
        
        if teachers_list:
            if len(teachers_list) > 1:
                for tid, tname in teachers_list:
                    subject_data.append({
                        'id': subject.id,
                        'name': f"{subject.name} ({tname})",
                        'teacher_id': tid,
                        'teacher_name': tname
                    })
            else:
                tid, tname = teachers_list[0]
                subject_data.append({
                    'id': subject.id,
                    'name': subject.name,
                    'teacher_id': tid,
                    'teacher_name': tname
                })

    lesson_times = {
        1: ("08:30", "10:05"),
        2: ("10:15", "11:50"),
        3: ("12:15", "13:50"),
        4: ("14:15", "15:50"),
        5: ("16:00", "17:35"),
        6: ("17:45", "19:20"),
        7: ("19:30", "21:05"),
        8: ("21:15", "22:50"),
    }

    context = {
        'groups': groups,
        'schedule_map': schedule_map,
        'subject_data': subject_data,
        'subject_teachers_map': subject_teachers_map,
        'days': [(1, 'Понеділок'), (2, 'Вівторок'), (3, 'Середа'), (4, 'Четвер'), (5, 'П’ятниця'), (6, 'Субота')],
        'lesson_numbers': range(1, 9),
        'lesson_times': lesson_times,
        'active_page': 'schedule_builder',
    }
    return render(request, 'main/schedule_builder.html', context)


@require_POST
@role_required('admin')
def save_schedule_changes(request: HttpRequest) -> JsonResponse:
    """API endpoint для збереження розкладу."""
    try:
        data = json.loads(request.body)
        group_id = data.get('group_id')
        schedule_entries = data.get('schedule', {})
        
        if not group_id:
            return JsonResponse({'status': 'error', 'message': 'Група не вибрана'}, status=400)
        
        group = get_object_or_404(StudyGroup, id=group_id)
        
        with transaction.atomic():
            # Імпорт валідаційного сервісу
            from main.services.schedule_service import validate_schedule_slot
            
            # Крок 1: Підготовка та валідація ВСІХ нових слотів (перед видаленням!)
            # Це дозволяє exclude_slot_id працювати правильно, оскільки старі слоти ще в БД
            slots_to_create = []
            
            for day_str, lessons in schedule_entries.items():
                day = int(day_str)
                for lesson_num_str, lesson_data in lessons.items():
                    lesson_num = int(lesson_num_str)
                    
                    if isinstance(lesson_data, dict):
                        subject_id = lesson_data.get('subject_id')
                        teacher_id = lesson_data.get('teacher_id')
                    else:
                        subject_id = lesson_data
                        teacher_id = None
                    
                    if subject_id:
                        # Підготовка даних для слоту
                        assignment = None
                        if teacher_id:
                            teacher = User.objects.filter(id=teacher_id).first()
                            if teacher:
                                assignment, _ = TeachingAssignment.objects.get_or_create(
                                    group=group,
                                    subject_id=subject_id,
                                    teacher=teacher
                                )
                        
                        if not assignment:
                            assignment = TeachingAssignment.objects.filter(
                                group=group,
                                subject_id=subject_id
                            ).first()
                        
                        start_time_str = "08:30"
                        classroom_name = ""
                        duration = 90
                        if isinstance(lesson_data, dict):
                            start_time_str = lesson_data.get('startTime', lesson_data.get('start_time', "08:30"))
                            classroom_name = lesson_data.get('classroom', "").strip()
                            duration = int(lesson_data.get('duration', 90))
                        
                        classroom_obj = None
                        if classroom_name:
                            classroom_obj, _ = Classroom.objects.get_or_create(name=classroom_name)

                        import datetime as _dt
                        start_time_obj = _dt.datetime.strptime(start_time_str, "%H:%M").time()

                        teacher_obj = None
                        if teacher_id:
                            teacher_obj = User.objects.filter(id=teacher_id).first()
                        elif assignment:
                            teacher_obj = assignment.teacher

                        # Знайти існуючий слот для виключення з перевірки конфліктів
                        existing_slot = ScheduleTemplate.objects.filter(
                            group=group,
                            day_of_week=day,
                            lesson_number=lesson_num
                        ).first()
                        exclude_id = existing_slot.id if existing_slot else None

                        # ВАЛІДАЦІЯ: check_current_group=False ігнорує конфлікти з цією ж групою,
                        # оскільки ми зараз перезаписуємо весь її розклад
                        is_valid, err = validate_schedule_slot(
                            group=group,
                            day=day,
                            lesson_number=lesson_num,
                            start_time=start_time_obj,
                            duration=duration,
                            subject=Subject.objects.filter(id=subject_id).first(),
                            teacher=teacher_obj,
                            classroom=classroom_obj,
                            exclude_slot_id=exclude_id,
                            check_current_group=False
                        )

                        if not is_valid:
                            day_name = {1:'Пн', 2:'Вт', 3:'Ср', 4:'Чт', 5:'Пт', 6:'Сб', 7:'Нд'}.get(day, str(day))
                            return JsonResponse({
                                'status': 'error',
                                'message': f"Конфлікт ({day_name}, пара №{lesson_num}): {err}"
                            }, status=400)

                        # Зберігаємо дані для створення після видалення
                        slots_to_create.append({
                            'group': group,
                            'subject_id': subject_id,
                            'teacher_id': teacher_id or (assignment.teacher_id if assignment else None),
                            'assignment': assignment,
                            'day_of_week': day,
                            'lesson_number': lesson_num,
                            'start_time': start_time_str,
                            'duration_minutes': duration,
                            'classroom': classroom_obj,
                        })
            
            # Крок 2: Видалити ВСІ старі слоти (валідація вже пройдена!)
            ScheduleTemplate.objects.filter(group=group).delete()
            
            # Крок 3: Створити нові слоти
            for slot_data in slots_to_create:
                ScheduleTemplate.objects.create(
                    group=slot_data['group'],
                    subject_id=slot_data['subject_id'],
                    teacher_id=slot_data['teacher_id'],
                    teaching_assignment=slot_data['assignment'],
                    day_of_week=slot_data['day_of_week'],
                    lesson_number=slot_data['lesson_number'],
                    start_time=slot_data['start_time'],
                    duration_minutes=slot_data['duration_minutes'],
                    classroom=slot_data['classroom'],
                    valid_from=date.today()
                )
        
        return JsonResponse({
            'status': 'success',
            'message': f'Розклад для групи {group.name} оновлено'
        })
    
    except json.JSONDecodeError:
        return JsonResponse({
            'status': 'error',
            'message': 'Невірний формат JSON'
        }, status=400)
    except Exception as e:
        import traceback
        traceback.print_exc()
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        }, status=500)

@role_required('admin')
def schedule_editor_view(request: HttpRequest) -> HttpResponse:
    """Новий редактор розкладу (List View) з 8 слотами."""
    group_id = request.GET.get('group_id')
    groups = StudyGroup.objects.all().order_by('name')
    
    selected_group = None
    if group_id:
        selected_group = get_object_or_404(StudyGroup, id=group_id)
    
    # Структура днів та слотів
    days_info = [
        (1, 'ПОНЕДІЛОК'),
        (2, 'ВІВТОРОК'),
        (3, 'СЕРЕДА'),
        (4, 'ЧЕТВЕР'),
        (5, 'П’ЯТНИЦЯ'),
    ]
    
    schedule_data = [] # Список об'єктів для кожного дня
    
    if selected_group:
        templates = ScheduleTemplate.objects.filter(group=selected_group).select_related('subject', 'teacher', 'classroom')
        template_dict = defaultdict(dict)
        for t in templates:
            template_dict[t.day_of_week][t.lesson_number] = t
            
        for day_num, day_name in days_info:
            slots = []
            for i in range(1, 9): # 8 слотів
                template = template_dict[day_num].get(i)
                slots.append({
                    'number': i,
                    'template': template,
                    'is_empty': template is None
                })
            schedule_data.append({
                'day_num': day_num,
                'day_name': day_name,
                'slots': slots
            })
            
    # Довідкові дані для модального вікна
    subjects = Subject.objects.all().order_by('name')
    teachers = User.objects.filter(role='teacher').order_by('full_name')
    classrooms = Classroom.objects.all().order_by('name')
    
    context = {
        'groups': groups,
        'selected_group': selected_group,
        'schedule_data': schedule_data,
        'subjects': subjects,
        'teachers': teachers,
        'classrooms': classrooms,
        'active_page': 'schedule_editor',
    }
    return render(request, 'main/schedule_editor.html', context)

@require_POST
@role_required('admin')
def api_save_schedule_slot(request: HttpRequest) -> JsonResponse:
    """API для збереження окремого слоту в ScheduleTemplate."""
    try:
        # Імпорт сервісу та форми
        from main.services.schedule_service import validate_schedule_slot
        from main.forms import ScheduleSlotForm
        
        data = json.loads(request.body)
        
        # Валідація вхідних даних через форму
        form = ScheduleSlotForm(data)
        if not form.is_valid():
            return JsonResponse({'status': 'error', 'message': f"Помилка даних: {form.errors.as_text()}"}, status=400)
            
        cd = form.cleaned_data
        group_id = cd['group_id']
        day = cd['day']
        lesson_num = cd['lesson_number']
        
        subject_id = cd.get('subject_id')
        teacher_id = cd.get('teacher_id')
        classroom_id = cd.get('classroom_id')
        start_time = cd['start_time']
        duration = cd['duration']
        
        group = get_object_or_404(StudyGroup, id=group_id)
        
        # Видалення якщо вибрано "пусто" (subject_id=None)
        if not subject_id:
            ScheduleTemplate.objects.filter(group=group, day_of_week=day, lesson_number=lesson_num).delete()
            return JsonResponse({'status': 'success', 'message': 'Слот очищено'})

        # (Конвертація часу вже зроблена формою)

        # Отримання об'єктів
        subject = get_object_or_404(Subject, id=subject_id)
        teacher = None
        if teacher_id:
            teacher = get_object_or_404(User, id=teacher_id)
        
        classroom = None
        if classroom_id:
            classroom = get_object_or_404(Classroom, id=classroom_id)
        
        # Знайти існуючий слот (для виключення при валідації)
        existing_slot = ScheduleTemplate.objects.filter(
            group=group, 
            day_of_week=day, 
            lesson_number=lesson_num
        ).first()
        exclude_id = existing_slot.id if existing_slot else None
        
        # VALIDATION через сервіс (замість 60+ рядків коду!)
        is_valid, error_message = validate_schedule_slot(
            group=group,
            day=day,
            lesson_number=lesson_num,
            start_time=start_time,
            duration=duration,
            subject=subject,
            teacher=teacher,
            classroom=classroom,
            exclude_slot_id=exclude_id
        )
        
        if not is_valid:
            return JsonResponse({
                'status': 'error', 
                'message': f"Конфлікт: {error_message}"
            }, status=400)

        # 1. Знаходимо або створюємо TeachingAssignment (SSOT)
        # У майбутньому це буде обов'язковим, зараз - забезпечуємо міграцію нових даних
        assignment = None
        if teacher:
            assignment, _ = TeachingAssignment.objects.get_or_create(
                subject=subject,
                teacher=teacher,
                group=group
            )

        # SAVE - з урахуванням можливості None для teacher
        with transaction.atomic():
            # Якщо викладач не вказаний, але є assignment (наприклад збережений раніше),
            # використаємо його викладача. Інакше залишимо None (модель дозволяє null тепер).
            teacher_to_save = teacher or (assignment.teacher if assignment else None)

            template, created = ScheduleTemplate.objects.update_or_create(
                group=group, day_of_week=day, lesson_number=lesson_num,
                defaults={
                    'subject': subject,
                    'teacher': teacher_to_save,
                    'teaching_assignment': assignment, # <-- НОВЕ ПОЛЕ
                    'classroom': classroom,
                    'start_time': start_time,
                    'duration_minutes': duration,
                }
            )
        
        return JsonResponse({
            'status': 'success', 
            'message': 'Збережено',
            'data': {
                'subject': template.subject.name,
                'teacher': template.teacher.full_name if template.teacher else '—',
                'classroom': template.classroom.name if template.classroom else '—',
                'time': f'{template.start_time.strftime("%H:%M")} (+{template.duration_minutes}хв)'
            }
        })

    except json.JSONDecodeError:
        return JsonResponse({'status': 'error', 'message': 'Невірний JSON формат'}, status=400)
    except Exception as e:
        import traceback
        traceback.print_exc()
        return JsonResponse({'status': 'error', 'message': f'Помилка при збереженні: {str(e)}'}, status=500)


@login_required
def schedule_view(request):
    user = request.user
    
    group_id = request.GET.get('group_id')
    week_shift = int(request.GET.get('week', 0))
    
    group = None
    if user.role == 'student':
        group = user.group
    elif group_id:
        group = get_object_or_404(StudyGroup, id=group_id)
    
    # Розрахунок дат тижня
    today = date.today()
    days_since_monday = today.weekday()
    monday = today - timedelta(days=days_since_monday)
    start_of_week = monday + timedelta(weeks=week_shift)
    end_of_week = start_of_week + timedelta(days=6)
    
    # Замість Lesson використовуємо ScheduleTemplate
    schedule_templates = []
    if group:
        schedule_templates = ScheduleTemplate.objects.filter(
            group=group
        ).select_related('subject', 'teacher', 'classroom').order_by('day_of_week', 'lesson_number')

    # Дні тижня для заголовка
    week_days = []
    day_names = ['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Нд']
    for i in range(7):
        d = start_of_week + timedelta(days=i)
        week_days.append({
            'date': d,
            'day_name': day_names[i],
            'day_of_week': i + 1,  # 1=Пн, 2=Вт, ..., 7=Нд
            'is_today': d == today
        })

    context = {
        'schedule_templates': schedule_templates,  # Замість 'lessons'
        'week_days': week_days,
        'group': group,
        'all_groups': StudyGroup.objects.all().order_by('name') if user.role != 'student' else None,
        'week_shift': week_shift,
        'start_of_week': start_of_week,
        'end_of_week': end_of_week,
        'active_page': 'schedule'
    }
    
    return render(request, 'schedule_timelord.html', context)



# =========================
# 3. ВИКЛАДАЧ
# =========================

@role_required('teacher')
def teacher_journal_view(request: HttpRequest) -> HttpResponse:
    from main.services.grading_service import get_teacher_journal_context
    
    teacher_id = request.user.id
    
    # Get all assignments for the teacher to populate filters
    assignments = TeachingAssignment.objects.filter(
        teacher_id=teacher_id
    ).select_related('subject', 'group')

    selected_subject_id = request.GET.get('subject')
    selected_group_id = request.GET.get('group')
    
    # Parse week offset
    try:
        week_offset = int(request.GET.get('week', 0))
    except (ValueError, TypeError):
        week_offset = 0
    
    groups = []
    seen_groups = set()
    for assignment in assignments:
        if assignment.group.id not in seen_groups:
            groups.append({
                'id': assignment.group.id,
                'name': assignment.group.name
            })
            seen_groups.add(assignment.group.id)
    
    # Filter subjects based on selected group if one is picked
    subjects = []
    seen_subjects = set()
    subject_assignments = assignments
    if selected_group_id:
        subject_assignments = assignments.filter(group_id=selected_group_id)
    
    for assignment in subject_assignments:
        if assignment.subject.id not in seen_subjects:
            subjects.append({
                'id': assignment.subject.id,
                'name': assignment.subject.name
            })
            seen_subjects.add(assignment.subject.id)
            
    context = {
        'subjects': sorted(subjects, key=lambda x: x['name']),
        'groups': sorted(groups, key=lambda x: x['name']),
        'selected_subject_id': selected_subject_id,
        'selected_group_id': selected_group_id,
        'week_offset': week_offset,
        'active_page': 'teacher',
    }

    if selected_subject_id and selected_group_id:
        try:
            # Check if this specific assignment exists for the teacher
            selected_assignment = assignments.filter(
                subject_id=selected_subject_id,
                group_id=selected_group_id
            ).first()

            if not selected_assignment:
                messages.warning(request, "У вас немає призначення на цей предмет у цій групі.")
            else:
                journal_context = get_teacher_journal_context(
                    group_id=int(selected_group_id),
                    subject_id=int(selected_subject_id),
                    week_offset=week_offset
                )
                context.update(journal_context)
                context['selected_assignment'] = selected_assignment
            
        except Exception as e:
            messages.error(request, f"Помилка завантаження журналу: {str(e)}")

    return render(request, 'teacher.html', context)

@require_POST
def api_save_grade(request: HttpRequest) -> JsonResponse:
    """
    API for saving a single grade entry instantly.
    Payload: { student_id, date, lesson_num, subject_id, value, comment }
    """
    from main.constants import DEFAULT_LESSON_TIMES
    from datetime import datetime, timedelta, date

    try:
        data = json.loads(request.body)
        
        # Handle both flat and nested (for compatibility if needed, but preference for flat)
        if 'changes' in data and len(data['changes']) > 0:
            data = data['changes'][0]
            student_id = data.get('student_pk')
        else:
            student_id = data.get('student_id')

        lesson_id = data.get('lesson_id')
        lesson_date_str = data.get('date')
        lesson_num = data.get('lesson_num')
        subject_id = data.get('subject_id')
        raw_value = data.get('value')
        absence_id = data.get('absence_id')
        comment_text = data.get('comment')

        if not lesson_id and not (student_id and lesson_date_str and lesson_num and subject_id):
            return JsonResponse({'status': 'error', 'message': f'Missing coordinates or lesson_id: s:{student_id} d:{lesson_date_str} n:{lesson_num} sub:{subject_id}'}, status=400)

        # 1. Resolve Teacher and Authorization
        if not request.user.is_authenticated or request.user.role != 'teacher':
             return JsonResponse({'status': 'error', 'message': 'Forbidden'}, status=403)
        teacher_id = request.user.id

        # 2. Resolve Student and Group
        student = get_object_or_404(User, pk=student_id)
        group = student.group
        if not group:
             return JsonResponse({'status': 'error', 'message': 'Student has no group'}, status=400)

        # 3. Resolve Lesson
        if lesson_id:
             current_lesson = get_object_or_404(Lesson, id=lesson_id)
        else:
             # Get start_time for the lesson number
             from main.constants import DEFAULT_TIME_SLOTS
             start_time_info = DEFAULT_TIME_SLOTS.get(int(lesson_num))
             if start_time_info:
                  start_time = start_time_info[0]
             else:
                  # Last resort fallback to deprecated mapping
                  start_time_str = DEFAULT_LESSON_TIMES.get(int(lesson_num), "08:30")
                  start_time = datetime.strptime(start_time_str, "%H:%M").time()

             # Determine Assignment
             try:
                 assignment = TeachingAssignment.objects.get(
                     teacher_id=teacher_id,
                     subject_id=int(subject_id),
                     group=group
                 )
             except TeachingAssignment.DoesNotExist:
                 return JsonResponse({'status': 'error', 'message': f'Assignment not found for teacher {teacher_id}, subject {subject_id}, group {group.id}'}, status=403)

             # Get/Create Lesson
             eval_type = assignment.evaluation_types.first()
             if not eval_type:
                 eval_type = EvaluationType.objects.create(
                     assignment=assignment, 
                     name="Заняття", 
                     weight_percent=0
                 )

             # CRITICAL: Use only unique fields for lookup to avoid IntegrityError
             current_lesson, created = Lesson.objects.get_or_create(
                 group=group,
                 date=lesson_date_str,
                 start_time=start_time,
                 defaults={
                     'subject_id': int(subject_id),
                     'teacher_id': teacher_id,
                     'end_time': (datetime.combine(date.today(), start_time) + timedelta(minutes=90)).time(),
                     'evaluation_type': eval_type
                 }
             )
             
             if not created:
                 # Check for subject conflict
                 if current_lesson.subject_id != int(subject_id):
                     print(f"[DEBUG] Lesson subject conflict: DB={current_lesson.subject_id}, REQ={subject_id}. Updating lesson subject.")
                     current_lesson.subject_id = int(subject_id)
                     current_lesson.teacher_id = teacher_id
                     current_lesson.evaluation_type = eval_type
                     current_lesson.save()
                 elif current_lesson.evaluation_type_id != eval_type.id:
                     current_lesson.evaluation_type = eval_type
                     current_lesson.save()
        
        print(f"[DEBUG] Using Lesson: id={current_lesson.id}, subject={current_lesson.subject_id}, group={current_lesson.group_id}")
        
        # 4. Parse Value and Save Performance
        grade_value = None
        absence_obj = None

        if raw_value in [None, '', '—'] and not comment_text:
             StudentPerformance.objects.filter(lesson=current_lesson, student_id=student_id).delete()
             return JsonResponse({'status': 'success', 'message': 'Cleared'})

        # Refined Parsing (Compatible with 'H', 'N', and numeric grades)
        raw_str = str(raw_value).upper().strip() if raw_value is not None else ""
        if raw_str in ['H', 'N', 'Н']: # Cyrillic H
             absence_obj = AbsenceReason.objects.filter(code='Н').first() or AbsenceReason.objects.first()
        elif absence_id:
             absence_obj = AbsenceReason.objects.filter(id=absence_id).first()
        elif raw_str.isdigit() or (raw_str.startswith('-') and raw_str[1:].isdigit()):
             grade_value = int(raw_str)
        
        print(f"[DEBUG] Saving Grade: Student={student_id}, Lesson={current_lesson.id}, Value={raw_value}")
        
        defaults = {}
        if grade_value is not None:
            defaults['earned_points'] = grade_value
            defaults['absence'] = None  # Clear absence if grade is set
        
        if 'absence_id' in data or absence_obj:
            defaults['absence'] = absence_obj
            if absence_obj:
                defaults['earned_points'] = None # Clear grade if absent
        
        if comment_text is not None:
            defaults['comment'] = comment_text

        perf, created = StudentPerformance.objects.update_or_create(
            lesson=current_lesson,
            student_id=student_id,
            defaults=defaults
        )
        print(f"[DEBUG] Performance saved: id={perf.id}, created={created}")
        
        return JsonResponse({'status': 'success', 'message': 'Saved'})

    except Exception as e:
        import traceback
        print(traceback.format_exc())
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)


@require_POST
def api_card_scan(request) -> JsonResponse:
    """
    Simulates RFID Scan.
    Payload: { student_id, action (ENTER/EXIT) }
    """
    from main.models import BuildingAccessLog
    
    try:
        data = json.loads(request.body)
        student_id = data.get('student_id')
        action = data.get('action', 'ENTER') # ENTER or EXIT
        
        BuildingAccessLog.objects.create(
            student_id=student_id,
            action=action
        )
        return JsonResponse({'status': 'success'})
    except Exception as e:
        import traceback
        print(traceback.format_exc()) # Print to server console
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)

# =========================
# 4. СТУДЕНТ
# =========================

@role_required('student')
def student_grades_view(request: HttpRequest) -> HttpResponse:
    """Сторінка оцінок студента."""
    from main.selectors import get_student_performance_data, get_subjects_for_group
    
    student = request.user
    
    # Збираємо фільтри з request.GET
    filters = {
        'date_from': request.GET.get('date_from'),
        'date_to': request.GET.get('date_to'),
        'subject_id': request.GET.get('subject'),
        'min_grade': request.GET.get('min_grade'),
        'max_grade': request.GET.get('max_grade'),
        'search_query': request.GET.get('search'),
    }
    
    # Видаляємо None значення
    filters = {k: v for k, v in filters.items() if v}
    
    # Використовуємо селектор для отримання оцінок
    grades = get_student_performance_data(student, filters)
    
    # Отримуємо предмети групи
    student_subjects = get_subjects_for_group(student.group)

    return render(request, 'student_grades.html', {
        'grades': grades,
        'student_subjects': student_subjects,
        'active_page': 'student_grades',
    })

@role_required('student')
def student_attendance_view(request: HttpRequest) -> HttpResponse:
    student = request.user
    
    search_query = request.GET.get('search', '')
    subject_id = request.GET.get('subject', '')
    date_from = request.GET.get('date_from', '')
    date_to = request.GET.get('date_to', '')
    is_respectful = request.GET.get('is_respectful', '')

    absences = StudentPerformance.objects.filter(
        student=student,
        absence__isnull=False
    ).select_related(
        'lesson__subject',
        'lesson__teacher',
        'absence'
    )

    if search_query:
        absences = absences.filter(lesson__topic__icontains=search_query)
    
    if subject_id:
        absences = absences.filter(lesson__subject_id=subject_id)
        
    if date_from:
        absences = absences.filter(lesson__date__gte=date_from)
        
    if date_to:
        absences = absences.filter(lesson__date__lte=date_to)

    if is_respectful == '1':
        absences = absences.filter(absence__is_respectful=True)
    elif is_respectful == '0':
        absences = absences.filter(absence__is_respectful=False)

    absences = absences.order_by('-lesson__date')
    
    total_absences = absences.count()
    unexcused = absences.filter(absence__is_respectful=False).count()
    
    student_subjects = Subject.objects.filter(
        teachingassignment__group=student.group
    ).distinct()
    
    context = {
        'absences': absences,
        'total': total_absences,
        'unexcused': unexcused,
        'student_subjects': student_subjects,
        'active_page': 'student_attendance',
    }
    return render(request, 'student_attendance.html', context)


@role_required('teacher')
def teacher_dashboard_view(request):
    """
    Командний центр викладача.
    Показує: розклад на сьогодні, проблемних студентів, статистику.
    """
    teacher = request.user
    today = date.today()
    
    # 1. Розклад на СЬОГОДНІ
    today_lessons = Lesson.objects.filter(
        teacher=teacher, 
        date=today
    ).select_related('group', 'subject', 'classroom', 'evaluation_type').order_by('start_time')

    # 2. "Радар Ризику" (Студенти з низьким середнім балом у ваших групах)
    my_groups = TeachingAssignment.objects.filter(teacher=teacher).values_list('group', flat=True)
    
    risk_students = []
    students_in_danger = User.objects.filter(
        group__in=my_groups,
        role='student'
    ).annotate(
        absences_count=Count('studentperformance', filter=Q(studentperformance__absence__isnull=False))
    ).filter(absences_count__gte=3).order_by('-absences_count')[:5]

    for s in students_in_danger:
        risk_students.append({
            'name': s.full_name,
            'group': s.group.name,
            'issue': f"{s.absences_count} пропусків",
            'severity': 'high' if s.absences_count > 5 else 'medium'
        })

    # 3. Статистика за тиждень (кількість проведених пар)
    start_week = today - timedelta(days=today.weekday())
    end_week = start_week + timedelta(days=6)
    
    weekly_load = Lesson.objects.filter(
        teacher=teacher,
        date__range=[start_week, end_week]
    ).count()

    context = {
        'today_lessons': today_lessons,
        'risk_students': risk_students,
        'weekly_load': weekly_load,
        'active_page': 'teacher_dashboard',
    }
    return render(request, 'teacher_dashboard.html', context)

@role_required('teacher')
def teacher_live_mode_view(request, lesson_id):
    """
    Інтерактивний екран для проведення пари.
    """
    from main.models import BuildingAccessLog
    from datetime import date

    # 1. Отримуємо урок і перевіряємо права
    lesson = get_object_or_404(Lesson, id=lesson_id, teacher=request.user)
    
    # 2. Отримуємо студентів групи
    students = User.objects.filter(role='student', group=lesson.group).order_by('full_name')
    
    # 3. Отримуємо вже існуючі оцінки
    performances = StudentPerformance.objects.filter(lesson=lesson).select_related('absence')
    perf_map = {p.student_id: p for p in performances}
    
    # 4. Отримуємо статус присутності по RFID (за сьогодні)
    today = date.today()
    access_logs = BuildingAccessLog.objects.filter(
        timestamp__date=today,
        student__in=students
    ).order_by('student', 'timestamp')
    
    in_building_map = {}
    student_logs = {}
    for log in access_logs:
        student_logs[log.student_id] = log
    for s in students:
        last_log = student_logs.get(s.id)
        in_building_map[s.id] = True if last_log and last_log.action == 'ENTER' else False

    # 5. Формуємо список для фронтенду
    student_list = []
    for s in students:
        perf = perf_map.get(s.id)
        
        # Визначаємо статус
        grade_value = None
        comment = ""
        is_in_building = in_building_map.get(s.id, False)
        
        # Пріоритет: 
        # 1. Ручна оцінка/відмітка в БД
        # 2. Якщо немає в БД -> статус по RFID (якщо не в будівлі - відсутній)
        if perf:
            if perf.earned_points is not None:
                grade_value = int(perf.earned_points) if perf.earned_points % 1 == 0 else perf.earned_points
            is_absent = True if perf.absence else False
            comment = perf.comment or ""
        else:
            # Дефолтна логіка: якщо не "пікнувся" — відсутній
            is_absent = not is_in_building
            
        student_list.append({
            'user': s,
            'grade': grade_value,
            'is_absent': is_absent,
            'comment': comment,
            'initials': "".join([name[0] for name in s.full_name.split()[:2]])
        })

    context = {
        'lesson': lesson,
        'student_list': student_list,
        'active_page': 'teacher_dashboard' 
    }
    return render(request, 'teacher_live_mode.html', context)


@role_required('student')
def student_dashboard_view(request: HttpRequest) -> HttpResponse:
    """Дашборд студента з аналітикою та розкладом."""
    student = request.user
    from django.utils import timezone
    now_aware = timezone.localtime(timezone.now())
    today = now_aware.date()
    now_time = now_aware.time()
    
    # 1. Загальна статистика (Середній бал)
    performance_queryset = StudentPerformance.objects.filter(student=student)
    
    stats = performance_queryset.filter(
        earned_points__isnull=False
    ).aggregate(avg_score=Avg('earned_points'))
    
    # 2. Відвідуваність (для кругової діаграми)
    total_lessons_count = performance_queryset.count()
    absence_stats = performance_queryset.filter(absence__isnull=False).aggregate(
        total_absences=Count('id'),
        respectful=Count('id', filter=Q(absence__is_respectful=True)),
        unrespectful=Count('id', filter=Q(absence__is_respectful=False))
    )
    
    present_count = total_lessons_count - (absence_stats['total_absences'] or 0)
    attendance_percent = round((present_count / total_lessons_count * 100), 1) if total_lessons_count > 0 else 0
    
    # 3. Дані для графіка (останні 30 оцінок)
    chart_data = performance_queryset.filter(
        earned_points__isnull=False
    ).select_related('lesson', 'lesson__subject').order_by('lesson__date', 'lesson__start_time')[:30]
    
    graph_labels = [p.lesson.date.strftime("%d.%m") for p in chart_data]
    graph_points = [float(p.earned_points) for p in chart_data]
    
    # 4. Уроки (Зараз та Наступний)
    lessons_today = Lesson.objects.filter(group=student.group, date=today).select_related('subject', 'classroom', 'teacher').order_by('start_time')
    
    current_lesson = None
    next_lesson = None
    
    for l in lessons_today:
        if l.start_time <= now_time <= l.end_time:
            current_lesson = l
        elif l.start_time > now_time:
            next_lesson = l
            break
            
    if not next_lesson:
        # Шукаємо наступний урок у майбутні дні
        next_lesson = Lesson.objects.filter(
            group=student.group,
            date__gt=today
        ).select_related('subject', 'classroom', 'teacher').order_by('date', 'start_time').first()
    
    # 5. Останні події (5 останніх оцінок)
    recent_events = performance_queryset.filter(
        earned_points__isnull=False
    ).select_related('lesson', 'lesson__subject').order_by('-lesson__date', '-lesson__start_time')[:5]

    context = {
        'avg_score': round(stats['avg_score'] or 0, 1),
        'attendance_percent': attendance_percent,
        'attendance_json': json.dumps({
            'present': present_count,
            'respectful': absence_stats['respectful'] or 0,
            'unrespectful': absence_stats['unrespectful'] or 0
        }),
        'graph_labels_json': json.dumps(graph_labels),
        'graph_points_json': json.dumps(graph_points),
        'current_lesson': current_lesson,
        'next_lesson': next_lesson,
        'recent_events': recent_events,
        'active_page': 'student_dashboard',
    }
    return render(request, 'student_dashboard.html', context)

# =========================
# 5. ЗВІТИ (АДМІН)
# =========================

@role_required('admin')
def admin_reports_view(request):
    return render(request, 'admin_reports.html', {'active_page': 'reports'})

@role_required('admin')
def report_absences_view(request):
    group_id = request.GET.get('group', '')
    subject_id = request.GET.get('subject', '')
    date_from = request.GET.get('date_from', '')
    date_to = request.GET.get('date_to', '')
    limit = int(request.GET.get('limit', 0) or 0)
    
    # Нові фільтри
    course = request.GET.get('course', '')
    specialty = request.GET.get('specialty', '')
    is_active = request.GET.get('is_active', '')

    students = User.objects.filter(role='student')
    
    if group_id:
        students = students.filter(group_id=group_id)
    
    # Фільтр по курсу (через групу)
    if course:
        students = students.filter(group__course=course)
    
    # Фільтр по спеціальності
    if specialty:
        students = students.filter(group__specialty__icontains=specialty)
    
    # Фільтр по статусу активності
    if is_active:
        students = students.filter(is_active=(is_active == 'true'))

    perf_filter = Q(studentperformance__absence__isnull=False)
    
    if subject_id:
        perf_filter &= Q(studentperformance__lesson__subject_id=subject_id)
    if date_from:
        perf_filter &= Q(studentperformance__lesson__date__gte=date_from)
    if date_to:
        perf_filter &= Q(studentperformance__lesson__date__lte=date_to)

    unexcused_filter = perf_filter & Q(studentperformance__absence__is_respectful=False)

    report_data = students.annotate(
        total_absences=Count('studentperformance', filter=perf_filter),
        unexcused_absences=Count('studentperformance', filter=unexcused_filter)
    ).filter(total_absences__gt=0).order_by('-total_absences')
    
    if limit > 0:
        report_data = report_data[:limit]

    for item in report_data:
        item.excused_absences = item.total_absences - item.unexcused_absences

    if request.GET.get('export') == 'csv':
        rows = [[u.full_name, u.group.name if u.group else '-', u.total_absences, u.unexcused_absences] for u in report_data]
        return generate_csv_response(f"absences_report_{date.today()}", ['ПІБ', 'Група', 'Всього', 'Неповажні'], rows)

    groups = StudyGroup.objects.all()
    all_subjects = Subject.objects.all()
    
    # Отримуємо унікальні спеціальності та курси
    specialties = StudyGroup.objects.exclude(specialty='').values_list('specialty', flat=True).distinct()
    courses = StudyGroup.objects.exclude(course__isnull=True).values_list('course', flat=True).distinct().order_by('course')
    
    context = {
        'report_data': report_data,
        'report_title': 'Звіт: Пропуски студентів',
        'is_absences_report': True,
        'is_weekly_report': False,
        'report_reset_url_name': 'report_absences',
        'groups': groups,
        'all_subjects': all_subjects,
        'specialties': specialties,
        'courses': courses,
        'active_page': 'reports'
    }
    return render(request, 'report_absences.html', context)

@role_required('admin')
def report_rating_view(request):
    group_id = request.GET.get('group', '')
    subject_id = request.GET.get('subject', '')
    date_from = request.GET.get('date_from', '')
    date_to = request.GET.get('date_to', '')
    
    # Нові фільтри
    course = request.GET.get('course', '')
    specialty = request.GET.get('specialty', '')
    is_active = request.GET.get('is_active', '')
    
    MIN_VOTES = 5
    
    perf_base_filter = Q(earned_points__isnull=False)
    perf_user_filter = Q(studentperformance__earned_points__isnull=False)
    
    if subject_id:
        term = Q(lesson__subject_id=subject_id)
        perf_base_filter &= term
        perf_user_filter &= Q(studentperformance__lesson__subject_id=subject_id)
    if date_from:
        term = Q(lesson__date__gte=date_from)
        perf_base_filter &= term
        perf_user_filter &= Q(studentperformance__lesson__date__gte=date_from)
    if date_to:
        term = Q(lesson__date__lte=date_to)
        perf_base_filter &= term
        perf_user_filter &= Q(studentperformance__lesson__date__lte=date_to)

    global_stats = StudentPerformance.objects.filter(perf_base_filter).annotate(
        weighted_val=F('earned_points') * F('lesson__evaluation_type__weight_percent')
    ).aggregate(
        total_weighted=Sum('weighted_val'),
        total_weights=Sum('lesson__evaluation_type__weight_percent')
    )
    
    C_sum = float(global_stats['total_weighted'] or 0)
    C_weight = float(global_stats['total_weights'] or 1)
    C = C_sum / C_weight if C_weight > 0 else 0
    
    students_query = User.objects.filter(role='student')
    if group_id:
        students_query = students_query.filter(group_id=group_id)
    
    # Нові фільтри
    if course:
        students_query = students_query.filter(group__course=course)
    if specialty:
        students_query = students_query.filter(group__specialty__icontains=specialty)
    if is_active:
        students_query = students_query.filter(is_active=(is_active == 'true'))

    students_data = students_query.annotate(
        v=Count('studentperformance', filter=perf_user_filter),
        weighted_sum=Sum(
            F('studentperformance__earned_points') * F('studentperformance__lesson__evaluation_type__weight_percent'),
            filter=perf_user_filter
        ),
        weight_total=Sum(
            F('studentperformance__lesson__evaluation_type__weight_percent'),
            filter=perf_user_filter
        )
    ).filter(v__gt=0)

    rating_list = []
    
    for student in students_data:
        v = student.v
        ws = float(student.weighted_sum or 0)
        wt = float(student.weight_total or 1)
        
        R = ws / wt if wt > 0 else 0
        
        weighted_rating = (v / (v + MIN_VOTES)) * R + (MIN_VOTES / (v + MIN_VOTES)) * float(C)
        
        group_name = student.group.name if student.group else '-'
        
        rating_list.append({
            'full_name': student.full_name,
            'group': {'name': group_name},
            'raw_avg': round(R, 2),
            'count': v,
            'weighted_avg': round(weighted_rating, 2)
        })

    rating_list.sort(key=lambda x: x['weighted_avg'], reverse=True)

    if request.GET.get('export') == 'csv':
        rows = [
            [r['full_name'], r['group']['name'], r['raw_avg'], r['weighted_avg'], r['count']] 
            for r in rating_list
        ]
        return generate_csv_response(
            f"rating_bayesian_{date.today()}", 
            ['ПІБ', 'Група', 'Середній бал', 'Рейтинг (Зважений)', 'К-сть оцінок'], 
            rows
        )

    groups = StudyGroup.objects.all()
    all_subjects = Subject.objects.all()
    
    # Отримуємо унікальні спеціальності та курси
    specialties = StudyGroup.objects.exclude(specialty='').values_list('specialty', flat=True).distinct()
    courses = StudyGroup.objects.exclude(course__isnull=True).values_list('course', flat=True).distinct().order_by('course')
    
    context = {
        'report_data': rating_list,
        'report_title': 'Звіт: Рейтинг студентів',
        'is_rating_report': True,
        'is_weekly_report': False,
        'report_reset_url_name': 'report_rating',
        'groups': groups,
        'all_subjects': all_subjects,
        'specialties': specialties,
        'courses': courses,
        'active_page': 'reports'
    }
    return render(request, 'report_absences.html', context)


@role_required('admin')
def report_weekly_absences_view(request):
    group_id = request.GET.get('group', '')
    subject_id = request.GET.get('subject', '')
    
    today = date.today()
    start_week = today - timedelta(days=today.weekday())
    end_week = start_week + timedelta(days=6)

    students = User.objects.filter(role='student')
    if group_id:
        students = students.filter(group_id=group_id)

    perf_filter = Q(
        studentperformance__absence__isnull=False,
        studentperformance__lesson__date__gte=start_week,
        studentperformance__lesson__date__lte=end_week
    )
    
    if subject_id:
        perf_filter &= Q(studentperformance__lesson__subject_id=subject_id)

    unexcused_filter = perf_filter & Q(studentperformance__absence__is_respectful=False)

    report_data = students.annotate(
        total_absences=Count('studentperformance', filter=perf_filter),
        unexcused_absences=Count('studentperformance', filter=unexcused_filter)
    ).filter(total_absences__gt=0).order_by('-total_absences')

    groups = StudyGroup.objects.all()
    all_subjects = Subject.objects.all()
    
    context = {
        'report_data': report_data,
        'report_title': f'Звіт: Пропуски за тиждень ({start_week} - {end_week})',
        'is_absences_report': True,
        'is_weekly_report': True,
        'report_reset_url_name': 'report_weekly_absences',
        'groups': groups,
        'all_subjects': all_subjects,
        'active_page': 'reports'
    }
    return render(request, 'report_absences.html', context)


# =========================
# 5. EVALUATION TYPES MANAGEMENT
# =========================

@role_required('teacher')
def manage_evaluation_types_view(request):
    teacher_id = request.user.id  # request.user
    
    assignments = TeachingAssignment.objects.filter(
        teacher_id=teacher_id
    ).select_related('subject', 'group')
    
    selected_assignment_id = request.GET.get('assignment')
    selected_assignment = None
    evaluation_types = []
    total_weight = 0
    
    if selected_assignment_id:
        try:
            selected_assignment = assignments.get(id=selected_assignment_id)
            evaluation_types = EvaluationType.objects.filter(
                assignment=selected_assignment
            ).order_by('name')
            total_weight = sum(et.weight_percent for et in evaluation_types)
        except TeachingAssignment.DoesNotExist:
            messages.error(request, "Призначення не знайдено")
    
    if request.method == 'POST':
        if not selected_assignment:
            messages.error(request, "Спочатку оберіть предмет та групу")
            return redirect('manage_evaluation_types')
        
        from .forms import EvaluationTypeForm
        form = EvaluationTypeForm(request.POST)
        
        if form.is_valid():
            eval_type = form.save(commit=False)
            eval_type.assignment = selected_assignment
            
            current_total = sum(et.weight_percent for et in evaluation_types)
            new_total = current_total + eval_type.weight_percent
            
            if new_total > 100:
                messages.error(request, f"Сума ваг не може перевищувати 100%. Поточна сума: {current_total}%, спроба додати: {eval_type.weight_percent}%")
            else:
                eval_type.save()
                messages.success(request, f"Тип оцінювання '{eval_type.name}' додано успішно")
                return redirect(f'manage_evaluation_types?assignment={selected_assignment.id}')
        else:
            messages.error(request, "Помилка при додаванні типу оцінювання")
    
    from .forms import EvaluationTypeForm
    form = EvaluationTypeForm()
    
    context = {
        'assignments': assignments,
        'selected_assignment': selected_assignment,
        'selected_assignment_id': selected_assignment_id,
        'evaluation_types': evaluation_types,
        'total_weight': total_weight,
        'form': form,
        'active_page': 'teacher',
    }
    return render(request, 'evaluation_types_config.html', context)


@role_required('teacher')
@require_POST
def evaluation_type_edit_view(request, pk):
    teacher_id = request.user.id
    eval_type = get_object_or_404(EvaluationType, pk=pk)
    
    if eval_type.assignment.teacher_id != teacher_id:
        messages.error(request, "У вас немає прав для редагування цього типу")
        return redirect('manage_evaluation_types')
    
    name = request.POST.get('name')
    weight_percent = request.POST.get('weight_percent')
    
    try:
        weight_percent = float(weight_percent)
        
        other_types = EvaluationType.objects.filter(
            assignment=eval_type.assignment
        ).exclude(pk=pk)
        other_total = sum(et.weight_percent for et in other_types)
        new_total = other_total + weight_percent
        
        if new_total > 100:
            messages.error(request, f"Сума ваг не може перевищувати 100%. Сума інших типів: {other_total}%")
        elif weight_percent < 0:
            messages.error(request, "Вага не може бути від'ємною")
        else:
            eval_type.name = name
            eval_type.weight_percent = weight_percent
            eval_type.save()
            messages.success(request, "Тип оцінювання оновлено")
    except (ValueError, TypeError):
        messages.error(request, "Некоректне значення ваги")
    
    return redirect(f'manage_evaluation_types?assignment={eval_type.assignment.id}')


@role_required('teacher')
@require_POST
def evaluation_type_delete_view(request, pk):
    teacher_id = request.user.id
    eval_type = get_object_or_404(EvaluationType, pk=pk)
    
    if eval_type.assignment.teacher_id != teacher_id:
        messages.error(request, "У вас немає прав для видалення цього типу")
        return redirect('manage_evaluation_types')
    
    assignment_id = eval_type.assignment.id
    
    if Lesson.objects.filter(evaluation_type=eval_type).exists():
        messages.error(request, "Неможливо видалити тип оцінювання, оскільки він використовується в занятях")
    else:
        eval_type.delete()
        messages.success(request, "Тип оцінювання видалено")
    
    return redirect(f'manage_evaluation_types?assignment={assignment_id}')


@role_required('teacher')
def get_evaluation_types_api(request):
    assignment_id = request.GET.get('assignment_id')
    
    if not assignment_id:
        return JsonResponse({'error': 'assignment_id обов\'язковий'}, status=400)
    
    teacher_id = request.user.id
    
    try:
        assignment = TeachingAssignment.objects.get(
            id=assignment_id,
            teacher_id=teacher_id
        )
        
        evaluation_types = EvaluationType.objects.filter(
            assignment=assignment
        ).values('id', 'name', 'weight_percent')
        
        return JsonResponse({
            'evaluation_types': list(evaluation_types)
        })
    except TeachingAssignment.DoesNotExist:
        return JsonResponse({'error': 'Призначення не знайдено'}, status=404)


# --- STUDENTS MANAGEMENT (EXTRA) ---

@login_required
def students_list_view(request):
    search_query = request.GET.get('search', '')
    group_id = request.GET.get('group', '')
    
    students = User.objects.filter(role='student').select_related('group')
    
    if search_query:
        students = students.filter(full_name__icontains=search_query)
        
    if group_id:
        students = students.filter(group_id=group_id)
        
    students = students.order_by('group__name', 'full_name')
    groups = StudyGroup.objects.all()
    
    return render(request, 'students.html', {
        'students': students, 
        'groups': groups,
        'active_page': 'students'
    })

@login_required
@require_http_methods(["POST"])
def student_add(request):
    full_name = request.POST.get('full_name')
    group_id = request.POST.get('group_id')
    email = request.POST.get('email')
    password = request.POST.get('password')

    if full_name and email and password:
        if User.objects.filter(email=email).exists():
            messages.error(request, f"Користувач з email {email} вже існує.")
        else:
            try:
                group = StudyGroup.objects.get(pk=group_id) if group_id else None
                
                # Якщо User менеджер налаштований через create_user (AbstractBaseUser):
                # User.objects.create_user(email=email, password=password, full_name=full_name, role='student', group=group)
                
                # Або старий метод, якщо ви не переписали менеджер (але ми домовилися що переписали)
                # Тут використовуємо create_user, бо це правильно для Django Auth
                User.objects.create_user(
                    email=email,
                    password=password,
                    full_name=full_name,
                    role='student',
                    group=group
                )
                messages.success(request, f"Студента {full_name} успішно додано.")
            except Exception as e:
                messages.error(request, f"Помилка при створенні: {e}")
    else:
        messages.error(request, "Заповніть всі обов'язкові поля.")

    return redirect('students_list')


@login_required
def timeline_schedule_view(request):
    user = request.user
    
    # Визначаємо групу
    group = user.group if user.role == 'student' else None
    if not group and request.GET.get('group_id'):
        group = get_object_or_404(StudyGroup, id=request.GET.get('group_id'))

    # Отримуємо всі часові слоти
    time_slots = TimeSlot.objects.all()
    
    # Дні тижня
    days_data = []
    days_names = {1: 'Понеділок', 2: 'Вівторок', 3: 'Середа', 4: 'Четвер', 5: 'П\'ятниця'}
    
    # TIMEZONE FIX
    from django.utils import timezone
    now_aware = timezone.localtime(timezone.now())
    current_time_minutes = now_aware.hour * 60 + now_aware.minute
    current_day = now_aware.weekday() + 1 # 1=Monday

    if group:
        # Беремо шаблони розкладу
        templates = ScheduleTemplate.objects.filter(
            group=group
        ).select_related('subject', 'teacher', 'teaching_assignment')

        # Дні тижня для таймлайну
        today_date = now_aware.date()
        start_week = today_date - timedelta(days=today_date.weekday())

        for day_num, day_name in days_names.items():
            day_lessons = []
            current_day_date = start_week + timedelta(days=day_num - 1)
            
            # Шукаємо уроки в цей день (згенеровані)
            lessons_in_db = Lesson.objects.filter(
                group=group,
                date=current_day_date
            ).select_related('subject', 'teacher')

            for slot in time_slots:
                # Мапінг слота в урок за часом
                lesson = lessons_in_db.filter(start_time=slot.start_time).first()
                
                start_min = slot.start_time.hour * 60 + slot.start_time.minute
                end_min = slot.end_time.hour * 60 + slot.end_time.minute
                duration = end_min - start_min
                
                status = 'future'
                progress = 0
                
                if day_num < current_day:
                    status = 'past'
                elif day_num == current_day:
                    if current_time_minutes > end_min:
                        status = 'past'
                    elif current_time_minutes >= start_min:
                        status = 'current'
                        passed = current_time_minutes - start_min
                        progress = int((passed / duration) * 100) if duration > 0 else 0
                
                day_lessons.append({
                    'slot': slot,
                    'assignment': lesson if lesson else None,
                    'status': status,
                    'progress': min(max(progress, 0), 100),
                    'duration': duration
                })
            
            days_data.append({
                'day_name': day_name,
                'is_today': day_num == current_day,
                'lessons': day_lessons
            })

    return render(request, 'timeline_schedule.html', {
        'days_data': days_data,
        'group': group,
        'all_groups': StudyGroup.objects.all().order_by('name') if user.role != 'student' else None,
        'active_page': 'schedule'
    })

@login_required
@require_http_methods(["POST"])
def student_delete(request, pk):
    student = get_object_or_404(User, pk=pk, role='student')
    name = student.full_name
    student.delete()
    messages.success(request, f"Студента {name} видалено.")
    return redirect('students_list')

@require_POST
@role_required('teacher')
def api_update_lesson(request: HttpRequest) -> JsonResponse:
    """API для оновлення теми та типу уроку."""
    try:
        data = json.loads(request.body)
        lesson_id = data.get('lesson_id')
        topic = data.get('topic')
        type_id = data.get('type_id')
        
        lesson = get_object_or_404(Lesson, id=lesson_id, teacher=request.user)
        
        if topic is not None:
            lesson.topic = topic
            
        if type_id:
            etype = get_object_or_404(EvaluationType, id=type_id, assignment__teacher=request.user)
            lesson.evaluation_type = etype
            
        lesson.save()
        
        return JsonResponse({
            'status': 'success',
            'topic': lesson.topic,
            'type_name': lesson.evaluation_type.name if lesson.evaluation_type else '—',
            'max_points': float(lesson.evaluation_type.weight_percent) if lesson.evaluation_type else 12
        })
        
    except Exception as e:
        import traceback
        print(traceback.format_exc())
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)

@role_required('teacher')
def teacher_settings_view(request: HttpRequest) -> HttpResponse:
    """Сторінка налаштувань викладача для керування типами занять."""
    teacher = request.user
    assignments = TeachingAssignment.objects.filter(teacher=teacher).select_related('subject', 'group')
    
    settings_data = []
    for a in assignments:
        types = a.evaluation_types.all()
        settings_data.append({
            'assignment': a,
            'types': types
        })
        
    return render(request, 'teacher_settings.html', {
        'settings_data': settings_data,
        'active_page': 'teacher'
    })

@require_POST
@role_required('teacher')
def api_manage_evaluation_types(request: HttpRequest) -> JsonResponse:
    """API для CRUD операцій над EvaluationType."""
    try:
        data = json.loads(request.body)
        action = data.get('action')
        
        if action == 'create':
            assignment_id = data.get('assignment_id')
            name = data.get('name')
            weight = data.get('weight', 0)
            
            assignment = get_object_or_404(TeachingAssignment, id=assignment_id, teacher=request.user)
            etype = EvaluationType.objects.create(
                assignment=assignment,
                name=name,
                weight_percent=weight
            )
            return JsonResponse({'status': 'success', 'id': etype.id})
            
        elif action == 'update':
            type_id = data.get('id')
            name = data.get('name')
            weight = data.get('weight')
            
            etype = get_object_or_404(EvaluationType, id=type_id, assignment__teacher=request.user)
            etype.name = name
            etype.weight_percent = weight
            etype.save()
            return JsonResponse({'status': 'success'})
            
        elif action == 'delete':
            type_id = data.get('id')
            etype = get_object_or_404(EvaluationType, id=type_id, assignment__teacher=request.user)
            
            if Lesson.objects.filter(evaluation_type=etype).exists():
                return JsonResponse({
                    'status': 'error', 
                    'message': 'Цей тип вже використовується в уроках і не може бути видалений.'
                }, status=400)
                
            etype.delete()
            return JsonResponse({'status': 'success'})
            
        return JsonResponse({'status': 'error', 'message': 'Unknown action'}, status=400)
        
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)


# =========================
# 6. ПРОФІЛЬ ТА НАЛАШТУВАННЯ
# =========================

@login_required
def profile_view(request: HttpRequest) -> HttpResponse:
    """Сторінка профілю користувача та налаштувань."""
    user = request.user
    if request.method == 'POST':
        form = ProfileForm(request.POST, request.FILES, instance=user)
        if form.is_valid():
            form.save()
            messages.success(request, "Профіль успішно оновлено!")
            return redirect('profile')
        else:
            messages.error(request, "Помилка при оновленні профілю.")
    else:
        form = ProfileForm(instance=user)

    context = {
        'user': user,
        'form': form,
        'active_page': 'profile',
    }
    return render(request, 'profile.html', context)
