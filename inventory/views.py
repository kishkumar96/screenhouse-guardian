from django.contrib import messages
from django.db.models import Count
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from config.permissions import is_manager, manager_required, observer_required

from .forms import AccessionForm, ArchiveTrackingUnitForm, BatchForm, CropForm
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


def _get_unit_for_archive(unit_code):
    return get_object_or_404(
        TrackingUnit.objects.select_related(
            'crop', 'accession', 'batch', 'position__bench__screen_house__site',
        ),
        unit_code=unit_code,
    )


@manager_required
def archive_tracking_unit(request, unit_code):
    unit = _get_unit_for_archive(unit_code)

    if not unit.is_active:
        messages.info(request, f'Unit {unit.unit_code} is already archived.')
        return redirect('observe_timeline', unit_code=unit_code)

    if request.method == 'POST':
        form = ArchiveTrackingUnitForm(request.POST)
        if form.is_valid():
            unit.is_active = False
            unit.archived_at = timezone.now()
            unit.archive_reason = form.cleaned_data['archive_reason']
            unit.save(update_fields=['is_active', 'archived_at', 'archive_reason'])
            messages.success(request, f'Unit {unit.unit_code} has been archived.')
            return redirect('observe_timeline', unit_code=unit_code)
    else:
        form = ArchiveTrackingUnitForm()

    latest_obs = unit.observations.order_by('-created_at').first()
    return render(request, 'inventory/archive_tracking_unit.html', {
        'unit': unit,
        'form': form,
        'latest_obs': latest_obs,
    })


@observer_required
def archived_tracking_units(request):
    units = (
        TrackingUnit.objects.filter(is_active=False)
        .select_related('crop', 'accession', 'batch', 'position__bench__screen_house__site')
        .order_by('-archived_at', '-created_at')
    )
    return render(request, 'inventory/archived_units.html', {
        'units': units,
    })
