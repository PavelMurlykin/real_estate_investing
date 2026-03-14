from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.views import LoginView, LogoutView
from django.shortcuts import redirect
from django.urls import reverse_lazy
from django.views.generic import CreateView, UpdateView

from .forms import UserLoginForm, UserProfileForm, UserRegistrationForm


class UserRegistrationView(CreateView):
    """Описание класса UserRegistrationView.

    Инкапсулирует данные и поведение, необходимые для работы компонента
    в данном модуле.
    """

    template_name = 'users/register.html'
    form_class = UserRegistrationForm
    success_url = reverse_lazy('users:login')

    def dispatch(self, request, *args, **kwargs):
        """Описание метода dispatch.

        Выполняет прикладную операцию текущего модуля.

        Аргументы:
            request: Входной параметр, влияющий на работу метода.
            *args: Входной параметр, влияющий на работу метода.
            **kwargs: Входной параметр, влияющий на работу метода.

        Возвращает:
            Any: Тип результата определяется вызывающим кодом.
        """
        if request.user.is_authenticated:
            return redirect('homepage:index')
        return super().dispatch(request, *args, **kwargs)


class UserLoginView(LoginView):
    """Описание класса UserLoginView.

    Инкапсулирует данные и поведение, необходимые для работы компонента
    в данном модуле.
    """

    template_name = 'users/login.html'
    authentication_form = UserLoginForm
    redirect_authenticated_user = True


class UserLogoutView(LogoutView):
    """Описание класса UserLogoutView.

    Инкапсулирует данные и поведение, необходимые для работы компонента
    в данном модуле.
    """

    next_page = reverse_lazy('homepage:index')


class UserProfileUpdateView(LoginRequiredMixin, UpdateView):
    """Описание класса UserProfileUpdateView.

    Инкапсулирует данные и поведение, необходимые для работы компонента
    в данном модуле.
    """

    template_name = 'users/profile_edit.html'
    form_class = UserProfileForm
    success_url = reverse_lazy('users:profile_edit')

    def get_object(self, queryset=None):
        """Описание метода get_object.

        Возвращает подготовленные данные для дальнейшей обработки.

        Аргументы:
            queryset: Входной параметр, влияющий на работу метода.

        Возвращает:
            Any: Тип результата зависит от контекста использования.
        """
        return self.request.user
