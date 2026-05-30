from django.shortcuts import render

from config.permissions import is_manager, observer_required
from .services import get_dashboard_data


@observer_required
def index(request):
    context = get_dashboard_data()
    context['show_manager_links'] = is_manager(request.user)
    context['show_staff_links'] = request.user.is_staff or request.user.is_superuser
    return render(request, 'dashboard/index.html', context)
