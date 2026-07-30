from datetime import date, timedelta

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.db.models import OuterRef, Q, Subquery
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from config.permissions import is_manager, manager_required, observer_required
from inventory.models import Crop, TrackingUnit
from .forms import (
    DailyRoundCreateForm,
    DailyRoundEditForm,
    DistributionEventForm,
    ObservationForm,
    ObservationPhotoForm,
    PropagationEventForm,
    QuantityEventForm,
    TreatmentForm,
    TreatmentOutcomeForm,
)
from .models import (
    DailyRound, DailyRoundItem, MAX_OBSERVATION_IMAGE_SIZE_MB, Observation, QuantityEvent, Treatment,
)
from .services import (
    apply_quantity_event,
    create_daily_round_with_items,
    get_weekly_summary,
    mark_overdue_rounds_missed,
    record_distribution,
    record_propagation,
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
    movements = (
        unit.movements
        .select_related(
            'moved_by',
            'from_position__bench__screen_house__site',
            'to_position__bench__screen_house__site',
        )
        .order_by('-moved_at')
    )
    distributions = (
        unit.distribution_events
        .select_related('created_by')
        .order_by('-distributed_at')
    )
    propagations = (
        unit.propagation_events_as_parent
        .prefetch_related('resulting_units')
        .select_related('created_by')
        .order_by('-propagated_at')
    )
    return render(request, 'monitoring/timeline.html', {
        'unit': unit,
        'observations': observations,
        'quantity_events': quantity_events,
        'treatments': treatments,
        'movements': movements,
        'distributions': distributions,
        'propagations': propagations,
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
def create_distribution(request, unit_code):
    unit = _get_unit_with_related(unit_code)

    if not unit.is_active:
        messages.error(request, 'Distributions cannot be recorded for archived units.')
        return redirect('observe_timeline', unit_code=unit_code)

    if request.method == 'POST':
        form = DistributionEventForm(request.POST, current_quantity=unit.quantity)
        if form.is_valid():
            record_distribution(
                tracking_unit=unit,
                quantity=form.cleaned_data['quantity'],
                recipient_name=form.cleaned_data['recipient_name'],
                recipient_organisation=form.cleaned_data['recipient_organisation'],
                purpose=form.cleaned_data['purpose'],
                notes=form.cleaned_data['notes'],
                user=request.user,
            )
            messages.success(
                request,
                f'Recorded distribution of {form.cleaned_data["quantity"]} '
                f'to {form.cleaned_data["recipient_name"]}.',
            )
            return redirect('observe_timeline', unit_code=unit_code)
    else:
        form = DistributionEventForm(current_quantity=unit.quantity)

    return render(request, 'monitoring/distribution_form.html', {
        'unit': unit,
        'form': form,
    })


@manager_required
def create_propagation(request, unit_code):
    unit = _get_unit_with_related(unit_code)

    if not unit.is_active:
        messages.error(request, 'Propagations cannot be recorded for archived units.')
        return redirect('observe_timeline', unit_code=unit_code)

    if request.method == 'POST':
        form = PropagationEventForm(request.POST, parent_unit=unit, current_quantity=unit.quantity)
        if form.is_valid():
            record_propagation(
                parent_unit=unit,
                method=form.cleaned_data['method'],
                quantity_taken=form.cleaned_data['quantity_taken'],
                notes=form.cleaned_data['notes'],
                user=request.user,
                resulting_units=form.cleaned_data['resulting_units'],
            )
            messages.success(request, f'Recorded propagation from {unit.unit_code}.')
            return redirect('observe_timeline', unit_code=unit_code)
    else:
        form = PropagationEventForm(parent_unit=unit, current_quantity=unit.quantity)

    return render(request, 'monitoring/propagation_form.html', {
        'unit': unit,
        'form': form,
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


# ── Follow-up list ─────────────────────────────────────────────────────────────

_COMPLETED_OUTCOMES = {
    Treatment.OUTCOME_IMPROVED,
    Treatment.OUTCOME_NO_CHANGE,
    Treatment.OUTCOME_WORSENED,
    Treatment.OUTCOME_RESOLVED,
}

STATUS_PENDING = 'pending'
STATUS_DUE_TODAY = 'due_today'
STATUS_OVERDUE = 'overdue'
STATUS_COMPLETED = 'completed'
STATUS_ALL = 'all'


@observer_required
def follow_up_list(request):
    today = timezone.localdate()

    # Base: treatments that have a follow_up_date set
    base_qs = (
        Treatment.objects
        .filter(follow_up_date__isnull=False)
        .select_related(
            'tracking_unit__crop',
            'tracking_unit__accession',
            'tracking_unit__position__bench__screen_house__site',
            'created_by',
        )
    )

    # Summary counts (always over all treatments with follow_up_date)
    counts = {
        'pending': base_qs.filter(outcome=Treatment.OUTCOME_PENDING).count(),
        'due_today': base_qs.filter(follow_up_date=today, outcome=Treatment.OUTCOME_PENDING).count(),
        'overdue': base_qs.filter(follow_up_date__lt=today, outcome=Treatment.OUTCOME_PENDING).count(),
        'completed': base_qs.filter(outcome__in=list(_COMPLETED_OUTCOMES)).count(),
    }

    # Apply status filter
    status_filter = request.GET.get('status', STATUS_PENDING)
    if status_filter == STATUS_DUE_TODAY:
        qs = base_qs.filter(follow_up_date=today, outcome=Treatment.OUTCOME_PENDING)
    elif status_filter == STATUS_OVERDUE:
        qs = base_qs.filter(follow_up_date__lt=today, outcome=Treatment.OUTCOME_PENDING)
    elif status_filter == STATUS_COMPLETED:
        qs = base_qs.filter(outcome__in=list(_COMPLETED_OUTCOMES))
    elif status_filter == STATUS_ALL:
        qs = base_qs
    else:  # default = pending
        status_filter = STATUS_PENDING
        qs = base_qs.filter(outcome=Treatment.OUTCOME_PENDING)

    # Apply treatment_type filter
    treatment_type = request.GET.get('treatment_type', '')
    if treatment_type:
        qs = qs.filter(treatment_type=treatment_type)

    # Apply location text filter (legacy + structured)
    location = request.GET.get('location', '').strip()
    if location:
        qs = qs.filter(
            Q(tracking_unit__location_text__icontains=location) |
            Q(tracking_unit__position__bench__name__icontains=location) |
            Q(tracking_unit__position__bench__screen_house__name__icontains=location) |
            Q(tracking_unit__position__bench__screen_house__site__name__icontains=location)
        )

    # Apply crop filter (by name, case-insensitive substring)
    crop = request.GET.get('crop', '').strip()
    if crop:
        qs = qs.filter(
            Q(tracking_unit__crop_name__icontains=crop) |
            Q(tracking_unit__crop__name__icontains=crop)
        )

    # Order: overdue first, then by date, then by unit code
    qs = qs.order_by('follow_up_date', 'tracking_unit__unit_code')

    return render(request, 'monitoring/follow_up_list.html', {
        'treatments': qs,
        'counts': counts,
        'status_filter': status_filter,
        'treatment_type_filter': treatment_type,
        'location_filter': location,
        'crop_filter': crop,
        'treatment_type_choices': Treatment.TYPE_CHOICES,
        'today': today,
        'show_manager_links': is_manager(request.user),
    })


# ── Weekly report ───────────────────────────────────────────────────────────────

@manager_required
def weekly_report(request):
    end_date_param = request.GET.get('end_date', '')
    end_date = timezone.localdate()
    if end_date_param:
        try:
            end_date = date.fromisoformat(end_date_param)
        except ValueError:
            messages.error(request, 'Invalid date. Showing the current week instead.')
            end_date = timezone.localdate()

    summary = get_weekly_summary(end_date=end_date)

    return render(request, 'monitoring/weekly_report.html', {
        'summary': summary,
        'prev_week_end': (end_date - timedelta(days=7)).isoformat(),
        'next_week_end': (end_date + timedelta(days=7)).isoformat(),
        'is_current_week': end_date >= timezone.localdate(),
    })


# ── Inventory reconciliation ─────────────────────────────────────────────────────

@manager_required
def reconcile_inventory(request):
    location_filter = (
        request.POST.get('location', '') if request.method == 'POST'
        else request.GET.get('location', '')
    ).strip()

    units = (
        TrackingUnit.objects.filter(is_active=True)
        .select_related('crop', 'accession', 'position__bench__screen_house__site')
        .order_by('unit_code')
    )
    if location_filter:
        units = units.filter(
            Q(location_text__icontains=location_filter) |
            Q(position__bench__name__icontains=location_filter) |
            Q(position__bench__screen_house__name__icontains=location_filter) |
            Q(position__bench__screen_house__site__name__icontains=location_filter)
        )

    results = []
    error_count = 0
    if request.method == 'POST':
        for unit in units:
            raw_value = request.POST.get(f'qty_{unit.pk}', '').strip()
            if not raw_value:
                continue
            try:
                counted = int(raw_value)
            except ValueError:
                messages.error(request, f'{unit.unit_code}: enter a whole number.')
                error_count += 1
                continue
            if counted == unit.quantity:
                continue
            try:
                event = apply_quantity_event(
                    tracking_unit=unit,
                    event_type=QuantityEvent.EVENT_TYPE_RECOUNT,
                    quantity_change=counted - unit.quantity,
                    user=request.user,
                    reason='Inventory reconciliation',
                )
                results.append(event)
            except ValidationError as e:
                message = e.messages[0] if hasattr(e, 'messages') and e.messages else str(e)
                messages.error(request, f'{unit.unit_code}: {message}')
                error_count += 1

        if results:
            messages.success(request, f'Reconciled {len(results)} unit(s).')
        elif error_count == 0:
            messages.info(request, 'No quantity changes were submitted.')

        units = (
            TrackingUnit.objects.filter(is_active=True)
            .select_related('crop', 'accession', 'position__bench__screen_house__site')
            .order_by('unit_code')
        )
        if location_filter:
            units = units.filter(
                Q(location_text__icontains=location_filter) |
                Q(position__bench__name__icontains=location_filter) |
                Q(position__bench__screen_house__name__icontains=location_filter) |
                Q(position__bench__screen_house__site__name__icontains=location_filter)
            )

    return render(request, 'monitoring/reconcile_inventory.html', {
        'units': units,
        'location_filter': location_filter,
        'results': results,
    })
