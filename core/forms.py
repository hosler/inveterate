from django import forms
from django.forms import widgets
from .models import Template, Plan, Service, BillingType
from django.forms import ModelForm
from django.contrib.auth import get_user_model

User = get_user_model()


class OrderProfileForm(forms.Form):
    first_name = forms.CharField(required=True, widget=widgets.TextInput(attrs={'class': 'required'}))
    last_name = forms.CharField(required=True)
    address1 = forms.CharField(required=True)
    address2 = forms.CharField(required=False)
    city = forms.CharField(required=True)
    state = forms.CharField(required=True)
    postcode = forms.CharField(required=True)
    country = forms.CharField(required=True)

    # class Meta:
    #     widgets = {
    #         'first_name': forms.TextInput(attrs={'class': 'myfieldclass'}),
    #     }


class OrderPackageForm(forms.Form):
    package = forms.ModelChoiceField(queryset=Plan.objects.all(), widget=forms.HiddenInput())


class OrderCustomizeVMForm(forms.Form):
    hostname = forms.CharField(max_length=50)
    password = forms.CharField(widget=forms.PasswordInput)
    template = forms.ModelChoiceField(queryset=Template.objects.all(),
                                      widget=forms.Select(attrs={'class': "selectpicker"}))


class NewServiceForm(forms.Form):
    owner = forms.ModelChoiceField(queryset=User.objects.all(),
                                   widget=forms.Select(attrs={'class': "selectpicker"}))
    hostname = forms.CharField(max_length=50)
    password = forms.CharField(widget=forms.PasswordInput)
    plan = forms.ModelChoiceField(queryset=Plan.objects.all(),
                                  widget=forms.Select(attrs={'class': "selectpicker"}))
    template = forms.ModelChoiceField(queryset=Template.objects.all(),
                                      widget=forms.Select(attrs={'class': "selectpicker"}))
    billing_type = forms.ModelChoiceField(queryset=BillingType.objects.all(),
                                          widget=forms.Select(attrs={'class': "selectpicker"}))
