# main/views.py

import csv
import json
from collections import defaultdict
from datetime import date, datetime, timedelta

from django.contrib import messages
from django.contrib.auth.hashers import check_password
from django.core.exceptions import ObjectDoesNotExist
from django.db import IntegrityError, transaction
from django.db.models import Avg, Count, F, Max, Min, Prefetch, Q, Sum
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_http_methods

from .forms import StudyGroupForm, SubjectForm, UserAdminForm
from .models import (
    AbsenceReason,
    EvaluationType,
    LessonSession,
    StudentPerformance,
    StudyGroup,
    Subject,
    TeachingAssignment,
    User,
    WeeklySchedule,
)

# =========================
# UTILITY & DECORATORS
# =========================

def role_required(allowed_roles):
    """
    Декоратор для перевірки ролі.
    allowed_roles може бути строкою ('admin') або списком (['admin', 'teacher']).
    """
    if isinstance(allowed_roles, str):
        allowed_roles = [allowed_roles]

    def decorator(view_func):
        def wrapper(request, *args, **kwargs):
            if 'user_id' not in request.session:
                return redirect('/')

            user_role = request.session.get('user_role')
            if user_role not in allowed_roles:
                messages.error(request, "У вас немає прав для доступу до цієї сторінки.")
                if user_role == 'student':
                    return redirect('student_grades')
                elif user_role == 'teacher':
                    return redirect('teacher_journal')
                else:
                    return redirect('/')

            # Виконуємо в'юху
            response = view_func(request, *args, **kwargs)

            # Додаємо заголовки для запобігання кешуванню. 
            # Це важливо, щоб після виходу користувач не міг повернутися назад через історію браузера.
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
    if 'user_id' in request.session:
        role = request.session.get('user_role')
        if role == 'admin':
            return redirect('admin_panel')
        if role == 'teacher':
            return redirect('teacher_journal')
        if role == 'student':
            return redirect('student_grades')

    return render(request, 'index.html')


@require_POST
def login_process(request):
    email = request.POST.get('username')
    password = request.POST.get('password')

    try:
        user = User.objects.get(email=email)
        if check_password(password, user.password_hash):
            request.session['user_id'] = user.id
            request.session['user_role'] = user.role
            request.session['user_name'] = user.full_name

            if user.role == 'admin':
                return redirect('admin_panel')
            elif user.role == 'teacher':
                return redirect('teacher_journal')
            elif user.role == 'student':
                return redirect('student_grades')
        else:
            messages.error(request, "Невірний пароль")
    except User.DoesNotExist:
        messages.error(request, "Користувача з таким email не знайдено")

    return redirect('login')


def logout_view(request):
    request.session.flush()
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
        'active_page': 'admin',
    }
    return render(request, 'admin.html', context)

# --- USERS ---
@role_required('admin')
def users_list_view(request):
    if request.method == 'POST':
        form = UserAdminForm(request.POST)
        if form.is_valid():
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
    if user.id == request.session.get('user_id'):
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
            # Якщо є помилки, виводимо їх
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f"{field}: {error}")
            return redirect('subjects_list')
    else:
        # GET запит - показуємо список предметів з пустою формою
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


# --- SCHEDULE ---
@role_required('admin')
@role_required('admin')
def set_weekly_schedule_view(request):
    """
    Сторінка налаштування розкладу з табличною сіткою на тиждень.
    Відображає матрицю: День тижня x Номер пари.
    """
    if request.method == 'POST':
        return save_schedule_changes(request)
    
    # GET-запит: показуємо форму
    # Отримуємо всі групи та їх розклад
    groups = StudyGroup.objects.all().order_by('name')
    
    # Отримуємо всі можливі призначення з їх викладачами
    # Групуємо за предметами та викладачами для зручності
    assignments = TeachingAssignment.objects.select_related(
        'subject', 'teacher', 'group'
    ).order_by('group__name', 'subject__name')
    
    # Будуємо словник {subject_id: [(teacher_id, teacher_name), ...]}
    subject_teachers = defaultdict(list)
    for assignment in assignments:
        subj_id = assignment.subject.id
        teacher_tuple = (assignment.teacher.id, assignment.teacher.full_name)
        if teacher_tuple not in subject_teachers[subj_id]:
            subject_teachers[subj_id].append(teacher_tuple)
    
    # Отримуємо поточний розклад
    current_schedule = WeeklySchedule.objects.all().select_related(
        'assignment__subject',
        'assignment__teacher',
        'assignment__group'
    )
    
    # Формуємо структуру: schedule_map[group_id][day][lesson_number] = {assignment_id, subject_id, subject_name, teacher_id, teacher_name}
    schedule_map_temp = defaultdict(lambda: defaultdict(dict))
    for item in current_schedule:
        grp_id = str(item.assignment.group.id)  # Конвертуємо в string для JSON
        day = str(item.day_of_week)
        lesson = str(item.lesson_number)
        schedule_map_temp[grp_id][day][lesson] = {
            'assignment_id': item.assignment.id,
            'subject_id': item.assignment.subject.id,
            'subject_name': item.assignment.subject.name,
            'teacher_id': item.assignment.teacher.id,
            'teacher_name': item.assignment.teacher.full_name
        }
    
    # Конвертуємо defaultdict в звичайний dict для JSON серіалізації
    schedule_map = {}
    for grp_id, days in schedule_map_temp.items():
        schedule_map[grp_id] = {}
        for day, lessons in days.items():
            schedule_map[grp_id][day] = dict(lessons)

    # Отримуємо унікальні предмети та їх викладачів
    subjects = Subject.objects.all().order_by('name')
    subject_data = []
    subject_teachers_map = {}  # Словник для JavaScript: {subject_id: [[tid, tname], ...]}
    
    for subject in subjects:
        teachers = TeachingAssignment.objects.filter(
            subject=subject
        ).select_related('teacher').values_list('teacher_id', 'teacher__full_name').distinct()
        teachers_list = list(teachers)
        
        # Зберігаємо список викладачів у словник для JavaScript
        if subject.id not in subject_teachers_map:
            subject_teachers_map[subject.id] = teachers_list
        
        if teachers_list:
            # Якщо більше одного викладача, додаємо прізвище для кожного у списку опцій
            if len(teachers_list) > 1:
                for tid, tname in teachers_list:
                    subject_data.append({
                        'id': subject.id,
                        'name': f"{subject.name} ({tname})",
                        'teacher_id': tid,
                        'teacher_name': tname
                    })
            else:
                # Один викладач - просто показуємо предмет
                tid, tname = teachers_list[0]
                subject_data.append({
                    'id': subject.id,
                    'name': subject.name,
                    'teacher_id': tid,
                    'teacher_name': tname
                })

    context = {
        'groups': groups,
        'schedule_map': schedule_map,  # Вже є звичайним dict
        'subject_data': subject_data,
        'subject_teachers_map': subject_teachers_map,  # Словник для JavaScript
        'days': [(1, 'Пн'), (2, 'Вт'), (3, 'Ср'), (4, 'Чт'), (5, 'Пт')],
        'lesson_numbers': range(1, 7),  # До 6 пар
        'active_page': 'schedule',
    }
    return render(request, 'main/schedule_builder.html', context)


@require_POST
@role_required('admin')
def save_schedule_changes(request):
    """API endpoint для збереження змін розкладу через JSON."""
    try:
        data = json.loads(request.body)
        group_id = data.get('group_id')
        schedule_entries = data.get('schedule', {})  # {day: {lesson_num: {subject_id, teacher_id}}}
        
        if not group_id:
            return JsonResponse({'status': 'error', 'message': 'Група не вибрана'}, status=400)
        
        # Перевіряємо, чи група існує
        group = get_object_or_404(StudyGroup, id=group_id)
        
        with transaction.atomic():
            # Видаляємо старий розклад для цієї групи
            WeeklySchedule.objects.filter(
                assignment__group=group
            ).delete()
            
            # Додаємо новий розклад
            for day_str, lessons in schedule_entries.items():
                day = int(day_str)
                for lesson_num_str, lesson_data in lessons.items():
                    lesson_num = int(lesson_num_str)
                    
                    # lesson_data може бути об'єктом {subject_id, teacher_id} або порожньо
                    if isinstance(lesson_data, dict):
                        subject_id = lesson_data.get('subject_id')
                        teacher_id = lesson_data.get('teacher_id')
                    else:
                        subject_id = lesson_data
                        teacher_id = None
                    
                    if subject_id:
                        # Шукаємо assignment за group+subject+teacher
                        if teacher_id:
                            assignment = TeachingAssignment.objects.filter(
                                group=group,
                                subject_id=subject_id,
                                teacher_id=teacher_id
                            ).first()
                        else:
                            # Якщо teacher не вказав, беремо будь-який assignment для цього предмету та групи
                            assignment = TeachingAssignment.objects.filter(
                                group=group,
                                subject_id=subject_id
                            ).first()
                        
                        if assignment:
                            WeeklySchedule.objects.create(
                                assignment=assignment,
                                day_of_week=day,
                                lesson_number=lesson_num
                            )
                        else:
                            # Якщо не знайдемо assignment, пропускаємо цю клітинку
                            pass
        
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


# =========================
# 3. ВИКЛАДАЧ
# =========================

@role_required('teacher')
def teacher_journal_view(request):
    teacher_id = request.session.get('user_id')
    
    # Отримуємо навантаження викладача (Предмет + Група)
    assignments = TeachingAssignment.objects.filter(
        teacher_id=teacher_id
    ).select_related('subject', 'group')

    # Отримуємо параметри фільтрації
    selected_subject_id = request.GET.get('subject')
    selected_group_id = request.GET.get('group')
    week_shift = int(request.GET.get('week', 0))
    
    # Обчислюємо дати тижня
    today = date.today()
    # Знаходимо понеділок поточного тижня
    days_since_monday = today.weekday()
    current_monday = today - timedelta(days=days_since_monday)
    # Зсуваємо на потрібний тиждень
    start_of_week = current_monday + timedelta(weeks=week_shift)
    end_of_week = start_of_week + timedelta(days=4)  # П'ятниця
    
    # Отримуємо унікальні предмети та групи для фільтрів
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
    
    # Фільтруємо призначення
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
            
            # Отримуємо студентів групи
            search_query = request.GET.get('search', '')
            students_query = selected_assignment.group.students.filter(role='student')
            
            if search_query:
                students_query = students_query.filter(full_name__icontains=search_query)
            
            students = students_query.order_by('full_name')
            
            # Отримуємо розклад для цього призначення на тиждень
            schedule_items = WeeklySchedule.objects.filter(
                assignment=selected_assignment
            ).order_by('day_of_week', 'lesson_number')
            
            # Створюємо заголовки занять по датах
            date_lessons_map = {}  # {date: [lesson_numbers]}
            
            for schedule_item in schedule_items:
                # Обчислюємо дату заняття
                # day_of_week: 1=Пн, 2=Вт, ..., 5=Пт
                lesson_date = start_of_week + timedelta(days=schedule_item.day_of_week - 1)
                
                if lesson_date not in date_lessons_map:
                    date_lessons_map[lesson_date] = []
                
                # Визначаємо тип заняття (Л, П, Лаб)
                lesson_type = 'Л'  # За замовчуванням лекція
                
                date_lessons_map[lesson_date].append({
                    'lesson_num': schedule_item.lesson_number,
                    'lesson_type': lesson_type
                })
            
            # Отримуємо всі проведені заняття для цього тижня для lookup
            existing_sessions = LessonSession.objects.filter(
                assignment=selected_assignment,
                date__gte=start_of_week,
                date__lte=end_of_week
            ).select_related('evaluation_type')
            
            sessions_map = {
                (sess.date, sess.lesson_number): sess 
                for sess in existing_sessions
            }

            # Формуємо lesson_headers
            for lesson_date in sorted(date_lessons_map.keys()):
                # Форматуємо дату
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
                    
                    # Шукаємо чи є вже створена сесія
                    session = sessions_map.get((lesson_date, l_num))
                    
                    if session:
                        l_type = session.evaluation_type.name
                        l_weight = session.evaluation_type.weight_percent
                        l_topic = session.topic
                    else:
                        l_type = 'Заняття' # Стандартна назва
                        l_weight = None
                        l_topic = ''

                    lesson_obj = type('Lesson', (), {
                        'lesson_num': l_num,
                        'lesson_type': l_type,
                        'weight_percent': l_weight,
                        'topic': l_topic
                    })()
                    lesson_header.lessons.append(lesson_obj)
                
                lesson_headers.append(lesson_header)
            
            # Отримуємо всі заняття та оцінки для цього тижня
            lessons = LessonSession.objects.filter(
                assignment=selected_assignment,
                date__gte=start_of_week,
                date__lte=end_of_week
            )
            
            performances = StudentPerformance.objects.filter(
                lesson__in=lessons
            ).select_related('lesson', 'absence')
            
            # Формуємо journal_data: {student_id: {date: {lesson_num: entry}}}
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
                
                # Визначаємо значення та тип
                if perf.grade is not None:
                    value = perf.grade
                    is_grade = True
                    display_value = str(perf.grade)
                elif perf.absence:
                    value = -1  # Код пропуску
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
        teacher_id = request.session.get('user_id')
        
        # Отримуємо дані з нового формату
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
                
                # Знаходимо assignment для перевірки прав
                try:
                    # Отримуємо студента щоб знайти групу
                    student = User.objects.get(pk=student_pk)
                    assignment = TeachingAssignment.objects.get(
                        teacher_id=teacher_id,
                        subject_id=subject_id,
                        group=student.group
                    )
                except (User.DoesNotExist, TeachingAssignment.DoesNotExist):
                    continue
                
                # Отримуємо або створюємо тип оцінювання
                eval_type = assignment.evaluation_types.first()
                if not eval_type:
                    eval_type = EvaluationType.objects.create(
                        assignment=assignment, 
                        name="Заняття", 
                        weight_percent=0
                    )
                
                # Знаходимо або створюємо сесію уроку
                lesson_session, created = LessonSession.objects.get_or_create(
                    assignment=assignment,
                    date=lesson_date,
                    lesson_number=lesson_num,
                    defaults={'evaluation_type': eval_type}
                )
                
                # Обробка значення
                grade_value = None
                absence_obj = None
                
                if value == '—' or value is None:
                    # Видаляємо запис якщо він існує
                    StudentPerformance.objects.filter(
                        lesson=lesson_session,
                        student_id=student_pk
                    ).delete()
                    continue
                
                try:
                    val_int = int(value)
                    if val_int > 0:
                        # Це оцінка
                        grade_value = val_int
                    else:
                        # Це пропуск (коди -1, -2 і т.д.)
                        code_map = {-1: 'Н', -2: 'ДЛ', -3: 'ПП'}
                        code_str = code_map.get(val_int, 'Н')
                        absence_obj = AbsenceReason.objects.filter(code=code_str).first()
                        if not absence_obj:
                            # Якщо не знайшли, використовуємо перший доступний
                            absence_obj = AbsenceReason.objects.first()
                except (ValueError, TypeError):
                    continue
                
                # Оновлюємо або створюємо запис успішності
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
    student_id = request.session.get('user_id')
    student = User.objects.get(id=student_id)
    
    # 1. Отримуємо параметри з GET-запиту
    date_from = request.GET.get('date_from')
    date_to = request.GET.get('date_to')
    subject_id = request.GET.get('subject')
    min_grade = request.GET.get('min_grade')
    max_grade = request.GET.get('max_grade')
    search_query = request.GET.get('search')

    # 2. Базовий запит
    grades = StudentPerformance.objects.filter(
        student_id=student_id, 
        grade__isnull=False
    ).select_related(
        'lesson', 
        'lesson__assignment__subject', 
        'lesson__assignment__teacher',
        'lesson__evaluation_type'
    ).order_by('-lesson__date')

    # 3. Застосування фільтрів
    if date_from:
        grades = grades.filter(lesson__date__gte=date_from)
    if date_to:
        grades = grades.filter(lesson__date__lte=date_to)
    
    if subject_id:
        grades = grades.filter(lesson__assignment__subject_id=subject_id)
        
    if min_grade:
        grades = grades.filter(grade__gte=min_grade)
    if max_grade:
        grades = grades.filter(grade__lte=max_grade)

    if search_query:
        # Пошук по коментарю або темі уроку
        grades = grades.filter(
            Q(comment__icontains=search_query) | 
            Q(lesson__topic__icontains=search_query)
        )

    # 4. Отримуємо предмети студента для фільтру
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
    student_id = request.session.get('user_id')
    
    # Фільтрація
    search_query = request.GET.get('search', '')
    subject_id = request.GET.get('subject', '')
    date_from = request.GET.get('date_from', '')
    date_to = request.GET.get('date_to', '')
    is_respectful = request.GET.get('is_respectful', '')

    absences = StudentPerformance.objects.filter(
        student_id=student_id,
        absence__isnull=False
    ).select_related(
        'lesson__assignment__subject',
        'lesson__assignment__teacher',
        'absence'
    )

    if search_query:
        absences = absences.filter(lesson__topic__icontains=search_query)
    
    if subject_id:
        absences = absences.filter(lesson__assignment__subject_id=subject_id)
        
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
    
    # Дані для фільтрів
    student_subjects = Subject.objects.filter(
        teachingassignment__group__students__id=student_id
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

    # Базова фільтрація для студентів
    students = User.objects.filter(role='student')
    
    if group_id:
        students = students.filter(group_id=group_id)

    # Параметри для анотації (фильтрація в Count)
    perf_filter = Q(studentperformance__absence__isnull=False)
    
    if subject_id:
        perf_filter &= Q(studentperformance__lesson__assignment__subject_id=subject_id)
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

    # Розрахунок поважних причин
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

# =========================
# 6. СКЛАДНА АНАЛІТИКА (MISSING PARTS)
# =========================

@role_required('admin')
def report_rating_view(request):
    """
    Генерує рейтинг студентів на основі зваженого середнього (Bayesian Average).
    """
    group_id = request.GET.get('group', '')
    subject_id = request.GET.get('subject', '')
    date_from = request.GET.get('date_from', '')
    date_to = request.GET.get('date_to', '')
    
    MIN_VOTES = 5  # мінімум оцінок для участі в рейтингу
    
    # Фільтрація для оцінок
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

    # 1. Рахуємо середнє по всій школі (C) - тепер теж зважене
    global_stats = StudentPerformance.objects.filter(perf_base_filter).annotate(
        weighted_val=F('grade') * F('lesson__evaluation_type__weight_percent')
    ).aggregate(
        total_weighted=Sum('weighted_val'),
        total_weights=Sum('lesson__evaluation_type__weight_percent')
    )
    
    C_sum = float(global_stats['total_weighted'] or 0)
    C_weight = float(global_stats['total_weights'] or 1) # уникнення ділення на 0
    C = C_sum / C_weight if C_weight > 0 else 0
    
    # 2. Отримуємо дані по студентах
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

    # 3. Рахуємо рейтинг у Python
    rating_list = []
    
    for student in students_data:
        v = student.v
        ws = float(student.weighted_sum or 0)
        wt = float(student.weight_total or 1)
        
        R = ws / wt if wt > 0 else 0
        
        # Bayesian Formula: (v / (v+m)) * R + (m / (v+m)) * C
        weighted_rating = (v / (v + MIN_VOTES)) * R + (MIN_VOTES / (v + MIN_VOTES)) * float(C)
        
        group_name = student.group.name if student.group else '-'
        
        rating_list.append({
            'full_name': student.full_name,
            'group': {'name': group_name}, # Для сумісності з шаблоном
            'raw_avg': round(R, 2),
            'count': v,
            'weighted_avg': round(weighted_rating, 2)
        })

    # Сортуємо: кращі зверху
    rating_list.sort(key=lambda x: x['weighted_avg'], reverse=True)

    # Експорт у CSV
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
    """Звіт про пропуски за останній тиждень."""
    group_id = request.GET.get('group', '')
    subject_id = request.GET.get('subject', '')
    
    today = date.today()
    start_week = today - timedelta(days=today.weekday()) # Понеділок
    end_week = start_week + timedelta(days=6) # Неділя

    # Фільтрація
    students = User.objects.filter(role='student')
    if group_id:
        students = students.filter(group_id=group_id)

    # Параметри для анотації (фильтрація в Count)
    perf_filter = Q(
        studentperformance__absence__isnull=False,
        studentperformance__lesson__date__gte=start_week,
        studentperformance__lesson__date__lte=end_week
    )
    
    if subject_id:
        perf_filter &= Q(studentperformance__lesson__assignment__subject_id=subject_id)

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
    """
    Сторінка управління типами оцінювання для викладача.
    Викладач вибирає предмет+групу і налаштовує типи оцінювання для них.
    """
    teacher_id = request.session.get('user_id')
    
    # Отримуємо всі призначення викладача
    assignments = TeachingAssignment.objects.filter(
        teacher_id=teacher_id
    ).select_related('subject', 'group')
    
    # Отримуємо вибране призначення з GET параметрів
    selected_assignment_id = request.GET.get('assignment')
    selected_assignment = None
    evaluation_types = []
    total_weight = 0
    
    if selected_assignment_id:
        try:
            selected_assignment = assignments.get(id=selected_assignment_id)
            # Отримуємо типи оцінювання для цього призначення
            evaluation_types = EvaluationType.objects.filter(
                assignment=selected_assignment
            ).order_by('name')
            total_weight = sum(et.weight_percent for et in evaluation_types)
        except TeachingAssignment.DoesNotExist:
            messages.error(request, "Призначення не знайдено")
    
    # Обробка POST запиту (додавання нового типу)
    if request.method == 'POST':
        if not selected_assignment:
            messages.error(request, "Спочатку оберіть предмет та групу")
            return redirect('manage_evaluation_types')
        
        from .forms import EvaluationTypeForm
        form = EvaluationTypeForm(request.POST)
        
        if form.is_valid():
            eval_type = form.save(commit=False)
            eval_type.assignment = selected_assignment
            
            # Перевіряємо чи сума не перевищує 100%
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
    """Редагування існуючого типу оцінювання."""
    teacher_id = request.session.get('user_id')
    eval_type = get_object_or_404(EvaluationType, pk=pk)
    
    # Перевіряємо що це тип належить викладачу
    if eval_type.assignment.teacher_id != teacher_id:
        messages.error(request, "У вас немає прав для редагування цього типу")
        return redirect('manage_evaluation_types')
    
    from .forms import EvaluationTypeForm
    
    # Отримуємо дані з POST
    name = request.POST.get('name')
    weight_percent = request.POST.get('weight_percent')
    
    try:
        weight_percent = float(weight_percent)
        
        # Перевіряємо чи сума не перевищує 100% (враховуючи що ми редагуємо існуючий)
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
    """Видалення типу оцінювання."""
    teacher_id = request.session.get('user_id')
    eval_type = get_object_or_404(EvaluationType, pk=pk)
    
    # Перевіряємо що це тип належить викладачу
    if eval_type.assignment.teacher_id != teacher_id:
        messages.error(request, "У вас немає прав для видалення цього типу")
        return redirect('manage_evaluation_types')
    
    assignment_id = eval_type.assignment.id
    
    # Перевіряємо чи не використовується цей тип в занятях
    if LessonSession.objects.filter(evaluation_type=eval_type).exists():
        messages.error(request, "Неможливо видалити тип оцінювання, оскільки він використовується в занятях")
    else:
        eval_type.delete()
        messages.success(request, "Тип оцінювання видалено")
    
    return redirect(f'manage_evaluation_types?assignment={assignment_id}')


@role_required('teacher')
def get_evaluation_types_api(request):
    """API endpoint для отримання типів оцінювання за assignment_id."""
    assignment_id = request.GET.get('assignment_id')
    
    if not assignment_id:
        return JsonResponse({'error': 'assignment_id обов\'язковий'}, status=400)
    
    teacher_id = request.session.get('user_id')
    
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



# --- ДОДАТИ В КІНЕЦЬ main/views.py ---

from django.contrib.auth.hashers import make_password

@login_required
def students_list_view(request):
    search_query = request.GET.get('search', '')
    group_id = request.GET.get('group', '')
    
    # Отримуємо всіх користувачів з роллю 'student'
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
    # Отримання даних з форми
    full_name = request.POST.get('full_name')
    group_id = request.POST.get('group_id')
    email = request.POST.get('email')
    password = request.POST.get('password')

    if full_name and email and password:
        # Перевірка чи існує email
        if User.objects.filter(email=email).exists():
            messages.error(request, f"Користувач з email {email} вже існує.")
        else:
            try:
                group = Group.objects.get(pk=group_id) if group_id else None
                
                User.objects.create(
                    full_name=full_name,
                    email=email,
                    password=make_password(password), # Хешуємо пароль
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
@require_http_methods(["POST"])
def student_delete(request, pk):
    student = get_object_or_404(User, pk=pk, role='student')
    name = student.full_name
    student.delete()
    messages.success(request, f"Студента {name} видалено.")
    return redirect('students_list')