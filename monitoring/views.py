from django.contrib import messages
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404, redirect, render

from config.permissions import is_manager, manager_required, observer_required
from inventory.models import TrackingUnit
from .forms import ObservationForm, ObservationPhotoForm, QuantityEventForm
from .models import MAX_OBSERVATION_IMAGE_SIZE_MB, Observation
from .services import apply_quantity_event


def _get_unit_with_related(unit_code):
    return get_object_or_404(
        TrackingUnit.objects.select_related(
            'crop', 'accession', 'batch', 'position__bench__screen_house__site',
        ),
        unit_code=unit_code,
    )


@observer_required
def index(request):
    return render(request, 'monitoring/index.html')


@observer_required
def observe(request, unit_code):
    unit = _get_unit_with_related(unit_code)

    if request.method == 'POST':
        form = ObservationForm(request.POST, tracking_unit=unit)
        has_photo = bool(request.FILES.get('image'))
        photo_form = (
            ObservationPhotoForm(request.POST, request.FILES)
            if has_photo
            else ObservationPhotoForm()
        )

        photo_valid = photo_form.is_valid() if has_photo else True

        if form.is_valid() and photo_valid:
            obs = form.save(commit=False)
            obs.tracking_unit = unit
            if request.user.is_authenticated:
                obs.created_by = request.user
            obs.save()

            if has_photo:
                photo = photo_form.save(commit=False)
                photo.observation = obs
                photo.save()

            messages.success(request, 'Observation saved successfully.')
            return redirect('observe_timeline', unit_code=unit_code)
    else:
        form = ObservationForm(tracking_unit=unit)
        photo_form = ObservationPhotoForm()

    latest_obs = (
        Observation.objects.filter(tracking_unit=unit)
        .order_by('-created_at')
        .first()
    )

    return render(request, 'monitoring/observe.html', {
        'unit': unit,
        'form': form,
        'photo_form': photo_form,
        'latest_obs': latest_obs,
        'max_photo_mb': MAX_OBSERVATION_IMAGE_SIZE_MB,
    })


@observer_required
def timeline(request, unit_code):
    unit = _get_unit_with_related(unit_code)
    observations = (
        unit.observations
        .select_related('created_by', 'corrects_observation')
        .prefetch_related('photos')
        .order_by('-created_at')
    )
    quantity_events = (
        unit.quantity_events
        .select_related('created_by')
        .order_by('-event_date')
    )
    return render(request, 'monitoring/timeline.html', {
        'unit': unit,
        'observations': observations,
        'quantity_events': quantity_events,
        'show_manager_links': is_manager(request.user),
    })


@manager_required
def create_quantity_event(request, unit_code):
    unit = _get_unit_with_related(unit_code)

    if request.method == 'POST':
        form = QuantityEventForm(request.POST, current_quantity=unit.quantity)
        if form.is_valid():
            try:
                event = apply_quantity_event(
                    tracking_unit=unit,
                    event_type=form.cleaned_data['event_type'],
                    quantity_change=form.cleaned_data['quantity_change'],
                    user=request.user,
                    reason=form.cleaned_data['reason'],
                )
                messages.success(
                    request,
                    f'Quantity updated from {event.quantity_before} to {event.quantity_after}.',
                )
                return redirect('observe_timeline', unit_code=unit_code)
            except ValidationError:
                form.add_error(
                    None,
                    'Quantity update failed. The unit quantity may have changed. Please try again.',
                )
    else:
        form = QuantityEventForm(current_quantity=unit.quantity)

    return render(request, 'monitoring/quantity_event_form.html', {
        'unit': unit,
        'form': form,
    })
