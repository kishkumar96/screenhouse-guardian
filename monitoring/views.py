from django.contrib import messages
from django.core.exceptions import ValidationError
from django.db.models import OuterRef, Subquery
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from config.permissions import is_manager, manager_required, observer_required
from inventory.models import TrackingUnit
from .forms import (
    DailyRoundCreateForm,
    DailyRoundEditForm,
    ObservationForm,
    ObservationPhotoForm,
    QuantityEventForm,
    TreatmentForm,
    TreatmentOutcomeForm,
)
from .models import DailyRound, DailyRoundItem, MAX_OBSERVATION_IMAGE_SIZE_MB, Observation, Treatment
from .services import (
    apply_quantity_event,
    create_daily_round_with_items,
    mark_overdue_rounds_missed,
    update_daily_round_status,
)


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

    # Resolve optional round_item link from QR or round detail page.
    round_item_id = request.GET.get('round_item') or request.POST.get('round_item')
    round_item = None
    if round_item_id:
        try:
            round_item = DailyRoundItem.objects.select_related('daily_round').get(
                pk=int(round_item_id),
                tracking_unit=unit,
            )
        except (DailyRoundItem.DoesNotExist, ValueError, TypeError):
            from django.http import Http404
            raise Http404('Round item not found or does not belong to this unit.')

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

            # Link to round item if present.
            if round_item is not None:
                round_item.observation = obs
                round_item.completed = True
                round_item.completed_at = timezone.now()
                round_item.save(update_fields=['observation', 'completed', 'completed_at'])
                update_daily_round_status(round_item.daily_round)
                messages.success(request, 'Observation saved and round item marked complete.')
                return redirect('monitoring:round_detail', round_id=round_item.daily_round_id)

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
        'round_item': round_item,
    })


@observer_required
def timeline(request, unit_code):
    unit = _get_unit_with_related(unit_code)
    observations = (
        unit.observations
        .select_related('created_by', 'corrects_observation')
        .prefetch_related('photos', 'round_items__daily_round')
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


# ── Daily round views ──────────────────────────────────────────────────────────

@observer_required
def round_list(request):
    mark_overdue_rounds_missed()
    rounds = (
        DailyRound.objects
        .select_related('assigned_to', 'created_by')
        .prefetch_related('items')
        .order_by('-date', '-created_at')
    )
    return render(request, 'monitoring/round_list.html', {
        'rounds': rounds,
        'show_manager_links': is_manager(request.user),
    })


@manager_required
def round_create(request):
    if request.method == 'POST':
        form = DailyRoundCreateForm(request.POST)
        if form.is_valid():
            try:
                daily_round = create_daily_round_with_items(
                    name=form.cleaned_data['name'],
                    date=form.cleaned_data['date'],
                    generation_mode=form.cleaned_data['generation_mode'],
                    location_filter=form.cleaned_data.get('location_filter', ''),
                    assigned_to=form.cleaned_data.get('assigned_to'),
                    notes=form.cleaned_data.get('notes', ''),
                    created_by=request.user,
                )
                item_count = daily_round.items.count()
                messages.success(
                    request,
                    f'Round created with {item_count} unit{"s" if item_count != 1 else ""}.',
                )
                return redirect('monitoring:round_detail', round_id=daily_round.pk)
            except ValidationError as exc:
                form.add_error(None, exc.message)
    else:
        form = DailyRoundCreateForm()

    return render(request, 'monitoring/round_form.html', {'form': form})


@observer_required
def round_detail(request, round_id):
    mark_overdue_rounds_missed()
    daily_round = get_object_or_404(
        DailyRound.objects.select_related('assigned_to', 'created_by'),
        pk=round_id,
    )

    _latest_obs_qs = Observation.objects.filter(
        tracking_unit=OuterRef('tracking_unit_id')
    ).order_by('-created_at')

    items = (
        daily_round.items
        .select_related(
            'tracking_unit__crop',
            'tracking_unit__accession',
            'tracking_unit__batch',
            'tracking_unit__position__bench__screen_house__site',
            'observation__created_by',
        )
        .annotate(
            latest_obs_status=Subquery(_latest_obs_qs.values('status')[:1]),
            latest_obs_at=Subquery(_latest_obs_qs.values('created_at')[:1]),
        )
        .order_by('tracking_unit__unit_code')
    )

    return render(request, 'monitoring/round_detail.html', {
        'daily_round': daily_round,
        'items': items,
        'show_manager_links': is_manager(request.user),
    })


@manager_required
def round_edit(request, round_id):
    daily_round = get_object_or_404(DailyRound, pk=round_id)
    if request.method == 'POST':
        form = DailyRoundEditForm(request.POST, instance=daily_round)
        if form.is_valid():
            form.save()
            messages.success(request, 'Round updated.')
            return redirect('monitoring:round_detail', round_id=daily_round.pk)
    else:
        form = DailyRoundEditForm(instance=daily_round)
    return render(request, 'monitoring/round_edit.html', {
        'daily_round': daily_round,
        'form': form,
    })
