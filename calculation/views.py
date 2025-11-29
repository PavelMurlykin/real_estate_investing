# calculation/views.py
from django.contrib import messages
from django.http import JsonResponse
from django.urls import reverse_lazy
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.views.generic import FormView

from property.models import Property
from .forms import CalculationForm


def get_property_cost(request, property_id):
    """Возвращает стоимость объекта в формате JSON"""
    try:
        property_obj = Property.objects.select_related(
            'building__real_estate_complex__developer',
            'building__real_estate_complex'
        ).get(id=property_id)

        return JsonResponse({
            'property_cost': str(property_obj.property_cost),
            'property_description': str(property_obj)
        })
    except Property.DoesNotExist:
        return JsonResponse({'error': 'Object not found'}, status=404)


@csrf_exempt
@require_POST
def clear_calculation_session(request):
    """Очищает данные расчета из сессии"""
    if 'calculation_data' in request.session:
        del request.session['calculation_data']
        request.session.modified = True
        return JsonResponse({'status': 'success'})
    return JsonResponse({'status': 'no data to clear'})


class CalculationView(FormView):
    template_name = 'calculation/calculation_form.html'
    form_class = CalculationForm
    success_url = reverse_lazy('calculation:calculation_form')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Добавляем все объекты недвижимости для выпадающего списка
        context['properties'] = Property.objects.select_related(
            'building__real_estate_complex__developer',
            'building__real_estate_complex'
        ).all()
        return context

    def get(self, request, *args, **kwargs):
        # При обычной загрузке страницы (GET запрос) очищаем сообщения
        # но сохраняем данные расчета в сессии для отображения результатов
        storage = messages.get_messages(request)
        for message in storage:
            # Это очистит сообщения при следующем запросе
            pass
        storage.used = True

        return super().get(request, *args, **kwargs)

    def form_valid(self, form):
        property_id = self.request.POST.get('property')
        custom_cost = form.cleaned_data['property_cost']

        try:
            property_obj = Property.objects.get(id=property_id)
            original_cost = property_obj.property_cost

            calculation_data = {
                'property_id': int(property_id),
                'property_description': str(property_obj),
                'original_cost': float(original_cost),
                'custom_cost': float(custom_cost),
                'difference': float(custom_cost) - float(original_cost)
            }

            self.request.session['calculation_data'] = calculation_data

            # Очищаем сообщения
            storage = messages.get_messages(self.request)
            for message in storage:
                pass
            storage.used = True

            # Добавляем новое сообщение об успехе
            messages.success(self.request, 'Расчет выполнен успешно!')

        except Property.DoesNotExist:
            form.add_error('property', 'Объект не найден')
            return self.form_invalid(form)

        return super().form_valid(form)
