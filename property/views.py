from django.shortcuts import render, get_object_or_404, redirect
from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView
from django.urls import reverse_lazy
from django.db.models import Q
from .models import Property
from .forms import PropertyForm, PropertyFilterForm


class PropertyListView(ListView):
    model = Property
    template_name = 'property/property_list.html'
    context_object_name = 'properties'
    paginate_by = 20

    def get_queryset(self):
        queryset = Property.objects.select_related(
            'building__real_estate_complex__developer',
            'building__real_estate_complex__district__city',
            'building__real_estate_complex',
            'building',
            'layout',
            'decoration'
        ).order_by('building__real_estate_complex__developer__name',
                   'building__real_estate_complex__name',
                   'building__number',
                   'apartment_number')

        # Фильтрация
        city = self.request.GET.get('city')
        developer = self.request.GET.get('developer')
        complex = self.request.GET.get('complex')

        if city:
            queryset = queryset.filter(building__real_estate_complex__district__city_id=city)
        if developer:
            queryset = queryset.filter(building__real_estate_complex__developer_id=developer)
        if complex:
            queryset = queryset.filter(building__real_estate_complex_id=complex)

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['filter_form'] = PropertyFilterForm(self.request.GET)
        return context


class PropertyDetailView(DetailView):
    model = Property
    template_name = 'property/property_detail.html'
    context_object_name = 'property'

    def get_queryset(self):
        return Property.objects.select_related(
            'building__real_estate_complex__developer',
            'building__real_estate_complex__district__city__region',
            'building__real_estate_complex__real_estate_class',
            'building__real_estate_complex__real_estate_type',
            'building',
            'layout',
            'decoration'
        )


class PropertyCreateView(CreateView):
    model = Property
    form_class = PropertyForm
    template_name = 'property/property_form.html'
    success_url = reverse_lazy('property:list')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Добавляем все необходимые данные для формы
        from .models import Region, City, District, Developer, RealEstateComplex, RealEstateComplexBuilding, \
            ApartmentLayout, ApartmentDecoration
        context['regions'] = Region.objects.all()
        context['cities'] = City.objects.all()
        context['districts'] = District.objects.all()
        context['developers'] = Developer.objects.all()
        context['complexes'] = RealEstateComplex.objects.all()
        context['buildings'] = RealEstateComplexBuilding.objects.all()
        context['layouts'] = ApartmentLayout.objects.all()
        context['decorations'] = ApartmentDecoration.objects.all()
        return context


class PropertyUpdateView(UpdateView):
    model = Property
    form_class = PropertyForm
    template_name = 'property/property_form.html'

    def get_success_url(self):
        return reverse_lazy('property:detail', kwargs={'pk': self.object.pk})

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Добавляем все необходимые данные для формы
        from .models import Region, City, District, Developer, RealEstateComplex, RealEstateComplexBuilding, \
            ApartmentLayout, ApartmentDecoration
        context['regions'] = Region.objects.all()
        context['cities'] = City.objects.all()
        context['districts'] = District.objects.all()
        context['developers'] = Developer.objects.all()
        context['complexes'] = RealEstateComplex.objects.all()
        context['buildings'] = RealEstateComplexBuilding.objects.all()
        context['layouts'] = ApartmentLayout.objects.all()
        context['decorations'] = ApartmentDecoration.objects.all()

        # Получаем текущий объект
        property_obj = self.get_object()

        # Если объект уже имеет корпус, получаем информацию о местоположении
        if property_obj.building:
            building = property_obj.building
            complex = building.real_estate_complex
            district = complex.district
            city = district.city
            region = city.region
            developer = complex.developer

            # Добавляем текущие значения в контекст
            context['current_region'] = region.id
            context['current_city'] = city.id
            context['current_district'] = district.id
            context['current_developer'] = developer.id
            context['current_complex'] = complex.id
            context['current_building'] = building.id

            # Фильтруем списки на основе текущих значений
            context['filtered_cities'] = City.objects.filter(region=region)
            context['filtered_districts'] = District.objects.filter(city=city)
            context['filtered_complexes'] = RealEstateComplex.objects.filter(district=district)
            context['filtered_buildings'] = RealEstateComplexBuilding.objects.filter(real_estate_complex=complex)

        return context


class PropertyDeleteView(DeleteView):
    model = Property
    template_name = 'property/property_confirm_delete.html'
    success_url = reverse_lazy('property:list')
