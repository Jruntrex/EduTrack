# main/forms.py

from django import forms
from django.forms import ModelForm
from .models import User, StudyGroup, Subject, TeachingAssignment, EvaluationType
from django.core.exceptions import ValidationError


class UserAdminForm(forms.ModelForm):
    """Кастомна форма для моделі User з коректним хешуванням пароля та підтвердженням."""

    password = forms.CharField(
        label="Пароль",
        widget=forms.PasswordInput,
        required=False,
        help_text="Залиште пустим, щоб не змінювати пароль",
    )

    confirm_password = forms.CharField(
        label="Підтвердіть пароль",
        widget=forms.PasswordInput,
        required=False,
    )

    # Додаємо поле для вибору предметів (для викладачів)
    subjects = forms.ModelMultipleChoiceField(
        queryset=Subject.objects.all(),
        required=False,
        widget=forms.CheckboxSelectMultiple,
        label="Предмети (для викладачів)",
    )

    class Meta:
        model = User
        fields = ['full_name', 'email', 'role', 'password', 'group']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Якщо редагуємо користувача (instance), то завантажуємо його предмети
        if self.instance.pk:
            # Редагування існуючого користувача - пароль опціональний
            self.fields['password'].required = False
            self.fields['confirm_password'].required = False
            if self.instance.role == 'teacher':
                # Отримуємо предмети, які викладає цей викладач
                teacher_subjects = Subject.objects.filter(
                    teachingassignment__teacher=self.instance
                ).distinct()
                self.fields['subjects'].initial = teacher_subjects
        else:
            # Створення нового користувача - пароль обов'язковий
            self.fields['password'].required = True
            self.fields['confirm_password'].required = True

    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get("password")
        confirm_password = cleaned_data.get("confirm_password")

        if password or confirm_password:
            if password != confirm_password:
                raise ValidationError("Паролі не співпадають")
        return cleaned_data

    def save(self, commit=True):
        user = super().save(commit=False)

        # Хешування нового пароля, якщо він був наданий
        new_password = self.cleaned_data.get('password')
        if new_password:
            user.set_password(new_password)

        # Забезпечення, що group = NULL для не-студентів
        if user.role != 'student':
            user.group = None

        if commit:
            user.save()

            # Обробляємо предмети тільки для викладачів
            if user.role == 'teacher':
                selected_subjects = self.cleaned_data.get('subjects', [])
                
                # Отримуємо поточні призначення
                current_assignments = TeachingAssignment.objects.filter(teacher=user)
                
                # Створюємо множину пар (subject_id, group_id) для вибраних предметів
                desired_assignments = set()
                for subject in selected_subjects:
                    for group in StudyGroup.objects.all():
                        desired_assignments.add((subject.id, group.id))
                
                # Знаходимо призначення які треба видалити (тільки ті, що не мають LessonSession)
                for assignment in current_assignments:
                    pair = (assignment.subject_id, assignment.group_id)
                    if pair not in desired_assignments:
                        # Перевіряємо чи є пов'язані заняття
                        if not assignment.lessonsession_set.exists():
                            assignment.delete()
                        # Якщо є заняття - просто залишаємо це призначення
                
                # Додаємо нові призначення (якщо вони ще не існують)
                existing_pairs = set(
                    current_assignments.values_list('subject_id', 'group_id')
                )
                for subject in selected_subjects:
                    for group in StudyGroup.objects.all():
                        pair = (subject.id, group.id)
                        if pair not in existing_pairs:
                            TeachingAssignment.objects.create(
                                subject=subject,
                                teacher=user,
                                group=group,
                            )

        return user


class StudyGroupForm(ModelForm):
    """Проста форма для додавання/редагування навчальної групи."""

    class Meta:
        model = StudyGroup
        fields = ['name']


class SubjectForm(ModelForm):
    """Форма для додавання/редагування предмета."""

    class Meta:
        model = Subject
        fields = ['name', 'description']
        widgets = {
            'name': forms.TextInput(attrs={'placeholder': 'Назва предмета'}),
        }