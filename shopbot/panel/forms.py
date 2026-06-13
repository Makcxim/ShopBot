from django import forms
from django.utils.text import slugify

from webapp.models import Product, Shop, ShopMembership


def unique_shop_slug(name):
    base = slugify(name) or 'shop'
    slug = base
    i = 2
    while Shop.objects.filter(slug=slug).exists():
        slug = f'{base}-{i}'
        i += 1
    return slug


class ProductForm(forms.ModelForm):
    class Meta:
        model = Product
        fields = [
            'shop', 'category', 'name', 'slug', 'short_description',
            'description', 'price_stars', 'image', 'is_active',
        ]
        widgets = {
            'description': forms.Textarea(attrs={'rows': 4}),
            'short_description': forms.TextInput(),
        }

    def __init__(self, *args, shops=None, **kwargs):
        super().__init__(*args, **kwargs)
        # Ограничиваем выбор магазина доступными пользователю
        if shops is not None:
            self.fields['shop'].queryset = shops
        self.fields['slug'].required = False
        for field in self.fields.values():
            css = field.widget.attrs.get('class', '')
            if isinstance(field.widget, (forms.CheckboxInput,)):
                field.widget.attrs['class'] = (css + ' form-check-input').strip()
            else:
                field.widget.attrs['class'] = (css + ' form-control').strip()

    def clean_slug(self):
        slug = self.cleaned_data.get('slug')
        if not slug:
            slug = slugify(self.cleaned_data.get('name', ''))
        return slug


class ShopForm(forms.ModelForm):
    class Meta:
        model = Shop
        fields = ['name', 'description', 'logo']
        widgets = {'description': forms.Textarea(attrs={'rows': 3})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs['class'] = (field.widget.attrs.get('class', '') + ' form-control').strip()


class MemberAddForm(forms.Form):
    """Добавление сотрудника по telegram_id или username."""
    identifier = forms.CharField(
        label='Telegram ID или username',
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': '123456789 или username'}),
    )
    role = forms.ChoiceField(
        choices=ShopMembership.Role.choices,
        widget=forms.Select(attrs={'class': 'form-select'}),
    )


class KeysUploadForm(forms.Form):
    """Загрузка ключей: по одному на строку."""
    keys = forms.CharField(
        widget=forms.Textarea(attrs={'rows': 8, 'class': 'form-control',
                                     'placeholder': 'Один ключ на строку'}),
        label='Ключи',
    )

    def cleaned_keys(self):
        raw = self.cleaned_data['keys']
        return [line.strip() for line in raw.splitlines() if line.strip()]
