from django.contrib import messages
from django.db.models import Count
from django.shortcuts import redirect, render

from config.permissions import is_manager, manager_required, observer_required

from .forms import AccessionForm, BatchForm, CropForm
from .models import Accession, Batch, Crop, TrackingUnit


@observer_required
def index(request):
    crop_count = Crop.objects.filter(is_active=True).count()
    accession_count = Accession.objects.filter(is_active=True).count()
    batch_count = Batch.objects.filter(is_active=True).count()
    unit_count = TrackingUnit.objects.filter(is_active=True).count()
    return render(request, 'inventory/index.html', {
        'crop_count': crop_count,
        'accession_count': accession_count,
        'batch_count': batch_count,
        'unit_count': unit_count,
        'show_manager_links': is_manager(request.user),
    })


@observer_required
def crop_list(request):
    if request.method == 'POST':
        if not is_manager(request.user):
            from django.core.exceptions import PermissionDenied
            raise PermissionDenied
        form = CropForm(request.POST)
        if form.is_valid():
            crop = form.save(commit=False)
            crop.created_by = request.user
            crop.save()
            messages.success(request, f'Crop "{crop.name}" created.')
            return redirect('inventory:crops')
    else:
        form = CropForm() if is_manager(request.user) else None

    crops = (
        Crop.objects.annotate(
            accession_count=Count('accessions', distinct=True),
            unit_count=Count('tracking_units', distinct=True),
        )
        .order_by('name')
    )
    return render(request, 'inventory/crops.html', {
        'crops': crops,
        'form': form,
        'show_manager_links': is_manager(request.user),
    })


@observer_required
def accession_list(request):
    if request.method == 'POST':
        if not is_manager(request.user):
            from django.core.exceptions import PermissionDenied
            raise PermissionDenied
        form = AccessionForm(request.POST)
        if form.is_valid():
            accession = form.save(commit=False)
            accession.created_by = request.user
            accession.save()
            messages.success(request, f'Accession "{accession.accession_code}" created.')
            return redirect('inventory:accessions')
    else:
        form = AccessionForm() if is_manager(request.user) else None

    accessions = (
        Accession.objects.select_related('crop')
        .annotate(
            batch_count=Count('batches', distinct=True),
            unit_count=Count('tracking_units', distinct=True),
        )
        .order_by('crop__name', 'accession_code')
    )
    return render(request, 'inventory/accessions.html', {
        'accessions': accessions,
        'form': form,
        'show_manager_links': is_manager(request.user),
    })


@observer_required
def batch_list(request):
    if request.method == 'POST':
        if not is_manager(request.user):
            from django.core.exceptions import PermissionDenied
            raise PermissionDenied
        form = BatchForm(request.POST)
        if form.is_valid():
            batch = form.save(commit=False)
            batch.created_by = request.user
            batch.save()
            messages.success(request, f'Batch "{batch.batch_code}" created.')
            return redirect('inventory:batches')
    else:
        form = BatchForm() if is_manager(request.user) else None

    batches = (
        Batch.objects.select_related('accession__crop')
        .annotate(unit_count=Count('tracking_units', distinct=True))
        .order_by('accession__crop__name', 'accession__accession_code', 'batch_code')
    )
    return render(request, 'inventory/batches.html', {
        'batches': batches,
        'form': form,
        'show_manager_links': is_manager(request.user),
    })
