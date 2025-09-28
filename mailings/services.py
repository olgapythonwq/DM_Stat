from django.core.mail import send_mail
from .models import MailingAttempt


def send_mailing(mailing):
    """Функция, отправляющая письма"""
    clients = mailing.clients.all()
    for client in clients:
        try:
            send_mail(
                subject=mailing.message.subject,
                message=mailing.message.body,
                from_email='your_email@example.com',
                recipient_list=[client.email],
            )
            status = 'Успешно'
            response = 'Письмо отправлено'
        except Exception as e:
            status = 'Не успешно'
            response = str(e)

        MailingAttempt.objects.create(
            mailing=mailing,
            status=status,
            server_response=response
        )

    mailing.status = 'Запущена'
    mailing.save()
