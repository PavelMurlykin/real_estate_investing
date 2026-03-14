from django.contrib.auth import views as auth_views
from django.urls import path, reverse_lazy

from .views import (
    UserLoginView,
    UserLogoutView,
    UserProfileUpdateView,
    UserRegistrationView,
)

app_name = 'users'

urlpatterns = [
    path('register/', UserRegistrationView.as_view(), name='register'),
    path('login/', UserLoginView.as_view(), name='login'),
    path('logout/', UserLogoutView.as_view(), name='logout'),
    path(
        'profile/edit/', UserProfileUpdateView.as_view(), name='profile_edit'
    ),
    path(
        'password/change/',
        auth_views.PasswordChangeView.as_view(
            template_name='users/password_change_form.html',
            success_url=reverse_lazy('users:password_change_done'),
        ),
        name='password_change',
    ),
    path(
        'password/change/done/',
        auth_views.PasswordChangeDoneView.as_view(
            template_name='users/password_change_done.html',
        ),
        name='password_change_done',
    ),
    path(
        'password/reset/',
        auth_views.PasswordResetView.as_view(
            template_name='users/password_reset_form.html',
            email_template_name='users/password_reset_email.html',
            subject_template_name='users/password_reset_subject.txt',
        ),
        name='password_reset',
    ),
    path(
        'password/reset/done/',
        auth_views.PasswordResetDoneView.as_view(
            template_name='users/password_reset_done.html',
        ),
        name='password_reset_done',
    ),
    path(
        'password/reset/<uidb64>/<token>/',
        auth_views.PasswordResetConfirmView.as_view(
            template_name='users/password_reset_confirm.html',
        ),
        name='password_reset_confirm',
    ),
    path(
        'password/reset/complete/',
        auth_views.PasswordResetCompleteView.as_view(
            template_name='users/password_reset_complete.html',
        ),
        name='password_reset_complete',
    ),
]
