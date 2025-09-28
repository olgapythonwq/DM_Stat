from django.contrib.auth.tokens import PasswordResetTokenGenerator


class AccountActivationTokenGenerator(PasswordResetTokenGenerator):
    pass  # Всё еае есть наследуется от родителя, ничего прописывать не надо


account_activation_token = AccountActivationTokenGenerator()  # Создание экземпляра генератора токена
