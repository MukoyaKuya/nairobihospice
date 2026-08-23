from django import forms


class ESASAssessmentForm(forms.Form):
    pain = forms.IntegerField(label="Pain (0 None - 10 Worst)", min_value=0, max_value=10, initial=0)
    tiredness = forms.IntegerField(label="Tiredness / Fatigue (0-10)", min_value=0, max_value=10, initial=0)
    drowsiness = forms.IntegerField(label="Drowsiness (0-10)", min_value=0, max_value=10, initial=0)
    nausea = forms.IntegerField(label="Nausea (0-10)", min_value=0, max_value=10, initial=0)
    appetite = forms.IntegerField(label="Lack of Appetite (0-10)", min_value=0, max_value=10, initial=0)
    breathlessness = forms.IntegerField(label="Shortness of Breath (0-10)", min_value=0, max_value=10, initial=0)
    depression = forms.IntegerField(label="Depression / Sadness (0-10)", min_value=0, max_value=10, initial=0)
    anxiety = forms.IntegerField(label="Anxiety / Nervousness (0-10)", min_value=0, max_value=10, initial=0)
    wellbeing = forms.IntegerField(label="Best to Worst Wellbeing (0-10)", min_value=0, max_value=10, initial=0)
    constipation = forms.IntegerField(label="Constipation (0-10)", min_value=0, max_value=10, initial=0)

    clinical_notes = forms.CharField(
        label="Clinical Notes / Exacerbating Factors",
        required=False,
        widget=forms.Textarea(attrs={'rows': 3, 'placeholder': 'Specific triggers, symptom relief responses, caregiver observations...'})
    )
