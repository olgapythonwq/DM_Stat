from django.contrib.auth.models import User


def register_user(data):
    user = User.objects.create_user(
        username=data['username'],
        email=data['email'],
        password=data['password']
    )
    # отправка email, активация, логика по умолчанию и т.д.
    return user
