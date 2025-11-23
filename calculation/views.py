# calculation/views.py
from django.contrib import messages
from django.http import JsonResponse
from django.urls import reverse_lazy
from django.views.decorators.csrf import csrf_exempt
from django.views.generic import FormView

from property.models import Property
from .forms import CalculationForm


@csrf_exempt  # На время разработки можно отключить CSRF для этого endpoint
def get_property_cost(request, property_id):
    """Возвращает стоимость объекта в формате JSON"""
    print(f"Получен запрос для property_id: {property_id}")  # Для отладки

    try:
        property_obj = Property.objects.select_related(
            'building__real_estate_complex__developer',
            'building__real_estate_complex'
        ).get(id=property_id)

        response_data = {
            'property_cost': str(property_obj.property_cost),
            'property_description': str(property_obj)
        }
        print(f"Отправляем данные: {response_data}")  # Для отладки

        return JsonResponse(response_data)

    except Property.DoesNotExist:
        print(f"Объект с ID {property_id} не найден")  # Для отладки
        return JsonResponse({'error': 'Object not found'}, status=404)
    except Exception as e:
        print(f"Ошибка: {str(e)}")  # Для отладки
        return JsonResponse({'error': str(e)}, status=500)


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

    def form_valid(self, form):
        property_id = self.request.POST.get('property')
        custom_cost = form.cleaned_data['property_cost']

        try:
            property_obj = Property.objects.get(id=property_id)
            original_cost = property_obj.property_cost

            calculation_data = {
                'property_id': property_obj.id,
                'original_cost': float(original_cost),
                'custom_cost': float(custom_cost),
                'property_description': str(property_obj),
                'difference': float(custom_cost) - float(original_cost)
            }

            self.request.session['calculation_data'] = calculation_data
            messages.success(self.request, 'Расчет выполнен успешно!')

        except Property.DoesNotExist:
            form.add_error('property', 'Объект не найден')
            return self.form_invalid(form)

        return super().form_valid(form)
