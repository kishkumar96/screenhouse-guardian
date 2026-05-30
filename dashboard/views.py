from django.shortcuts import render

from .services import get_dashboard_data


def index(request):
    context = get_dashboard_data()
    return render(request, 'dashboard/index.html', context)
