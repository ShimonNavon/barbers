from django import forms

from .models import Group, GroupMembership


class PostForm(forms.Form):
    text = forms.CharField(max_length=2000)
    image = forms.FileField(required=False)
    group = forms.CharField(required=False)  # slug

    def __init__(self, member, *args, **kwargs):
        self.member = member
        super().__init__(*args, **kwargs)

    def clean_group(self):
        slug = self.cleaned_data.get("group", "").strip()
        if not slug:
            return None
        try:
            group = Group.objects.get(slug=slug)
        except Group.DoesNotExist:
            raise forms.ValidationError("קבוצה לא קיימת")
        if not GroupMembership.objects.filter(
                group=group, member=self.member).exists():
            raise forms.ValidationError("אפשר לפרסם רק בקבוצות שהצטרפת אליהן")
        return group


class CommentForm(forms.Form):
    text = forms.CharField(max_length=500)
