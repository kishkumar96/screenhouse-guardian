from django.contrib import messages
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render

from inventory.models import TrackingUnit
from .forms import ObservationForm, ObservationPhotoForm
from .models import Observation


def index(request):
    return HttpResponse('<h1>Monitoring</h1><p>Use <code>/observe/&lt;unit_code&gt;/</code> to record an observation.</p>')


def observe(request, unit_code):
    unit = get_object_or_404(TrackingUnit, unit_code=unit_code)

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
    })


def timeline(request, unit_code):
    unit = get_object_or_404(TrackingUnit, unit_code=unit_code)
    observations = (
        unit.observations
        .select_related('created_by', 'corrects_observation')
        .prefetch_related('photos')
        .order_by('-created_at')
    )
    return render(request, 'monitoring/timeline.html', {
        'unit': unit,
        'observations': observations,
    })
