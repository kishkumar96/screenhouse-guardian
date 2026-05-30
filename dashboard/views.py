from django.shortcuts import render

from config.permissions import observer_required
from .services import get_dashboard_data


@observer_required
def index(request):
    context = get_dashboard_data()
    return render(request, 'dashboard/index.html', context)
