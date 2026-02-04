import csv
import json
from collections import defaultdict
from datetime import date, datetime, timedelta

from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.hashers import make_password  # Залишаємо для ручного створення, якщо потрібно
from django.core.exceptions import ObjectDoesNotExist
from django.db import IntegrityError, transaction
from django.db.models import Avg, Count, F, Max, Min, Prefetch, Q, Sum
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST, require_http_methods

from .forms import ClassroomForm, StudyGroupForm, SubjectForm, UserAdminForm
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
from datetime import time

# =========================
# UTILITY & DECORATORS
# =========================

def role_required(allowed_roles):
    """
    Декоратор для перевірки ролі через стандартний request.user.
    allowed_roles може бути строкою ('admin') або списком (['admin', 'teacher']).
    """
    if isinstance(allowed_roles, str):
        allowed_roles = [allowed_roles]

    def decorator(view_func):
        def wrapper(request, *args, **kwargs):
            # 1. Перевірка авторизації Django
            if not request.user.is_authenticated:
                return redirect('login')

            # 2. Перевірка ролі
            if request.user.role not in allowed_roles:
                messages.error(request, "У вас немає прав для доступу до цієї сторінки.")
                # Редірект на "свою" сторінку, щоб уникнути циклів
                if request.user.role == 'student':
                    return redirect('student_grades')
                elif request.user.role == 'teacher':
                    return redirect('teacher_journal')
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

def login_view(request):
    """Сторінка входу."""
    if request.user.is_authenticated:
        role = request.user.role
        if role == 'admin':
            return redirect('admin_panel')
        if role == 'teacher':
            return redirect('teacher_journal')
        if role == 'student':
            return redirect('student_grades')

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
            return redirect('teacher_journal')
        elif user.role == 'student':
            return redirect('student_grades')
        else:
            return redirect('login')
    else:
        messages.error(request, "Невірний email або пароль")
        return redirect('login')


def logout_view(request):
    """Вихід із системи."""
    logout(request)
    return redirect('login')

# =========================
# 2. АДМІНІСТРАТОР
# =========================

@role_required('admin')
def admin_panel_view(request):
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
def users_list_view(request):
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
def user_edit_view(request, pk):
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
        
        # Намагаємося визначити номер пари за часом
        # У новому конструкторі ми використовуємо номери слотів.
        # Для сумісності спробуємо знайти найбільш підходящий слот.
        slot_times = {"08:30": 1, "10:15": 2, "12:15": 3, "14:15": 4, "16:00": 5, "17:45": 6}
        start_time_str = item.start_time.strftime("%H:%M")
        lesson_num = slot_times.get(start_time_str, None)
        
        if lesson_num:
            schedule_map_temp[grp_id][day][str(lesson_num)] = {
                'subject_id': item.subject.id,
                'subject_name': item.subject.name,
                'teacher_id': item.teacher.id,
                'teacher_name': item.teacher.full_name,
                'start_time': start_time_str,
                'classroom': item.classroom or ""
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

    context = {
        'groups': groups,
        'schedule_map': schedule_map,
        'subject_data': subject_data,
        'subject_teachers_map': subject_teachers_map,
        'days': [(1, 'Пн'), (2, 'Вт'), (3, 'Ср'), (4, 'Чт'), (5, 'Пт')],
        'lesson_numbers': range(1, 7),
        'active_page': 'schedule_builder',
    }
    return render(request, 'main/schedule_builder.html', context)


@require_POST
@role_required('admin')
def save_schedule_changes(request):
    """API endpoint для збереження розкладу."""
    try:
        data = json.loads(request.body)
        group_id = data.get('group_id')
        schedule_entries = data.get('schedule', {})
        
        if not group_id:
            return JsonResponse({'status': 'error', 'message': 'Група не вибрана'}, status=400)
        
        group = get_object_or_404(StudyGroup, id=group_id)
        
        with transaction.atomic():
            ScheduleTemplate.objects.filter(
                group=group
            ).delete()
            
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
                        if teacher_id:
                            assignment = TeachingAssignment.objects.filter(
                                group=group,
                                subject_id=subject_id,
                                teacher_id=teacher_id
                            ).first()
                        else:
                            assignment = TeachingAssignment.objects.filter(
                                group=group,
                                subject_id=subject_id
                            ).first()
                        
                        if assignment:
                            # Використовуємо дані з фронтенду
                            start_time_str = "08:30"
                            classroom = ""
                            if isinstance(lesson_data, dict):
                                start_time_str = lesson_data.get('startTime', lesson_data.get('start_time', "08:30"))
                                classroom = lesson_data.get('classroom', "")
                            
                            ScheduleTemplate.objects.create(
                                group=group,
                                subject_id=subject_id,
                                teacher_id=teacher_id or assignment.teacher_id,
                                day_of_week=day,
                                start_time=start_time_str,
                                classroom=classroom,
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
def schedule_editor_view(request):
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
def api_save_schedule_slot(request):
    """API для збереження окремого слоту в ScheduleTemplate."""
    try:
        data = json.loads(request.body)
        group_id = data.get('group_id')
        day = int(data.get('day'))
        lesson_num = int(data.get('lesson_number'))
        
        subject_id = data.get('subject_id')
        teacher_id = data.get('teacher_id')
        classroom_id = data.get('classroom_id')
        start_time_str = data.get('start_time')
        duration = int(data.get('duration', 80))
        
        if not all([group_id, day, lesson_num]):
            return JsonResponse({'status': 'error', 'message': 'Недостатньо даних'}, status=400)
            
        group = get_object_or_404(StudyGroup, id=group_id)
        
        # Видалення якщо вибрано "пусто" (subject_id=None)
        if not subject_id:
            ScheduleTemplate.objects.filter(group=group, day_of_week=day, lesson_number=lesson_num).delete()
            return JsonResponse({'status': 'success', 'message': 'Слот очищено'})

        # Конвертація часу
        try:
            h, m = map(int, start_time_str.split(':'))
            start_time = time(h, m)
        except:
            return JsonResponse({'status': 'error', 'message': 'Невірний формат часу'}, status=400)

        # Розрахунок кінця пари (спрощено, без переходу через добу)
        start_dt = datetime.combine(date.today(), start_time)
        end_dt = start_dt + timedelta(minutes=duration)
        end_time = end_dt.time()
        
        # VALIDATION: Overlap within the SAME group
        # Перевірка з попередньою(lesson_num-1) та наступною(lesson_num+1) парою
        conflicts = ScheduleTemplate.objects.filter(group=group, day_of_week=day).exclude(lesson_number=lesson_num)
        for c in conflicts:
            c_start = datetime.combine(date.today(), c.start_time)
            c_end = c_start + timedelta(minutes=c.duration_minutes)
            
            # Перетин інтервалів: max(start) < min(end)
            if max(start_dt, c_start) < min(end_dt, c_end):
                return JsonResponse({
                    'status': 'error', 
                    'message': f'Конфлікт: Пара №{c.lesson_number} ({c.start_time.strftime("%H:%M")}) перетинається з цим часом.'
                }, status=400)
        
        # VALIDATION: Teacher busy
        if teacher_id:
            teacher_conflicts = ScheduleTemplate.objects.filter(
                teacher_id=teacher_id, 
                day_of_week=day
            ).exclude(group=group, lesson_number=lesson_num)
            for tc in teacher_conflicts:
                tc_start = datetime.combine(date.today(), tc.start_time)
                tc_end = tc_start + timedelta(minutes=tc.duration_minutes)
                if max(start_dt, tc_start) < min(end_dt, tc_end):
                    return JsonResponse({
                        'status': 'error', 
                        'message': f'Викладач уже зайнятий у групі {tc.group.name} о {tc.start_time.strftime("%H:%M")}'
                    }, status=400)

        # VALIDATION: Classroom busy
        if classroom_id:
            room_conflicts = ScheduleTemplate.objects.filter(
                classroom_id=classroom_id, 
                day_of_week=day
            ).exclude(group=group, lesson_number=lesson_num)
            for rc in room_conflicts:
                rc_start = datetime.combine(date.today(), rc.start_time)
                rc_end = rc_start + timedelta(minutes=rc.duration_minutes)
                if max(start_dt, rc_start) < min(end_dt, rc_end):
                    return JsonResponse({
                        'status': 'error', 
                        'message': f'Аудиторія зайнята групою {rc.group.name} о {rc.start_time.strftime("%H:%M")}'
                    }, status=400)

        # SAVE
        template, created = ScheduleTemplate.objects.update_or_create(
            group=group, day_of_week=day, lesson_number=lesson_num,
            defaults={
                'subject_id': subject_id,
                'teacher_id': teacher_id,
                'classroom_id': classroom_id,
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

    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)


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
    
    lessons = []
    if group:
        lessons = Lesson.objects.filter(
            group=group,
            date__gte=start_of_week,
            date__lte=end_of_week
        ).select_related('subject', 'teacher', 'evaluation_type')

    # Дні тижня для заголовка
    week_days = []
    day_names = ['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Нд']
    for i in range(7):
        d = start_of_week + timedelta(days=i)
        week_days.append({
            'date': d,
            'day_name': day_names[i],
            'is_today': d == today
        })

    context = {
        'lessons': lessons,
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
def teacher_journal_view(request):
    # Отримуємо ID з request.user
    teacher_id = request.user.id
    
    assignments = TeachingAssignment.objects.filter(
        teacher_id=teacher_id
    ).select_related('subject', 'group')

    selected_subject_id = request.GET.get('subject')
    selected_group_id = request.GET.get('group')
    week_shift = int(request.GET.get('week', 0))
    
    today = date.today()
    days_since_monday = today.weekday()
    current_monday = today - timedelta(days=days_since_monday)
    start_of_week = current_monday + timedelta(weeks=week_shift)
    end_of_week = start_of_week + timedelta(days=4)
    
    subjects = []
    groups = []
    seen_subjects = set()
    seen_groups = set()
    
    for assignment in assignments:
        if assignment.subject.id not in seen_subjects:
            subject_obj = type('SubjectFilter', (), {
                'pk': assignment.subject.id,
                'subject_name': assignment.subject.name
            })()
            subjects.append(subject_obj)
            seen_subjects.add(assignment.subject.id)
        
        if assignment.group.id not in seen_groups:
            group_obj = type('GroupFilter', (), {
                'pk': assignment.group.id,
                'name': assignment.group.name
            })()
            groups.append(group_obj)
            seen_groups.add(assignment.group.id)
    
    selected_assignment = None
    students = []
    lesson_headers = []
    journal_data = {}
    
    if selected_subject_id and selected_group_id:
        try:
            selected_assignment = assignments.get(
                subject_id=selected_subject_id,
                group_id=selected_group_id
            )
            
            search_query = request.GET.get('search', '')
            students_query = selected_assignment.group.students.filter(role='student')
            
            if search_query:
                students_query = students_query.filter(full_name__icontains=search_query)
            
            students = students_query.order_by('full_name')
            
            schedule_items = ScheduleTemplate.objects.filter(
                group=selected_assignment.group,
                subject=selected_assignment.subject,
                teacher=selected_assignment.teacher
            ).order_by('day_of_week')
            
            date_lessons_map = {}
            
            for schedule_item in schedule_items:
                lesson_date = start_of_week + timedelta(days=schedule_item.day_of_week - 1)
                
                if lesson_date not in date_lessons_map:
                    date_lessons_map[lesson_date] = []
                
                lesson_type = 'Л'
                
                date_lessons_map[lesson_date].append({
                    'lesson_num': schedule_item.lesson_number,
                    'lesson_type': lesson_type,
                    'classroom': schedule_item.classroom
                })
            
            existing_sessions = Lesson.objects.filter(
                group=selected_assignment.group,
                subject=selected_assignment.subject,
                teacher=selected_assignment.teacher,
                date__gte=start_of_week,
                date__lte=end_of_week
            ).select_related('evaluation_type', 'classroom')
            
            sessions_map = {
                (sess.date, sess.lesson_number): sess 
                for sess in existing_sessions
            }

            for lesson_date in sorted(date_lessons_map.keys()):
                day_names = ['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Нд']
                day_name = day_names[lesson_date.weekday()]
                date_formatted = lesson_date.strftime('%d.%m')
                
                lesson_header = type('LessonHeader', (), {
                    'date': lesson_date,
                    'date_formatted': date_formatted,
                    'day_name': day_name,
                    'lessons': []
                })()
                
                for lesson_info in date_lessons_map[lesson_date]:
                    l_num = lesson_info['lesson_num']
                    
                    session = sessions_map.get((lesson_date, l_num))
                    
                    if session:
                        l_type = session.evaluation_type.name if session.evaluation_type else 'Заняття'
                        l_weight = session.evaluation_type.weight_percent if session.evaluation_type else None
                        l_topic = session.topic
                        l_classroom = session.classroom
                    else:
                        l_type = 'Заняття'
                        l_weight = None
                        l_topic = ''
                        l_classroom = lesson_info.get('classroom')

                    lesson_obj = type('Lesson', (), {
                        'lesson_num': l_num,
                        'lesson_type': l_type,
                        'weight_percent': l_weight,
                        'topic': l_topic,
                        'classroom': l_classroom
                    })()
                    lesson_header.lessons.append(lesson_obj)
                
                lesson_headers.append(lesson_header)
            
            lessons = Lesson.objects.filter(
                group=selected_assignment.group,
                subject=selected_assignment.subject,
                teacher=selected_assignment.teacher,
                date__gte=start_of_week,
                date__lte=end_of_week
            )
            
            performances = StudentPerformance.objects.filter(
                lesson__in=lessons
            ).select_related('lesson', 'absence')
            
            for student in students:
                journal_data[student.pk] = {}
            
            for perf in performances:
                student_id = perf.student_id
                lesson_date = perf.lesson.date
                lesson_num = perf.lesson.lesson_number
                
                if student_id not in journal_data:
                    journal_data[student_id] = {}
                
                if lesson_date not in journal_data[student_id]:
                    journal_data[student_id][lesson_date] = {}
                
                if perf.grade is not None:
                    value = perf.grade
                    is_grade = True
                    display_value = str(perf.grade)
                elif perf.absence:
                    value = -1
                    is_grade = False
                    display_value = perf.absence.code
                else:
                    value = None
                    is_grade = False
                    display_value = '—'
                
                entry = type('JournalEntry', (), {
                    'value': value,
                    'is_grade': is_grade,
                    'get_display_value': display_value
                })()
                
                journal_data[student_id][lesson_date][lesson_num] = entry
                
        except TeachingAssignment.DoesNotExist:
            messages.error(request, "Призначення не знайдено")

    context = {
        'subjects': subjects,
        'groups': groups,
        'selected_subject_id': selected_subject_id,
        'selected_group_id': selected_group_id,
        'selected_assignment': selected_assignment,
        'students': students,
        'lesson_headers': lesson_headers,
        'journal_data': journal_data,
        'week_shift': week_shift,
        'start_of_week': start_of_week,
        'end_of_week': end_of_week,
        'active_page': 'teacher',
    }
    return render(request, 'teacher.html', context)

@role_required('teacher')
@require_POST
def save_journal_entries(request):
    try:
        data = json.loads(request.body)
        teacher_id = request.user.id  # Використовуємо request.user.id
        
        changes = data.get('changes', [])
        
        if not changes:
            return JsonResponse({'status': 'error', 'message': 'Відсутні дані'}, status=400)

        with transaction.atomic():
            for change in changes:
                student_pk = change.get('student_pk')
                lesson_date = change.get('date')
                lesson_num = change.get('lesson_num')
                value = change.get('value')
                subject_id = change.get('subject_id')
                
                if not (student_pk and lesson_date and lesson_num and subject_id):
                    continue
                
                try:
                    student = User.objects.get(pk=student_pk)
                    assignment = TeachingAssignment.objects.get(
                        teacher_id=teacher_id,
                        subject_id=subject_id,
                        group=student.group
                    )
                except (User.DoesNotExist, TeachingAssignment.DoesNotExist):
                    continue
                
                eval_type = assignment.evaluation_types.first()
                if not eval_type:
                    eval_type = EvaluationType.objects.create(
                        assignment=assignment, 
                        name="Заняття", 
                        weight_percent=0
                    )
                
                # Створюємо урок в новій системі
                # Припускаємо стандартний час для старого журналу
                times = {1: "08:30", 2: "10:05", 3: "11:40", 4: "13:15", 5: "14:50", 6: "16:25"}
                start_time = times.get(int(lesson_num), "08:30")
                
                lesson_session, created = Lesson.objects.get_or_create(
                    group=student.group,
                    subject=assignment.subject,
                    teacher=assignment.teacher,
                    date=lesson_date,
                    start_time=start_time,
                    defaults={
                        'evaluation_type': eval_type,
                        'end_time': (datetime.combine(date.today(), datetime.strptime(start_time, "%H:%M").time()) + timedelta(minutes=90)).time()
                    }
                )
                
                grade_value = None
                absence_obj = None
                
                if value == '—' or value is None:
                    StudentPerformance.objects.filter(
                        lesson=lesson_session,
                        student_id=student_pk
                    ).delete()
                    continue
                
                try:
                    val_int = int(value)
                    if val_int > 0:
                        grade_value = val_int
                    else:
                        code_map = {-1: 'Н', -2: 'ДЛ', -3: 'ПП'}
                        code_str = code_map.get(val_int, 'Н')
                        absence_obj = AbsenceReason.objects.filter(code=code_str).first()
                        if not absence_obj:
                            absence_obj = AbsenceReason.objects.first()
                except (ValueError, TypeError):
                    continue
                
                StudentPerformance.objects.update_or_create(
                    lesson=lesson_session,
                    student_id=student_pk,
                    defaults={
                        'grade': grade_value,
                        'absence': absence_obj
                    }
                )

        return JsonResponse({'status': 'success', 'message': 'Дані збережено'})

    except Exception as e:
        import traceback
        traceback.print_exc()
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)

# =========================
# 4. СТУДЕНТ
# =========================

@role_required('student')
def student_grades_view(request):
    # Отримуємо студента з request.user
    student = request.user
    
    date_from = request.GET.get('date_from')
    date_to = request.GET.get('date_to')
    subject_id = request.GET.get('subject')
    min_grade = request.GET.get('min_grade')
    max_grade = request.GET.get('max_grade')
    search_query = request.GET.get('search')

    grades = StudentPerformance.objects.filter(
        student=student, 
        grade__isnull=False
    ).select_related(
        'lesson', 
        'lesson__subject', 
        'lesson__teacher',
        'lesson__evaluation_type'
    ).order_by('-lesson__date')

    if date_from:
        grades = grades.filter(lesson__date__gte=date_from)
    if date_to:
        grades = grades.filter(lesson__date__lte=date_to)
    
    if subject_id:
        grades = grades.filter(lesson__subject_id=subject_id)
        
    if min_grade:
        grades = grades.filter(grade__gte=min_grade)
    if max_grade:
        grades = grades.filter(grade__lte=max_grade)

    if search_query:
        grades = grades.filter(
            Q(comment__icontains=search_query) | 
            Q(lesson__topic__icontains=search_query)
        )

    student_subjects = Subject.objects.filter(
        teachingassignment__group=student.group
    ).distinct()

    return render(request, 'student_grades.html', {
        'grades': grades,
        'student_subjects': student_subjects,
        'active_page': 'student_grades',
    })

@role_required('student')
def student_attendance_view(request):
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

    students = User.objects.filter(role='student')
    
    if group_id:
        students = students.filter(group_id=group_id)

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
    
    context = {
        'report_data': report_data,
        'report_title': 'Звіт: Пропуски студентів',
        'is_absences_report': True,
        'is_weekly_report': False,
        'report_reset_url_name': 'report_absences',
        'groups': groups,
        'all_subjects': all_subjects,
        'active_page': 'reports'
    }
    return render(request, 'report_absences.html', context)

@role_required('admin')
def report_rating_view(request):
    group_id = request.GET.get('group', '')
    subject_id = request.GET.get('subject', '')
    date_from = request.GET.get('date_from', '')
    date_to = request.GET.get('date_to', '')
    
    MIN_VOTES = 5
    
    perf_base_filter = Q(grade__isnull=False)
    perf_user_filter = Q(studentperformance__grade__isnull=False)
    
    if subject_id:
        term = Q(lesson__assignment__subject_id=subject_id)
        perf_base_filter &= term
        perf_user_filter &= Q(studentperformance__lesson__assignment__subject_id=subject_id)
    if date_from:
        term = Q(lesson__date__gte=date_from)
        perf_base_filter &= term
        perf_user_filter &= Q(studentperformance__lesson__date__gte=date_from)
    if date_to:
        term = Q(lesson__date__lte=date_to)
        perf_base_filter &= term
        perf_user_filter &= Q(studentperformance__lesson__date__lte=date_to)

    global_stats = StudentPerformance.objects.filter(perf_base_filter).annotate(
        weighted_val=F('grade') * F('lesson__evaluation_type__weight_percent')
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

    students_data = students_query.annotate(
        v=Count('studentperformance', filter=perf_user_filter),
        weighted_sum=Sum(
            F('studentperformance__grade') * F('studentperformance__lesson__evaluation_type__weight_percent'),
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
    
    context = {
        'report_data': rating_list,
        'report_title': 'Звіт: Рейтинг студентів',
        'is_rating_report': True,
        'is_weekly_report': False,
        'report_reset_url_name': 'report_rating',
        'groups': groups,
        'all_subjects': all_subjects,
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
    
    now = datetime.now()
    current_time_minutes = now.hour * 60 + now.minute
    current_day = now.weekday() + 1

    if group:
        # Беремо шаблони розкладу
        templates = ScheduleTemplate.objects.filter(
            group=group
        ).select_related('subject', 'teacher')

        # Дні тижня для таймлайну
        today_date = date.today()
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