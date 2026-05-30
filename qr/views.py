from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from config.permissions import manager_required, observer_required
from inventory.models import TrackingUnit
from .services import generate_qr_for_tracking_unit


def index(request):
    return HttpResponse('<h1>QR</h1><p>Use <code>/qr/units/&lt;unit_code&gt;/label/</code> to view a label.</p>')


@observer_required
def label(request, unit_code):
    unit = get_object_or_404(TrackingUnit, unit_code=unit_code)
    return render(request, 'qr/label.html', {'unit': unit})


@manager_required
@require_POST
def generate(request, unit_code):
    unit = get_object_or_404(TrackingUnit, unit_code=unit_code)
    generate_qr_for_tracking_unit(unit, request=request)
    return redirect('qr:label', unit_code=unit_code)
