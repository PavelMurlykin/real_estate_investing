from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend
from django.db.models import Q

from .utils import normalize_phone_number


class EmailOrPhoneBackend(ModelBackend):
    def authenticate(self, request, username=None, password=None, **kwargs):
        login_value = username or kwargs.get('login') or kwargs.get(get_user_model().USERNAME_FIELD)
        if not login_value or password is None:
            return None

        login_value = login_value.strip()
        user_model = get_user_model()
        query = Q(email__iexact=login_value)

        if '@' not in login_value:
            phone_number = normalize_phone_number(login_value)
            if phone_number:
                query |= Q(phone_number=phone_number)

        try:
            user = user_model._default_manager.get(query)
        except user_model.DoesNotExist:
            user_model().set_password(password)
            return None
        except user_model.MultipleObjectsReturned:
            user = user_model._default_manager.filter(query).order_by('id').first()

        if user is not None and user.check_password(password) and self.user_can_authenticate(user):
            return user
        return None
