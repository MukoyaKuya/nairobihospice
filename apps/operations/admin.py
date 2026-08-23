from django.contrib import admin

from .models import (
    ProcurementOrder,
    ProcurementOrderItem,
    StockItem,
    StockMovement,
    Vendor,
)


@admin.register(Vendor)
class VendorAdmin(admin.ModelAdmin):
    list_display = ['name', 'code', 'category', 'contact_person', 'phone_number', 'status']
    list_filter = ['category', 'status']
    search_fields = ['name', 'code', 'contact_person', 'email']


@admin.register(StockItem)
class StockItemAdmin(admin.ModelAdmin):
    list_display = ['item_code', 'name', 'category', 'quantity_on_hand', 'unit_of_measure', 'minimum_reorder_level', 'unit_cost_kes', 'is_controlled_substance']
    list_filter = ['category', 'is_controlled_substance']
    search_fields = ['item_code', 'name']


class ProcurementOrderItemInline(admin.TabularInline):
    model = ProcurementOrderItem
    extra = 1


@admin.register(ProcurementOrder)
class ProcurementOrderAdmin(admin.ModelAdmin):
    list_display = ['po_number', 'vendor', 'order_date', 'status', 'total_amount_kes', 'requested_by']
    list_filter = ['status', 'order_date']
    search_fields = ['po_number', 'vendor__name', 'invoice_number']
    inlines = [ProcurementOrderItemInline]


@admin.register(StockMovement)
class StockMovementAdmin(admin.ModelAdmin):
    list_display = ['stock_item', 'movement_type', 'quantity', 'balance_after', 'reference_document', 'created_at']
    list_filter = ['movement_type', 'created_at']
    search_fields = ['stock_item__name', 'reference_document']
