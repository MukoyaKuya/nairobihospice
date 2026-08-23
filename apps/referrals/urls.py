from django.urls import path

from . import views

app_name = 'referrals'

urlpatterns = [
    path('', views.ReferralListView.as_view(), name='referral_list'),
    path('create/', views.ReferralCreateView.as_view(), name='referral_create'),
    path('<uuid:pk>/', views.ReferralDetailView.as_view(), name='referral_detail'),
    path('<uuid:pk>/review/', views.ReferralReviewView.as_view(), name='referral_review'),
    path('<uuid:pk>/convert/', views.ReferralConvertView.as_view(), name='referral_convert'),
]
