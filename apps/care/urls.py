from django.urls import path

from . import views

app_name = 'care'

urlpatterns = [
    path('', views.CarePlanListView.as_view(), name='care_plan_list'),
    path('list/', views.CarePlanListView.as_view(), name='careplan_list'),
    path('create/', views.CarePlanCreateView.as_view(), name='care_plan_create'),
    path('create/<uuid:patient_id>/', views.CarePlanCreateView.as_view(), name='care_plan_create'),
    path('patient/<uuid:patient_id>/care-plan/create/', views.CarePlanCreateView.as_view(), name='care_plan_create'),
    path('patient/<uuid:patient_id>/care-team/', views.CareTeamAssignView.as_view(), name='care_team_manage'),
    path('care-plan/<uuid:pk>/', views.CarePlanDetailView.as_view(), name='care_plan_detail'),
    path('care-plan/<uuid:pk>/add-need/', views.CarePlanNeedCreateView.as_view(), name='care_plan_add_need'),
    path('advices/', views.ClinicalAdviceListView.as_view(), name='advice_list'),
    path('advices/create/', views.ClinicalAdviceCreateView.as_view(), name='advice_create'),
    path('advices/<uuid:pk>/edit/', views.ClinicalAdviceUpdateView.as_view(), name='advice_edit'),
    path('advices/<uuid:pk>/delete/', views.ClinicalAdviceDeleteView.as_view(), name='advice_delete'),
]
