from django.db import transaction
from django.db.models import Count
from django.db.models.deletion import ProtectedError
from django.http import HttpResponseRedirect
from django.urls import reverse_lazy
from django.views.generic import CreateView, DeleteView, DetailView, ListView, UpdateView

from .forms import (
    DeveloperForm,
    PropertyFilterForm,
    PropertyForm,
    RealEstateComplexBuildingFormSet,
    RealEstateComplexForm,
)
from .models import (
    ApartmentDecoration,
    ApartmentLayout,
    City,
    Developer,
    District,
    Property,
    RealEstateComplex,
    RealEstateComplexBuilding,
    Region,
)


class ProtectedDeleteMixin:
    protected_error_message = 'Нельзя удалить запись из-за связанных данных.'

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        try:
            return super().post(request, *args, **kwargs)
        except ProtectedError:
            context = self.get_context_data(object=self.object)
            context['protected_error'] = self.protected_error_message
            return self.render_to_response(context, status=400)


class DeveloperListView(ListView):
    model = Developer
    template_name = 'property/developer_list.html'
    context_object_name = 'developers'
    paginate_by = 20

    def get_queryset(self):
        return Developer.objects.order_by('name')


class DeveloperCreateView(CreateView):
    model = Developer
    form_class = DeveloperForm
    template_name = 'property/developer_form.html'
    success_url = reverse_lazy('property:developer_list')


class DeveloperUpdateView(UpdateView):
    model = Developer
    form_class = DeveloperForm
    template_name = 'property/developer_form.html'
    success_url = reverse_lazy('property:developer_list')


class DeveloperDeleteView(ProtectedDeleteMixin, DeleteView):
    model = Developer
    template_name = 'property/developer_confirm_delete.html'
    success_url = reverse_lazy('property:developer_list')
    protected_error_message = 'Нельзя удалить застройщика: с ним связаны записи ЖК.'


class RealEstateComplexListView(ListView):
    model = RealEstateComplex
    template_name = 'property/real_estate_complex_list.html'
    context_object_name = 'complexes'
    paginate_by = 20

    def get_queryset(self):
        return (
            RealEstateComplex.objects
            .annotate(buildings_count=Count('realestatecomplexbuilding'))
            .select_related(
                'developer',
                'district__city',
                'real_estate_class',
                'real_estate_type',
            )
            .order_by('developer__name', 'name')
        )


class RealEstateComplexFormsetMixin:
    model = RealEstateComplex
    form_class = RealEstateComplexForm
    template_name = 'property/real_estate_complex_form.html'
    success_url = reverse_lazy('property:complex_list')

    def get_formset(self):
        instance = self.object if getattr(self, 'object', None) else RealEstateComplex()
        if self.request.method == 'POST':
            return RealEstateComplexBuildingFormSet(self.request.POST, instance=instance, prefix='buildings')
        return RealEstateComplexBuildingFormSet(instance=instance, prefix='buildings')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.setdefault('building_formset', self.get_formset())
        return context

    def form_valid(self, form):
        context = self.get_context_data(form=form)
        building_formset = context['building_formset']

        if not building_formset.is_valid():
            return self.form_invalid(form)

        with transaction.atomic():
            self.object = form.save()
            building_formset.instance = self.object
            building_formset.save()

        return HttpResponseRedirect(self.get_success_url())


class RealEstateComplexCreateView(RealEstateComplexFormsetMixin, CreateView):
    pass


class RealEstateComplexUpdateView(RealEstateComplexFormsetMixin, UpdateView):
    pass


class RealEstateComplexDeleteView(ProtectedDeleteMixin, DeleteView):
    model = RealEstateComplex
    template_name = 'property/real_estate_complex_confirm_delete.html'
    success_url = reverse_lazy('property:complex_list')
    protected_error_message = 'Нельзя удалить ЖК: сначала удалите или отвяжите связанные корпуса и объекты.'


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
            'decoration',
        ).order_by(
            'building__real_estate_complex__developer__name',
            'building__real_estate_complex__name',
            'building__number',
            'apartment_number',
        )

        city = self.request.GET.get('city')
        developer = self.request.GET.get('developer')
        complex_id = self.request.GET.get('complex')

        if city:
            queryset = queryset.filter(building__real_estate_complex__district__city_id=city)
        if developer:
            queryset = queryset.filter(building__real_estate_complex__developer_id=developer)
        if complex_id:
            queryset = queryset.filter(building__real_estate_complex_id=complex_id)

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
            'decoration',
        )


class PropertyCreateView(CreateView):
    model = Property
    form_class = PropertyForm
    template_name = 'property/property_form.html'
    success_url = reverse_lazy('property:list')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
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
        context['regions'] = Region.objects.all()
        context['cities'] = City.objects.all()
        context['districts'] = District.objects.all()
        context['developers'] = Developer.objects.all()
        context['complexes'] = RealEstateComplex.objects.all()
        context['buildings'] = RealEstateComplexBuilding.objects.all()
        context['layouts'] = ApartmentLayout.objects.all()
        context['decorations'] = ApartmentDecoration.objects.all()

        property_obj = self.get_object()

        if property_obj.building:
            building = property_obj.building
            real_estate_complex = building.real_estate_complex
            district = real_estate_complex.district
            city = district.city
            region = city.region
            developer = real_estate_complex.developer

            context['current_region'] = region.id
            context['current_city'] = city.id
            context['current_district'] = district.id
            context['current_developer'] = developer.id
            context['current_complex'] = real_estate_complex.id
            context['current_building'] = building.id

            context['filtered_cities'] = City.objects.filter(region=region)
            context['filtered_districts'] = District.objects.filter(city=city)
            context['filtered_complexes'] = RealEstateComplex.objects.filter(district=district)
            context['filtered_buildings'] = RealEstateComplexBuilding.objects.filter(
                real_estate_complex=real_estate_complex,
            )

        return context


class PropertyDeleteView(DeleteView):
    model = Property
    template_name = 'property/property_confirm_delete.html'
    success_url = reverse_lazy('property:list')
