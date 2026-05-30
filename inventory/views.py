from django.shortcuts import render

from config.permissions import observer_required


@observer_required
def index(request):
    return render(request, 'inventory/index.html')
