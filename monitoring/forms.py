from django import forms

from .models import Observation, ObservationPhoto


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
