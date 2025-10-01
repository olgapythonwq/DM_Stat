from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin, PermissionRequiredMixin
from django.core.exceptions import PermissionDenied
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy
from django.views import View
from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView, TemplateView

from users.models import CustomUser
from .models import Message, Client, Mailing, MailingAttempt
from .forms import MessageForm, ClientForm, MailingForm
from django.contrib import messages
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views.decorators.cache import cache_page
from django.core.cache import cache


import logging
logger = logging.getLogger(__name__)

# --- Базовые миксины / утилиты ---


class OwnerAssignMixin:
    def form_valid(self, form):
        form.instance.user = self.request.user
        form.instance.owner = self.request.user
        return super().form_valid(form)


class OwnerRequiredMixin(UserPassesTestMixin):
    def test_func(self):
        try:
            obj = self.get_object()
        except Exception as e:
            logger.warning(f"Access denied: failed to get object in {self.__class__.__name__} for user "
                           f"{self.request.user}. Error: {e}")
            return False

        user = self.request.user

        # Владелец всегда имеет доступ
        if obj.owner == user or user.is_superuser:
            return True

        # Менеджеры могут только просматривать
        model_name = obj._meta.model_name
        if user.groups.filter(name='Менеджеры').exists():
            # Менеджерам только просмотр
            if self.request.method in ['GET', 'HEAD']:
                return True
            return False

        # model_perm_map = {
        #     'client': 'mailings.can_view_all_clients',
        #     'message': 'mailings.can_view_all_messages',
        #     'mailing': 'mailings.can_view_all_mailings',
        # }
        #
        # model_name = obj._meta.model_name
        # required_permission = model_perm_map.get(model_name)
        #
        # if required_permission and user.has_perm(required_permission):
        #     return True
        #
        # if hasattr(self, 'required_permission') and user.has_perm(self.required_permission):
        #     return True

        logger.warning(f"Access denied: user {user} tried to access {model_name} object with id {obj.pk} "
                       f"without sufficient permissions in {self.__class__.__name__}")
        return False


class SomeAdminView(PermissionRequiredMixin, TemplateView):
    permission_required = 'mailings.can_view_all_mailings'


@method_decorator(cache_page(60 * 5), name='dispatch')  # кеш на 5 минут
class DashboardView(TemplateView):
    template_name = 'mailings/dashboard.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Общая статистика всех пользователей (для незалогиненного или для администратора)
        context['total_mailings'] = Mailing.objects.count()
        context['total_clients'] = Client.objects.count()
        context['total_messages'] = Message.objects.count()
        context['total_attempts'] = MailingAttempt.objects.count()
        context['attempts_successful'] = MailingAttempt.objects.filter(status=True).count()
        context['attempts_failed'] = MailingAttempt.objects.filter(status=False).count()

        # Статистика именно для текущего пользователя (если он авторизован)
        user = self.request.user
        if user.is_authenticated:
            context['user_mailings'] = Mailing.objects.filter(owner=user).count()
            context['user_clients'] = Client.objects.filter(owner=user).count()
            context['user_messages'] = Message.objects.filter(owner=user).count()
            context['user_attempts'] = MailingAttempt.objects.filter(mailing__owner=user).count()
            context['user_attempts_successful'] = MailingAttempt.objects.filter(mailing__owner=user,
                                                                                status=True).count()
            context['user_attempts_failed'] = MailingAttempt.objects.filter(mailing__owner=user, status=False).count()

        return context


# --- Message CRUD ---

class MessageListView(LoginRequiredMixin, ListView):
    model = Message
    template_name = 'mailings/message_list.html'
    context_object_name = 'message_list'

    def get_queryset(self):
        user = self.request.user
        cache_key = f"messages_user_{user.id}"
        queryset = cache.get(cache_key)

        if queryset is None:
            if user.has_perm('mailings.can_view_all_messages'):
                queryset = Message.objects.all()
            else:
                queryset = Message.objects.filter(owner=user)
            cache.set(cache_key, queryset, 60 * 2)  # кеш 2 минуты

        return queryset


class MessageDetailView(LoginRequiredMixin, OwnerRequiredMixin, DetailView):
    model = Message
    template_name = 'mailings/message_detail.html'
    context_object_name = 'message'


class MessageCreateView(LoginRequiredMixin, OwnerAssignMixin, CreateView):
    model = Message
    form_class = MessageForm
    template_name = 'mailings/message_create.html'
    context_object_name = 'message'
    success_url = reverse_lazy('mailings:message_list')

    def form_valid(self, form):
        response = super().form_valid(form)
        logger.info(f"User {self.request.user} created Message with id {self.object.pk}")
        return response


class MessageUpdateView(LoginRequiredMixin, OwnerRequiredMixin, UpdateView):
    model = Message
    form_class = MessageForm
    template_name = 'mailings/message_update.html'
    context_object_name = 'message'
    required_permission = 'mailings.change_message'
    success_url = reverse_lazy('mailings:message_list')


class MessageDeleteView(LoginRequiredMixin, OwnerRequiredMixin, DeleteView):
    model = Message
    template_name = 'mailings/message_confirm_delete.html'
    context_object_name = 'message'
    required_permission = 'mailings.delete_message'
    success_url = reverse_lazy('mailings:message_list')

# --- Client (Recipient) CRUD ---


@method_decorator(cache_page(60 * 2), name='dispatch')  # кеш 2 минуты
class ClientListView(LoginRequiredMixin, ListView):
    model = Client
    template_name = 'mailings/client_list.html'
    context_object_name = 'clients'

    def get_queryset(self):
        user = self.request.user
        if user.has_perm('mailings.can_view_all_clients'):
            return Client.objects.all()
        return Client.objects.filter(owner=user)


class ClientDetailView(LoginRequiredMixin, OwnerRequiredMixin, DetailView):
    model = Client
    template_name = 'mailings/client_detail.html'
    context_object_name = 'client'


class ClientCreateView(LoginRequiredMixin, OwnerAssignMixin, CreateView):
    model = Client
    form_class = ClientForm
    template_name = 'mailings/client_create.html'
    context_object_name = 'client'
    success_url = reverse_lazy('mailings:client_list')


class ClientUpdateView(LoginRequiredMixin, OwnerRequiredMixin, UpdateView):
    model = Client
    form_class = ClientForm
    template_name = 'mailings/client_update.html'
    context_object_name = 'client'
    required_permission = 'mailings.change_client'
    success_url = reverse_lazy('mailings:client_list')


class ClientDeleteView(LoginRequiredMixin, OwnerRequiredMixin, DeleteView):
    model = Client
    template_name = 'mailings/client_confirm_delete.html'
    context_object_name = 'client'
    required_permission = 'mailings.delete_client'
    success_url = reverse_lazy('mailings:client_list')

# --- Mailing CRUD (Campaigns) ---


class MailingListView(LoginRequiredMixin, ListView):
    model = Mailing
    template_name = 'mailings/mailing_list.html'
    context_object_name = 'mailings'

    def get_queryset(self):
        user = self.request.user
        if user.has_perm('mailings.can_view_all_mailings'):
            return Mailing.objects.all()
        # Возвращать рассылки, где user — текущий, или owner — текущий
        return Mailing.objects.filter(Q(owner=user) | Q(user=user))

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        # Проверяем, состоит ли пользователь в группе 'Менеджеры'
        context['is_manager'] = user.groups.filter(name='Менеджеры').exists()
        return context

    def post(self, request, *args, **kwargs):
        user = request.user
        # Проверка группы
        if not (user.groups.filter(name='Менеджеры').exists() or user.is_superuser):
            messages.error(request, "У вас нет прав завершать рассылки.")
            return redirect('mailings:mailing_list')

        # Завершение рассылки
        mailing_id = request.POST.get('finish_mailing_id')
        if mailing_id:
            mailing = get_object_or_404(Mailing, id=mailing_id)
            mailing.status = 'Завершена'
            mailing.end_time = timezone.now()
            mailing.save()
            messages.success(request, f'Рассылка #{mailing.id} успешно завершена.')

        # Запуск рассылки
        start_mailing_id = request.POST.get('start_mailing_id')
        if start_mailing_id:
            mailing = get_object_or_404(Mailing, id=start_mailing_id)
            if mailing.status == 'Создана':
                mailing.status = 'Запущена'
                mailing.start_time = timezone.now()
                mailing.save()
                messages.success(request, f'Рассылка #{mailing.id} запущена.')
            else:
                messages.warning(request, f'Рассылка #{mailing.id} уже была запущена или завершена.')

        return redirect('mailings:mailing_list')


class MailingDetailView(LoginRequiredMixin, OwnerRequiredMixin, DetailView):
    model = Mailing
    template_name = 'mailings/mailing_detail.html'
    context_object_name = 'mailing'


class MailingCreateView(LoginRequiredMixin, OwnerAssignMixin, CreateView):
    model = Mailing
    form_class = MailingForm
    template_name = 'mailings/mailing_create.html'
    context_object_name = 'mailing'
    success_url = reverse_lazy('mailings:mailing_list')

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs


class MailingUpdateView(LoginRequiredMixin, OwnerRequiredMixin, UpdateView):
    model = Mailing
    form_class = MailingForm
    template_name = 'mailings/mailing_update.html'
    context_object_name = 'mailing'
    required_permission = 'mailings.change_mailing'
    success_url = reverse_lazy('mailings:mailing_list')

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user  # передаем текущего пользователя
        return kwargs

    def form_valid(self, form):
        user = self.request.user
        if form.cleaned_data['status'] == 'Завершена' and not (user.has_perm('mailings.change_mailing') or user.is_superuser):
            logger.warning(
                f"User {user} attempted to set mailing {form.instance.pk} status to 'Завершена' without permission")
            raise PermissionDenied("Недостаточно прав для завершения рассылки.")

        # Устанавливаем end_time автоматически
        if form.cleaned_data['status'] == 'Завершена':
            form.instance.end_time = timezone.now()

        return super().form_valid(form)


class MailingDeleteView(LoginRequiredMixin, OwnerRequiredMixin, DeleteView):
    model = Mailing
    template_name = 'mailings/mailing_confirm_delete.html'
    context_object_name = 'mailing'
    required_permission = 'mailings.delete_mailing'
    success_url = reverse_lazy('mailings:mailing_list')

# --- Attempts (просмотр) ---


class MailingAttemptListView(LoginRequiredMixin, ListView):
    model = MailingAttempt
    template_name = 'mailings/attempt_list.html'
    context_object_name = 'attempts'

    def get_queryset(self):
        user = self.request.user
        queryset = MailingAttempt.objects.all()

        if not user.has_perm('mailings.can_view_all_mailings'):
            queryset = queryset.filter(mailing__owner=user)

        mailing_id = self.request.GET.get('mailing_id')
        if mailing_id:
            queryset = queryset.filter(mailing__id=mailing_id)

        return queryset
