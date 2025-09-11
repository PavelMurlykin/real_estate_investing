from django.shortcuts import render


def property_detail(request, pk):
    template = 'property/detail.html'
    return render(request, template)


def property_list(request):
    template = 'property/list.html'
    return render(request, template)
