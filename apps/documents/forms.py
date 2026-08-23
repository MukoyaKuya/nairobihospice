from pathlib import Path
from zipfile import is_zipfile

from django import forms
from PIL import Image, UnidentifiedImageError

from .malware import scan_uploaded_file
from .models import PatientDocument

MAX_DOCUMENT_SIZE = 10 * 1024 * 1024
ALLOWED_DOCUMENT_EXTENSIONS = {'.pdf', '.docx', '.jpg', '.jpeg', '.png'}
ALLOWED_DOCUMENT_CONTENT_TYPES = {
    'application/pdf',
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    'image/jpeg',
    'image/png',
}


class PatientDocumentForm(forms.ModelForm):
    class Meta:
        model = PatientDocument
        fields = ['category', 'title', 'file', 'description']
        widgets = {
            'title': forms.TextInput(attrs={'placeholder': 'e.g. KNH Discharge Summary July 2026'}),
            'description': forms.Textarea(attrs={'rows': 2, 'placeholder': 'Brief description of document contents...'}),
        }

    def clean_file(self):
        uploaded_file = self.cleaned_data['file']
        extension = Path(uploaded_file.name).suffix.lower()
        if uploaded_file.size > MAX_DOCUMENT_SIZE:
            raise forms.ValidationError('Clinical documents must be 10 MB or smaller.')
        if extension not in ALLOWED_DOCUMENT_EXTENSIONS:
            raise forms.ValidationError('Allowed document types are PDF, DOCX, JPEG, and PNG.')
        if uploaded_file.content_type not in ALLOWED_DOCUMENT_CONTENT_TYPES:
            raise forms.ValidationError('The uploaded file type is not permitted.')
        # Client MIME types and extensions are advisory. Verify common magic
        # bytes before storing sensitive clinical files.
        header = uploaded_file.read(16)
        uploaded_file.seek(0)
        if extension == '.pdf' and not header.startswith(b'%PDF-'):
            raise forms.ValidationError('The uploaded file is not a valid PDF.')
        if extension in {'.jpg', '.jpeg'} and not header.startswith(b'\xff\xd8\xff'):
            raise forms.ValidationError('The uploaded file is not a valid JPEG image.')
        if extension == '.png' and not header.startswith(b'\x89PNG\r\n\x1a\n'):
            raise forms.ValidationError('The uploaded file is not a valid PNG image.')
        if extension in {'.docx'} and not is_zipfile(uploaded_file):
            raise forms.ValidationError('The uploaded file is not a valid DOCX document.')
        if extension in {'.jpg', '.jpeg', '.png'}:
            try:
                uploaded_file.seek(0)
                with Image.open(uploaded_file) as image:
                    if image.width > 10000 or image.height > 10000 or image.width * image.height > 25_000_000:
                        raise forms.ValidationError('Images must not exceed 10,000 pixels per side or 25 megapixels.')
                    image.verify()
            except UnidentifiedImageError as exc:
                raise forms.ValidationError('The uploaded image could not be decoded.') from exc
            except OSError as exc:
                raise forms.ValidationError('The uploaded image is corrupt or invalid.') from exc
        try:
            scan_uploaded_file(uploaded_file)
        except forms.ValidationError:
            raise
        except Exception as exc:
            raise forms.ValidationError('The uploaded file could not be scanned.') from exc
        uploaded_file.seek(0)
        return uploaded_file
