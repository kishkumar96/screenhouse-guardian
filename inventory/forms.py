from django import forms

from .models import Accession, Batch, Crop


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
