from django.core.management.base import BaseCommand
from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType
from users.models import CustomUser
from mailings.models import Mailing, Message, Client  # замените на актуальные модели

class Command(BaseCommand):
    help = 'Создает группу "Менеджеры" с нужными правами'

    def handle(self, *args, **kwargs):
        group, created = Group.objects.get_or_create(name='Менеджеры')  # Получаем или создаём группу
        if created:
            self.stdout.write(self.style.SUCCESS('Группа "Менеджеры" создана.'))
        else:
            self.stdout.write('Группа "Менеджеры" уже существует.')

        # Добавим нужные права (только просмотр)
        models = [Mailing, Message, Client, CustomUser]
        # Назначаем права: только просмотр и изменение (для блокировки/отключения)
        needed_permissions = ['view', 'change']

        for model in models:
            content_type = ContentType.objects.get_for_model(model)
            for action in needed_permissions:
                codename = f"{action}_{model._meta.model_name}"
                try:
                    permission = Permission.objects.get(content_type=content_type, codename=codename)
                    group.permissions.add(permission)
                    self.stdout.write(f'Добавлено право: {permission.name}')
                except Permission.DoesNotExist:
                    self.stdout.write(self.style.WARNING(f'Право {codename} не найдено для модели {model.__name__}'))

        self.stdout.write(self.style.SUCCESS('Права для группы "Менеджеры" успешно назначены.'))
