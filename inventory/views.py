from django.http import HttpResponse

from config.permissions import observer_required

@observer_required
def index(request):
    return HttpResponse("<h1>Inventory</h1><p>Phase 1A implementation coming soon.</p>")
