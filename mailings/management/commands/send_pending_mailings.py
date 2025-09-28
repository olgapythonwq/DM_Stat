from django.core.management.base import BaseCommand
from django.utils.timezone import now
from mailings.models import Mailing, MailingAttempt
from django.core.mail import send_mail
from django.conf import settings


class Command(BaseCommand):
    help = 'Отправляет запланированные рассылки, если время пришло'

    def handle(self, *args, **options):
        mailings = Mailing.objects.filter(status='Создана', start_time__lte=now())

        for mailing in mailings:
            subject = mailing.message.subject
            body = mailing.message.body
            recipients = [client.email for client in mailing.client.all()]

            if not recipients:
                self.stdout.write(self.style.WARNING(f'Нет получателей у рассылки #{mailing.id}'))
                continue

            try:
                send_mail(subject, body, settings.EMAIL_HOST_USER, recipients)
                success = True
                error_message = 'Отправлено успешно'
                self.stdout.write(self.style.SUCCESS(f'Рассылка #{mailing.id} отправлена'))
            except Exception as e:
                success = False
                error_message = str(e)
                self.stdout.write(self.style.ERROR(f'Ошибка при отправке рассылки #{mailing.id}: {e}'))

            # Создание попытки рассылки
            MailingAttempt.objects.create(
                mailing=mailing,
                status=success,
                server_response=error_message,
                # `attempt_time` автоматически добавляется, не указываем
            )

            if success:
                mailing.status = 'Завершена'
                mailing.end_time = now()
                mailing.save()
