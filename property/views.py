from django.contrib import messages
from django.core.paginator import Paginator
from django.shortcuts import render, redirect, get_object_or_404

from mortgage.utils import format_currency
from .forms import PropertyForm
from .models import Property


def property_detail(request, pk):
    template = 'property/property_detail.html'
    property_obj = get_object_or_404(Property, pk=pk)
    property_obj.formatted_cost = format_currency(property_obj.property_cost)

    return render(request, template, {
        'property': property_obj
    })


def property_list(request):
    template = 'property/property_list.html'
    properties = Property.objects.all()

    # Пагинация
    paginator = Paginator(properties, 10)  # 10 объектов на страницу
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    # Форматирование стоимости
    for prop in page_obj:
        prop.formatted_cost = format_currency(prop.property_cost)

    return render(request, template, {
        'page_obj': page_obj
    })


def property_create(request):
    if request.method == 'POST':
        form = PropertyForm(request.POST)
        if form.is_valid():
            property_obj = form.save()
            messages.success(request, 'Объект успешно создан!')
            return redirect('property:property_detail', pk=property_obj.pk)
    else:
        form = PropertyForm()

    return render(request, 'property/property_form.html', {
        'form': form,
        'title': 'Добавить объект'
    })


def property_update(request, pk):
    property_obj = get_object_or_404(Property, pk=pk)

    if request.method == 'POST':
        form = PropertyForm(request.POST, instance=property_obj)
        if form.is_valid():
            form.save()
            messages.success(request, 'Объект успешно обновлен!')
            return redirect('property:property_detail', pk=property_obj.pk)
    else:
        form = PropertyForm(instance=property_obj)

    return render(request, 'property/property_form.html', {
        'form': form,
        'title': 'Редактировать объект',
        'property': property_obj
    })


def property_delete(request, pk):
    property_obj = get_object_or_404(Property, pk=pk)

    if request.method == 'POST':
        property_obj.delete()
        messages.success(request, 'Объект успешно удален!')
        return redirect('property:property_list')

    return render(request, 'property/property_confirm_delete.html', {
        'property': property_obj
    })
