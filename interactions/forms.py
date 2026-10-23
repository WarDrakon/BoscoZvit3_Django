from django import forms

from config.forms import StyledFormMixin

from .models import Report


class ContactRequestForm(StyledFormMixin, forms.Form):
    message = forms.CharField(label="Коротке повідомлення", max_length=500, required=False,
                              widget=forms.Textarea(attrs={"rows": 3, "placeholder": "Представтесь і поясніть, чому ви підходите один одному"}))


class ReportForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = Report
        fields = ["reason", "description"]
        widgets = {"description": forms.Textarea(attrs={"rows": 4})}
