from django import forms
from .models import Profile, Skill, SessionRequest


class ProfileForm(forms.ModelForm):
    class Meta:
        model = Profile
        fields = ['bio', 'photo']
        widgets = {
            'bio': forms.Textarea(attrs={'rows': 4, 'class': 'form-control'}),
            'photo': forms.ClearableFileInput(attrs={'class': 'form-control'}),
        }


class SessionRequestForm(forms.ModelForm):
    class Meta:
        model = SessionRequest
        fields = [
            'proposed_title',
            'proposed_date_time',
            'proposed_duration_minutes',
            'proposed_location',
            'proposed_capacity',
            'message',
        ]
        widgets = {
            'proposed_title': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'ex: Piano Lesson'}),
            'proposed_date_time': forms.DateTimeInput(attrs={'class': 'form-control', 'type': 'datetime-local'}),
            'proposed_duration_minutes': forms.NumberInput(attrs={'class': 'form-control', 'min': 5, 'placeholder': 'ex: 60'}),
            'proposed_location': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'ex: Zoom'}),
            'proposed_capacity': forms.NumberInput(attrs={'class': 'form-control', 'min': 1, 'placeholder': 'ex: 2'}),
            'message': forms.Textarea(attrs={'rows': 3, 'class': 'form-control', 'placeholder': 'Optional message to the skill owner...'}),
        }
        labels = {
            'proposed_title': 'Session Title',
            'proposed_date_time': 'Proposed Date & Time',
            'proposed_duration_minutes': 'Duration (minutes)',
            'proposed_location': 'Location',
            'proposed_capacity': 'Max Attendees',
            'message': 'Message (optional)',
        }


class SkillForm(forms.ModelForm): # form for editing your skills, put name + description
    class Meta:
        model = Skill
        fields = ['name', 'description']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'rows': 2, 'class': 'form-control'}),
        }
