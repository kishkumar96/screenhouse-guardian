from django.contrib import messages
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404, redirect, render

from config.permissions import is_manager, manager_required, observer_required
from inventory.models import TrackingUnit
from .forms import ObservationForm, ObservationPhotoForm, QuantityEventForm, TreatmentForm, TreatmentOutcomeForm
from .models import MAX_OBSERVATION_IMAGE_SIZE_MB, Observation, Treatment
from .services import apply_quantity_event


def _get_unit_with_related(unit_code):
    return get_object_or_404(
        TrackingUnit.objects.select_related(
            'crop', 'accession', 'batch', 'position__bench__screen_house__site',
        ),
        unit_code=unit_code,
    )


def _get_quantity_suggestion(unit):
    latest_observation = (
        unit.observations
        .order_by('-created_at')
        .first()
    )
    latest_quantity_event = (
        unit.quantity_events
        .order_by('-event_date')
        .first()
    )

    if not latest_observation:
        return None

    if latest_quantity_event and latest_quantity_event.event_date >= latest_observation.created_at:
        return None

    if latest_observation.status != Observation.STATUS_DEAD:
        return None

    affected_quantity = latest_observation.affected_quantity
    if affected_quantity is None:
        if unit.unit_type == TrackingUnit.UNIT_TYPE_INDIVIDUAL and unit.quantity > 0:
            affected_quantity = 1
        else:
            return None

    if affected_quantity <= 0:
        return None

    return {
        'event_type': 'death',
        'quantity_change': -affected_quantity,
        'affected_quantity': affected_quantity,
        'observed_at': latest_observation.observed_at,
    }


@observer_required
def index(request):
    return render(request, 'monitoring/index.html')


@observer_required
def observe(request, unit_code):
    unit = _get_unit_with_related(unit_code)

    if not unit.is_active:
        return render(request, 'monitoring/observe.html', {
            'unit': unit,
            'archived': True,
        })

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
    treatments = (
        unit.treatments
        .select_related('created_by', 'related_observation')
        .order_by('-treatment_date')
    )
    return render(request, 'monitoring/timeline.html', {
        'unit': unit,
        'observations': observations,
        'quantity_events': quantity_events,
        'treatments': treatments,
        'show_manager_links': is_manager(request.user),
    })


@manager_required
def create_quantity_event(request, unit_code):
    unit = _get_unit_with_related(unit_code)
    quantity_suggestion = _get_quantity_suggestion(unit)

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
        initial = {}
        if quantity_suggestion:
            initial = {
                'event_type': quantity_suggestion['event_type'],
                'quantity_change': quantity_suggestion['quantity_change'],
            }
        form = QuantityEventForm(initial=initial, current_quantity=unit.quantity)

    return render(request, 'monitoring/quantity_event_form.html', {
        'unit': unit,
        'form': form,
        'quantity_suggestion': quantity_suggestion,
    })


@manager_required
def create_treatment(request, unit_code):
    unit = _get_unit_with_related(unit_code)

    if not unit.is_active:
        messages.error(request, 'Treatments cannot be recorded for archived units.')
        return redirect('observe_timeline', unit_code=unit_code)

    if request.method == 'POST':
        form = TreatmentForm(request.POST, tracking_unit=unit)
        if form.is_valid():
            treatment = form.save(commit=False)
            treatment.tracking_unit = unit
            treatment.created_by = request.user
            treatment.save()
            messages.success(request, 'Treatment recorded successfully.')
            return redirect('observe_timeline', unit_code=unit_code)
    else:
        form = TreatmentForm(tracking_unit=unit)

    latest_obs = (
        unit.observations.order_by('-created_at').first()
    )

    return render(request, 'monitoring/treatment_form.html', {
        'unit': unit,
        'form': form,
        'latest_obs': latest_obs,
    })


@manager_required
def update_treatment_outcome(request, treatment_id):
    treatment = get_object_or_404(Treatment, pk=treatment_id)
    unit = treatment.tracking_unit

    if request.method == 'POST':
        form = TreatmentOutcomeForm(request.POST, instance=treatment)
        if form.is_valid():
            form.save()
            messages.success(request, 'Treatment outcome updated.')
            return redirect('observe_timeline', unit_code=unit.unit_code)
    else:
        form = TreatmentOutcomeForm(instance=treatment)

    return render(request, 'monitoring/treatment_outcome_form.html', {
        'treatment': treatment,
        'unit': unit,
        'form': form,
    })
