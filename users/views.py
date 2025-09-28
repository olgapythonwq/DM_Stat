from django.conf import settings  # Получаем доступ к конфигурации (например, EMAIL_HOST_USER)
from django.contrib import messages  # Для отображения сообщений пользователю (успех/ошибка)
from django.contrib.auth import get_user_model  # Для входа пользователя в систему
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin  # Для ограничения доступа к профилю
from django.contrib.auth.views import LoginView, LogoutView  # Готовые представления входа и выхода
from django.core.mail import send_mail  # Отправка писем
from django.shortcuts import redirect, get_object_or_404  # Для переадресации
from django.urls import reverse_lazy, reverse  # Для получения URL по имени
from django.utils.encoding import force_bytes, force_str  # Кодирование/декодирование user.id
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode  # Безопасное кодирование id
from django.views import View  # Базовый класс представления
from django.views.generic import CreateView, UpdateView, ListView  # Готовые классы для создания/редактирования

from .forms import CustomUserCreationForm, EmailAuthenticationForm, UserProfileForm  # Формы регис-ии, логина, профиля
from .models import CustomUser  # Кастомная модель пользователя
from .tokens import account_activation_token  # Токен-генератор для активации аккаунта
import logging


logger = logging.getLogger(__name__)  # Получаем логгер для приложения users


class RegisterView(CreateView):
    template_name = 'users/register.html'
    form_class = CustomUserCreationForm
    success_url = reverse_lazy('users:login')  # После регистрации — на страницу логина

    def form_valid(self, form):
        user = form.save(commit=False)  # Сохраняем, но не коммитим в БД
        user.is_active = False  # Делаем пользователя неактивным (требуется активация по email)
        user.save()

        self.send_activation_email(user)  # Отправляем письмо с токеном активации

        messages.success(self.request, 'Подтвердите email — ссылка отправлена на вашу почту.')
        return redirect('users:login')  # Не логиним — пока не подтвердил почту

    def send_activation_email(self, user):
        uid = urlsafe_base64_encode(force_bytes(user.pk))  # Кодируем ID пользователя
        token = account_activation_token.make_token(user)  # Генерируем токен

        activation_link = self.request.build_absolute_uri(
            reverse('users:activate', kwargs={'uidb64': uid, 'token': token})  # Строим ссылку активации
        )

        subject = 'Подтверждение регистрации'
        message = f'Здравствуйте, {user.username}!\n\nДля активации аккаунта перейдите по ссылке:\n{activation_link}'

        try:
            send_mail(subject, message, settings.EMAIL_HOST_USER, [user.email], fail_silently=False)

            logger.info(f"[Активация] Письмо успешно отправлено пользователю {user.email}")
            logger.debug(f"[Активация] UID: {uid}, Token: {token}, Ссылка: {activation_link}")

        except Exception as e:
            logger.error(f"[Активация] Ошибка при отправке письма пользователю {user.email}: {e}")


class ActivateAccountView(View):
    def get(self, request, uidb64, token):
        try:
            uid = force_str(urlsafe_base64_decode(uidb64))  # Декодируем user ID
            user = CustomUser.objects.get(pk=uid)
        except (TypeError, ValueError, OverflowError, CustomUser.DoesNotExist):
            user = None

        if user is not None and account_activation_token.check_token(user, token):  # Проверяем токен
            user.is_active = True
            user.save()
            messages.success(request, 'Аккаунт успешно активирован!')
            logger.info(f"[Активация] Пользователь {user.email} активировал аккаунт.")
            return redirect('users:login')
        else:
            messages.error(request, 'Ссылка активации недействительна.')
            return redirect('users:login')


class CustomLoginView(LoginView):
    authentication_form = EmailAuthenticationForm  # Используем форму с email вместо username
    template_name = 'users/login.html'

    def get_success_url(self):
        return reverse('mailings:mailing_list')  # После логина — в рассылки


class ProfileUpdateView(LoginRequiredMixin, UpdateView):  # LoginRequiredMixin запрещает доступ неавторизованным
    model = CustomUser
    form_class = UserProfileForm
    template_name = 'users/profile_edit.html'
    success_url = reverse_lazy('mailings:mailing_list')

    def get_object(self):
        return self.request.user  # Только текущий пользователь может редактировать свой профиль


class CustomLogoutView(LogoutView):
    next_page = reverse_lazy('users:login')  # После выхода — на логин


User = get_user_model()


class UserListView(LoginRequiredMixin, UserPassesTestMixin, ListView):
    model = User
    template_name = 'users/user_list.html'
    context_object_name = 'users'

    def test_func(self):
        return self.request.user.is_staff


class UserActivationToggleView(LoginRequiredMixin, UserPassesTestMixin, View):
    def test_func(self):
        return self.request.user.is_staff  # Разрешить только штату

    def post(self, request, *args, **kwargs):
        user = get_object_or_404(User, pk=kwargs['pk'])
        if user == request.user:
            messages.error(request, "Нельзя отключить самого себя.")
            return redirect('users:user_list')

        user.is_active = not user.is_active
        user.save()

        status = "активирован" if user.is_active else "деактивирован"
        logger.info(
            f"[Менеджер] {request.user.username} изменил статус {user.username} на "
            f"{'активен' if user.is_active else 'неактивен'}")
        messages.success(request, f"Пользователь {user.username} был {status}.")
        return redirect('users:user_list')
