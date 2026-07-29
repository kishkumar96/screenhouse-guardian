from django import forms

from .models import Accession, Batch, Crop, Position

ARCHIVE_REASON_CHOICES = [
    ('dead', 'Dead'),
    ('empty', 'Empty'),
    ('distributed', 'Distributed'),
    ('transferred', 'Transferred'),
    ('merged', 'Merged'),
    ('destroyed', 'Destroyed'),
    ('entered_by_mistake', 'Entered by mistake'),
    ('retired', 'Retired'),
    ('other', 'Other'),
]


class CropForm(forms.ModelForm):
    class Meta:
        model = Crop
        fields = ['name', 'scientific_name', 'category', 'notes']
        widgets = {
            'notes': forms.Textarea(attrs={'rows': 3}),
        }


class AccessionForm(forms.ModelForm):
    class Meta:
        model = Accession
        fields = ['crop', 'accession_code', 'source_country', 'source_organisation', 'notes']
        widgets = {
            'notes': forms.Textarea(attrs={'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['crop'].queryset = Crop.objects.filter(is_active=True).order_by('name')
        self.fields['crop'].empty_label = '— Select crop —'


class BatchForm(forms.ModelForm):
    class Meta:
        model = Batch
        fields = ['accession', 'batch_code', 'source_type', 'received_date', 'initial_quantity', 'notes']
        widgets = {
            'received_date': forms.DateInput(attrs={'type': 'date'}),
            'notes': forms.Textarea(attrs={'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['accession'].queryset = (
            Accession.objects.filter(is_active=True)
            .select_related('crop')
            .order_by('crop__name', 'accession_code')
        )
        self.fields['accession'].empty_label = '— Select accession —'


class ArchiveTrackingUnitForm(forms.Form):
    archive_reason = forms.ChoiceField(
        choices=ARCHIVE_REASON_CHOICES,
        label='Archive reason',
    )
    confirm = forms.BooleanField(
        label='I confirm I want to archive this unit. This removes it from the active dashboard.',
        required=True,
        error_messages={'required': 'You must check this box to confirm the archive.'},
    )


class MoveTrackingUnitForm(forms.Form):
    to_position = forms.ModelChoiceField(
        queryset=Position.objects.none(),
        required=False,
        label='New position (structured)',
        empty_label='— No structured position —',
    )
    to_location_text = forms.CharField(
        max_length=255,
        required=False,
        label='New location (free text)',
    )
    reason = forms.CharField(
        widget=forms.Textarea(attrs={'rows': 2}),
        required=False,
        label='Reason for move',
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['to_position'].queryset = (
            Position.objects.filter(is_active=True)
            .select_related('bench__screen_house__site')
            .order_by('bench__screen_house__site__name', 'bench__screen_house__name', 'bench__name', 'code')
        )

    def clean(self):
        cleaned = super().clean()
        to_position = cleaned.get('to_position')
        to_location_text = cleaned.get('to_location_text', '').strip()
        if not to_position and not to_location_text:
            raise forms.ValidationError(
                'Select a structured position or enter a free-text location.'
            )
        cleaned['to_location_text'] = to_location_text
        return cleaned
