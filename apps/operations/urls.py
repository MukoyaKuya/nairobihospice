from django.urls import path

from . import views

app_name = 'operations'

urlpatterns = [
    path('', views.OperationsDashboardView.as_view(), name='dashboard'),
    path('vendors/', views.VendorListView.as_view(), name='vendor_list'),
    path('vendors/create/', views.VendorCreateView.as_view(), name='vendor_create'),
    path('vendors/<uuid:pk>/', views.VendorDetailView.as_view(), name='vendor_detail'),
    path('procurement/', views.ProcurementOrderListView.as_view(), name='procurement_list'),
    path('procurement/create/', views.ProcurementOrderCreateView.as_view(), name='procurement_create'),
    path('procurement/<uuid:pk>/', views.ProcurementOrderDetailView.as_view(), name='procurement_detail'),
    path('inventory/', views.InventoryListView.as_view(), name='inventory_list'),
    path('inventory/create/', views.StockItemCreateView.as_view(), name='stock_item_create'),
    path('inventory/receive/', views.StockReceiveView.as_view(), name='stock_receive'),
    path('inventory/movements/', views.StockMovementListView.as_view(), name='stock_movements'),
    path('invoices/', views.InvoiceListView.as_view(), name='invoice_list'),
    path('invoices/create/', views.InvoiceCreateView.as_view(), name='invoice_create'),
    path('invoices/<uuid:pk>/', views.InvoiceDetailView.as_view(), name='invoice_detail'),
    path('invoices/<uuid:pk>/add-item/', views.InvoiceAddLineItemView.as_view(), name='invoice_add_item'),
    path('invoices/<uuid:pk>/pdf/', views.InvoicePdfView.as_view(), name='invoice_pdf'),
    path('disease-analytics/', views.DiseaseAnalyticsView.as_view(), name='disease_analytics'),
    path('deletions/', views.PatientDeletionRequestListView.as_view(), name='deletion_requests'),
    path('deletions/<uuid:pk>/approve/', views.PatientDeletionRequestApproveView.as_view(), name='deletion_request_approve'),
    path('deletions/<uuid:pk>/reject/', views.PatientDeletionRequestRejectView.as_view(), name='deletion_request_reject'),
    path('deletions/appointments/<uuid:pk>/approve/', views.AppointmentDeletionRequestApproveView.as_view(), name='appointment_deletion_approve'),
    path('deletions/appointments/<uuid:pk>/reject/', views.AppointmentDeletionRequestRejectView.as_view(), name='appointment_deletion_reject'),
]
