import datetime

from django import forms
from django.utils import timezone

from .models import Observation, ObservationPhoto, QuantityEvent, Treatment


class ObservationForm(forms.ModelForm):
    """
    Form for recording a new observation from the mobile observation page.

    Pass tracking_unit so that:
    - affected_quantity can be validated against unit quantity
    - corrects_observation dropdown is scoped to the same unit
    """

    def __init__(self, *args, tracking_unit=None, **kwargs):
        super().__init__(*args, **kwargs)
        self._tracking_unit = tracking_unit

        if tracking_unit is not None:
            self.fields['corrects_observation'].queryset = (
                Observation.objects.filter(tracking_unit=tracking_unit).order_by('-created_at')
            )
        else:
            self.fields['corrects_observation'].queryset = Observation.objects.none()

    def clean_affected_quantity(self):
        affected = self.cleaned_data.get('affected_quantity')
        if affected is not None and self._tracking_unit is not None:
            if affected > self._tracking_unit.quantity:
                raise forms.ValidationError(
                    f'Cannot exceed unit quantity of {self._tracking_unit.quantity}.'
                )
        return affected

    def clean(self):
        cleaned_data = super().clean()
        obs_type = cleaned_data.get('observation_type')
        corrects = cleaned_data.get('corrects_observation')

        if obs_type == Observation.OBSERVATION_TYPE_CORRECTION and not corrects:
            self.add_error(
                'corrects_observation',
                'A correction observation must reference the observation it corrects.',
            )
        return cleaned_data

    @property
    def detail_fields(self):
        """Secondary detail fields rendered in the collapsible section."""
        names = [
            'affected_quantity', 'affected_zone', 'water_condition',
            'pest_signs', 'disease_signs', 'action_taken', 'growth_stage',
        ]
        return [self[name] for name in names]

    class Meta:
        model = Observation
        fields = [
            'observation_type',
            'corrects_observation',
            'status',
            'growth_stage',
            'affected_quantity',
            'affected_zone',
            'water_condition',
            'pest_signs',
            'disease_signs',
            'action_taken',
            'notes',
        ]
        widgets = {
            'notes': forms.Textarea(attrs={'rows': 4, 'placeholder': 'Any additional notes…'}),
            'action_taken': forms.TextInput(attrs={'placeholder': 'e.g. Applied fungicide, removed affected leaves'}),
            'pest_signs': forms.TextInput(attrs={'placeholder': 'e.g. Aphids on undersides'}),
            'disease_signs': forms.TextInput(attrs={'placeholder': 'e.g. Powdery mildew on leaves'}),
            'growth_stage': forms.TextInput(attrs={'placeholder': 'e.g. Seedling, vegetative, flowering'}),
            'affected_zone': forms.TextInput(attrs={'placeholder': 'e.g. Top half, left side'}),
            'water_condition': forms.TextInput(attrs={'placeholder': 'e.g. Dry, saturated, wilting'}),
        }


class ObservationPhotoForm(forms.ModelForm):

    class Meta:
        model = ObservationPhoto
        fields = ['image', 'caption']
        widgets = {
            'caption': forms.TextInput(attrs={'placeholder': 'Optional caption'}),
        }


class QuantityEventForm(forms.Form):
    """
    Form for recording a quantity event (death, loss, recount, correction).

    Pass current_quantity so validation can check for negative results and
    handle the recount case (where the user enters physical_quantity and the
    change is computed automatically).
    """

    ALLOWED_EVENT_TYPES = [
        (QuantityEvent.EVENT_TYPE_DEATH, 'Death / Culling'),
        (QuantityEvent.EVENT_TYPE_LOSS, 'Loss'),
        (QuantityEvent.EVENT_TYPE_RECOUNT, 'Recount'),
        (QuantityEvent.EVENT_TYPE_CORRECTION, 'Correction'),
    ]

    event_type = forms.ChoiceField(
        choices=ALLOWED_EVENT_TYPES,
        label='Event type',
    )
    quantity_change = forms.IntegerField(
        required=False,
        label='Quantity change',
        help_text=(
            'Enter a negative number for deaths/losses (e.g. −3 means three died). '
            'Corrections may be positive or negative.'
        ),
    )
    physical_quantity = forms.IntegerField(
        required=False,
        min_value=0,
        label='Physical count',
        help_text='Enter the quantity you physically counted. The difference is computed automatically.',
    )
    reason = forms.CharField(
        required=True,
        label='Reason',
        widget=forms.Textarea(attrs={'rows': 3, 'placeholder': 'Briefly describe the reason for this change…'}),
        help_text='Required. Used for the audit trail.',
    )

    def __init__(self, *args, current_quantity=None, **kwargs):
        if args:
            data = args[0]
            if data is not None and hasattr(data, 'copy'):
                data = data.copy()
                event_type = data.get('event_type')
                if event_type == QuantityEvent.EVENT_TYPE_RECOUNT:
                    data['quantity_change'] = ''
                else:
                    data['physical_quantity'] = ''
                args = (data, *args[1:])
        super().__init__(*args, **kwargs)
        self._current_quantity = current_quantity

    def clean(self):
        cleaned = super().clean()
        event_type = cleaned.get('event_type')
        quantity_change = cleaned.get('quantity_change')
        physical_quantity = cleaned.get('physical_quantity')
        current = self._current_quantity

        if not event_type:
            return cleaned

        if event_type == QuantityEvent.EVENT_TYPE_RECOUNT:
            if physical_quantity is None:
                self.add_error('physical_quantity', 'Physical count is required for recount.')
            elif current is not None:
                computed = physical_quantity - current
                if computed == 0:
                    self.add_error(
                        'physical_quantity',
                        'Physical count matches current quantity — no change to record.',
                    )
                else:
                    cleaned['quantity_change'] = computed
        else:
            if quantity_change is None:
                self.add_error('quantity_change', 'Quantity change is required.')
            elif quantity_change == 0:
                self.add_error('quantity_change', 'Quantity change cannot be zero.')
            elif event_type in (
                QuantityEvent.EVENT_TYPE_DEATH,
                QuantityEvent.EVENT_TYPE_LOSS,
            ) and quantity_change > 0:
                self.add_error(
                    'quantity_change',
                    f'Quantity change must be negative for {event_type} events.',
                )
            elif (
                current is not None
                and quantity_change is not None
                and current + quantity_change < 0
            ):
                self.add_error(
                    'quantity_change',
                    f'Would result in a negative quantity '
                    f'({current} + {quantity_change} = {current + quantity_change}).',
                )

        return cleaned


class TreatmentForm(forms.ModelForm):

    def __init__(self, *args, tracking_unit=None, **kwargs):
        super().__init__(*args, **kwargs)
        self._tracking_unit = tracking_unit
        if tracking_unit is not None:
            self.fields['related_observation'].queryset = (
                Observation.objects.filter(tracking_unit=tracking_unit).order_by('-created_at')
            )
        else:
            self.fields['related_observation'].queryset = Observation.objects.none()

    def clean_reason(self):
        reason = self.cleaned_data.get('reason', '').strip()
        if not reason:
            raise forms.ValidationError('Reason is required.')
        return reason

    def clean_follow_up_date(self):
        follow_up_date = self.cleaned_data.get('follow_up_date')
        if follow_up_date is not None:
            today = timezone.localdate()
            if follow_up_date < today:
                raise forms.ValidationError('Follow-up date cannot be in the past.')
        return follow_up_date

    class Meta:
        model = Treatment
        fields = [
            'treatment_type',
            'product_used',
            'dose_rate',
            'reason',
            'follow_up_date',
            'outcome',
            'notes',
            'related_observation',
        ]
        widgets = {
            'reason': forms.Textarea(attrs={'rows': 3, 'placeholder': 'Why was this treatment applied?'}),
            'notes': forms.Textarea(attrs={'rows': 3, 'placeholder': 'Any additional notes…'}),
            'product_used': forms.TextInput(attrs={'placeholder': 'e.g. Mancozeb 80 WP'}),
            'dose_rate': forms.TextInput(attrs={'placeholder': 'e.g. 2 g/L'}),
            'follow_up_date': forms.DateInput(attrs={'type': 'date'}),
        }


class TreatmentOutcomeForm(forms.ModelForm):

    class Meta:
        model = Treatment
        fields = ['outcome', 'notes']
        widgets = {
            'notes': forms.Textarea(attrs={'rows': 3, 'placeholder': 'Update notes…'}),
        }
