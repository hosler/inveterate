from django.conf.urls import include
from django.urls import path
from drf_auto_endpoint.router import router

# class MyRouter(EndpointRouter):
#     def __init__(self, *args, **kwargs):
#         self.APIRootView._ignore_model_permissions = False
#         #self.APIRootView.permission_classes = [IsAuthenticated]
#         super().__init__(*args, **kwargs)

#router.APIRootView._ignore_model_permissions = False

urlpatterns = [
    path('', include(router.urls)),
]
