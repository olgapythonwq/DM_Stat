from django import forms
from django.core.exceptions import ValidationError

from .models import Message, Client, Mailing

FORBIDDEN_WORDS = ['криптовалюта', 'крипта', 'биржа', ]


def contains_forbidden_words(text):
    text_lower = text.lower()
    for word in FORBIDDEN_WORDS:
        if word in text_lower:
            raise ValidationError(f"Текст содержит запрещённое слово: '{word}'")


class ClientForm(forms.ModelForm):
    class Meta:
        model = Client
        fields = ['email', 'full_name', 'comment']

    def __init__(self, *args, **kwargs):
        super(ClientForm, self).__init__(*args, **kwargs)
        self.fields['email'].widget.attrs.update({'class': 'form-control', 'placeholder': 'Введите почту'})
        self.fields['full_name'].widget.attrs.update({'class': 'form-control', 'placeholder': 'Введите ФИО'})
        self.fields['comment'].widget.attrs.update({'class': 'form-control', 'placeholder': 'Введите комментарий'})

    def clean_comment(self):
        comment = self.cleaned_data.get('comment')
        contains_forbidden_words(comment)
        return comment


class MessageForm(forms.ModelForm):
    class Meta:
        model = Message
        fields = ['subject', 'body']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields['subject'].widget.attrs.update({'class': 'form-control', 'placeholder': 'Введите тему сообщения'})
        self.fields['body'].widget.attrs.update({'class': 'form-control', 'placeholder': 'Введите текст сообщения'})

    def clean_body(self):
        body = self.cleaned_data.get('body')
        contains_forbidden_words(body)
        return body


class MailingForm(forms.ModelForm):
    class Meta:
        model = Mailing
        fields = ['start_time', 'message', 'status', 'client']

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)  # Получаем текущего пользователя
        super().__init__(*args, **kwargs)

        self.fields['client'] = forms.ModelMultipleChoiceField(
            queryset=Client.objects.all(),
            widget=forms.CheckboxSelectMultiple,
            label='Выберите клиентов',
        )

        self.fields['start_time'].widget.attrs.update(
            {'class': 'form-control', 'placeholder': 'Введите дату и время начала'})
        self.fields['status'].widget.attrs.update({'class': 'form-control'})
        self.fields['message'].widget.attrs.update({'class': 'form-control'})

        self.fields['status'].label = 'Текущий статус рассылки'
        self.fields['message'].label = 'Выберите сообщение из списка'
        self.fields['client'].label = 'Выберите получателей рассылки'

        if user:
            self.fields['message'].queryset = self.fields['message'].queryset.filter(owner=user)
            self.fields['client'].queryset = self.fields['client'].queryset.filter(owner=user)
        else:
            self.fields['message'].queryset = Message.objects.none()
            self.fields['client'].queryset = Client.objects.none()

        # Отключаем поле 'status' только для не-суперпользователей
        if not user.is_superuser:
            self.fields['status'].disabled = True

        # При редактировании: если есть instance с установленным статусом, показываем его как initial
        if self.instance and self.instance.pk:
            self.fields['status'].initial = self.instance.status
        else:
            self.fields['status'].initial = 'Создана'

