from django.contrib.auth.views import LoginView, LogoutView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import redirect
from django.urls import reverse_lazy
from django.views.generic import CreateView, UpdateView

from .forms import UserLoginForm, UserProfileForm, UserRegistrationForm


class UserRegistrationView(CreateView):
    template_name = 'users/register.html'
    form_class = UserRegistrationForm
    success_url = reverse_lazy('users:login')

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            return redirect('homepage:index')
        return super().dispatch(request, *args, **kwargs)


class UserLoginView(LoginView):
    template_name = 'users/login.html'
    authentication_form = UserLoginForm
    redirect_authenticated_user = True


class UserLogoutView(LogoutView):
    next_page = reverse_lazy('homepage:index')


class UserProfileUpdateView(LoginRequiredMixin, UpdateView):
    template_name = 'users/profile_edit.html'
    form_class = UserProfileForm
    success_url = reverse_lazy('users:profile_edit')

    def get_object(self, queryset=None):
        return self.request.user
