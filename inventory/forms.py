from django import forms

from .models import Accession, Batch, Crop

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
