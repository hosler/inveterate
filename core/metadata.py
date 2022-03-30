from rest_framework.metadata import SimpleMetadata
from drf_auto_endpoint.metadata import AutoMetadataMixin
from django.utils.encoding import force_str
from drf_auto_endpoint.adapters import BaseAdapter, MetaDataInfo, PROPERTY, GETTER
from drf_auto_endpoint.utils import get_languages, get_field_dict

class AutoMetadata(AutoMetadataMixin, SimpleMetadata):
    def get_field_info(self, field):
        field_info = super().get_field_info(field)
        pattern = getattr(field, 'regex', None)
        if pattern is not None and pattern != '':
            field_info['pattern'] = force_str(pattern, strings_only=True)
        return field_info

    def get_field_dict(self, *args, **kwargs):
        blah = get_field_dict(*args, **kwargs)
        print(blah)
        return blah

    def determine_metadata(self, request, view):
        meta_data = super().determine_metadata(request, view)
        return meta_data